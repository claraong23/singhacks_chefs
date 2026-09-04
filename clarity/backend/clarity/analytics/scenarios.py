"""Deterministic what-if calculations for event-linked portfolio exposure.

This module deliberately returns sensitivity estimates, not forecasts or trade
recommendations. Scenario assumptions are explicit so an RM can challenge them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .lookthrough import Exposure


@dataclass(frozen=True)
class Scenario:
    """One named market shock applied to a mapped theme."""

    key: str
    name: str
    theme_key: str
    shock_pct: float
    description: str


@dataclass(frozen=True)
class ScenarioImpact:
    scenario: Scenario
    theme: Exposure
    impact_usd: float
    impact_pct_of_household: float


# Initial scenarios use the existing event-linked Hormuz theme. These are
# screening sensitivities, not predictions of what the market will do.
DEFAULT_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        key="hormuz_reopens",
        name="Hormuz reopens",
        theme_key="energy_hormuz",
        shock_pct=-15.0,
        description="Energy and freight risk premium falls if the route reopens.",
    ),
    Scenario(
        key="hormuz_escalates",
        name="Hormuz escalation",
        theme_key="energy_hormuz",
        shock_pct=20.0,
        description="Energy and freight exposure rises if disruption worsens.",
    ),
    Scenario(
        key="technology_drawdown",
        name="Technology drawdown",
        theme_key="us_tech_ai",
        shock_pct=-15.0,
        description=(
            "Technology and AI-linked holdings decline under renewed concern about "
            "AI capital expenditure."
        ),
    ),
    Scenario(
        key="rates_remain_higher",
        name="Renewed rate pressure",
        theme_key="duration",
        shock_pct=-8.0,
        description=(
            "Rate-sensitive holdings decline if yields rise again and expected policy "
            "easing is delayed."
        ),
    ),
)


def apply_theme_shock(theme: Exposure, scenario: Scenario) -> ScenarioImpact:
    """Apply ``scenario.shock_pct`` to one mapped theme exposure."""
    impact = theme.attributed_usd * scenario.shock_pct / 100.0
    # Exposure.pct_of_household already uses the household's USD denominator.
    impact_pct = theme.pct_of_household * scenario.shock_pct / 100.0
    return ScenarioImpact(
        scenario=scenario,
        theme=theme,
        impact_usd=impact,
        impact_pct_of_household=impact_pct,
    )


def calculate_impacts(
    themes: list[Exposure],
    scenarios: tuple[Scenario, ...] = DEFAULT_SCENARIOS,
    minimum_theme_pct: float = 10.0,
) -> list[ScenarioImpact]:
    """Calculate scenarios for material themes only, largest impact first."""
    by_key = {theme.key: theme for theme in themes}
    impacts: list[ScenarioImpact] = []
    for scenario in scenarios:
        theme = by_key.get(scenario.theme_key)
        if theme is None or theme.pct_of_household < minimum_theme_pct:
            continue
        impacts.append(apply_theme_shock(theme, scenario))
    return sorted(impacts, key=lambda item: -abs(item.impact_usd))
