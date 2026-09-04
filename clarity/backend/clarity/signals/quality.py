"""Data-quality signals.

The dataset contains a small number of artefacts of the kind present in any
bank's production systems. Working around them silently would be the wrong
answer: an RM who quotes a stale mark to a client has a problem the model
created. These checks surface the artefact, size it, and say what it does to the
rest of the analysis.
"""

from __future__ import annotations

from typing import Iterable

from .. import config
from ..contracts import (
    Category,
    Confidence,
    Evidence,
    Fact,
    Insight,
    Severity,
)
from ..loaders import days_between
from .base import SignalContext, priority, signal


@signal("stale_valuation")
def stale_valuation(ctx: SignalContext) -> Iterable[Insight]:
    """Positions carried at a mark older than the snapshot they appear in."""
    stale: list[tuple[dict, int]] = []
    for h in ctx.book.holdings_by_client_date.get((ctx.client_id, ctx.snapshot), []):
        valuation_date = h.get("valuation_date")
        if not valuation_date or valuation_date == h.get("snapshot_date"):
            continue
        lag = days_between(valuation_date, h["snapshot_date"]) or 0
        if lag > 45:
            stale.append((h, lag))
    if not stale:
        return

    total = sum(h.get("market_value_usd") or 0.0 for h, _ in stale)
    pct = ctx.view.weight(total)
    worst_lag = max(lag for _, lag in stale)

    severity = Severity.HIGH if pct >= 15 else Severity.MEDIUM
    score, reasons = priority(severity, materiality_pct=pct, amount_usd=total)

    yield Insight(
        id=f"{ctx.client_id}-stale-marks",
        client_id=ctx.client_id,
        category=Category.DATA_QUALITY,
        severity=severity,
        headline=(
            f"USD {total:,.0f} ({pct:.0f}% of the household) is carried at a mark "
            f"up to {worst_lag} days old"
        ),
        summary=(
            "These positions have a valuation_date earlier than the snapshot they "
            "appear in. Quarterly-reported private marks lagging a quarter is normal "
            "and not an error, but the reported wealth figure is only as current as "
            "its oldest input, and any percentage of the household computed against it "
            "inherits the lag."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact(
                h.get("instrument_name", ""),
                f"USD {h.get('market_value_usd'):,.0f}, valued {h.get('valuation_date')} "
                f"for a {h.get('snapshot_date')} snapshot ({lag} days)",
                h.get("market_value_usd"),
                "USD",
            )
            for h, lag in stale
        ],
        client_relevance=(
            "Worth saying out loud before quoting a total wealth figure, particularly "
            "where the stale position is large enough to move the percentage weights."
        ),
        suggested_next_step=(
            "Ask the custodian or manager for the latest available mark before the "
            "meeting, and present the total with the as-at date attached."
        ),
        evidence=[
            Evidence(
                source_file="holdings.csv",
                row_or_id=h["instrument_id"],
                field="valuation_date",
                value=h.get("valuation_date"),
                snapshot_date=h.get("snapshot_date"),
                note=f"{h.get('instrument_name')}: {lag} days behind the snapshot.",
            )
            for h, lag in stale
        ],
        confidence=Confidence.MEASURED,
        instrument_ids=[h["instrument_id"] for h, _ in stale],
        amount_usd=total,
        open_questions=["What is the most recent available valuation for this position?"],
    )


@signal("facility_reconciliation")
def facility_reconciliation(ctx: SignalContext) -> Iterable[Insight]:
    """Movements in a drawn balance that the transaction ledger does not explain."""
    for facility in ctx.facilities:
        gaps = [
            r
            for r in facility.drawn_reconciliation
            if abs(r["unexplained"]) > 1000
        ]
        if not gaps:
            continue

        worst = max(gaps, key=lambda r: abs(r["unexplained"]))
        score, reasons = priority(Severity.MEDIUM, materiality_pct=None)

        yield Insight(
            id=f"{ctx.client_id}-recon-{facility.facility_id}",
            client_id=ctx.client_id,
            category=Category.DATA_QUALITY,
            severity=Severity.MEDIUM,
            headline=(
                f"{facility.currency} {abs(worst['unexplained']):,.0f} of drawdown on "
                f"{facility.facility_id} is not explained by the transaction ledger"
            ),
            summary=(
                f"Between {worst['from_snapshot']} and {worst['to_snapshot']} the "
                f"drawn balance moved by {facility.currency} "
                f"{worst['drawn_change']:,.0f}, while transactions.csv records "
                f"{facility.currency} {worst['explained_by_transactions']:,.0f} of "
                "facility activity in the same window. The difference is reported "
                "rather than reconciled away, because the loan-to-value figures depend "
                "on the drawn balance being right."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact(
                    f"{r['from_snapshot']} to {r['to_snapshot']}",
                    f"drawn {r['drawn_change']:+,.0f}, transactions "
                    f"{r['explained_by_transactions']:+,.0f}, gap "
                    f"{r['unexplained']:+,.0f} {facility.currency}",
                    r["unexplained"],
                    facility.currency,
                )
                for r in gaps
            ],
            client_relevance=(
                "Not a client conversation. It is a note for the file and a question "
                "for operations before the numbers are used externally."
            ),
            suggested_next_step=(
                "Confirm the drawdown history with operations before quoting "
                "loan-to-value to the client or to credit risk."
            ),
            evidence=[
                Evidence(
                    source_file="credit_facilities.csv",
                    row_or_id=facility.facility_id,
                    field=f"drawn_{worst['to_snapshot']}",
                    value=worst["drawn_change"],
                    snapshot_date=worst["to_snapshot"],
                    note="Change in drawn balance over the period.",
                )
            ]
            + [
                Evidence(
                    source_file="transactions.csv",
                    row_or_id=tid,
                    field="amount",
                    value=worst["explained_by_transactions"],
                    note="Facility activity recorded in the same window.",
                )
                for tid in worst["transaction_ids"]
            ],
            confidence=Confidence.MEASURED,
            portfolio_ids=[facility.portfolio_id],
        )


