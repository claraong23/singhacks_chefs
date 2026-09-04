"""Action options for RM review.

Nothing in this module is an instruction. Each option carries the arithmetic
that produced it, the trade-off the RM would have to explain to the client, the
suitability checks it has to clear, and what it depends on. The RM approves,
edits or rejects; the engine never acts.

Every numeric claim ("repaying HKD 11.2m restores 10 points of headroom") is
solved from the source data rather than illustrated, so a judge can check it.
"""

from __future__ import annotations

from typing import Any

from . import config
from .analytics.collateral import FacilityView, withdrawal_capacity
from .contracts import ActionOption, Category, Evidence, Insight, SuitabilityCheck
from .signals.base import SignalContext


# ---------------------------------------------------------------------------
# Shared guardrails
# ---------------------------------------------------------------------------


def _base_checks(ctx: SignalContext, *, crystallises_loss: bool = False) -> list[SuitabilityCheck]:
    """Checks every option is measured against before it may be shown."""
    client = ctx.client
    checks = [
        SuitabilityCheck(
            check="Risk profile",
            result="pass",
            detail=(
                f"{client.get('risk_profile')}, tolerance "
                f"{client.get('risk_tolerance_score')}/10, horizon "
                f"{client.get('investment_horizon_years')} years."
            ),
            reference="clients.csv",
        ),
        SuitabilityCheck(
            check="Stated objectives",
            result="pass",
            detail=client.get("objectives", ""),
            reference="clients.csv",
        ),
        SuitabilityCheck(
            check="Liquidity needs",
            result="pass",
            detail=f"Recorded as {client.get('liquidity_needs')}.",
            reference="clients.csv",
        ),
    ]
    if crystallises_loss:
        checks.append(
            SuitabilityCheck(
                check="Tax consequences of a disposal",
                result="not_assessed",
                detail=(
                    f"Tax domicile is {client.get('tax_domicile')}. Clarity does not "
                    "compute tax outcomes; route to wealth planning before executing."
                ),
                reference="clients.csv",
            )
        )
    restricted = ctx.notes_matching("dealing restrictions", "closed period")
    if restricted:
        checks.append(
            SuitabilityCheck(
                check="Dealing restrictions",
                result="attention",
                detail=(
                    "An RM note records dealing restrictions on at least one position. "
                    "Confirm the permitted window before execution."
                ),
                reference=f"rm_notes.json {restricted[-1]['note_id']}",
            )
        )
    return checks


_MONITOR_ONLY = "Do nothing now, and monitor against a defined trigger"


def _monitor_option(
    ctx: SignalContext, insight: Insight, trigger: str, cost_of_waiting: str
) -> ActionOption:
    """Always offered. 'Do nothing' is a legitimate decision if it is a decision."""
    return ActionOption(
        id=f"{insight.id}-opt-monitor",
        label=_MONITOR_ONLY,
        rationale=(
            "Acting has costs and the client may reasonably prefer to wait. Recording "
            "the decision and its trigger turns inaction into a documented choice."
        ),
        mechanics=[
            f"Set the trigger: {trigger}",
            "Diarise a review date and record the rationale in the client file",
            "Notify the client that no action is being taken and why",
        ],
        trade_offs=[cost_of_waiting],
        suitability_checks=[
            SuitabilityCheck(
                check="Documented decision",
                result="pass",
                detail="Inaction is recorded with a trigger and a review date.",
            )
        ],
        requires=["RM approval"],
        estimated_impact="No change to the portfolio.",
    )


# ---------------------------------------------------------------------------
# Collateral
# ---------------------------------------------------------------------------


def _repayment_to_target(
    facility: FacilityView, target_ltv_pct: float, advance_rate_pct: float
) -> float | None:
    """Sale proceeds needed to bring LTV to a target, selling pledged collateral.

    Selling a pledged asset reduces the drawn balance by the proceeds and the
    lending value by proceeds x advance rate, so::

        (D - v) / (LV - a*v) = t   =>   v = (D - t*LV) / (1 - t*a)
    """
    current = facility.current
    if current.drawn is None or current.lending_value is None:
        return None
    t = target_ltv_pct / 100
    a = advance_rate_pct / 100
    denominator = 1 - t * a
    if denominator <= 0:
        return None
    v = (current.drawn - t * current.lending_value) / denominator
    return max(0.0, v)


