"""Household valuation and roll-up.

A client's risk is not visible one portfolio at a time. Everything here
aggregates to the *household* first and keeps the per-portfolio detail attached,
because that is the level at which concentration, liquidity and currency
exposure actually bite.

Reporting currency is USD throughout. ``holdings.market_value_usd`` is used
directly rather than re-derived, and reconciles to ``portfolios.aum_<date>``
converted at that snapshot's FX to within rounding on all 24 portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..loaders import DataBook


@dataclass(frozen=True)
class Position:
    """One instrument held by one client, summed across their portfolios."""

    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str
    region: str
    currency: str
    liquidity_tier: str
    market_value_usd: float
    weight_pct: float
    lending_value_usd: float
    advance_rate_pct: float | None
    unrealised_pnl_usd: float
    cost_basis_usd: float
    portfolio_ids: tuple[str, ...]
    concentration_limit_applies: bool
    sustainability_excluded: bool
    underlying_reference: str

    @property
    def unrealised_pnl_pct(self) -> float | None:
        if not self.cost_basis_usd:
            return None
        return self.unrealised_pnl_usd / self.cost_basis_usd * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "asset_class": self.asset_class,
            "sub_asset_class": self.sub_asset_class,
            "sector": self.sector,
            "region": self.region,
            "currency": self.currency,
            "liquidity_tier": self.liquidity_tier,
            "market_value_usd": self.market_value_usd,
            "weight_pct": self.weight_pct,
            "lending_value_usd": self.lending_value_usd,
            "advance_rate_pct": self.advance_rate_pct,
            "unrealised_pnl_usd": self.unrealised_pnl_usd,
            "unrealised_pnl_pct": self.unrealised_pnl_pct,
            "portfolio_ids": list(self.portfolio_ids),
            "concentration_limit_applies": self.concentration_limit_applies,
            "sustainability_excluded": self.sustainability_excluded,
            "underlying_reference": self.underlying_reference,
        }


@dataclass
class HouseholdView:
    """Everything a client owns at one snapshot, aggregated and sliced."""

    client_id: str
    snapshot: str
    total_usd: float
    positions: list[Position]
    by_asset_class: dict[str, float]
    by_liquidity_tier: dict[str, float]
    by_currency: dict[str, float]
    by_region: dict[str, float]
    by_sector: dict[str, float]
    by_portfolio: dict[str, float]

    def weight(self, amount: float) -> float:
        return 0.0 if not self.total_usd else amount / self.total_usd * 100

    def asset_class_pct(self, asset_class: str) -> float:
        return self.weight(self.by_asset_class.get(asset_class, 0.0))

    def position(self, instrument_id: str) -> Position | None:
        for p in self.positions:
            if p.instrument_id == instrument_id:
                return p
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "snapshot": self.snapshot,
            "total_usd": self.total_usd,
            "positions": [p.to_dict() for p in self.positions],
            "by_asset_class": self.by_asset_class,
            "by_liquidity_tier": self.by_liquidity_tier,
            "by_currency": self.by_currency,
            "by_region": self.by_region,
            "by_sector": self.by_sector,
            "by_portfolio": self.by_portfolio,
        }


def _bucket(target: dict[str, float], key: str, value: float) -> None:
    if not key:
        key = "Unclassified"
    target[key] = target.get(key, 0.0) + value


def household_view(
    book: DataBook, client_id: str, snapshot: str = config.AS_OF
) -> HouseholdView:
    """Aggregate every portfolio a client holds into a single wealth view.

    Custody accounts are included: they are part of the client's wealth even
    though no mandate governs them. Mandate checks exclude them separately.
    """
    rows = book.holdings_by_client_date.get((client_id, snapshot), [])
    merged: dict[str, dict[str, Any]] = {}

    for h in rows:
        iid = h["instrument_id"]
        instrument = book.instrument(iid)
        mv = h.get("market_value_usd") or 0.0
        # Lending value is quoted in the portfolio's base currency.
        pf = book.portfolios.get(h["portfolio_id"], {})
        lv_base = h.get("lending_value_base") or 0.0
        lv_usd = book.to_usd(lv_base, pf.get("base_currency", "USD"), snapshot) or 0.0
        pnl_base = h.get("unrealised_pnl_base") or 0.0
        pnl_usd = book.to_usd(pnl_base, pf.get("base_currency", "USD"), snapshot) or 0.0
        cost_base = h.get("cost_basis_base") or 0.0
        cost_usd = (
            book.to_usd(cost_base, pf.get("base_currency", "USD"), snapshot) or 0.0
        )

        entry = merged.get(iid)
        if entry is None:
            entry = {
                "instrument_id": iid,
                "instrument_name": h.get("instrument_name")
                or instrument.get("instrument_name", iid),
                "asset_class": h.get("asset_class") or instrument.get("asset_class", ""),
                "sub_asset_class": h.get("sub_asset_class")
                or instrument.get("sub_asset_class", ""),
                "sector": h.get("sector") or instrument.get("sector", ""),
                "region": h.get("region") or instrument.get("region", ""),
                "currency": h.get("instrument_ccy") or instrument.get("currency", ""),
                "liquidity_tier": h.get("liquidity_tier")
                or instrument.get("liquidity_tier", ""),
                "market_value_usd": 0.0,
                "lending_value_usd": 0.0,
                "unrealised_pnl_usd": 0.0,
                "cost_basis_usd": 0.0,
                "advance_rate_pct": h.get("advance_rate_pct"),
                "portfolio_ids": [],
                "concentration_limit_applies": instrument.get(
                    "concentration_limit_applies"
                )
                == "Y",
                "sustainability_excluded": instrument.get("sustainability_excluded")
                == "Y",
                "underlying_reference": instrument.get("underlying_reference") or "",
            }
            merged[iid] = entry
        entry["market_value_usd"] += mv
        entry["lending_value_usd"] += lv_usd
        entry["unrealised_pnl_usd"] += pnl_usd
        entry["cost_basis_usd"] += cost_usd
        if h["portfolio_id"] not in entry["portfolio_ids"]:
            entry["portfolio_ids"].append(h["portfolio_id"])

    total = sum(e["market_value_usd"] for e in merged.values())
    positions = [
        Position(
            instrument_id=e["instrument_id"],
            instrument_name=e["instrument_name"],
            asset_class=e["asset_class"],
            sub_asset_class=e["sub_asset_class"],
            sector=e["sector"],
            region=e["region"],
            currency=e["currency"],
            liquidity_tier=e["liquidity_tier"],
            market_value_usd=e["market_value_usd"],
            weight_pct=(e["market_value_usd"] / total * 100) if total else 0.0,
            lending_value_usd=e["lending_value_usd"],
            advance_rate_pct=e["advance_rate_pct"],
            unrealised_pnl_usd=e["unrealised_pnl_usd"],
            cost_basis_usd=e["cost_basis_usd"],
            portfolio_ids=tuple(e["portfolio_ids"]),
            concentration_limit_applies=e["concentration_limit_applies"],
            sustainability_excluded=e["sustainability_excluded"],
            underlying_reference=e["underlying_reference"],
        )
        for e in merged.values()
    ]
    positions.sort(key=lambda p: -p.market_value_usd)

    by_asset_class: dict[str, float] = {}
    by_liquidity: dict[str, float] = {}
    by_currency: dict[str, float] = {}
    by_region: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for p in positions:
        _bucket(by_asset_class, p.asset_class, p.market_value_usd)
        _bucket(by_liquidity, p.liquidity_tier, p.market_value_usd)
        _bucket(by_currency, p.currency, p.market_value_usd)
        _bucket(by_region, p.region, p.market_value_usd)
        _bucket(by_sector, p.sector, p.market_value_usd)

    by_portfolio: dict[str, float] = {}
    for h in rows:
        _bucket(by_portfolio, h["portfolio_id"], h.get("market_value_usd") or 0.0)

    return HouseholdView(
        client_id=client_id,
        snapshot=snapshot,
        total_usd=total,
        positions=positions,
        by_asset_class=by_asset_class,
        by_liquidity_tier=by_liquidity,
        by_currency=by_currency,
        by_region=by_region,
        by_sector=by_sector,
        by_portfolio=by_portfolio,
    )


def portfolio_allocation(
    book: DataBook, portfolio_id: str, snapshot: str = config.AS_OF
) -> tuple[float, dict[str, float]]:
    """Return ``(total_base_ccy, {asset_class: pct})`` for one portfolio."""
    rows = book.holdings_by_portfolio_date.get((portfolio_id, snapshot), [])
    total = sum(r.get("market_value_base") or 0.0 for r in rows)
    buckets: dict[str, float] = {}
    for r in rows:
        _bucket(buckets, r.get("asset_class", ""), r.get("market_value_base") or 0.0)
    pct = {k: (v / total * 100 if total else 0.0) for k, v in buckets.items()}
    return total, pct


@dataclass(frozen=True)
class SnapshotPoint:
    snapshot: str
    label: str
    total_usd: float
    change_usd: float | None
    change_pct: float | None


def household_timeseries(book: DataBook, client_id: str) -> list[SnapshotPoint]:
    """Household wealth in USD at each of the five snapshots.

    Note this is a *value* series, not a performance series: it includes
    contributions, withdrawals and FX. Attribution separates those.
    """
    points: list[SnapshotPoint] = []
    previous: float | None = None
    for snapshot in config.SNAPSHOTS:
        rows = book.holdings_by_client_date.get((client_id, snapshot), [])
        total = sum(r.get("market_value_usd") or 0.0 for r in rows)
        change = None if previous is None else total - previous
        change_pct = (
            None if previous in (None, 0) else (total - previous) / previous * 100
        )
        points.append(
            SnapshotPoint(
                snapshot=snapshot,
                label=config.SNAPSHOT_LABELS.get(snapshot, snapshot),
                total_usd=total,
                change_usd=change,
                change_pct=change_pct,
            )
        )
        previous = total
    return points


def realisable_by_tier(view: HouseholdView) -> dict[str, float]:
    """Market value available at each liquidity tier, in tier order."""
    return {
        tier: view.by_liquidity_tier.get(tier, 0.0) for tier in config.LIQUIDITY_TIERS
    }


def readily_realisable_usd(view: HouseholdView) -> float:
    """Value the client could realistically raise inside about 30 days."""
    return sum(
        view.by_liquidity_tier.get(tier, 0.0) for tier in config.READILY_REALISABLE
    )
