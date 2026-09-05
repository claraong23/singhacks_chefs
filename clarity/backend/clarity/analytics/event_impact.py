"""Book-wide event-to-client exposure screening.

The event log is authoritative.  This module does not ask an LLM which clients
are affected: it follows the curated event -> theme -> instrument links in
``lookthrough.py`` and applies an explicit scenario shock only when one exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import Severity
from ..loaders import DataBook
from ..signals.base import priority
from .lookthrough import THEMES, Exposure, theme_exposures
from .scenarios import DEFAULT_SCENARIOS, Scenario, apply_theme_shock
from .valuation import household_view


_EVENT_SEVERITY: dict[str, Severity] = {
    "severe": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}


@dataclass(frozen=True)
class EventClientImpact:
    client_id: str
    client_name: str
    theme_key: str
    theme_name: str
    exposure_usd: float
    exposure_pct: float
    estimated_impact_usd: float | None
    estimated_impact_pct: float | None
    scenario_name: str | None
    shock_pct: float | None
    priority_score: float
    priority_reasons: tuple[str, ...]
    instrument_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "theme_key": self.theme_key,
            "theme_name": self.theme_name,
            "exposure_usd": self.exposure_usd,
            "exposure_pct": self.exposure_pct,
            "estimated_impact_usd": self.estimated_impact_usd,
            "estimated_impact_pct": self.estimated_impact_pct,
            "scenario_name": self.scenario_name,
            "shock_pct": self.shock_pct,
            "priority_score": round(self.priority_score, 1),
            "priority_reasons": list(self.priority_reasons),
            "instrument_ids": list(self.instrument_ids),
        }


def _scenario_for_theme(theme_key: str) -> Scenario | None:
    """Choose one downside scenario, if the theme has an explicit assumption."""
    candidates = [
        scenario
        for scenario in DEFAULT_SCENARIOS
        if scenario.theme_key == theme_key and scenario.shock_pct < 0
    ]
    return candidates[0] if candidates else None


def _themes_for_event(event_id: str) -> list[str]:
    return [theme.key for theme in THEMES if event_id in theme.event_ids]


def _client_impact(
    book: DataBook,
    event: dict[str, Any],
    client_id: str,
    theme: Exposure,
) -> EventClientImpact:
    severity = _EVENT_SEVERITY.get(
        str(event.get("severity") or "").lower(), Severity.MEDIUM
    )
    scenario = _scenario_for_theme(theme.key)
    impact = apply_theme_shock(theme, scenario) if scenario else None
    amount = abs(impact.impact_usd) if impact else theme.attributed_usd
    materiality = (
        abs(impact.impact_pct_of_household) if impact else theme.pct_of_household
    )
    score, reasons = priority(
        severity, materiality_pct=materiality, amount_usd=amount, days_until=0
    )
    if scenario is None:
        reasons.append("Exposure measured; no shock assumption is configured")
    return EventClientImpact(
        client_id=client_id,
        client_name=str(book.client(client_id).get("client_name") or client_id),
        theme_key=theme.key,
        theme_name=theme.name,
        exposure_usd=theme.attributed_usd,
        exposure_pct=theme.pct_of_household,
        estimated_impact_usd=impact.impact_usd if impact else None,
        estimated_impact_pct=impact.impact_pct_of_household if impact else None,
        scenario_name=scenario.name if scenario else None,
        shock_pct=scenario.shock_pct if scenario else None,
        priority_score=score,
        priority_reasons=tuple(reasons),
        instrument_ids=tuple(leg.instrument_id for leg in theme.legs),
    )


def event_impact_view(book: DataBook, event_id: str) -> dict[str, Any]:
    """Return the ranked clients whose current holdings map to one event."""
    if event_id not in book.events_by_id:
        raise KeyError(f"Unknown event {event_id}")
    event = book.events_by_id[event_id]
    theme_keys = set(_themes_for_event(event_id))
    impacts: list[EventClientImpact] = []
    for client_id in book.clients:
        view = household_view(book, client_id)
        for theme in theme_exposures(view):
            if theme.key in theme_keys and theme.attributed_usd > 0:
                impacts.append(_client_impact(book, event, client_id, theme))
    impacts.sort(key=lambda item: (-item.priority_score, -item.exposure_usd))
    scenario_comparisons = []
    for scenario in DEFAULT_SCENARIOS:
        if scenario.theme_key not in theme_keys:
            continue
        affected = []
        for item in impacts:
            if item.theme_key != scenario.theme_key:
                continue
            affected.append(
                {
                    "client_id": item.client_id,
                    "client_name": item.client_name,
                    "exposure_usd": item.exposure_usd,
                    "exposure_pct": item.exposure_pct,
                    "estimated_impact_usd": item.exposure_usd * scenario.shock_pct / 100.0,
                    "estimated_impact_pct": item.exposure_pct * scenario.shock_pct / 100.0,
                }
            )
        scenario_comparisons.append(
            {
                "key": scenario.key,
                "name": scenario.name,
                "theme_key": scenario.theme_key,
                "shock_pct": scenario.shock_pct,
                "description": scenario.description,
                "affected_clients": affected,
            }
        )
    return {
        "event": {
            "event_id": event["event_id"],
            "event_date": event["event_date"],
            "event_type": event["event_type"],
            "region": event["region"],
            "description": event["description"],
            "primary_transmission": event["primary_transmission"],
            "severity": event["severity"],
        },
        "themes": [
            {"key": theme.key, "name": theme.name, "description": theme.description}
            for theme in THEMES
            if theme.key in theme_keys
        ],
        "affected_clients": [item.to_dict() for item in impacts],
        "scenario_comparisons": scenario_comparisons,
        "method": (
            "event_log.csv event -> curated theme -> current household holdings; "
            "estimated impact appears only where an explicit scenario shock exists"
        ),
        "limitations": [
            "The mapping is curated from the synthetic repository data, not inferred by AI.",
            "Estimated impacts are linear sensitivities, not forecasts.",
            "No product or trade recommendation is produced.",
        ],
    }
