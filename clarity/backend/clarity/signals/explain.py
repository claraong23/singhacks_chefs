"""Explanation: turning a change in value into something an RM can say out loud.

The sentences here are assembled from computed numbers by ordinary Python, not
generated. Every clause is traceable to an attribution figure, a market series
or a row in ``event_log.csv``. An optional language model can rewrite the same
facts more fluently (see ``clarity.narrative``), but nothing downstream depends
on it and the default output is fully deterministic.
"""

from __future__ import annotations

from typing import Any, Iterable

from .. import config
from ..analytics.attribution import (
    NEW_POSITION_ASSUMPTION,
    THEME_MARKET_SERIES,
    contribution_evidence,
    market_evidence,
    market_moves,
)
from ..analytics.lookthrough import THEMES_BY_KEY
from ..contracts import (
    Category,
    Confidence,
    Evidence,
    Fact,
    Insight,
    Severity,
)
from .base import SignalContext, priority, signal


def _money(value: float) -> str:
    """Absolute amount. Use where the direction is already in the sentence."""
    return f"USD {abs(value):,.0f}"


def _signed(value: float) -> str:
    """Amount with its sign, for figures read out of a list."""
    return f"{'+' if value >= 0 else '-'}USD {abs(value):,.0f}"


def _clip(text: str, limit: int = 130) -> str:
    """Trim to a word boundary rather than mid-word."""
    text = text.strip()
    if len(text) <= limit:
        return text.rstrip(".")
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;") + "..."


def build_explanation(ctx: SignalContext, period: str = "ytd") -> dict[str, Any]:
    """A structured 'what changed and why' for one client and period."""
    result = ctx.ytd if period == "ytd" else ctx.recent
    direction = "up" if result.change_usd >= 0 else "down"

    themes = sorted(result.by_theme.items(), key=lambda kv: kv[1])
    drivers: list[dict[str, Any]] = []
    for key, amount in themes:
        if abs(amount) < max(50_000, abs(result.start_value_usd) * 0.002):
            continue
        theme = THEMES_BY_KEY.get(key)
        if theme is None:
            continue
        moves = market_moves(
            ctx.book, THEME_MARKET_SERIES.get(key, ()), result.start, result.end
        )
        events = [
            ctx.book.events_by_id[e]
            for e in theme.event_ids
            if e in ctx.book.events_by_id
            and result.start <= e_date(ctx, e) <= result.end
        ]
        drivers.append(
            {
                "theme_key": key,
                "theme_name": theme.name,
                "amount_usd": amount,
                "pct_of_start": result.pct_of_start(amount),
                "market_moves": moves,
                "events": [
                    {
                        "event_id": e["event_id"],
                        "event_date": e["event_date"],
                        "description": e["description"],
                        "primary_transmission": e["primary_transmission"],
                        "severity": e["severity"],
                    }
                    for e in events
                ],
            }
        )
    drivers.sort(key=lambda d: abs(d["amount_usd"]), reverse=True)

    sentences = [
        f"Between {result.start} and {result.end} the household moved {direction} "
        f"{_money(result.change_usd)}"
        + (
            f", or {abs(result.change_pct):.1f}%"
            if result.change_pct is not None
            else ""
        )
        + f", from {_money(result.start_value_usd)} to {_money(result.end_value_usd)}."
    ]
    sentences.append(
        f"Of that, {_signed(result.price_effect_usd)} came from market moves, "
        f"{_signed(result.fx_effect_usd)} from currency translation and "
        f"{_signed(result.flow_effect_usd)} from money paid in or taken out."
    )
    for driver in drivers[:3]:
        clause = f"{driver['theme_name']} contributed {_signed(driver['amount_usd'])}"
        if driver["pct_of_start"] is not None:
            clause += f" ({driver['pct_of_start']:+.1f} points)"
        if driver["market_moves"]:
            move = driver["market_moves"][0]
            clause += (
                f", as {move['series_name']} moved from {move['start_value']} to "
                f"{move['end_value']} {move['unit']}"
            )
        if driver["events"]:
            event = driver["events"][0]
            clause += (
                f". The event log records on {event['event_date']}: "
                f"{_clip(event['description'])}"
            )
        sentences.append(clause if clause.endswith("...") else clause + ".")

    # Where translation dominates, saying a theme "drove" the move would be
    # wrong: the underlying assets may not have moved at all.
    fx_dominates = abs(result.fx_effect_usd) > abs(result.price_effect_usd)
    if fx_dominates:
        primary_driver = "currency translation"
        base_ccy = ctx.client.get("base_currency")
        sentences.insert(
            2,
            f"Currency did more of the work than markets: reported in USD, the "
            f"translation effect of {_money(result.fx_effect_usd)} is larger than the "
            f"{_money(result.price_effect_usd)} of market movement. Measured in the "
            f"client's own {base_ccy} reporting currency, the picture is different.",
        )
    elif drivers:
        primary_driver = drivers[0]["theme_name"]
    else:
        primary_driver = "broad market moves"

    return {
        "client_id": ctx.client_id,
        "period": period,
        "primary_driver": primary_driver,
        "fx_dominates": fx_dominates,
        "start": result.start,
        "end": result.end,
        "start_label": config.SNAPSHOT_LABELS.get(result.start, result.start),
        "end_label": config.SNAPSHOT_LABELS.get(result.end, result.end),
        "change_usd": result.change_usd,
        "change_pct": result.change_pct,
        "price_effect_usd": result.price_effect_usd,
        "fx_effect_usd": result.fx_effect_usd,
        "flow_effect_usd": result.flow_effect_usd,
        "drivers": drivers,
        "detractors": [c.to_dict() for c in result.market_detractors[:5]],
        "contributors": [c.to_dict() for c in result.market_contributors[:5]],
        "narrative": sentences,
        "provenance": "deterministic",
    }