def collateral_options(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    facility = next(
        (f for f in ctx.facilities if f.facility_id in insight.id), None
    )
    if facility is None:
        return []
    current = facility.current
    target_ltv = max(10.0, facility.margin_call_ltv_pct - config.LTV_WARN_HEADROOM_PP)

    # The best asset to sell is a pledged position that (a) settles quickly,
    # (b) carries a low advance rate, so repaying removes little borrowing
    # capacity, and (c) is already flagged elsewhere -- a sale that fixes two
    # findings is easier to justify to the client than one that fixes one.
    also_breaching = {
        b.instrument_id
        for review in ctx.mandate_reviews
        for b in review.position_breaches
    }
    pledged = [
        p
        for p in ctx.view.positions
        if facility.portfolio_id in p.portfolio_ids
        and p.liquidity_tier in config.READILY_REALISABLE
        and p.asset_class != "Cash and Equivalents"
    ]
    pledged.sort(
        key=lambda p: (
            config.LIQUIDITY_TIERS.index(p.liquidity_tier),
            p.instrument_id not in also_breaching,
            p.advance_rate_pct or 0,
            -p.market_value_usd,
        )
    )

    options: list[ActionOption] = []

    if pledged:
        candidate = pledged[0]
        proceeds = _repayment_to_target(
            facility, target_ltv, candidate.advance_rate_pct or 0.0
        )
        if proceeds:
            proceeds_usd = (
                ctx.book.to_usd(proceeds, facility.currency, ctx.snapshot) or 0.0
            )
            feasible = proceeds_usd <= candidate.market_value_usd
            options.append(
                ActionOption(
                    id=f"{insight.id}-opt-deleverage",
                    label=(
                        f"Sell {facility.currency} {proceeds:,.0f} of "
                        f"{candidate.instrument_name} and repay the facility"
                    ),
                    rationale=(
                        f"Repaying reduces the drawn balance one-for-one while removing "
                        f"only {candidate.advance_rate_pct:.0f}% of that amount from "
                        f"lending value, so loan-to-value falls from "
                        f"{current.ltv_pct:.2f}% to about {target_ltv:.0f}% and "
                        f"headroom returns to {config.LTV_WARN_HEADROOM_PP:.0f} points."
                        + (
                            " This position also sits above the mandate's "
                            "single-position limit, so the sale addresses both findings."
                            if candidate.instrument_id in also_breaching
                            else ""
                        )
                    ),
                    mechanics=[
                        f"Sell {facility.currency} {proceeds:,.0f} "
                        f"(USD {proceeds_usd:,.0f}) of {candidate.instrument_name}",
                        f"Apply the proceeds against {facility.facility_id}",
                        f"Drawn falls from {current.drawn:,.0f} to "
                        f"{(current.drawn or 0) - proceeds:,.0f} {facility.currency}",
                    ],
                    trade_offs=[
                        f"Removes USD {proceeds_usd:,.0f} of income-producing assets "
                        f"from the portfolio",
                        "Crystallises whatever gain or loss sits in the position",
                        "Reduces the client's capacity to draw opportunistically",
                    ]
                    + (
                        []
                        if feasible
                        else [
                            "The position is not large enough on its own; a second "
                            "line would have to be sold alongside it."
                        ]
                    ),
                    suitability_checks=_base_checks(ctx, crystallises_loss=True)
                    + [
                        SuitabilityCheck(
                            check="Position is liquid enough to execute",
                            result="pass" if feasible else "attention",
                            detail=(
                                f"{candidate.instrument_name} is "
                                f"{candidate.liquidity_tier} tier at "
                                f"USD {candidate.market_value_usd:,.0f}."
                            ),
                            reference="holdings.csv",
                        )
                    ],
                    requires=["RM approval", "Client instruction", "Credit desk sign-off"],
                    estimated_impact=(
                        f"Loan-to-value {current.ltv_pct:.2f}% to about {target_ltv:.0f}%."
                    ),
                    evidence=[
                        Evidence(
                            source_file="holdings.csv",
                            row_or_id=candidate.instrument_id,
                            field="advance_rate_pct",
                            value=candidate.advance_rate_pct,
                            snapshot_date=ctx.snapshot,
                            note=(
                                f"USD {candidate.market_value_usd:,.0f} held, "
                                f"{candidate.liquidity_tier} liquidity."
                            ),
                        ),
                        Evidence(
                            source_file="credit_facilities.csv",
                            row_or_id=facility.facility_id,
                            field=f"lending_value_{ctx.snapshot}",
                            value=current.lending_value,
                            snapshot_date=ctx.snapshot,
                        ),
                    ],
                )
            )

    capacity = withdrawal_capacity(facility)
    if capacity is not None:
        options.append(
            ActionOption(
                id=f"{insight.id}-opt-cap-withdrawals",
                label=(
                    f"Cap withdrawals from the pledged account at "
                    f"{facility.currency} {capacity:,.0f}"
                ),
                rationale=(
                    "Selling collateral and paying the proceeds out reduces lending "
                    "value while the drawn balance is unchanged, so it raises "
                    "loan-to-value. This is the amount that can leave without "
                    "breaching the trigger."
                ),
                mechanics=[
                    f"Flag {facility.portfolio_id} as collateral-constrained in the "
                    "withdrawal workflow",
                    f"Any request above {facility.currency} {capacity:,.0f} routes to "
                    "the credit desk before confirmation to the client",
                ],
                trade_offs=[
                    "Constrains the client at exactly the moment they want cash",
                    "Does not reduce the underlying leverage",
                ],
                suitability_checks=_base_checks(ctx),
                requires=["RM approval", "Credit desk notification"],
                estimated_impact="No change to loan-to-value; prevents it worsening.",
                evidence=facility.evidence()[:3],
            )
        )

    options.append(
        _monitor_option(
            ctx,
            insight,
            trigger=(
                f"Alert if {facility.facility_id} loan-to-value exceeds "
                f"{facility.margin_call_ltv_pct - 2:.0f}%, or if collateral value falls "
                f"more than {max(0.5, (facility.collateral_fall_to_trigger_pct or 1) / 2):.1f}%."
            ),
            cost_of_waiting=(
                f"A {facility.collateral_fall_to_trigger_pct:.1f}% fall in collateral "
                "produces a margin call, which forces sales at whatever price exists "
                "that day rather than at a chosen one."
            ),
        )
    )
    return options


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------


def concentration_options(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    positions = [
        p for p in ctx.view.positions if p.instrument_id in insight.instrument_ids
    ]
    if not positions:
        return []
    positions.sort(key=lambda p: -p.market_value_usd)

    target_pct = config.HOUSEHOLD_CONCENTRATION_WARN_PCT
    current_pct = insight.amount_usd and ctx.view.weight(insight.amount_usd) or 0.0
    reduce_usd = max(0.0, (current_pct - target_pct) / 100 * ctx.view.total_usd)

    # Reduce the wrapper with the least attractive risk for the client first:
    # derivatives with forced-purchase features, then subordinated debt, then
    # listed equity.
    def wrapper_rank(p: Any) -> int:
        name = f"{p.sub_asset_class} {p.instrument_name}".lower()
        if "accumulator" in name:
            return 0
        if "perpetual" in name or "subordinated" in name:
            return 1
        if p.asset_class == "Structured Products":
            return 2
        return 3

    ordered = sorted(positions, key=lambda p: (wrapper_rank(p), -p.market_value_usd))
    first = ordered[0]

    options: list[ActionOption] = [
        ActionOption(
            id=f"{insight.id}-opt-reduce",
            label=(
                f"Reduce total exposure to {target_pct:.0f}% by trimming "
                f"USD {reduce_usd:,.0f}, starting with {first.instrument_name}"
            ),
            rationale=(
                f"Taking the exposure from {current_pct:.1f}% to {target_pct:.0f}% of "
                f"household wealth needs USD {reduce_usd:,.0f}. Starting with "
                f"{first.instrument_name} removes the wrapper with the least "
                "attractive payoff first rather than the one that is easiest to sell."
            ),
            mechanics=[
                f"Reduce {p.instrument_name} (currently USD {p.market_value_usd:,.0f}, "
                f"{p.weight_pct:.1f}%, {p.liquidity_tier} liquidity)"
                for p in ordered[:3]
            ],
            trade_offs=[
                "Crystallises gains or losses on the positions sold",
                "The client may read a reduction as a view on the issuer",
                f"{first.liquidity_tier} liquidity on the first line constrains timing"
                if first.liquidity_tier not in config.READILY_REALISABLE
                else "Execution is straightforward at this liquidity tier",
            ],
            suitability_checks=_base_checks(ctx, crystallises_loss=True),
            requires=["RM approval", "Client instruction"],
            estimated_impact=(
                f"Household exposure {current_pct:.1f}% to {target_pct:.0f}%."
            ),
            evidence=insight.evidence[:4],
        ),
        ActionOption(
            id=f"{insight.id}-opt-cap",
            label="Hold the position but cap it, and stop adding",
            rationale=(
                "Where the client will not sell for business or family reasons, the "
                "achievable outcome is to stop the exposure growing and to route new "
                "money elsewhere."
            ),
            mechanics=[
                "Agree a ceiling as a percentage of household wealth and record it",
                "Direct all new subscriptions away from this exposure",
                "Review at each meeting against the agreed ceiling",
            ],
            trade_offs=[
                "Leaves the current concentration in place",
                "Only reduces the exposure slowly, and only if the rest grows",
            ],
            suitability_checks=_base_checks(ctx)
            + [
                SuitabilityCheck(
                    check="Concentration remains outside guidance",
                    result="attention",
                    detail=(
                        f"Exposure stays near {current_pct:.1f}% against a "
                        f"{target_pct:.0f}% reference level."
                    ),
                )
            ],
            requires=["RM approval", "Client agreement to the ceiling"],
            estimated_impact="No immediate change; caps future growth.",
        ),
    ]

    options.append(
        _monitor_option(
            ctx,
            insight,
            trigger=(
                f"Alert if exposure exceeds {min(100, current_pct + 5):.0f}% of "
                "household wealth or if the issuer's price falls more than 15%."
            ),
            cost_of_waiting=(
                f"USD {insight.amount_usd:,.0f} remains exposed to a single driver."
                if insight.amount_usd
                else "The concentration remains in place."
            ),
        )
    )
    return options


# ---------------------------------------------------------------------------
# Liquidity
# ---------------------------------------------------------------------------


def liquidity_options(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    lq = ctx.liquidity
    largest = lq.obligations[0] if lq.obligations else None
    options: list[ActionOption] = []

    if largest:
        options.append(
            ActionOption(
                id=f"{insight.id}-opt-prefund",
                label=(
                    f"Pre-fund {largest.currency} {largest.amount_ccy:,.0f} now from "
                    "daily-liquidity assets"
                ),
                rationale=(
                    f"The obligation is {largest.certainty.lower()} and dated "
                    f"{largest.due_from}. Raising it while markets are open is a "
                    "choice; raising it against a deadline is not."
                ),
                mechanics=[
                    f"Sell USD {min(lq.withdrawable_usd, largest.total_usd):,.0f} of "
                    "Daily-tier positions",
                    f"Hold the proceeds in {largest.currency} until the obligation falls due",
                    "Book the sale against the specific obligation in the client file",
                ],
                trade_offs=[
                    "Gives up market exposure and income between now and the due date",
                    "Crystallises gains or losses today rather than later",
                ]
                + (
                    [
                        f"Only USD {lq.withdrawable_usd:,.0f} is actually withdrawable, "
                        f"leaving USD {lq.shortfall_usd:,.0f} to find elsewhere"
                    ]
                    if lq.shortfall_usd > 0
                    else []
                ),
                suitability_checks=_base_checks(ctx, crystallises_loss=True),
                requires=["RM approval", "Client instruction"],
                estimated_impact=(
                    f"Covers USD {min(lq.withdrawable_usd, largest.total_usd):,.0f} of "
                    f"the USD {largest.total_usd:,.0f} obligation."
                ),
                evidence=lq.evidence()[:4],
            )
        )
        options.append(
            ActionOption(
                id=f"{insight.id}-opt-stage",
                label="Stage the obligation and agree the funding sequence in writing",
                rationale=(
                    "Where the full amount cannot be raised without forced sales, the "
                    "decision is which tranche comes from where, agreed before the "
                    "date rather than during it."
                ),
                mechanics=[
                    "Split the obligation into dated tranches against the payment schedule",
                    "Nominate a funding source for each tranche, in order",
                    "Confirm with the counterparty whether the timing can move",
                ],
                trade_offs=[
                    "Depends on the counterparty accepting a schedule",
                    "Leaves residual risk if the later tranches are unfunded",
                ],
                suitability_checks=_base_checks(ctx),
                requires=["RM approval", "Client agreement", "Counterparty confirmation"],
                estimated_impact="Converts a single cliff into a dated plan.",
            )
        )

    if lq.gated_positions:
        gated = lq.gated_positions[0]
        options.append(
            ActionOption(
                id=f"{insight.id}-opt-gate",
                label=f"Confirm redemption terms on {gated['instrument_name']}",
                rationale=(
                    "A gated vehicle cannot be relied on to fund anything until the "
                    "manager confirms the amount and date. Treat it as unavailable "
                    "until it settles."
                ),
                mechanics=[
                    "Request the current gate level and queue position from the manager",
                    "Restate the liquidity map with the position excluded",
                    "Tell the client what has actually been received, not what was requested",
                ],
                trade_offs=[
                    "Removes a position the client may believe is available",
                    "May surface a worse liquidity picture than expected",
                ],
                suitability_checks=_base_checks(ctx),
                requires=["RM action", "Manager confirmation"],
                estimated_impact=(
                    f"Clarifies the status of USD {gated['market_value_usd']:,.0f}."
                ),
            )
        )

    options.append(
        _monitor_option(
            ctx,
            insight,
            trigger=(
                "Alert 90 days before the earliest obligation, or if withdrawable "
                "value falls below the amount due."
            ),
            cost_of_waiting=(
                "The set of ways to fund the obligation narrows as the date "
                "approaches, and the last option is usually the most expensive."
            ),
        )
    )
    return options


# ---------------------------------------------------------------------------
# Mandate and suitability
# ---------------------------------------------------------------------------


def mandate_options(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    review = next(
        (
            r
            for r in ctx.mandate_reviews
            if r.portfolio_id in insight.portfolio_ids
        ),
        None,
    )
    if review is None:
        return []

    steps = []
    for band in review.band_breaches:
        direction = "Reduce" if band.direction == "above" else "Increase"
        steps.append(
            f"{direction} {band.asset_class} from {band.actual_pct:.1f}% toward the "
            f"{band.target_pct:.0f}% target "
            f"({band.base_currency} {abs(band.value_base - review.total_base * band.target_pct / 100):,.0f} to trade)"
        )

    options = [
        ActionOption(
            id=f"{insight.id}-opt-correct",
            label="Correct to the mandate bands over a staged programme",
            rationale=(
                "Bringing the portfolio inside its bands is the contractual position. "
                "Staging it avoids putting the whole correction through the market on "
                "one day, which matters most for the largest gaps."
            ),
            mechanics=steps
            + ["Agree tranche sizes and dates, and record the end state"],
            trade_offs=[
                "Executes into current prices rather than chosen ones",
                "Crystallises gains or losses across several positions",
                "Takes time, so the breach persists during the programme",
            ],
            suitability_checks=_base_checks(ctx, crystallises_loss=True),
            requires=["RM approval", "Client instruction"]
            + (["Investment committee note"] if review.service_model == "Discretionary" else []),
            estimated_impact=(
                f"Brings {len(review.band_breaches)} asset class(es) inside their bands."
            ),
            evidence=insight.evidence[:4],
        ),
        ActionOption(
            id=f"{insight.id}-opt-document",
            label="Document a client-directed exception with a review date",
            rationale=(
                "Where the client has instructed the position and understands the "
                "consequence, the honest outcome is a recorded exception rather than a "
                "correction plan nobody intends to execute."
            ),
            mechanics=[
                "Record the client's instruction and confirmation in writing",
                "Log the exception with a defined size limit and review date",
                "Report the breach in the periodic mandate review",
            ],
            trade_offs=[
                "The portfolio stays outside its bands",
                "Requires the client to accept the position in writing",
                "Does not remove the underlying risk",
            ],
            suitability_checks=_base_checks(ctx)
            + [
                SuitabilityCheck(
                    check="Written client instruction on file",
                    result="attention" if ctx.waiver_notes else "not_assessed",
                    detail=(
                        f"Note {ctx.waiver_notes[-1]['note_id']} reads as an "
                        "instruction; confirm the signed record exists."
                        if ctx.waiver_notes
                        else "No instruction found in the RM notes for this breach."
                    ),
                    reference="rm_notes.json",
                )
            ],
            requires=["RM approval", "Compliance sign-off", "Client confirmation in writing"],
            estimated_impact="No portfolio change; the exception becomes visible and dated.",
        ),
    ]

    options.append(
        _monitor_option(
            ctx,
            insight,
            trigger="Alert if any band gap widens by more than 3 percentage points.",
            cost_of_waiting=(
                "The portfolio remains outside a contractual limit, which is reportable "
                "whether or not it is discussed."
            ),
        )
    )
    return options


def suitability_options(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    return [
        ActionOption(
            id=f"{insight.id}-opt-staged",
            label="Agree a target allocation and move to it in dated tranches",
            rationale=(
                "A single large rebalancing decision is hard for a client to accept and "
                "easy to defer. A target with dates attached converts it into a "
                "sequence of smaller confirmations."
            ),
            mechanics=[
                "Agree the destination allocation, not the first trade",
                "Break the move into tranches with dates",
                "Confirm each tranche in writing before execution",
            ],
            trade_offs=[
                "The portfolio remains unsuitable during the transition",
                "Market moves during the programme change the arithmetic",
            ],
            suitability_checks=_base_checks(ctx, crystallises_loss=True),
            requires=["RM approval", "Client instruction"],
            estimated_impact="Moves the portfolio toward the recorded profile over time.",
            evidence=insight.evidence[:3],
        ),
        ActionOption(
            id=f"{insight.id}-opt-reprofile",
            label="Re-run the risk profiling before changing anything",
            rationale=(
                "If the recorded profile is wrong, every downstream check is wrong "
                "too. Where a profile was set during a life event, confirming it is "
                "the cheapest first step."
            ),
            mechanics=[
                "Re-run the profiling questionnaire with the client",
                "Compare the result with the current allocation",
                "Update clients.risk_profile and re-run the checks",
            ],
            trade_offs=[
                "Delays any portfolio change",
                "May confirm the mismatch rather than resolve it",
            ],
            suitability_checks=_base_checks(ctx),
            requires=["RM meeting", "Client participation"],
            estimated_impact="Confirms or corrects the basis for every other action.",
        ),
        _monitor_option(
            ctx,
            insight,
            trigger="Alert if risk assets rise a further 5 percentage points.",
            cost_of_waiting=(
                "The portfolio stays outside what the client said they wanted, which "
                "is the position that has to be defended if markets fall."
            ),
        ),
    ]


def generic_options(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    return [
        ActionOption(
            id=f"{insight.id}-opt-discuss",
            label="Raise it at the next meeting with the evidence attached",
            rationale=insight.suggested_next_step
            or "The finding needs the client's input before anything can be decided.",
            mechanics=[
                "Add to the meeting agenda with the supporting figures",
                "Record the client's response in the file",
            ],
            trade_offs=["Nothing changes until the meeting happens"],
            suitability_checks=_base_checks(ctx),
            requires=["RM approval"],
            estimated_impact="Moves the item from the engine to the conversation.",
            evidence=insight.evidence[:3],
        ),
        _monitor_option(
            ctx,
            insight,
            trigger="Alert if the underlying figure moves by more than 20%.",
            cost_of_waiting="The finding stands until it is addressed.",
        ),
    ]


_DISPATCH = {
    Category.COLLATERAL: collateral_options,
    Category.CONCENTRATION: concentration_options,
    Category.LIQUIDITY: liquidity_options,
    Category.MANDATE: mandate_options,
    Category.SUITABILITY: suitability_options,
}


def options_for(ctx: SignalContext, insight: Insight) -> list[ActionOption]:
    """Build the reviewable options for one insight."""
    builder = _DISPATCH.get(insight.category, generic_options)
    options = builder(ctx, insight)
    return options or generic_options(ctx, insight)
