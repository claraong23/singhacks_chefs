"""Mandate governance.

Three separate questions, deliberately not merged:

1. Is the portfolio inside its strategic asset allocation bands?
2. Is any single position above the mandate's single-position limit? The limit
   is written to apply to single-name and single-asset exposures, so
   ``concentration_limit_applies`` gates the check -- a diversified fund at 20%
   is not a breach of a 12% single-position limit.
3. Does the portfolio hold anything the mandate's exclusions forbid?

Custody portfolios are skipped entirely. They form part of the wealth view but
no mandate governs them, and reporting a "breach" against an account the bank
does not manage would be wrong.

Whether a breach is drift or client-directed changes the conversation
completely, so where an RM note records an instruction or a waiver it is
attached -- flagged as reported, never as verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .. import config
from ..contracts import Evidence
from ..loaders import DataBook
from .valuation import portfolio_allocation

#: Phrases in an RM note that suggest a breach was instructed rather than drifted.
_WAIVER_PATTERNS = (
    r"waiver",
    r"confirmed the instruction in writing",
    r"client[- ]directed",
    r"acknowledged (?:this|the point) and (?:confirmed|proceeded)",
    r"instructed",
)


@dataclass
class BandBreach:
    portfolio_id: str
    mandate_code: str
    asset_class: str
    actual_pct: float
    min_pct: float
    target_pct: float
    max_pct: float
    direction: str  # "above" | "below"
    breach_pp: float
    value_base: float
    base_currency: str

    @property
    def is_material(self) -> bool:
        return self.breach_pp >= config.MANDATE_TOLERANCE_PCT

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "mandate_code": self.mandate_code,
            "asset_class": self.asset_class,
            "actual_pct": self.actual_pct,
            "min_pct": self.min_pct,
            "target_pct": self.target_pct,
            "max_pct": self.max_pct,
            "direction": self.direction,
            "breach_pp": self.breach_pp,
            "value_base": self.value_base,
            "base_currency": self.base_currency,
        }


@dataclass
class PositionBreach:
    portfolio_id: str
    mandate_code: str
    instrument_id: str
    instrument_name: str
    actual_pct: float
    limit_pct: float
    breach_pp: float
    value_base: float
    base_currency: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "mandate_code": self.mandate_code,
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "actual_pct": self.actual_pct,
            "limit_pct": self.limit_pct,
            "breach_pp": self.breach_pp,
            "value_base": self.value_base,
            "base_currency": self.base_currency,
        }


@dataclass
class ExclusionBreach:
    portfolio_id: str
    mandate_code: str
    instrument_id: str
    instrument_name: str
    pct_of_portfolio: float
    value_base: float
    base_currency: str
    service_model: str
    mandate_notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "mandate_code": self.mandate_code,
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "pct_of_portfolio": self.pct_of_portfolio,
            "value_base": self.value_base,
            "base_currency": self.base_currency,
            "service_model": self.service_model,
            "mandate_notes": self.mandate_notes,
        }


@dataclass
class MandateReview:
    portfolio_id: str
    client_id: str
    mandate_code: str
    mandate_name: str
    service_model: str
    governed: bool
    base_currency: str
    total_base: float
    allocation_pct: dict[str, float]
    band_breaches: list[BandBreach]
    position_breaches: list[PositionBreach]
    exclusion_breaches: list[ExclusionBreach]

    @property
    def has_findings(self) -> bool:
        return bool(
            self.band_breaches or self.position_breaches or self.exclusion_breaches
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "client_id": self.client_id,
            "mandate_code": self.mandate_code,
            "mandate_name": self.mandate_name,
            "service_model": self.service_model,
            "governed": self.governed,
            "base_currency": self.base_currency,
            "total_base": self.total_base,
            "allocation_pct": self.allocation_pct,
            "band_breaches": [b.to_dict() for b in self.band_breaches],
            "position_breaches": [b.to_dict() for b in self.position_breaches],
            "exclusion_breaches": [b.to_dict() for b in self.exclusion_breaches],
        }


def review_portfolio(
    book: DataBook, portfolio_id: str, snapshot: str = config.AS_OF
) -> MandateReview:
    pf = book.portfolios[portfolio_id]
    mandate = book.mandate_for(portfolio_id) or {}
    governed = book.is_mandated(portfolio_id)
    total_base, allocation = portfolio_allocation(book, portfolio_id, snapshot)
    base_ccy = pf.get("base_currency", "USD")

    band_breaches: list[BandBreach] = []
    position_breaches: list[PositionBreach] = []
    exclusion_breaches: list[ExclusionBreach] = []

    if governed and mandate:
        bands = mandate.get("bands", {})
        for asset_class in config.ASSET_CLASSES:
            band = bands.get(asset_class)
            if not band:
                continue
            actual = allocation.get(asset_class, 0.0)
            lo = band.get("min_pct") or 0.0
            hi = band.get("max_pct") or 0.0
            if actual > hi:
                direction, breach = "above", actual - hi
            elif actual < lo:
                direction, breach = "below", lo - actual
            else:
                continue
            if breach < config.MANDATE_TOLERANCE_PCT:
                continue
            band_breaches.append(
                BandBreach(
                    portfolio_id=portfolio_id,
                    mandate_code=mandate["mandate_code"],
                    asset_class=asset_class,
                    actual_pct=actual,
                    min_pct=lo,
                    target_pct=band.get("target_pct") or 0.0,
                    max_pct=hi,
                    direction=direction,
                    breach_pp=breach,
                    value_base=total_base * actual / 100,
                    base_currency=base_ccy,
                )
            )

        limit = mandate.get("max_single_position_pct")
        excluded_terms = mandate.get("notes") or ""
        rows = book.holdings_by_portfolio_date.get((portfolio_id, snapshot), [])
        # Sum by instrument first: the same instrument can appear on more than
        # one row within a portfolio.
        by_instrument: dict[str, float] = {}
        for r in rows:
            by_instrument[r["instrument_id"]] = by_instrument.get(
                r["instrument_id"], 0.0
            ) + (r.get("market_value_base") or 0.0)

        for instrument_id, value in by_instrument.items():
            instrument = book.instrument(instrument_id)
            pct = value / total_base * 100 if total_base else 0.0

            if (
                limit
                and instrument.get("concentration_limit_applies") == "Y"
                and pct > limit + config.MANDATE_TOLERANCE_PCT
            ):
                position_breaches.append(
                    PositionBreach(
                        portfolio_id=portfolio_id,
                        mandate_code=mandate["mandate_code"],
                        instrument_id=instrument_id,
                        instrument_name=instrument.get("instrument_name", instrument_id),
                        actual_pct=pct,
                        limit_pct=limit,
                        breach_pp=pct - limit,
                        value_base=value,
                        base_currency=base_ccy,
                    )
                )

            if (
                "exclusion" in excluded_terms.lower()
                and instrument.get("sustainability_excluded") == "Y"
            ):
                exclusion_breaches.append(
                    ExclusionBreach(
                        portfolio_id=portfolio_id,
                        mandate_code=mandate["mandate_code"],
                        instrument_id=instrument_id,
                        instrument_name=instrument.get("instrument_name", instrument_id),
                        pct_of_portfolio=pct,
                        value_base=value,
                        base_currency=base_ccy,
                        service_model=pf.get("service_model", ""),
                        mandate_notes=excluded_terms,
                    )
                )

    band_breaches.sort(key=lambda b: -b.breach_pp)
    position_breaches.sort(key=lambda b: -b.breach_pp)
    exclusion_breaches.sort(key=lambda b: -b.pct_of_portfolio)

    return MandateReview(
        portfolio_id=portfolio_id,
        client_id=pf["client_id"],
        mandate_code=pf.get("mandate_code", ""),
        mandate_name=pf.get("mandate_name", ""),
        service_model=pf.get("service_model", ""),
        governed=governed,
        base_currency=base_ccy,
        total_base=total_base,
        allocation_pct=allocation,
        band_breaches=band_breaches,
        position_breaches=position_breaches,
        exclusion_breaches=exclusion_breaches,
    )


def review_client(
    book: DataBook, client_id: str, snapshot: str = config.AS_OF
) -> list[MandateReview]:
    return [
        review_portfolio(book, pf["portfolio_id"], snapshot)
        for pf in book.portfolios_by_client.get(client_id, [])
    ]


def waiver_notes(book: DataBook, client_id: str) -> list[dict[str, Any]]:
    """RM notes that read as a client instruction or a waiver on file.

    Matched on wording, so treat as a prompt to check the file -- not as proof
    that a waiver exists.
    """
    out: list[dict[str, Any]] = []
    for note in book.notes_by_client.get(client_id, []):
        text = note.get("note", "")
        if any(re.search(p, text, re.IGNORECASE) for p in _WAIVER_PATTERNS):
            out.append(note)
    return out


def waiver_evidence(notes: list[dict[str, Any]]) -> list[Evidence]:
    return [
        Evidence(
            source_file="rm_notes.json",
            row_or_id=n["note_id"],
            field="note",
            value=n["note"],
            snapshot_date=n.get("note_date"),
            note="RM note. Subjective, and not independently verified.",
        )
        for n in notes
    ]
