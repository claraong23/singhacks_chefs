"""Governance signals: mandate bands, position limits, exclusions, suitability.

The distinction that matters throughout this file is between a breach that
*drifted* and a breach the client *asked for*. They look identical in the
holdings file and lead to completely different conversations, so where an RM
note records an instruction or a waiver it is attached to the finding -- clearly
marked as reported rather than verified.
"""

from __future__ import annotations

from typing import Iterable

from .. import config
from ..analytics.mandate import waiver_evidence
from ..contracts import (
    Assumption,
    Category,
    Confidence,
    Evidence,
    Fact,
    Insight,
    Severity,
    SuitabilityCheck,
)
from ..loaders import days_between
from .base import SignalContext, priority, signal

#: Where the client's own words sit relative to what they hold.
_RISK_ORDER = {
    "Conservative": 1,
    "Income": 2,
    "Sustainable Balanced": 3,
    "Balanced": 3,
    "Balanced Growth": 4,
    "Growth": 5,
    "Dynamic Opportunistic": 6,
}

#: Asset classes we treat as risk assets when testing a profile mismatch.
_RISK_ASSETS = ("Equity", "Alternatives", "Structured Products", "Commodities")


@signal("mandate_bands")
def mandate_bands(ctx: SignalContext) -> Iterable[Insight]:
    """Portfolios sitting outside their strategic asset allocation bands."""
    for review in ctx.mandate_reviews:
        if not review.band_breaches:
            continue
        pf = ctx.book.portfolios[review.portfolio_id]
        worst = review.band_breaches[0]
        total_breach = sum(b.breach_pp for b in review.band_breaches)
        severity = (
            Severity.CRITICAL
            if worst.breach_pp >= 20
            else Severity.HIGH
            if worst.breach_pp >= 8
            else Severity.MEDIUM
        )
        waivers = ctx.waiver_notes
        score, reasons = priority(
            severity,
            materiality_pct=ctx.view.weight(
                ctx.view.by_portfolio.get(review.portfolio_id, 0.0)
            ),
            amount_usd=ctx.view.by_portfolio.get(review.portfolio_id),
        )
        if waivers:
            reasons.append("An RM note may record a client instruction; check the file")

        facts = [
            Fact(
                b.asset_class,
                f"{b.actual_pct:.1f}% vs band {b.min_pct:.0f}-{b.max_pct:.0f}% "
                f"(target {b.target_pct:.0f}%), {b.breach_pp:.1f}pp {b.direction}",
                b.actual_pct,
                "%",
                "up" if b.direction == "above" else "down",
            )
            for b in review.band_breaches
        ]

        yield Insight(
            id=f"{ctx.client_id}-bands-{review.portfolio_id}",
            client_id=ctx.client_id,
            category=Category.MANDATE,
            severity=severity,
            headline=(
                f"{pf.get('portfolio_name')} sits outside "
                f"{len(review.band_breaches)} of its {review.mandate_name} bands"
            ),
            summary=(
                f"The largest gap is {worst.asset_class} at {worst.actual_pct:.1f}% "
                f"against a {worst.min_pct:.0f}-{worst.max_pct:.0f}% band, "
                f"{worst.breach_pp:.1f} percentage points {worst.direction} the limit. "
                f"Across all asset classes the portfolio is {total_breach:.1f} "
                f"percentage points away from its permitted ranges."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=facts,
            client_relevance=(
                f"This is a {review.service_model.lower()} portfolio. "
                + (
                    "The bank selected these positions, so the breach is the bank's to explain."
                    if review.service_model == "Discretionary"
                    else "Positions are client-directed, so the fix needs the client's agreement."
                )
            ),
            suggested_next_step=(
                "Agree a dated correction plan, or record a documented decision to "
                "stay outside the band."
            ),
            evidence=[
                Evidence(
                    source_file="mandates.csv",
                    row_or_id=f"{b.mandate_code}/{b.asset_class}",
                    field="min_pct/max_pct",
                    value=f"{b.min_pct}-{b.max_pct}",
                    note=f"Actual {b.actual_pct:.1f}% at {ctx.snapshot}.",
                )
                for b in review.band_breaches
            ]
            + [
                Evidence(
                    source_file="portfolios.csv",
                    row_or_id=review.portfolio_id,
                    field="service_model",
                    value=review.service_model,
                )
            ]
            + waiver_evidence(waivers)[:1],
            assumptions=[
                Assumption(
                    statement=(
                        "Weights are measured within the portfolio in its base "
                        "currency, as the mandate is written."
                    ),
                    basis="mandates.csv bands apply per portfolio, not per household.",
                )
            ],
            suitability_checks=[
                SuitabilityCheck(
                    check="Breach is drift or client-directed",
                    result="attention" if waivers else "not_assessed",
                    detail=(
                        f"Note {waivers[-1]['note_id']} of {waivers[-1]['note_date']} "
                        "reads as a client instruction or a waiver. Confirm the signed "
                        "record before treating the breach as authorised."
                        if waivers
                        else "No RM note in the file reads as an instruction or waiver "
                        "for this portfolio, so the breach is treated as drift."
                    ),
                    reference="rm_notes.json",
                )
            ],
            confidence=Confidence.MEASURED,
            portfolio_ids=[review.portfolio_id],
        )


@signal("single_position_limit")
def single_position_limit(ctx: SignalContext) -> Iterable[Insight]:
    """Positions above the mandate's single-position ceiling.

    The limit is written for single-name and single-asset exposures, so
    ``concentration_limit_applies`` gates the test. A diversified fund at 20% is
    not a breach of a 12% single-position limit.
    """
    for review in ctx.mandate_reviews:
        if not review.position_breaches:
            continue
        pf = ctx.book.portfolios[review.portfolio_id]
        worst = review.position_breaches[0]
        severity = Severity.HIGH if worst.breach_pp >= 5 else Severity.MEDIUM
        score, reasons = priority(
            severity,
            materiality_pct=ctx.view.weight(
                sum(
                    ctx.book.to_usd(b.value_base, b.base_currency, ctx.snapshot) or 0.0
                    for b in review.position_breaches
                )
            ),
        )

        yield Insight(
            id=f"{ctx.client_id}-poslimit-{review.portfolio_id}",
            client_id=ctx.client_id,
            category=Category.MANDATE,
            severity=severity,
            headline=(
                f"{len(review.position_breaches)} position(s) above the "
                f"{worst.limit_pct:.0f}% single-position limit"
            ),
            summary=(
                f"{worst.instrument_name} is {worst.actual_pct:.1f}% of "
                f"{pf.get('portfolio_name')} against a {worst.limit_pct:.0f}% ceiling. "
                "The limit applies to single-name and single-asset exposures; "
                "diversified funds and sovereign bonds are excluded from the test."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact(
                    b.instrument_name,
                    f"{b.actual_pct:.1f}% vs {b.limit_pct:.0f}% limit "
                    f"({b.base_currency} {b.value_base:,.0f})",
                    b.actual_pct,
                    "%",
                )
                for b in review.position_breaches
            ],
            client_relevance=(
                "Single-position limits exist to cap the damage one issuer can do. "
                "Where several breaches share an underlying driver, the effective "
                "concentration is larger than any one line suggests."
            ),
            suggested_next_step=(
                "Rank the breaches by how correlated they are with each other before "
                "deciding which to reduce first."
            ),
            evidence=[
                Evidence(
                    source_file="mandates.csv",
                    row_or_id=review.mandate_code,
                    field="max_single_position_pct",
                    value=worst.limit_pct,
                )
            ]
            + [
                Evidence(
                    source_file="instruments.csv",
                    row_or_id=b.instrument_id,
                    field="concentration_limit_applies",
                    value="Y",
                    note=f"{b.instrument_name} at {b.actual_pct:.1f}%.",
                )
                for b in review.position_breaches
            ],
            confidence=Confidence.MEASURED,
            portfolio_ids=[review.portfolio_id],
            instrument_ids=[b.instrument_id for b in review.position_breaches],
        )


@signal("sustainability_exclusions")
def sustainability_exclusions(ctx: SignalContext) -> Iterable[Insight]:
    """Holdings that the mandate's binding exclusions forbid."""
    for review in ctx.mandate_reviews:
        if not review.exclusion_breaches:
            continue
        total_pct = sum(b.pct_of_portfolio for b in review.exclusion_breaches)
        discretionary = review.service_model == "Discretionary"
        severity = Severity.CRITICAL if discretionary else Severity.HIGH
        score, reasons = priority(
            severity,
            materiality_pct=ctx.view.weight(
                sum(
                    ctx.book.to_usd(b.value_base, b.base_currency, ctx.snapshot) or 0.0
                    for b in review.exclusion_breaches
                )
            ),
        )
        if discretionary:
            reasons.append("Discretionary mandate: the bank selected the positions")

        awareness_notes = ctx.notes_matching("sustainab", "not aware", "policy")

        yield Insight(
            id=f"{ctx.client_id}-exclusions-{review.portfolio_id}",
            client_id=ctx.client_id,
            category=Category.MANDATE,
            severity=severity,
            headline=(
                f"{total_pct:.0f}% of a mandate with binding exclusions is invested "
                f"in excluded instruments"
            ),
            summary=(
                f"{review.mandate_name} carries binding exclusions, and "
                f"{len(review.exclusion_breaches)} holding(s) are flagged "
                f"sustainability_excluded in the instrument master. "
                + (
                    "The portfolio is discretionary, so these were selected by the "
                    "bank under a mandate that forbids them."
                    if discretionary
                    else "The portfolio is advisory, so the positions are client-directed."
                )
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact(
                    b.instrument_name,
                    f"{b.pct_of_portfolio:.1f}% "
                    f"({b.base_currency} {b.value_base:,.0f})",
                    b.pct_of_portfolio,
                    "%",
                )
                for b in review.exclusion_breaches
            ]
            + [Fact("Mandate exclusions", review.exclusion_breaches[0].mandate_notes)],
            client_relevance=(
                "A sustainability policy the client believes is being applied, and is "
                "not, is a trust problem before it is a portfolio problem."
                if awareness_notes
                else "The exclusions are contractual, not preferences."
            ),
            suggested_next_step=(
                "Confirm the exclusion list with compliance, then agree an exit path "
                "and a date for each position with the client."
            ),
            evidence=[
                Evidence(
                    source_file="instruments.csv",
                    row_or_id=b.instrument_id,
                    field="sustainability_excluded",
                    value="Y",
                    note=b.instrument_name,
                )
                for b in review.exclusion_breaches
            ]
            + [
                Evidence(
                    source_file="mandates.csv",
                    row_or_id=review.mandate_code,
                    field="mandate_notes",
                    value=review.exclusion_breaches[0].mandate_notes,
                ),
                Evidence(
                    source_file="portfolios.csv",
                    row_or_id=review.portfolio_id,
                    field="service_model",
                    value=review.service_model,
                ),
            ]
            + [
                Evidence(
                    source_file="rm_notes.json",
                    row_or_id=n["note_id"],
                    field="note",
                    value=n["note"],
                    snapshot_date=n["note_date"],
                    note="RM note. Client statement, not independently verified.",
                )
                for n in awareness_notes[-1:]
            ],
            confidence=Confidence.MEASURED,
            portfolio_ids=[review.portfolio_id],
            instrument_ids=[b.instrument_id for b in review.exclusion_breaches],
        )


@signal("risk_profile_mismatch")
def risk_profile_mismatch(ctx: SignalContext) -> Iterable[Insight]:
    """What the client holds against what they said they wanted."""
    profile = ctx.client.get("risk_profile", "")
    tolerance = ctx.client.get("risk_tolerance_score") or 5
    risk_asset_usd = sum(
        ctx.view.by_asset_class.get(ac, 0.0) for ac in _RISK_ASSETS
    )
    risk_pct = ctx.view.weight(risk_asset_usd)

    #: Rough ceilings implied by the profile, taken from the mandate bands for
    #: the matching strategy rather than invented.
    implied_ceiling = {1: 45, 2: 45, 3: 55, 4: 65, 5: 75, 6: 80, 7: 88, 8: 93, 9: 100, 10: 100}
    ceiling = implied_ceiling.get(int(tolerance), 75)
    if risk_pct <= ceiling + 5:
        return

    gap = risk_pct - ceiling
    severity = Severity.CRITICAL if gap >= 20 else Severity.HIGH
    score, reasons = priority(severity, materiality_pct=min(100.0, gap * 2))
    reasons.append(
        f"Risk assets {risk_pct:.0f}% against about {ceiling}% implied by a "
        f"tolerance score of {tolerance:.0f}/10"
    )

    quotes = ctx.notes_matching(
        "never taken a risk", "does not understand", "safe", "conservative", "boring"
    )

    yield Insight(
        id=f"{ctx.client_id}-riskprofile",
        client_id=ctx.client_id,
        category=Category.SUITABILITY,
        severity=severity,
        headline=(
            f"Portfolio holds {risk_pct:.0f}% risk assets against a "
            f"{profile} profile"
        ),
        summary=(
            f"Equity, alternatives, structured products and commodities total "
            f"USD {risk_asset_usd:,.0f}, {risk_pct:.1f}% of household wealth. The "
            f"client is profiled {profile} with a risk tolerance of {tolerance:.0f}/10 "
            f"and an investment horizon of "
            f"{ctx.client.get('investment_horizon_years')} years."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact(
                asset_class,
                f"{ctx.view.asset_class_pct(asset_class):.1f}% "
                f"(USD {ctx.view.by_asset_class.get(asset_class, 0.0):,.0f})",
                ctx.view.asset_class_pct(asset_class),
                "%",
            )
            for asset_class in config.ASSET_CLASSES
            if ctx.view.by_asset_class.get(asset_class)
        ]
        + [
            Fact("Recorded risk profile", profile),
            Fact("Risk tolerance", f"{tolerance:.0f}/10", tolerance),
            Fact("Life stage", ctx.client.get("life_stage", "")),
        ],
        client_relevance=(
            "Where a portfolio was inherited or transferred in, the allocation "
            "reflects the previous owner's decisions rather than this client's."
            if "inherit" in (ctx.client.get("source_of_wealth") or "").lower()
            else "The allocation is the starting point for any suitability discussion."
        ),
        suggested_next_step=(
            "Agree a target allocation and a staged path to it, rather than presenting "
            "a single large rebalancing decision."
        ),
        evidence=[
            Evidence(
                source_file="clients.csv",
                row_or_id=ctx.client_id,
                field="risk_profile",
                value=profile,
            ),
            Evidence(
                source_file="clients.csv",
                row_or_id=ctx.client_id,
                field="risk_tolerance_score",
                value=tolerance,
            ),
        ]
        + [
            Evidence(
                source_file="rm_notes.json",
                row_or_id=n["note_id"],
                field="note",
                value=n["note"],
                snapshot_date=n["note_date"],
                note="RM note. Client's own words, not independently verified.",
            )
            for n in quotes[-2:]
        ],
        assumptions=[
            Assumption(
                statement=(
                    "The risk-asset ceiling implied by a tolerance score is a "
                    "reference band, not a bank policy limit."
                ),
                basis="Derived from the mandate bands for the matching strategy.",
                impact_if_wrong=(
                    "The mandate band check is the contractual test; this signal adds "
                    "the client's own framing to it."
                ),
            )
        ],
        suitability_checks=[
            SuitabilityCheck(
                check="Allocation consistent with recorded profile",
                result="fail",
                detail=f"{risk_pct:.1f}% risk assets against a {profile} profile.",
                reference="clients.csv, holdings.csv",
            )
        ],
        confidence=Confidence.DERIVED,
        amount_usd=risk_asset_usd,
    )


@signal("kyc_overdue")
def kyc_overdue(ctx: SignalContext) -> Iterable[Insight]:
    """A KYC review that has passed its date, in the same list as everything else."""
    due = ctx.client.get("kyc_review_due")
    days = days_between(config.AS_OF, due) if due else None
    if days is None or days > 30:
        return

    overdue = days < 0
    severity = Severity.MEDIUM if overdue else Severity.LOW
    score, reasons = priority(severity, materiality_pct=0.0, days_until=days)

    yield Insight(
        id=f"{ctx.client_id}-kyc",
        client_id=ctx.client_id,
        category=Category.ADMIN,
        severity=severity,
        headline=(
            f"KYC review {'overdue by' if overdue else 'due in'} {abs(days)} days"
        ),
        summary=(
            f"clients.kyc_review_due is {due} against a dataset date of {config.AS_OF}. "
            "Worth clearing in the same meeting rather than as a separate contact."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact("Review due", due),
            Fact("Days", f"{days}", days),
        ],
        client_relevance="Administrative, but it blocks other actions if it lapses.",
        suggested_next_step="Fold the review into the next scheduled meeting.",
        evidence=[
            Evidence(
                source_file="clients.csv",
                row_or_id=ctx.client_id,
                field="kyc_review_due",
                value=due,
            )
        ],
        confidence=Confidence.MEASURED,
    )
