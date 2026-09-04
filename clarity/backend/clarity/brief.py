"""The meeting brief.

What Priscilla actually walks into the room with: why she is there, what she
should say first, what she must not say, what to ask, and a draft follow-up she
can edit.

Every line is assembled from computed facts and cited notes. Where a statement
comes from an RM note rather than the data it is marked as reported, because a
client's recollection and their holdings file disagree often enough that the
difference is usually the point of the meeting.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import config
from .contracts import Insight, MeetingBrief, Severity
from .signals.base import SignalContext
from .signals.explain import build_explanation

_GUARDRAILS = [
    "Do not present any figure as investment advice. These are options for review.",
    "Do not quote a tax outcome. Tax domicile drives the treatment and wealth "
    "planning owns the answer.",
    "Do not describe a private markets or unlisted mark as current without saying "
    "when it was struck.",
    "Do not present an RM note as an independently verified fact.",
    "Do not promise a redemption date for a gated vehicle.",
]


def _severity_rank(insight: Insight) -> int:
    order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    return order[insight.severity]


def build_brief(ctx: SignalContext, insights: list[Insight]) -> MeetingBrief:
    client = ctx.client
    live = [i for i in insights if i.status.value != "dismissed"]
    top = sorted(live, key=lambda i: (-i.priority_score,))[:4]
    explanation = build_explanation(ctx, "ytd")

    purpose_bits = [insight.headline for insight in top[:2]]
    purpose = (
        f"Review {client.get('client_name')}. " + ". Then: ".join(purpose_bits) + "."
        if purpose_bits
        else f"Routine review of {client.get('client_name')}."
    )

    talking_points = [
        explanation["narrative"][0],
        explanation["narrative"][1],
    ]
    for insight in top:
        talking_points.append(f"{insight.headline}. {insight.summary}")

    questions: list[str] = []
    for insight in top:
        questions.extend(insight.open_questions)
    objectives = client.get("objectives") or ""
    if objectives:
        questions.append(
            f"Are these still the objectives? Recorded as: {objectives}"
        )
    if client.get("life_stage"):
        questions.append(
            f"Has anything changed in the client's circumstances? Life stage on file "
            f"is \"{client.get('life_stage')}\"."
        )
    # Deduplicate, keep order.
    seen: set[str] = set()
    questions = [q for q in questions if not (q in seen or seen.add(q))][:8]

    relationship: list[str] = []
    for note in ctx.notes[-3:]:
        relationship.append(
            f"{note['note_date']} ({note['channel']}, {note['note_id']}): {note['note']}"
        )

    # A finding that merely *rests* on an RM note is not a contradiction. Only
    # cases where the client's stated position and the holdings file actually
    # disagree belong here.
    _CONFLICT_MARKERS = ("-contradiction-", "-samebet-", "-loss-aversion", "-riskprofile")
    contradictions: list[str] = []
    for insight in live:
        if any(marker in insight.id for marker in _CONFLICT_MARKERS):
            contradictions.append(f"{insight.headline}. {insight.summary}")
    for review in ctx.mandate_reviews:
        if review.exclusion_breaches and ctx.notes_matching("fully aligned", "not aware"):
            contradictions.append(
                "The client believes the sustainability policy is being applied; the "
                "holdings file shows excluded instruments inside the mandate."
            )
    for facility in ctx.facilities:
        if facility.cure_narrative and "market" in facility.cure_narrative:
            contradictions.append(
                f"{facility.facility_id} looks healthy today, but the previous breach "
                "was resolved by a market move rather than by an action."
            )
    seen = set()
    contradictions = [c for c in contradictions if not (c in seen or seen.add(c))][:5]

    do_not_say = list(_GUARDRAILS)
    stale = [i for i in live if i.id.endswith("-stale-marks")]
    if stale:
        do_not_say.append(
            "Do not quote the total wealth figure without the as-at caveat: "
            + stale[0].headline
        )
    reconciliation = [i for i in live if "-recon-" in i.id]
    if reconciliation:
        do_not_say.append(
            "Do not quote loan-to-value externally until operations confirm the drawn "
            "balance: " + reconciliation[0].headline
        )

    lead = top[0] if top else None
    follow_up = _draft_follow_up(ctx, explanation, lead)

    return MeetingBrief(
        client_id=ctx.client_id,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        as_of=config.AS_OF,
        purpose=purpose,
        talking_points=talking_points,
        questions_to_ask=questions,
        relationship_context=relationship,
        contradictions=contradictions,
        do_not_say=do_not_say,
        draft_follow_up=follow_up,
        provenance="deterministic",
    )


def _draft_follow_up(ctx: SignalContext, explanation: dict, lead: Insight | None) -> str:
    client = ctx.client
    # Naming order differs across this book, and an entity client has no given
    # name at all, so the full name is used rather than guessing at a first name.
    name = client.get("client_name") or "client"
    language = client.get("reporting_language", "English")

    lines = [
        f"Dear {name},",
        "",
        "Thank you for your time today. A short summary of what we discussed and "
        "what happens next.",
        "",
        f"Where the portfolio stands. {explanation['narrative'][0]} "
        f"{explanation['narrative'][1]}",
    ]
    if lead:
        lines += [
            "",
            f"What we focused on. {lead.headline}. {lead.summary}",
            "",
            f"What we agreed to look at. {lead.suggested_next_step}",
        ]
    lines += [
        "",
        "Nothing in this note is a recommendation to buy or sell. Any action will be "
        "confirmed with you in writing before it is taken, and the figures above are "
        f"as at {config.AS_OF}.",
        "",
        "Kind regards,",
        client.get("rm_name", "Relationship Manager"),
        client.get("rm_desk", ""),
    ]
    if language and language != "English":
        lines += [
            "",
            f"[Draft is in English. Client's reporting language is {language}; route "
            "through translation before sending.]",
        ]
    return "\n".join(lines)
