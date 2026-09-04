"""Lombard collateral and loan-to-value.

Loan-to-value is ``drawn / lending_value``, where lending value is market value
after per-asset advance-rate haircuts. Using raw market value would understate
every LTV in the book -- illiquid alternatives carry a 0% advance rate and
contribute nothing to borrowing capacity however large they are.

Tracing LTV across the five snapshots answers a question a single number cannot:
whether a breach was *cured by an action* or *cured by the market*. A facility
that fell back inside its trigger because a commodity rally lifted the
collateral is not a facility that has been fixed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import config
from ..contracts import Evidence
from ..loaders import DataBook


@dataclass(frozen=True)
class LtvPoint:
    snapshot: str
    label: str
    drawn: float | None
    collateral_market_value: float | None
    lending_value: float | None
    ltv_pct: float | None
    headroom: float | None
    breached: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot,
            "label": self.label,
            "drawn": self.drawn,
            "collateral_market_value": self.collateral_market_value,
            "lending_value": self.lending_value,
            "ltv_pct": self.ltv_pct,
            "headroom": self.headroom,
            "breached": self.breached,
        }


@dataclass
class FacilityView:
    facility_id: str
    client_id: str
    portfolio_id: str
    facility_type: str
    currency: str
    credit_limit: float
    interest_rate_pct: float
    margin_call_ltv_pct: float
    series: list[LtvPoint]
    #: Percentage points between the current LTV and the margin-call trigger.
    headroom_pp: float | None
    #: How far collateral could fall before the trigger is hit, in percent.
    collateral_fall_to_trigger_pct: float | None
    breaches: list[LtvPoint]
    cure_narrative: str | None
    drawn_reconciliation: list[dict[str, Any]]

    @property
    def current(self) -> LtvPoint:
        return self.series[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "facility_id": self.facility_id,
            "client_id": self.client_id,
            "portfolio_id": self.portfolio_id,
            "facility_type": self.facility_type,
            "currency": self.currency,
            "credit_limit": self.credit_limit,
            "interest_rate_pct": self.interest_rate_pct,
            "margin_call_ltv_pct": self.margin_call_ltv_pct,
            "series": [p.to_dict() for p in self.series],
            "headroom_pp": self.headroom_pp,
            "collateral_fall_to_trigger_pct": self.collateral_fall_to_trigger_pct,
            "breaches": [p.to_dict() for p in self.breaches],
            "cure_narrative": self.cure_narrative,
            "drawn_reconciliation": self.drawn_reconciliation,
        }

    def evidence(self) -> list[Evidence]:
        out = [
            Evidence(
                source_file="credit_facilities.csv",
                row_or_id=self.facility_id,
                field="margin_call_ltv_pct",
                value=self.margin_call_ltv_pct,
                note="Margin-call trigger.",
            )
        ]
        for point in self.series:
            if point.ltv_pct is None:
                continue
            out.append(
                Evidence(
                    source_file="credit_facilities.csv",
                    row_or_id=self.facility_id,
                    field=f"ltv_pct_{point.snapshot}",
                    value=round(point.ltv_pct, 2),
                    snapshot_date=point.snapshot,
                    note="Breached the trigger." if point.breached else None,
                )
            )
        return out


def _reconcile_drawn(
    book: DataBook, facility: dict[str, Any]
) -> list[dict[str, Any]]:
    """Check each change in ``drawn`` against facility activity in transactions.

    Where the two disagree we report the gap rather than assuming the ledger is
    right. Production banking data contains exactly this kind of artefact.
    """
    portfolio_id = facility.get("collateral_portfolio_id")
    rows = [
        t
        for t in book.transactions
        if t.get("portfolio_id") == portfolio_id
        and "facility" in str(t.get("transaction_type", "")).lower()
    ]
    out: list[dict[str, Any]] = []
    for prev, curr in zip(config.SNAPSHOTS, config.SNAPSHOTS[1:]):
        before = book.dated(facility, "drawn", prev)
        after = book.dated(facility, "drawn", curr)
        if before is None or after is None:
            continue
        delta = after - before
        if abs(delta) < 1:
            continue
        matched = [t for t in rows if prev < (t.get("trade_date") or "") <= curr]
        explained = sum(t.get("amount") or 0.0 for t in matched)
        out.append(
            {
                "from_snapshot": prev,
                "to_snapshot": curr,
                "drawn_change": delta,
                "explained_by_transactions": explained,
                "unexplained": delta - explained,
                "transaction_ids": [t["transaction_id"] for t in matched],
            }
        )
    return out


def _cure_narrative(facility: dict[str, Any], series: list[LtvPoint]) -> str | None:
    """Describe how a past breach stopped being a breach."""
    for prev, curr in zip(series, series[1:]):
        if not prev.breached or curr.breached:
            continue
        if prev.drawn is None or curr.drawn is None:
            continue
        repaid = prev.drawn - curr.drawn
        collateral_move = (
            (curr.lending_value - prev.lending_value) if prev.lending_value else 0.0
        )
        if repaid > 1:
            return (
                f"The breach at {prev.snapshot} was cured by {prev.snapshot} to "
                f"{curr.snapshot} by a repayment of {repaid:,.0f} "
                f"{facility.get('facility_ccy', '')}."
            )
        return (
            f"The breach at {prev.snapshot} was cured by {curr.snapshot} without any "
            f"repayment: the drawn balance was unchanged and lending value rose by "
            f"{collateral_move:,.0f} {facility.get('facility_ccy', '')} as the "
            f"collateral appreciated. The exposure was resolved by the market, not "
            f"by an action, and would return if the move reversed."
        )
    return None


def facility_view(book: DataBook, facility: dict[str, Any]) -> FacilityView:
    trigger = facility.get("margin_call_ltv_pct") or 0.0
    series: list[LtvPoint] = []
    for snapshot in config.SNAPSHOTS:
        ltv = book.dated(facility, "ltv_pct", snapshot)
        series.append(
            LtvPoint(
                snapshot=snapshot,
                label=config.SNAPSHOT_LABELS.get(snapshot, snapshot),
                drawn=book.dated(facility, "drawn", snapshot),
                collateral_market_value=book.dated(
                    facility, "collateral_market_value", snapshot
                ),
                lending_value=book.dated(facility, "lending_value", snapshot),
                ltv_pct=ltv,
                headroom=book.dated(facility, "headroom", snapshot),
                breached=bool(ltv is not None and trigger and ltv > trigger),
            )
        )

    current = series[-1]
    headroom_pp = (
        None if current.ltv_pct is None or not trigger else trigger - current.ltv_pct
    )
    # Lending value scales with collateral value, so the fall that takes LTV to
    # the trigger is 1 - (current LTV / trigger).
    fall_pct = (
        None
        if not current.ltv_pct or not trigger
        else max(0.0, (1 - current.ltv_pct / trigger) * 100)
    )

    return FacilityView(
        facility_id=facility["facility_id"],
        client_id=facility["client_id"],
        portfolio_id=facility.get("collateral_portfolio_id", ""),
        facility_type=facility.get("facility_type", ""),
        currency=facility.get("facility_ccy", ""),
        credit_limit=facility.get("credit_limit") or 0.0,
        interest_rate_pct=facility.get("interest_rate_pct") or 0.0,
        margin_call_ltv_pct=trigger,
        series=series,
        headroom_pp=headroom_pp,
        collateral_fall_to_trigger_pct=fall_pct,
        breaches=[p for p in series if p.breached],
        cure_narrative=_cure_narrative(facility, series),
        drawn_reconciliation=_reconcile_drawn(book, facility),
    )


def client_facilities(book: DataBook, client_id: str) -> list[FacilityView]:
    return [
        facility_view(book, f) for f in book.facilities_by_client.get(client_id, [])
    ]


def withdrawal_capacity(view: FacilityView) -> float | None:
    """Cash that can be taken out of the collateral pool before the trigger hits.

    Selling a collateral asset and withdrawing the proceeds removes lending
    value while the drawn balance stays put, so the capacity is
    ``lending_value - drawn / trigger``.
    """
    current = view.current
    if current.lending_value is None or current.drawn is None or not view.margin_call_ltv_pct:
        return None
    required_lending_value = current.drawn / (view.margin_call_ltv_pct / 100)
    return max(0.0, current.lending_value - required_lending_value)
