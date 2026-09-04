"""Look-through: what a client is actually exposed to.

``instruments.asset_class`` tells you what an instrument is called.
``instruments.underlying_reference`` tells you what it is exposed to. A client
can hold a bond, a share and a structured product that all reference the same
issuer and see three modest line items instead of one large bet.

The mapping below is curated rather than inferred by string similarity. With 62
instruments that is both feasible and preferable: every link cites the field it
was read from, so a reviewer can check it in the source file rather than trust a
matcher.

**Sizing convention for worst-of baskets.** A worst-of structure pays the
holder's downside on whichever basket member performs worst, so the holder is
economically exposed to the full notional of *each* member, not to a 1/n slice.
We therefore attribute 100% of notional to each named underlying and say so in
the assumption attached to every insight that uses it. This is the conservative
reading; a mark-to-market delta treatment would give a smaller number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..contracts import Assumption, Evidence
from ..loaders import DataBook
from .valuation import HouseholdView

# ---------------------------------------------------------------------------
# Issuer links
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IssuerLink:
    issuer_key: str
    issuer_name: str
    #: Fraction of the instrument's market value attributed to this issuer.
    weight: float
    #: The instruments.csv column the link was read from.
    basis_field: str
    basis_note: str


#: instrument_id -> issuer links. An instrument may reference several issuers.
ISSUER_LINKS: dict[str, tuple[IssuerLink, ...]] = {
    "SYN-ST-0106": (
        IssuerLink(
            "GOLDEN_HARBOUR",
            "Golden Harbour Properties Ltd",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-FI-0207": (
        IssuerLink(
            "GOLDEN_HARBOUR",
            "Golden Harbour Properties Ltd",
            1.0,
            "instrument_name",
            "Subordinated perpetual issued by the same company. Ranks below senior debt.",
        ),
    ),
    "SYN-SP-0503": (
        IssuerLink(
            "GOLDEN_HARBOUR",
            "Golden Harbour Properties Ltd",
            1.0,
            "underlying_reference",
            "Accumulator on the issuer's shares, with a double-up feature below strike.",
        ),
    ),
    "SYN-ST-0103": (
        IssuerLink(
            "HELIOS",
            "Helios Cloud Systems Inc",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-SP-0502": (
        IssuerLink(
            "HELIOS",
            "Helios Cloud Systems Inc",
            1.0,
            "underlying_reference",
            "Single-underlying equity linked note on the issuer.",
        ),
    ),
    "SYN-SP-0501": (
        IssuerLink(
            "HELIOS",
            "Helios Cloud Systems Inc",
            1.0,
            "underlying_reference",
            "Worst-of basket member. Full notional attributed by convention.",
        ),
        IssuerLink(
            "GLOBAL_ENERGY_MAJORS",
            "Global Energy Majors ADR",
            1.0,
            "underlying_reference",
            "Worst-of basket member. Full notional attributed by convention.",
        ),
        IssuerLink(
            "GULF_MARINE",
            "Gulf Marine Services",
            1.0,
            "underlying_reference",
            "Worst-of basket member. Not present elsewhere in the instrument universe.",
        ),
    ),
    "SYN-ST-0104": (
        IssuerLink(
            "PACIFIC_ORIENT",
            "Pacific Orient Shipping Ltd",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-SP-0505": (
        IssuerLink(
            "PACIFIC_ORIENT",
            "Pacific Orient Shipping Ltd",
            1.0,
            "underlying_reference",
            "Worst-of basket member. Full notional attributed by convention.",
        ),
        IssuerLink(
            "GLOBAL_ENERGY_MAJORS",
            "Global Energy Majors ADR",
            1.0,
            "underlying_reference",
            "Worst-of basket member. Full notional attributed by convention.",
        ),
        IssuerLink(
            "BARA_NUSANTARA",
            "Bara Nusantara Energy Tbk",
            1.0,
            "underlying_reference",
            "Worst-of basket member. Full notional attributed by convention.",
        ),
    ),
    "SYN-ST-0101": (
        IssuerLink(
            "BARA_NUSANTARA",
            "Bara Nusantara Energy Tbk",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-ST-0105": (
        IssuerLink(
            "SUNRISE_PALM",
            "Sunrise Palm Resources Ltd",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-ST-0107": (
        IssuerLink(
            "NORDVIND",
            "Nordvind Industrial AB",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-ST-0108": (
        IssuerLink(
            "KANTO_PHARMA",
            "Kanto Pharma Holdings KK",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-ST-0109": (
        IssuerLink(
            "VERDANT_HEALTH",
            "Verdant Health Group Ltd",
            1.0,
            "instrument_name",
            "Direct equity in the issuer.",
        ),
    ),
    "SYN-ST-0102": (
        IssuerLink(
            "MERIDIAN_SEMI",
            "Meridian Semiconductor Corp",
            1.0,
            "instrument_name",
            "Direct equity in the issuer. Unrelated to Meridian Private Equity Fund VII "
            "despite the shared word; the two are not aggregated.",
        ),
    ),
    "SYN-FI-0206": (
        IssuerLink(
            "PACIFIC_RIM_BANK",
            "Pacific Rim Bank",
            1.0,
            "instrument_name",
            "Subordinated perpetual issued by the bank.",
        ),
    ),
    "SYN-AL-0308": (
        IssuerLink(
            "ARANYA_TECH",
            "Aranya Technologies Pte Ltd",
            1.0,
            "underlying_reference",
            "Unlisted Series D preference shares, last priced September 2025.",
        ),
    ),
}

#: Instruments whose underlying constituents the dataset does not name. We can
#: see the exposure exists but not what it is; that limitation is reported
#: rather than guessed at.
UNRESOLVED_UNDERLYINGS: dict[str, str] = {
    "SYN-SP-0506": (
        "underlying_reference names 'three Asian banking majors' without identifying "
        "them, so the individual issuers behind this note cannot be verified from the "
        "dataset."
    ),
}

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    description: str
    #: instrument_id -> share of market value attributed to the theme.
    members: dict[str, float]
    event_ids: tuple[str, ...] = ()

    def weight_for(self, instrument_id: str) -> float:
        return self.members.get(instrument_id, 0.0)


THEMES: tuple[Theme, ...] = (
    Theme(
        key="energy_hormuz",
        name="Energy and the Strait of Hormuz",
        description=(
            "Instruments whose value moves with the oil complex, freight rates and the "
            "Gulf risk premium. The transmission channels are named in event_log.csv."
        ),
        members={
            "SYN-EQ-0008": 1.0,
            "SYN-CM-0403": 1.0,
            "SYN-ST-0101": 1.0,
            "SYN-ST-0104": 1.0,
            "SYN-EQ-0025": 1.0,
            "SYN-SP-0501": 1.0,
            "SYN-SP-0505": 1.0,
        },
        event_ids=("EVT-04", "EVT-05", "EVT-06", "EVT-07", "EVT-08", "EVT-10", "EVT-16"),
    ),
    Theme(
        key="us_tech_ai",
        name="US technology and AI capital expenditure",
        description=(
            "Exposure to the megacap technology complex, including single names and "
            "notes written on them."
        ),
        members={
            "SYN-EQ-0003": 1.0,
            "SYN-ST-0102": 1.0,
            "SYN-ST-0103": 1.0,
            "SYN-SP-0502": 1.0,
            "SYN-SP-0501": 1.0,
            "SYN-AL-0308": 1.0,
        },
        event_ids=("EVT-11",),
    ),
    Theme(
        key="gold_monetary",
        name="Gold and monetary debasement hedges",
        description="Physical gold, gold ETFs and notes referencing XAU spot.",
        members={"SYN-CM-0401": 1.0, "SYN-CM-0402": 1.0, "SYN-SP-0504": 1.0},
        event_ids=("EVT-01", "EVT-02", "EVT-03"),
    ),
    Theme(
        key="duration",
        name="Interest rate duration",
        description=(
            "Fixed income whose price is driven primarily by the level of yields "
            "rather than by credit. Perpetuals carry the longest effective duration."
        ),
        members={
            "SYN-FI-0201": 1.0,
            "SYN-FI-0211": 1.0,
            "SYN-FI-0203": 1.0,
            "SYN-FI-0209": 1.0,
            "SYN-FI-0210": 1.0,
            "SYN-FI-0212": 1.0,
            "SYN-FI-0206": 1.0,
            "SYN-FI-0207": 1.0,
        },
        event_ids=("EVT-09", "EVT-12", "EVT-13", "EVT-15"),
    ),
    Theme(
        key="hk_property",
        name="Hong Kong property",
        description=(
            "Hong Kong real estate exposure across every wrapper it appears in: "
            "direct property, listed equity, subordinated debt and equity derivatives."
        ),
        members={
            "SYN-ST-0106": 1.0,
            "SYN-FI-0207": 1.0,
            "SYN-SP-0503": 1.0,
            "SYN-AL-0307": 1.0,
        },
    ),
    Theme(
        key="private_markets",
        name="Private markets and gated vehicles",
        description=(
            "Positions that cannot be sold on demand: private funds, semi-liquid "
            "vehicles subject to gates, and direct real estate."
        ),
        members={
            "SYN-AL-0301": 1.0,
            "SYN-AL-0302": 1.0,
            "SYN-AL-0305": 1.0,
            "SYN-AL-0306": 1.0,
            "SYN-AL-0307": 1.0,
            "SYN-AL-0308": 1.0,
            "SYN-AL-0309": 1.0,
        },
        event_ids=("EVT-14",),
    ),
    Theme(
        key="healthcare",
        name="Healthcare and pharmaceuticals",
        description=(
            "Healthcare revenue exposure, including single employer or family "
            "business holdings in the sector."
        ),
        members={"SYN-EQ-0006": 1.0, "SYN-ST-0108": 1.0, "SYN-ST-0109": 1.0},
    ),
    Theme(
        key="greater_china_consumer",
        name="Greater China consumer demand",
        description=(
            "Revenue exposure to Greater China discretionary spending, including "
            "luxury distribution."
        ),
        members={"SYN-EQ-0010": 1.0, "SYN-EQ-0021": 1.0},
    ),
)

THEMES_BY_KEY: dict[str, Theme] = {t.key: t for t in THEMES}

WORST_OF_ASSUMPTION = Assumption(
    statement=(
        "Worst-of structured products are counted at 100% of notional against each "
        "named underlying rather than a 1/n share."
    ),
    basis=(
        "The holder bears the downside of whichever basket member performs worst, so "
        "notional exposure to each name is the conservative reading for a "
        "concentration check."
    ),
    impact_if_wrong=(
        "A delta-adjusted treatment would show a smaller figure. The direction of the "
        "finding does not change, only its size."
    ),
)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class ExposureLeg:
    """One instrument's contribution to an aggregated exposure."""

    instrument_id: str
    instrument_name: str
    wrapper: str
    market_value_usd: float
    attributed_usd: float
    basis_field: str
    basis_note: str
    portfolio_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "wrapper": self.wrapper,
            "market_value_usd": self.market_value_usd,
            "attributed_usd": self.attributed_usd,
            "basis_field": self.basis_field,
            "basis_note": self.basis_note,
            "portfolio_ids": list(self.portfolio_ids),
        }


