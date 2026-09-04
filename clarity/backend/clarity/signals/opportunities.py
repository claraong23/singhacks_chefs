"""Guarded event-linked conversation opportunities.

These signals identify a reason for an RM conversation.  They never select a
security, recommend a trade, or imply that a market event will persist.
"""

from __future__ import annotations

from typing import Iterable

from .. import config
from ..contracts import Category, Confidence, Evidence, Fact, Insight, Severity, SuitabilityCheck
from .base import SignalContext, priority, signal


OBJECTIVE_THEME_TERMS: dict[str, tuple[str, ...]] = {
    "energy_hormuz": ("energy", "inflation", "income"),
    "us_tech_ai": ("technology", "growth", "entrepreneur", "diversif"),
    "gold_monetary": ("preserv", "inflation", "defensive"),
    "duration": ("income", "capital preservation", "retirement"),
    "private_markets": ("private", "alternatives", "long-term growth"),
}


def _objective_matches(objectives: str, theme_key: str) -> bool:
    text = objectives.lower()
    return any(term in text for term in OBJECTIVE_THEME_TERMS.get(theme_key, ()))


@signal("guarded_event_opportunity")
def guarded_event_opportunity(ctx: SignalContext) -> Iterable[Insight]:
    objectives = str(ctx.client.get("objectives") or "")
    mandate_clear = not any(
        review.band_breaches or review.position_breaches or review.exclusion_breaches
        for review in ctx.mandate_reviews
        if review.governed
    )
    liquidity_clear = (
        ctx.liquidity.shortfall_usd <= 0
        and ctx.liquidity.withdrawable_usd >= ctx.liquidity.obligations_confirmed_usd
    )
    if not mandate_clear or not liquidity_clear:
        return

    for theme in ctx.theme_exposures:
        if not theme.event_ids or not _objective_matches(objectives, theme.key):
            continue
        # A discussion is only labelled as an opportunity where the household
        # is not already concentrated in that same theme.
        if theme.pct_of_household >= config.HOUSEHOLD_CONCENTRATION_WARN_PCT:
            continue
        event = max(
            (
                ctx.book.events_by_id[event_id]
                for event_id in theme.event_ids
                if event_id in ctx.book.events_by_id
            ),
            key=lambda row: row["event_date"],
            default=None,
        )
        if event is None:
            continue
        score, reasons = priority(
            Severity.LOW,
            materiality_pct=theme.pct_of_household,
            amount_usd=theme.attributed_usd,
        )
        reasons.append("Passed liquidity, mandate and concentration guardrails")
        yield Insight(
            id=f"{ctx.client_id}-opportunity-{theme.key}",
            client_id=ctx.client_id,
            category=Category.OPPORTUNITY,
            severity=Severity.LOW,
            headline=f"{theme.name} may be worth discussing",
            summary=(
                f"A dated market event connects to {theme.pct_of_household:.1f}% of "
                "household wealth and to a stated client objective. This is a prompt "
                "for an RM conversation, not a recommendation to buy or sell."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact("Current related exposure", f"USD {theme.attributed_usd:,.0f} ({theme.pct_of_household:.1f}%)", theme.attributed_usd, "USD"),
                Fact("Readily withdrawable", f"USD {ctx.liquidity.withdrawable_usd:,.0f}", ctx.liquidity.withdrawable_usd, "USD"),
            ],
            client_relevance=f"The client's stated objectives include: {objectives}",
            suggested_next_step=(
                "RM may ask whether the event changes the client's priorities or "
                "concerns; any action remains subject to a separate suitability review."
            ),
            evidence=theme.evidence() + [
                Evidence(
                    source_file="event_log.csv",
                    row_or_id=event["event_id"],
                    field="description",
                    value=event["description"],
                    snapshot_date=event["event_date"],
                    note=f"Transmission: {event['primary_transmission']}",
                ),
                Evidence(
                    source_file="clients.csv",
                    row_or_id=ctx.client_id,
                    field="objectives",
                    value=objectives,
                ),
            ],
            suitability_checks=[
                SuitabilityCheck("Adequate liquidity", "pass", "No current liquidity shortfall and confirmed needs are covered."),
                SuitabilityCheck("No active mandate conflict", "pass", "No governed portfolio currently has a measured mandate breach."),
                SuitabilityCheck("No existing theme concentration", "pass", f"Current exposure is below the {config.HOUSEHOLD_CONCENTRATION_WARN_PCT:.0f}% household warning threshold."),
                SuitabilityCheck("No product recommendation", "pass", "The signal proposes a conversation only."),
            ],
            confidence=Confidence.DERIVED,
            related_event_ids=[event["event_id"]],
            portfolio_ids=sorted({pid for leg in theme.legs for pid in leg.portfolio_ids}),
            instrument_ids=[leg.instrument_id for leg in theme.legs],
            amount_usd=theme.attributed_usd,
            open_questions=["Does this event change the client's priorities?", "Would any eventual option remain suitable after full review?"],
        )
