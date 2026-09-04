"""Portfolio income.

``transactions.csv`` records income at the quarter ends that fall inside the
snapshot window -- 31 March and 30 June 2026. Two quarters of receipts are
doubled to give a run rate. That is a real assumption and it is returned
alongside the number rather than buried.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import config
from ..contracts import Assumption, Evidence
from ..loaders import DataBook

INCOME_TYPES = ("Coupon", "Dividend", "Interest", "Distribution")
COST_TYPES = ("Management Fee", "Interest Charge", "Custody Fee")

RUN_RATE_ASSUMPTION = Assumption(
    statement=(
        "Annual income is estimated by doubling the two quarters of receipts "
        "recorded in transactions.csv for 2026."
    ),
    basis=(
        "The file records income at 31 March and 30 June 2026 only; no full-year "
        "figure is provided."
    ),
    impact_if_wrong=(
        "Semi-annual coupons or irregular distributions would make the run rate "
        "over- or under-stated. Check against the coupon schedule before quoting it "
        "to a client."
    ),
)


@dataclass
class IncomeView:
    client_id: str
    quarters_observed: int
    gross_income_usd: float
    costs_usd: float
    net_income_usd: float
    annualised_gross_usd: float
    annualised_net_usd: float
    yield_pct: float | None
    by_instrument: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "quarters_observed": self.quarters_observed,
            "gross_income_usd": self.gross_income_usd,
            "costs_usd": self.costs_usd,
            "net_income_usd": self.net_income_usd,
            "annualised_gross_usd": self.annualised_gross_usd,
            "annualised_net_usd": self.annualised_net_usd,
            "yield_pct": self.yield_pct,
            "by_instrument": self.by_instrument,
        }

    def evidence(self) -> list[Evidence]:
        return [
            Evidence(
                source_file="transactions.csv",
                row_or_id=f"{self.client_id} income",
                field="amount",
                value=f"USD {self.gross_income_usd:,.0f} over "
                f"{self.quarters_observed} quarters",
                snapshot_date=config.AS_OF,
                note="Coupon, dividend, interest and distribution rows for 2026.",
            ),
            Evidence(
                source_file="transactions.csv",
                row_or_id=f"{self.client_id} costs",
                field="amount",
                value=f"USD {self.costs_usd:,.0f}",
                snapshot_date=config.AS_OF,
                note="Management fees and facility interest charges.",
            ),
        ]


def income_view(
    book: DataBook, client_id: str, household_total_usd: float | None = None
) -> IncomeView:
    gross = 0.0
    costs = 0.0
    quarters: set[str] = set()
    by_instrument: dict[str, float] = {}

    for t in book.transactions_by_client.get(client_id, []):
        trade_date = t.get("trade_date") or ""
        if not trade_date.startswith("2026"):
            continue
        amount_usd = (
            book.to_usd(t.get("amount") or 0.0, t.get("currency") or "USD", config.AS_OF)
            or 0.0
        )
        ttype = t.get("transaction_type") or ""
        if ttype in INCOME_TYPES:
            gross += amount_usd
            quarters.add(trade_date)
            key = t.get("instrument_id") or ttype
            by_instrument[key] = by_instrument.get(key, 0.0) + amount_usd
        elif ttype in COST_TYPES:
            costs += abs(amount_usd)

    # Quarter ends are the only dates income is booked on.
    observed = len({d for d in quarters if d.endswith(("-03-31", "-06-30", "-09-30", "-12-31"))}) or 1
    factor = 4 / observed
    annual_gross = gross * factor
    annual_net = (gross - costs) * factor

    return IncomeView(
        client_id=client_id,
        quarters_observed=observed,
        gross_income_usd=gross,
        costs_usd=costs,
        net_income_usd=gross - costs,
        annualised_gross_usd=annual_gross,
        annualised_net_usd=annual_net,
        yield_pct=(
            None
            if not household_total_usd
            else annual_gross / household_total_usd * 100
        ),
        by_instrument=dict(
            sorted(by_instrument.items(), key=lambda kv: -kv[1])
        ),
    )