@dataclass
class Exposure:
    """An aggregated exposure to one issuer or one theme."""

    key: str
    name: str
    kind: str  # "issuer" | "theme"
    attributed_usd: float
    pct_of_household: float
    legs: list[ExposureLeg]
    #: True when at least one leg is only visible through a look-through.
    hidden: bool
    event_ids: tuple[str, ...] = ()

    @property
    def direct_usd(self) -> float:
        return sum(
            leg.attributed_usd for leg in self.legs if leg.basis_field == "instrument_name"
        )

    @property
    def looked_through_usd(self) -> float:
        return self.attributed_usd - self.direct_usd

    def evidence(self) -> list[Evidence]:
        return [
            Evidence(
                source_file="instruments.csv",
                row_or_id=leg.instrument_id,
                field=leg.basis_field,
                value=leg.instrument_name
                if leg.basis_field == "instrument_name"
                else leg.basis_note,
                note=f"USD {leg.attributed_usd:,.0f} attributed via {leg.wrapper}.",
            )
            for leg in self.legs
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "kind": self.kind,
            "attributed_usd": self.attributed_usd,
            "pct_of_household": self.pct_of_household,
            "direct_usd": self.direct_usd,
            "looked_through_usd": self.looked_through_usd,
            "hidden": self.hidden,
            "legs": [leg.to_dict() for leg in self.legs],
            "event_ids": list(self.event_ids),
        }


