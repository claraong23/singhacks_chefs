"""Attribution: what changed between two snapshots, and why.

"Down 4.1%" is a number. "Down 4.1%, of which 3.3 points came from duration as
the 10-year moved from 4.05% to 4.66%, partly offset by gold" is an
explanation. This module produces the second.

Each position's USD change between two snapshots is split into three exact,
non-overlapping parts:

    price = q0 * (p1 - p0) * f0        market move in the instrument's currency
    fx    = q0 *  p1       * (f1 - f0) translation of the new price
    flow  = (q1 - q0) * p1 * f1        the client bought or sold

Those three sum to ``q1*p1*f1 - q0*p0*f0`` with no residual, so a total can
always be reconciled back to the snapshots it came from.

Positions opened during the period are handled separately. Treating a new
holding as pure flow at its closing mark hides its loss -- CL-0014's HKD 25m
accumulator would appear as a USD 1.9m *inflow* rather than the USD 1.3m loss it
is. For those, money deployed is taken from ``cost_basis_base`` and everything
above or below cost is reported as a price effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import config
from ..contracts import Assumption, Evidence
from ..loaders import DataBook
from .lookthrough import THEMES

NEW_POSITION_ASSUMPTION = Assumption(
    statement=(
        "For positions opened during the period, money deployed is taken from "
        "cost_basis_base and converted at the closing snapshot's exchange rate."
    ),
    basis=(
        "cost_basis_base is struck at the rate prevailing when the position was "
        "acquired, and the dataset does not record the acquisition rate separately."
    ),
    impact_if_wrong=(
        "A small FX component of the gain or loss is reported as a price effect. It "
        "does not change the size of the total move."
    ),
)


@dataclass
class Contribution:
    instrument_id: str
    instrument_name: str
    asset_class: str
    currency: str
    start_value_usd: float
    end_value_usd: float
    price_effect_usd: float
    fx_effect_usd: float
    flow_effect_usd: float
    price_start: float | None
    price_end: float | None

    @property
    def total_usd(self) -> float:
        return self.price_effect_usd + self.fx_effect_usd + self.flow_effect_usd

    @property
    def price_return_pct(self) -> float | None:
        if not self.price_start or self.price_end is None:
            return None
        return (self.price_end / self.price_start - 1) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "asset_class": self.asset_class,
            "currency": self.currency,
            "start_value_usd": self.start_value_usd,
            "end_value_usd": self.end_value_usd,
            "price_effect_usd": self.price_effect_usd,
            "fx_effect_usd": self.fx_effect_usd,
            "flow_effect_usd": self.flow_effect_usd,
            "total_usd": self.total_usd,
            "price_return_pct": self.price_return_pct,
            "price_start": self.price_start,
            "price_end": self.price_end,
        }


@dataclass
class AttributionResult:
    client_id: str
    start: str
    end: str
    start_value_usd: float
    end_value_usd: float
    change_usd: float
    change_pct: float | None
    price_effect_usd: float
    fx_effect_usd: float
    flow_effect_usd: float
    contributions: list[Contribution]
    by_asset_class: dict[str, float]
    by_theme: dict[str, float]

    @property
    def detractors(self) -> list[Contribution]:
        return [c for c in self.contributions if c.total_usd < 0][:8]

    @property
    def contributors(self) -> list[Contribution]:
        return [c for c in self.contributions if c.total_usd > 0][:8]

    @property
    def market_detractors(self) -> list[Contribution]:
        """Ranked by market move alone, ignoring money paid in or taken out.

        This is the list an RM needs when a client asks what went wrong: a
        position bought during the period can be the largest loss in the book
        while still showing a positive total change.
        """
        ranked = sorted(self.contributions, key=lambda c: c.price_effect_usd)
        return [c for c in ranked if c.price_effect_usd < 0][:8]

    @property
    def market_contributors(self) -> list[Contribution]:
        ranked = sorted(
            self.contributions, key=lambda c: c.price_effect_usd, reverse=True
        )
        return [c for c in ranked if c.price_effect_usd > 0][:8]

    def pct_of_start(self, amount: float) -> float | None:
        if not self.start_value_usd:
            return None
        return amount / self.start_value_usd * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "start": self.start,
            "end": self.end,
            "start_label": config.SNAPSHOT_LABELS.get(self.start, self.start),
            "end_label": config.SNAPSHOT_LABELS.get(self.end, self.end),
            "start_value_usd": self.start_value_usd,
            "end_value_usd": self.end_value_usd,
            "change_usd": self.change_usd,
            "change_pct": self.change_pct,
            "price_effect_usd": self.price_effect_usd,
            "fx_effect_usd": self.fx_effect_usd,
            "flow_effect_usd": self.flow_effect_usd,
            "contributions": [c.to_dict() for c in self.contributions],
            "market_detractors": [c.to_dict() for c in self.market_detractors],
            "market_contributors": [c.to_dict() for c in self.market_contributors],
            "by_asset_class": self.by_asset_class,
            "by_theme": self.by_theme,
        }


def _positions(book: DataBook, client_id: str, snapshot: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for h in book.holdings_by_client_date.get((client_id, snapshot), []):
        iid = h["instrument_id"]
        entry = out.setdefault(
            iid,
            {
                "quantity": 0.0,
                "price_local": h.get("price_local"),
                "currency": h.get("instrument_ccy"),
                "market_value_usd": 0.0,
                "cost_basis_usd": 0.0,
                "instrument_name": h.get("instrument_name"),
                "asset_class": h.get("asset_class"),
            },
        )
        entry["quantity"] += h.get("quantity") or 0.0
        entry["market_value_usd"] += h.get("market_value_usd") or 0.0
        pf = book.portfolios.get(h["portfolio_id"], {})
        entry["cost_basis_usd"] += (
            book.to_usd(
                h.get("cost_basis_base") or 0.0,
                pf.get("base_currency", "USD"),
                snapshot,
            )
            or 0.0
        )
    return out


def attribute(
    book: DataBook,
    client_id: str,
    start: str = config.BASELINE_SNAPSHOT,
    end: str = config.AS_OF,
) -> AttributionResult:
    """Decompose a household's change in USD value between two snapshots."""
    before = _positions(book, client_id, start)
    after = _positions(book, client_id, end)

    contributions: list[Contribution] = []
    for iid in set(before) | set(after):
        b = before.get(iid)
        a = after.get(iid)
        instrument = book.instrument(iid)
        currency = (a or b).get("currency") or instrument.get("currency") or "USD"
        f0 = book.usd_per_unit(currency, start) or 1.0
        f1 = book.usd_per_unit(currency, end) or 1.0

        q0 = (b or {}).get("quantity", 0.0)
        q1 = (a or {}).get("quantity", 0.0)
        p0 = (b or {}).get("price_local")
        p1 = (a or {}).get("price_local")
        if p0 is None:
            p0 = instrument.get(f"price_{start}")
        if p1 is None:
            p1 = instrument.get(f"price_{end}")

        start_value = (b or {}).get("market_value_usd", 0.0)
        end_value = (a or {}).get("market_value_usd", 0.0)

        if a is None:
            # Position exited: the whole move is a flow at the old valuation.
            price_effect = fx_effect = 0.0
            flow_effect = -start_value
        elif b is None:
            # Position opened during the period. Money deployed is the cost
            # basis; the gap between cost and today's mark is a price effect,
            # not a flow.
            cost = a.get("cost_basis_usd") or 0.0
            fx_effect = 0.0
            if cost:
                flow_effect = cost
                price_effect = end_value - cost
            else:
                flow_effect = end_value
                price_effect = 0.0
        else:
            price_effect = q0 * ((p1 or 0.0) - (p0 or 0.0)) * f0
            fx_effect = q0 * (p1 or 0.0) * (f1 - f0)
            flow_effect = (q1 - q0) * (p1 or 0.0) * f1
            # The three terms are exact against q*p*fx, but start and end values
            # are taken from holdings.market_value_usd, which the source rounds
            # independently. Fold the residual into the price effect so a
            # client's total always reconciles to the snapshots it came from.
            residual = (end_value - start_value) - (
                price_effect + fx_effect + flow_effect
            )
            price_effect += residual

        contributions.append(
            Contribution(
                instrument_id=iid,
                instrument_name=(a or b).get("instrument_name")
                or instrument.get("instrument_name", iid),
                asset_class=(a or b).get("asset_class")
                or instrument.get("asset_class", ""),
                currency=currency,
                start_value_usd=start_value,
                end_value_usd=end_value,
                price_effect_usd=price_effect,
                fx_effect_usd=fx_effect,
                flow_effect_usd=flow_effect,
                price_start=p0,
                price_end=p1,
            )
        )

    contributions.sort(key=lambda c: c.total_usd)

    start_total = sum(c.start_value_usd for c in contributions)
    end_total = sum(c.end_value_usd for c in contributions)

    by_asset_class: dict[str, float] = {}
    for c in contributions:
        key = c.asset_class or "Unclassified"
        by_asset_class[key] = by_asset_class.get(key, 0.0) + c.total_usd

    by_theme: dict[str, float] = {}
    for theme in THEMES:
        total = sum(
            c.total_usd * theme.weight_for(c.instrument_id)
            for c in contributions
            if theme.weight_for(c.instrument_id)
        )
        if total:
            by_theme[theme.key] = total

    return AttributionResult(
        client_id=client_id,
        start=start,
        end=end,
        start_value_usd=start_total,
        end_value_usd=end_total,
        change_usd=end_total - start_total,
        change_pct=(
            None if not start_total else (end_total - start_total) / start_total * 100
        ),
        price_effect_usd=sum(c.price_effect_usd for c in contributions),
        fx_effect_usd=sum(c.fx_effect_usd for c in contributions),
        flow_effect_usd=sum(c.flow_effect_usd for c in contributions),
        contributions=contributions,
        by_asset_class=by_asset_class,
        by_theme=by_theme,
    )