def e_date(ctx: SignalContext, event_id: str) -> str:
    return ctx.book.events_by_id.get(event_id, {}).get("event_date", "")


@signal("material_move")
def material_move(ctx: SignalContext) -> Iterable[Insight]:
    """Explain a move large enough that the client will ask about it."""
    result = ctx.ytd
    if result.change_pct is None:
        return

    biggest_theme = None
    if result.by_theme:
        biggest_theme = min(result.by_theme.items(), key=lambda kv: kv[1])
    theme_points = (
        result.pct_of_start(biggest_theme[1]) if biggest_theme else None
    )

    material = abs(result.change_pct) >= 5.0 or (
        theme_points is not None and theme_points <= -3.0
    )
    if not material:
        return

    severity = (
        Severity.HIGH
        if result.change_pct <= -8
        else Severity.MEDIUM
        if result.change_pct < 0
        else Severity.LOW
    )
    score, reasons = priority(
        severity,
        materiality_pct=abs(result.change_pct),
        amount_usd=abs(result.change_usd),
    )

    explanation = build_explanation(ctx, "ytd")
    facts = [
        Fact(
            "Household value",
            f"{_money(result.start_value_usd)} to {_money(result.end_value_usd)}",
            result.end_value_usd,
            "USD",
            "down" if result.change_usd < 0 else "up",
        ),
        Fact(
            "Change since year-end 2025",
            f"{'+' if result.change_usd >= 0 else '-'}{_money(result.change_usd)} "
            f"({result.change_pct:+.1f}%)",
            result.change_usd,
            "USD",
        ),
        Fact(
            "Market effect",
            f"{'+' if result.price_effect_usd >= 0 else '-'}{_money(result.price_effect_usd)}",
            result.price_effect_usd,
            "USD",
        ),
        Fact(
            "Currency effect",
            f"{'+' if result.fx_effect_usd >= 0 else '-'}{_money(result.fx_effect_usd)}",
            result.fx_effect_usd,
            "USD",
        ),
        Fact(
            "Money in and out",
            f"{'+' if result.flow_effect_usd >= 0 else '-'}{_money(result.flow_effect_usd)}",
            result.flow_effect_usd,
            "USD",
        ),
    ]
    for driver in explanation["drivers"][:3]:
        facts.append(
            Fact(
                driver["theme_name"],
                f"{'+' if driver['amount_usd'] >= 0 else '-'}{_money(driver['amount_usd'])}"
                + (
                    f" ({driver['pct_of_start']:+.1f} points)"
                    if driver["pct_of_start"] is not None
                    else ""
                ),
                driver["amount_usd"],
                "USD",
            )
        )
    for contribution in result.market_detractors[:3]:
        facts.append(
            Fact(
                contribution.instrument_name,
                f"{_money(contribution.price_effect_usd)} from the market move"
                + (
                    f", price {contribution.price_start} to {contribution.price_end}"
                    if contribution.price_start
                    else ""
                ),
                contribution.price_effect_usd,
                "USD",
                "down",
            )
        )

    all_events = [
        e
        for driver in explanation["drivers"][:3]
        for e in driver["events"]
    ]

    yield Insight(
        id=f"{ctx.client_id}-explain-ytd",
        client_id=ctx.client_id,
        category=Category.PERFORMANCE,
        severity=severity,
        headline=(
            f"Household {'down' if result.change_usd < 0 else 'up'} "
            f"{abs(result.change_pct):.1f}% year to date, driven by "
            + explanation["primary_driver"]
        ),
        summary=" ".join(explanation["narrative"]),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=facts,
        client_relevance=(
            "This is the answer to the first question the client will ask. Having the "
            "attribution and the event behind it means the answer does not depend on "
            "recalling what happened in March."
        ),
        suggested_next_step=(
            "Open the meeting with the attribution rather than the headline number."
        ),
        evidence=contribution_evidence(
            result.market_detractors, result.start, result.end
        )
        + [
            e
            for driver in explanation["drivers"][:3]
            for e in market_evidence(driver["market_moves"], result.start, result.end)
        ]
        + [
            Evidence(
                source_file="event_log.csv",
                row_or_id=e["event_id"],
                field="description",
                value=e["description"],
                snapshot_date=e["event_date"],
                note=f"Transmission: {e['primary_transmission']}. Severity {e['severity']}.",
            )
            for e in all_events[:5]
        ],
        assumptions=[NEW_POSITION_ASSUMPTION],
        confidence=Confidence.MEASURED,
        related_event_ids=[e["event_id"] for e in all_events],
        amount_usd=abs(result.change_usd),
    )