def _wrapper_label(asset_class: str, sub_asset_class: str) -> str:
    if asset_class == "Structured Products":
        return sub_asset_class or "structured product"
    if asset_class == "Fixed Income":
        return sub_asset_class or "bond"
    if asset_class == "Alternatives":
        return sub_asset_class or "private holding"
    return sub_asset_class or asset_class.lower()


def issuer_exposures(view: HouseholdView) -> list[Exposure]:
    """Aggregate the household by underlying issuer, looking through wrappers."""
    grouped: dict[str, dict[str, Any]] = {}
    for position in view.positions:
        for link in ISSUER_LINKS.get(position.instrument_id, ()):
            entry = grouped.setdefault(
                link.issuer_key,
                {"name": link.issuer_name, "legs": [], "total": 0.0},
            )
            attributed = position.market_value_usd * link.weight
            entry["total"] += attributed
            entry["legs"].append(
                ExposureLeg(
                    instrument_id=position.instrument_id,
                    instrument_name=position.instrument_name,
                    wrapper=_wrapper_label(
                        position.asset_class, position.sub_asset_class
                    ),
                    market_value_usd=position.market_value_usd,
                    attributed_usd=attributed,
                    basis_field=link.basis_field,
                    basis_note=link.basis_note,
                    portfolio_ids=position.portfolio_ids,
                )
            )

    exposures = [
        Exposure(
            key=key,
            name=entry["name"],
            kind="issuer",
            attributed_usd=entry["total"],
            pct_of_household=view.weight(entry["total"]),
            legs=sorted(entry["legs"], key=lambda l: -l.attributed_usd),
            hidden=any(leg.basis_field != "instrument_name" for leg in entry["legs"])
            and len(entry["legs"]) > 1,
        )
        for key, entry in grouped.items()
    ]
    exposures.sort(key=lambda e: -e.attributed_usd)
    return exposures