#: Market series that make a themed move legible, in the order we quote them.
THEME_MARKET_SERIES: dict[str, tuple[str, ...]] = {
    "energy_hormuz": ("BRENT_USD_BBL", "TTF_GAS_EUR_MWH"),
    "us_tech_ai": ("NASDAQ_COMP",),
    "gold_monetary": ("GOLD_USD_OZ",),
    "duration": ("UST_10Y_PCT", "UST_2Y_PCT"),
    "hk_property": ("HSI",),
    "greater_china_consumer": ("HSI",),
    "private_markets": (),
}


def market_moves(
    book: DataBook, series_ids: tuple[str, ...], start: str, end: str
) -> list[dict[str, Any]]:
    """The market levels behind a themed move, for citation in the narrative."""
    out: list[dict[str, Any]] = []
    for series_id in series_ids:
        meta = book.market_meta.get(series_id)
        v0 = book.market_value(series_id, start)
        v1 = book.market_value(series_id, end)
        if meta is None or v0 is None or v1 is None:
            continue
        out.append(
            {
                "series_id": series_id,
                "series_name": meta["series_name"],
                "unit": meta["unit"],
                "start_value": v0,
                "end_value": v1,
                "change": v1 - v0,
                "change_pct": None if not v0 else (v1 / v0 - 1) * 100,
            }
        )
    return out


def market_evidence(moves: list[dict[str, Any]], start: str, end: str) -> list[Evidence]:
    out: list[Evidence] = []
    for m in moves:
        out.append(
            Evidence(
                source_file="market_context.csv",
                row_or_id=m["series_id"],
                field="value",
                value=f"{m['start_value']} -> {m['end_value']} {m['unit']}",
                snapshot_date=end,
                note=f"{m['series_name']}, {start} to {end}.",
            )
        )
    return out


def contribution_evidence(
    contributions: list[Contribution], start: str, end: str, limit: int = 5
) -> list[Evidence]:
    out: list[Evidence] = []
    for c in contributions[:limit]:
        out.append(
            Evidence(
                source_file="holdings.csv",
                row_or_id=c.instrument_id,
                field="market_value_usd",
                value=f"{c.start_value_usd:,.0f} -> {c.end_value_usd:,.0f}",
                snapshot_date=end,
                note=(
                    f"{c.instrument_name}: price effect USD {c.price_effect_usd:,.0f}, "
                    f"FX USD {c.fx_effect_usd:,.0f}, flows USD {c.flow_effect_usd:,.0f} "
                    f"between {start} and {end}."
                ),
            )
        )
    return out
