"""Liquidity: what is owed, and what can actually be sold to meet it.

The mistake this module exists to avoid is comparing a liability to a total
portfolio value. A client with USD 88m is not liquid if USD 24m of it is in a
gated private credit fund and a private equity vehicle with a 0% advance rate.

Three constraints are applied in order:

1. **Tier.** Only Daily and Weekly positions count as realisable inside a month.
2. **Encumbrance.** Assets pledged against a Lombard facility cannot simply be
   sold and withdrawn -- doing so removes lending value while the drawn balance
   stays put. Withdrawable value is capped at what keeps LTV under the trigger.
3. **Certainty.** Confirmed obligations are separated from likely and
   conditional ones, because the RM conversation differs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .. import config
from ..contracts import Assumption, Evidence
from ..loaders import DataBook, parse_date
from .collateral import client_facilities, withdrawal_capacity
from .valuation import HouseholdView

_QUARTER_STARTS = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}

ANNUAL_ASSUMPTION = Assumption(
    statement=(
        "'Annual' rows in planned_cash_needs are read as an amount per year; "
        "'Annual instalments' rows are read as a total spread evenly across the "
        "due_from to due_to window."
    ),
    basis=(
        "The file uses both wordings. CN-012 (USD 1.28m, 'Annual') matches the "
        "client's stated USD 1.1m annual drawdown in clients.objectives as raised in "
        "note N-016, so 'Annual' is per year. CN-007 (USD 5m, 'Annual instalments', "
        "two children, four-year window) would exceed the client's entire household "
        "wealth if read the same way, so 'instalments' is read as a total."
    ),
    impact_if_wrong=(
        "Reading CN-007 as USD 5m per year would put this client's obligations above "
        "their total wealth. Each row is listed individually with its recurrence so "
        "the RM can check the source."
    ),
)

ENCUMBRANCE_ASSUMPTION = Assumption(
    statement=(
        "Withdrawable value from a pledged portfolio is capped at "
        "lending_value - drawn / margin_call_ltv, not at market value."
    ),
    basis=(
        "Selling collateral and withdrawing the proceeds reduces lending value while "
        "the drawn balance is unchanged, so LTV rises."
    ),
    impact_if_wrong="Overstates what the client can raise without a margin call.",
)


def _parse_window_start(text: str) -> date | None:
    """Turn '2026 Q4 to 2028 Q2' into the first day of the opening quarter."""
    match = re.search(r"(\d{4})\s*(Q[1-4])", text or "")
    if not match:
        return None
    return parse_date(f"{match.group(1)}-{_QUARTER_STARTS[match.group(2)]}")


def _horizon_end(months: int) -> date:
    start = parse_date(config.AS_OF)
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, 28)
    return date(year, month, day)


def _annual_dates(start: date, end: date) -> list[date]:
    dates: list[date] = []
    cursor = start
    while cursor <= end:
        dates.append(cursor)
        try:
            cursor = cursor.replace(year=cursor.year + 1)
        except ValueError:  # 29 February
            cursor = cursor.replace(year=cursor.year + 1, day=28)
    return dates


def schedule(need: dict[str, Any], horizon_end: date) -> tuple[int, float]:
    """Return ``(occurrences inside the horizon, amount per occurrence)``.

    The recurrence column distinguishes 'Annual' from 'Annual instalments'. The
    first is an amount per year; the second is a total paid down in yearly
    steps. Treating them the same puts one client's obligations above their
    total wealth, so the wording is respected.
    """
    amount = need.get("amount") or 0.0
    start = parse_date(need.get("due_from") or "") or parse_date(config.AS_OF)
    end = parse_date(need.get("due_to") or "") or horizon_end
    today = parse_date(config.AS_OF)
    recurrence = (need.get("recurrence") or "").lower()

    if "one-off" in recurrence or not recurrence:
        return (1 if start <= horizon_end and end >= today else 0), amount

    if "irregular" in recurrence:
        # No fixed cadence; the whole amount can land inside the window.
        return (1 if start <= horizon_end else 0), amount

    all_dates = _annual_dates(start, end)
    in_horizon = [d for d in all_dates if today <= d <= horizon_end]

    if "instalment" in recurrence:
        per_occurrence = amount / len(all_dates) if all_dates else amount
    else:
        per_occurrence = amount

    return len(in_horizon), per_occurrence


def annual_amount(need: dict[str, Any]) -> float:
    """The amount this need costs in a typical year."""
    start = parse_date(need.get("due_from") or "")
    end = parse_date(need.get("due_to") or "")
    amount = need.get("amount") or 0.0
    recurrence = (need.get("recurrence") or "").lower()
    if "instalment" in recurrence and start and end:
        dates = _annual_dates(start, end)
        return amount / len(dates) if dates else amount
    return amount


@dataclass
class Obligation:
    id: str
    source: str  # "planned_cash_needs" | "commitments"
    description: str
    currency: str
    amount_ccy: float
    amount_usd: float
    occurrences: int
    total_usd: float
    due_from: str
    due_to: str
    certainty: str
    recurrence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "description": self.description,
            "currency": self.currency,
            "amount_ccy": self.amount_ccy,
            "amount_usd": self.amount_usd,
            "occurrences": self.occurrences,
            "total_usd": self.total_usd,
            "due_from": self.due_from,
            "due_to": self.due_to,
            "certainty": self.certainty,
            "recurrence": self.recurrence,
        }


@dataclass
class LiquidityView:
    client_id: str
    snapshot: str
    horizon_months: int
    horizon_end: str
    total_usd: float
    by_tier: dict[str, float]
    readily_realisable_usd: float
    encumbered_cap_usd: float | None
    withdrawable_usd: float
    gated_usd: float
    illiquid_usd: float
    obligations: list[Obligation]
    obligations_confirmed_usd: float
    obligations_total_usd: float
    coverage_ratio: float | None
    shortfall_usd: float
    gated_positions: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "snapshot": self.snapshot,
            "horizon_months": self.horizon_months,
            "horizon_end": self.horizon_end,
            "total_usd": self.total_usd,
            "by_tier": self.by_tier,
            "readily_realisable_usd": self.readily_realisable_usd,
            "encumbered_cap_usd": self.encumbered_cap_usd,
            "withdrawable_usd": self.withdrawable_usd,
            "gated_usd": self.gated_usd,
            "illiquid_usd": self.illiquid_usd,
            "obligations": [o.to_dict() for o in self.obligations],
            "obligations_confirmed_usd": self.obligations_confirmed_usd,
            "obligations_total_usd": self.obligations_total_usd,
            "coverage_ratio": self.coverage_ratio,
            "shortfall_usd": self.shortfall_usd,
            "gated_positions": self.gated_positions,
            "notes": list(self.notes),
        }

    def evidence(self) -> list[Evidence]:
        out: list[Evidence] = []
        for o in self.obligations:
            out.append(
                Evidence(
                    source_file=(
                        "planned_cash_needs.csv"
                        if o.source == "planned_cash_needs"
                        else "commitments.csv"
                    ),
                    row_or_id=o.id,
                    field="amount" if o.source == "planned_cash_needs" else "uncalled",
                    value=f"{o.currency} {o.amount_ccy:,.0f}",
                    note=f"{o.description} ({o.certainty}, {o.due_from} to {o.due_to}).",
                )
            )
        for p in self.gated_positions:
            out.append(
                Evidence(
                    source_file="holdings.csv",
                    row_or_id=p["instrument_id"],
                    field="liquidity_tier",
                    value=p["liquidity_tier"],
                    snapshot_date=self.snapshot,
                    note=f"USD {p['market_value_usd']:,.0f} not available on demand.",
                )
            )
        return out


def liquidity_view(
    book: DataBook,
    client_id: str,
    view: HouseholdView,
    horizon_months: int = config.NEAR_TERM_MONTHS,
) -> LiquidityView:
    snapshot = view.snapshot
    horizon_end = _horizon_end(horizon_months)

    by_tier = {
        tier: view.by_liquidity_tier.get(tier, 0.0) for tier in config.LIQUIDITY_TIERS
    }
    readily = sum(by_tier[t] for t in config.READILY_REALISABLE)
    gated = by_tier.get("Quarterly Gate", 0.0)
    illiquid = by_tier.get("Illiquid", 0.0)

    # Encumbrance: cap what can leave a pledged portfolio.
    facilities = client_facilities(book, client_id)
    encumbered_cap: float | None = None
    for facility in facilities:
        capacity = withdrawal_capacity(facility)
        if capacity is None:
            continue
        pf = book.portfolios.get(facility.portfolio_id, {})
        capacity_usd = (
            book.to_usd(capacity, pf.get("base_currency", "USD"), snapshot) or 0.0
        )
        pledged_realisable = 0.0
        for position in view.positions:
            if facility.portfolio_id not in position.portfolio_ids:
                continue
            if position.liquidity_tier in config.READILY_REALISABLE:
                pledged_realisable += position.market_value_usd
        # Only the pledged slice is capped; unpledged assets stay free.
        allowed = min(pledged_realisable, capacity_usd)
        encumbered_cap = (encumbered_cap or 0.0) + (pledged_realisable - allowed)

    withdrawable = max(0.0, readily - (encumbered_cap or 0.0))

    # planned_cash_needs and commitments overlap for at least one client: a
    # need described as "outstanding private markets commitments" restates the
    # uncalled column of commitments.csv. Counting both doubles the obligation,
    # so the restatement is dropped and the drop is reported.
    commitments = book.commitments_by_client.get(client_id, [])
    uncalled_total_usd = sum(
        book.to_usd(c.get("uncalled") or 0.0, c.get("currency", "USD"), snapshot) or 0.0
        for c in commitments
    )
    duplicated_need_ids: set[str] = set()
    if uncalled_total_usd:
        for need in book.cash_needs_by_client.get(client_id, []):
            description = (need.get("description") or "").lower()
            if "commitment" not in description and "capital call" not in description:
                continue
            amount_usd = (
                book.to_usd(need.get("amount") or 0.0, need.get("currency", "USD"), snapshot)
                or 0.0
            )
            if abs(amount_usd - uncalled_total_usd) <= uncalled_total_usd * 0.05:
                duplicated_need_ids.add(need["need_id"])

    obligations: list[Obligation] = []
    for need in book.cash_needs_by_client.get(client_id, []):
        if need["need_id"] in duplicated_need_ids:
            continue
        occurrences, amount = schedule(need, horizon_end)
        if occurrences <= 0:
            continue
        amount_usd = book.to_usd(amount, need.get("currency", "USD"), snapshot) or 0.0
        obligations.append(
            Obligation(
                id=need["need_id"],
                source="planned_cash_needs",
                description=need.get("description", ""),
                currency=need.get("currency", ""),
                amount_ccy=amount,
                amount_usd=amount_usd,
                occurrences=occurrences,
                total_usd=amount_usd * occurrences,
                due_from=need.get("due_from", ""),
                due_to=need.get("due_to", ""),
                certainty=need.get("certainty", ""),
                recurrence=need.get("recurrence", ""),
            )
        )

    for commitment in commitments:
        window_start = _parse_window_start(commitment.get("expected_call_window", ""))
        if window_start and window_start > horizon_end:
            continue
        uncalled = commitment.get("uncalled") or 0.0
        if uncalled <= 0:
            continue
        amount_usd = (
            book.to_usd(uncalled, commitment.get("currency", "USD"), snapshot) or 0.0
        )
        obligations.append(
            Obligation(
                id=commitment["commitment_id"],
                source="commitments",
                description=f"Uncalled commitment to {commitment.get('fund_name', '')}",
                currency=commitment.get("currency", ""),
                amount_ccy=uncalled,
                amount_usd=amount_usd,
                occurrences=1,
                total_usd=amount_usd,
                due_from=commitment.get("expected_call_window", ""),
                due_to=commitment.get("expected_call_window", ""),
                certainty="Committed - callable at the manager's discretion",
                recurrence="Irregular",
            )
        )

    obligations.sort(key=lambda o: -o.total_usd)
    total_obligations = sum(o.total_usd for o in obligations)
    confirmed = sum(
        o.total_usd
        for o in obligations
        if o.certainty.lower().startswith(("confirmed", "committed"))
    )

    gated_positions = [
        {
            "instrument_id": p.instrument_id,
            "instrument_name": p.instrument_name,
            "liquidity_tier": p.liquidity_tier,
            "market_value_usd": p.market_value_usd,
            "advance_rate_pct": p.advance_rate_pct,
        }
        for p in view.positions
        if p.liquidity_tier in ("Quarterly Gate", "Illiquid")
    ]

    coverage = None if not total_obligations else withdrawable / total_obligations
    shortfall = max(0.0, total_obligations - withdrawable)

    notes: list[str] = []
    if encumbered_cap:
        notes.append(
            f"USD {encumbered_cap:,.0f} of readily realisable value is pledged as "
            f"collateral and cannot be withdrawn without breaching a facility trigger."
        )
    if gated:
        notes.append(
            f"USD {gated:,.0f} sits in vehicles subject to a redemption gate; a "
            f"submitted redemption is not the same as cash received."
        )
    if total_obligations > view.total_usd:
        notes.append(
            "Obligations inside the horizon exceed total household wealth. Check the "
            "recurrence reading on the largest line before using this figure."
        )
    for need_id in sorted(duplicated_need_ids):
        notes.append(
            f"planned_cash_needs {need_id} restates the uncalled column of "
            f"commitments.csv (USD {uncalled_total_usd:,.0f}); it is counted once, "
            f"from commitments.csv."
        )

    return LiquidityView(
        client_id=client_id,
        snapshot=snapshot,
        horizon_months=horizon_months,
        horizon_end=horizon_end.isoformat(),
        total_usd=view.total_usd,
        by_tier=by_tier,
        readily_realisable_usd=readily,
        encumbered_cap_usd=encumbered_cap,
        withdrawable_usd=withdrawable,
        gated_usd=gated,
        illiquid_usd=illiquid,
        obligations=obligations,
        obligations_confirmed_usd=confirmed,
        obligations_total_usd=total_obligations,
        coverage_ratio=coverage,
        shortfall_usd=shortfall,
        gated_positions=gated_positions,
        notes=notes,
    )