def theme_exposures(view: HouseholdView) -> list[Exposure]:
    """Aggregate the household by market theme, so events map to holdings."""
    exposures: list[Exposure] = []
    for theme in THEMES:
        legs: list[ExposureLeg] = []
        total = 0.0
        for position in view.positions:
            weight = theme.weight_for(position.instrument_id)
            if not weight:
                continue
            attributed = position.market_value_usd * weight
            total += attributed
            legs.append(
                ExposureLeg(
                    instrument_id=position.instrument_id,
                    instrument_name=position.instrument_name,
                    wrapper=_wrapper_label(
                        position.asset_class, position.sub_asset_class
                    ),
                    market_value_usd=position.market_value_usd,
                    attributed_usd=attributed,
                    basis_field="asset_class"
                    if position.asset_class != "Structured Products"
                    else "underlying_reference",
                    basis_note=theme.description,
                    portfolio_ids=position.portfolio_ids,
                )
            )
        if not legs:
            continue
        exposures.append(
            Exposure(
                key=theme.key,
                name=theme.name,
                kind="theme",
                attributed_usd=total,
                pct_of_household=view.weight(total),
                legs=sorted(legs, key=lambda l: -l.attributed_usd),
                hidden=any(
                    leg.basis_field == "underlying_reference" for leg in legs
                ),
                event_ids=theme.event_ids,
            )
        )
    exposures.sort(key=lambda e: -e.attributed_usd)
    return exposures


def unresolved_notes(view: HouseholdView) -> list[str]:
    """Honest disclosure of what the dataset does not let us verify."""
    return [
        UNRESOLVED_UNDERLYINGS[p.instrument_id]
        for p in view.positions
        if p.instrument_id in UNRESOLVED_UNDERLYINGS
    ]


def events_for_themes(
    book: DataBook, exposures: Iterable[Exposure]
) -> list[dict[str, Any]]:
    """The event_log rows behind a set of themed exposures, newest first."""
    ids: list[str] = []
    for exposure in exposures:
        for event_id in exposure.event_ids:
            if event_id not in ids:
                ids.append(event_id)
    events = [book.events_by_id[i] for i in ids if i in book.events_by_id]
    events.sort(key=lambda e: e["event_date"], reverse=True)
    return events
