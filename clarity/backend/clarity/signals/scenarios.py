"""Event-linked scenario signals for RM review."""

from __future__ import annotations

from typing import Iterable

from .. import config
from ..analytics.scenarios import calculate_impacts
from ..contracts import (
    Category,
    Confidence,
    Evidence,
    Fact,
    Insight,
    Severity,
    SuitabilityCheck,
)
from .base import SignalContext, priority, signal


@signal("event_scenario_sensitivity")
def event_scenario_sensitivity(ctx: SignalContext) -> Iterable[Insight]:
    """Surface material sensitivity to explicit event-linked market shocks."""
    for impact in calculate_impacts(ctx.theme_exposures):
        theme = impact.theme
        shock = impact.scenario.shock_pct
        severity = (
            Severity.HIGH if abs(theme.pct_of_household) >= 25 else Severity.MEDIUM
        )
        score, reasons = priority(
            severity,
            materiality_pct=abs(impact.impact_pct_of_household),
            amount_usd=abs(impact.impact_usd),
        )
        events = [
            ctx.book.events_by_id[event_id]
            for event_id in theme.event_ids
            if event_id in ctx.book.events_by_id
        ]

        yield Insight(
            id=f"{ctx.client_id}-scenario-{impact.scenario.key}",
            client_id=ctx.client_id,
            category=Category.OPPORTUNITY,
            severity=severity,
            headline=(
                f"{impact.scenario.name}: {theme.name} sensitivity is "
                f"{abs(impact.impact_pct_of_household):.1f}% of household wealth"
            ),
            summary=(
                f"A {shock:+.0f}% move in the {theme.name} theme would imply an "
                f"estimated {impact.impact_usd:+,.0f} USD change for this household. "
                "This is a sensitivity estimate under an explicit assumption, not a "
                "forecast or recommendation."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact(
                    "Current theme exposure",
                    f"USD {theme.attributed_usd:,.0f} ({theme.pct_of_household:.1f}%)",
                    theme.attributed_usd,
                    "USD",
                ),
                Fact("Scenario shock", f"{shock:+.1f}%", shock, "%"),
                Fact(
                    "Estimated household impact",
                    f"USD {impact.impact_usd:+,.0f} ({impact.impact_pct_of_household:+.1f}%)",
                    impact.impact_usd,
                    "USD",
                ),
            ],
            client_relevance=(
                f"The client's holdings share a common driver: {theme.name}. "
                "The result shows how sensitive the household is if that driver changes."
            ),
            suggested_next_step=(
                "RM to discuss whether this sensitivity is understood and intentional, "
                "then record the client's view before considering any action."
            ),
            evidence=theme.evidence()
            + [
                Evidence(
                    source_file="event_log.csv",
                    row_or_id=event["event_id"],
                    field="description",
                    value=event["description"],
                    snapshot_date=event["event_date"],
                    note=f"Transmission: {event['primary_transmission']}",
                )
                for event in events[:4]
            ],
            assumptions=[
                config.SCENARIO_SHOCK_ASSUMPTION,
            ],
            suitability_checks=[
                SuitabilityCheck(
                    check="Scenario is reviewed as a sensitivity, not a forecast",
                    result="attention",
                    detail=(
                        "The RM must decide whether the stated shock is useful for "
                        "this client conversation."
                    ),
                    reference="analytics/scenarios.py",
                )
            ],
            confidence=Confidence.DERIVED,
            related_event_ids=list(theme.event_ids),
            portfolio_ids=sorted(
                {portfolio_id for leg in theme.legs for portfolio_id in leg.portfolio_ids}
            ),
            instrument_ids=[leg.instrument_id for leg in theme.legs],
            amount_usd=abs(impact.impact_usd),
            open_questions=[
                "Would a different shock size be more appropriate for this client?",
                "Are all mapped instruments expected to move by the same percentage?",
            ],
        )