@signal("note_contradicts_data")
def note_contradicts_data(ctx: SignalContext) -> Iterable[Insight]:
    """Where a client's stated position and the holdings file disagree.

    Only checks that can be settled with arithmetic are made. A percentage the
    client quoted in a note is compared with the same percentage computed from
    holdings; nothing is inferred from tone.
    """
    import re

    findings: list[dict] = []
    for note in ctx.notes:
        text = note.get("note") or ""
        for match in re.finditer(r"(\d{1,2})%\s+(hedge|position|allocation)", text, re.I):
            claimed = float(match.group(1))
            # Match the claim to a theme mentioned in the same sentence.
            sentence = text[max(0, match.start() - 160) : match.end() + 60].lower()
            for exposure in ctx.theme_exposures:
                first_word = exposure.name.split()[0].lower()
                if first_word not in sentence:
                    continue
                if exposure.pct_of_household <= claimed * 1.5:
                    continue
                findings.append(
                    {
                        "note": note,
                        "claimed_pct": claimed,
                        "actual_pct": exposure.pct_of_household,
                        "exposure": exposure,
                        "quote": match.group(0),
                    }
                )
                break

    for finding in findings:
        exposure = finding["exposure"]
        score, reasons = priority(
            Severity.MEDIUM,
            materiality_pct=exposure.pct_of_household - finding["claimed_pct"],
            amount_usd=exposure.attributed_usd,
        )
        yield Insight(
            id=f"{ctx.client_id}-contradiction-{exposure.key}",
            client_id=ctx.client_id,
            category=Category.SUITABILITY,
            severity=Severity.MEDIUM,
            headline=(
                f"Client describes a {finding['claimed_pct']:.0f}% position; it is now "
                f"{exposure.pct_of_household:.0f}%"
            ),
            summary=(
                f"Note {finding['note']['note_id']} of "
                f"{finding['note']['note_date']} records the client's own sizing as "
                f"\"{finding['quote']}\". Measured across the household today, "
                f"{exposure.name} is USD {exposure.attributed_usd:,.0f}, or "
                f"{exposure.pct_of_household:.1f}%. The position has grown rather than "
                "been added to, which is a different conversation."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact("Client's stated sizing", f"{finding['claimed_pct']:.0f}%", finding["claimed_pct"], "%"),
                Fact(
                    "Measured today",
                    f"{exposure.pct_of_household:.1f}% "
                    f"(USD {exposure.attributed_usd:,.0f})",
                    exposure.pct_of_household,
                    "%",
                ),
            ]
            + [
                Fact(
                    leg.instrument_name,
                    f"USD {leg.attributed_usd:,.0f}",
                    leg.attributed_usd,
                    "USD",
                )
                for leg in exposure.legs
            ],
            client_relevance=(
                "The client has not changed their mind; the market changed the size of "
                "the position for them. Framing it that way keeps the conversation "
                "about rebalancing rather than about being wrong."
            ),
            suggested_next_step=(
                "Show the drift from the original sizing and ask whether the original "
                "intent still stands."
            ),
            evidence=[
                Evidence(
                    source_file="rm_notes.json",
                    row_or_id=finding["note"]["note_id"],
                    field="note",
                    value=finding["note"]["note"],
                    snapshot_date=finding["note"]["note_date"],
                    note="RM note. Client statement, not independently verified.",
                )
            ]
            + exposure.evidence(),
            confidence=Confidence.REPORTED,
            instrument_ids=[leg.instrument_id for leg in exposure.legs],
            amount_usd=exposure.attributed_usd,
        )


@signal("loader_warnings")
def loader_warnings(ctx: SignalContext) -> Iterable[Insight]:
    """Referential integrity problems found while loading, if any touch this client."""
    if not ctx.book.warnings:
        return
    relevant = [w for w in ctx.book.warnings if ctx.client_id in w]
    if not relevant:
        return
    score, reasons = priority(Severity.LOW, materiality_pct=None)
    yield Insight(
        id=f"{ctx.client_id}-loader-warnings",
        client_id=ctx.client_id,
        category=Category.DATA_QUALITY,
        severity=Severity.LOW,
        headline=f"{len(relevant)} referential integrity warning(s) on load",
        summary="; ".join(relevant[:5]),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[Fact("Warning", w) for w in relevant[:5]],
        client_relevance="Affects completeness of the figures shown for this client.",
        suggested_next_step="Check the source extract before relying on the totals.",
        evidence=[],
        confidence=Confidence.MEASURED,
    )
