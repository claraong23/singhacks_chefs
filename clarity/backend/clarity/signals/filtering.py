"""Deterministic alert-quality filtering.

Filtering happens after every signal has run and before results are ranked. The
policy is intentionally conservative: high and critical findings are never
suppressed, and subjective RM notes can add context but cannot erase a measured
risk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from .. import config
from ..contracts import Category, Insight, Severity

if TYPE_CHECKING:
    from .base import SignalContext


_MATERIALITY_FILTER_CATEGORIES = {
    Category.CONCENTRATION,
    Category.CURRENCY,
    Category.LIQUIDITY,
    Category.OPPORTUNITY,
    Category.PERFORMANCE,
}

_CATEGORY_TERMS: dict[Category, tuple[str, ...]] = {
    Category.CONCENTRATION: ("concentration", "exposure", "position", "overweight"),
    Category.LIQUIDITY: ("liquidity", "cash", "commitment", "capital call", "funding"),
    Category.CURRENCY: ("currency", "fx", "dollar", "euro", "hkd", "sgd", "yen"),
    Category.MANDATE: ("mandate", "waiver", "band", "allocation", "client-directed"),
    Category.COLLATERAL: ("lombard", "facility", "ltv", "margin", "collateral", "leverage"),
}

_AWARENESS_TERMS = (
    "aware",
    "understands",
    "comfortable",
    "accepted",
    "accepts",
    "client-directed",
    "instructed",
    "waiver",
    "does not want to sell",
    "will not sell",
)


def _deduplicate(insights: Iterable[Insight]) -> list[Insight]:
    """Keep one insight per stable id, preferring the higher priority version."""
    by_id: dict[str, Insight] = {}
    for insight in insights:
        existing = by_id.get(insight.id)
        if existing is None or insight.priority_score > existing.priority_score:
            by_id[insight.id] = insight
    return list(by_id.values())


def _is_tiny_low_severity(ctx: SignalContext, insight: Insight) -> bool:
    """Return true only for quantified, tiny, low-importance market findings."""
    if insight.severity not in (Severity.LOW, Severity.INFO):
        return False
    if insight.category not in _MATERIALITY_FILTER_CATEGORIES:
        return False
    if insight.amount_usd is None or ctx.view.total_usd <= 0:
        return False
    materiality_pct = abs(insight.amount_usd) / ctx.view.total_usd * 100
    return materiality_pct < config.ALERT_MIN_MATERIALITY_PCT


def _matching_awareness_notes(ctx: SignalContext, insight: Insight) -> list[dict]:
    """Find notes that explicitly combine awareness language with the alert topic."""
    topic_terms = _CATEGORY_TERMS.get(insight.category, ())
    if not topic_terms:
        return []
    matches: list[dict] = []
    for note in ctx.notes:
        text = str(note.get("note") or "").lower()
        if not any(marker in text for marker in _AWARENESS_TERMS):
            continue
        if any(term in text for term in topic_terms):
            matches.append(note)
    return matches


def _annotate_known_context(ctx: SignalContext, insight: Insight) -> None:
    """Attach subjective awareness context without changing measured severity."""
    notes = _matching_awareness_notes(ctx, insight)
    if not notes:
        return
    latest = notes[-1]
    reason = (
        f"RM note {latest.get('note_id')} dated {latest.get('note_date')} may indicate "
        "the client already knows about this topic; severity is unchanged until confirmed"
    )
    if reason not in insight.priority_reasons:
        insight.priority_reasons.append(reason)
    question = "Does the earlier client acknowledgement still apply to the measured exposure today?"
    if question not in insight.open_questions:
        insight.open_questions.append(question)


def filter_insights(ctx: SignalContext, insights: Iterable[Insight]) -> list[Insight]:
    """Return the active, relevant insight set before final ranking.

    Dismissal state is intentionally not handled here. It belongs to ReviewStore,
    where the RM decision is retained in the audit trail.
    """
    filtered: list[Insight] = []
    for insight in _deduplicate(insights):
        if _is_tiny_low_severity(ctx, insight):
            continue
        _annotate_known_context(ctx, insight)
        filtered.append(insight)
    return filtered
