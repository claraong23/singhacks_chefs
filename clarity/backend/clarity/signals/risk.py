"""Risk signals: collateral, concentration, liquidity and currency.

Every check in this file answers a question an RM would actually be asked in a
meeting, and returns the arithmetic that supports the answer.
"""

from __future__ import annotations

from typing import Iterable

from .. import config
from ..analytics.collateral import withdrawal_capacity
from ..analytics.lookthrough import WORST_OF_ASSUMPTION, unresolved_notes
from ..analytics.liquidity import ANNUAL_ASSUMPTION, ENCUMBRANCE_ASSUMPTION
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
from .base import SignalContext, priority, signal

#: Words in ``clients.source_of_wealth`` that tie a client's wealth to a theme.
_WEALTH_THEME_TERMS: dict[str, tuple[str, ...]] = {
    "energy_hormuz": (
        "coal",
        "energy",
        "oil",
        "gas",
        "shipping",
        "marine",
        "port services",
        "chartering",
    ),
    "us_tech_ai": ("software", "technology", "semiconductor", "cloud"),
    "hk_property": ("property development", "property"),
    "greater_china_consumer": ("luxury", "retail"),
    "healthcare": ("healthcare", "pharmaceutical", "clinics", "medical"),
}


# ---------------------------------------------------------------------------
# Collateral
# ---------------------------------------------------------------------------


@signal("collateral_headroom")
def collateral_headroom(ctx: SignalContext) -> Iterable[Insight]:
    """How close is each facility to its margin-call trigger, and why."""
    for facility in ctx.facilities:
        current = facility.current
        if current.ltv_pct is None or facility.headroom_pp is None:
            continue

        breached_now = current.ltv_pct > facility.margin_call_ltv_pct
        if breached_now:
            severity = Severity.CRITICAL
        elif facility.headroom_pp <= config.LTV_CRITICAL_HEADROOM_PP:
            severity = Severity.CRITICAL
        elif facility.headroom_pp <= config.LTV_WARN_HEADROOM_PP:
            severity = Severity.HIGH
        elif facility.breaches:
            severity = Severity.MEDIUM
        else:
            continue

        pf = ctx.book.portfolios.get(facility.portfolio_id, {})
        drawn_usd = (
            ctx.book.to_usd(current.drawn or 0.0, facility.currency, ctx.snapshot) or 0.0
        )
        materiality = ctx.view.weight(drawn_usd)

        facts = [
            Fact(
                "Loan-to-value today",
                f"{current.ltv_pct:.2f}%",
                current.ltv_pct,
                "%",
                "up"
                if len(facility.series) > 1
                and (facility.series[-2].ltv_pct or 0) < current.ltv_pct
                else "down",
            ),
            Fact(
                "Margin-call trigger",
                f"{facility.margin_call_ltv_pct:.0f}%",
                facility.margin_call_ltv_pct,
                "%",
            ),
            Fact(
                "Headroom",
                f"{facility.headroom_pp:.2f} percentage points",
                facility.headroom_pp,
                "pp",
            ),
            Fact(
                "Collateral fall that triggers a call",
                f"{facility.collateral_fall_to_trigger_pct:.1f}%",
                facility.collateral_fall_to_trigger_pct,
                "%",
            ),
            Fact(
                "Drawn",
                f"{facility.currency} {current.drawn:,.0f}",
                current.drawn,
                facility.currency,
            ),
        ]

        capacity = withdrawal_capacity(facility)
        if capacity is not None:
            facts.append(
                Fact(
                    "Cash that can leave the pledged account",
                    f"{facility.currency} {capacity:,.0f}",
                    capacity,
                    facility.currency,
                )
            )

        summary_parts = [
            f"{facility.facility_id} sits at {current.ltv_pct:.2f}% loan-to-value "
            f"against a {facility.margin_call_ltv_pct:.0f}% trigger. A "
            f"{facility.collateral_fall_to_trigger_pct:.1f}% fall in collateral value "
            f"is enough to produce a margin call."
        ]
        if facility.breaches:
            dates = ", ".join(p.snapshot for p in facility.breaches)
            summary_parts.append(f"The trigger was already breached at {dates}.")
        if facility.cure_narrative:
            summary_parts.append(facility.cure_narrative)

        score, reasons = priority(
            severity, materiality_pct=materiality, days_until=0, amount_usd=drawn_usd
        )

        yield Insight(
            id=f"{ctx.client_id}-collateral-{facility.facility_id}",
            client_id=ctx.client_id,
            category=Category.COLLATERAL,
            severity=severity,
            headline=(
                f"Lombard facility {facility.headroom_pp:.2f}pp from a margin call"
                if not breached_now
                else "Lombard facility is above its margin-call trigger"
            ),
            summary=" ".join(summary_parts),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=facts,
            client_relevance=(
                f"Client & Situation Context: For {ctx.client.get('client_name')}"
                + (f" ({ctx.client.get('source_of_wealth')})" if ctx.client.get('source_of_wealth') else "")
                + f", credit facility {facility.facility_id} is secured by {pf.get('portfolio_name', facility.portfolio_id)} "
                f"with {facility.currency} {current.drawn:,.0f} drawn. Current LTV is {current.ltv_pct:.2f}% against a "
                f"{facility.margin_call_ltv_pct:.0f}% margin trigger (headroom is just {facility.headroom_pp:.2f} percentage points). "
                f"Withdrawing or selling assets from the pledged account reduces collateral lending value and increases the loan ratio, "
                f"directly restricting the client from using this portfolio to fund upcoming cash commitments."
            ),
            suggested_next_step=(
                "Agree a collateral plan before the next client-driven withdrawal: "
                "either reduce drawn, add eligible collateral, or accept a smaller "
                "withdrawal than the client expects."
            ),
            evidence=facility.evidence(),
            assumptions=[
                Assumption(
                    statement=(
                        "Lending value is used for loan-to-value, not market value."
                    ),
                    basis=(
                        "Advance rates haircut each asset; illiquid alternatives carry "
                        "a 0% advance rate and add no borrowing capacity."
                    ),
                ),
                ENCUMBRANCE_ASSUMPTION,
            ],
            suitability_checks=[
                SuitabilityCheck(
                    check="Leverage consistent with risk profile",
                    result="attention" if severity == Severity.CRITICAL else "pass",
                    detail=(
                        f"Client risk profile is {ctx.client.get('risk_profile')} "
                        f"(tolerance {ctx.client.get('risk_tolerance_score')}/10) with "
                        f"{ctx.client.get('liquidity_needs')} stated liquidity needs."
                    ),
                    reference="clients.csv",
                )
            ],
            confidence=Confidence.MEASURED,
            portfolio_ids=[facility.portfolio_id],
            amount_usd=drawn_usd,
        )


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------


@signal("hidden_issuer_concentration")
def hidden_issuer_concentration(ctx: SignalContext) -> Iterable[Insight]:
    """Single-issuer exposure once wrappers are looked through."""
    for exposure in ctx.issuer_exposures:
        if exposure.pct_of_household < config.HOUSEHOLD_CONCENTRATION_WARN_PCT:
            continue
        if len(exposure.legs) < 2 and not exposure.hidden:
            # A single line item at 15% is visible on any statement; the
            # mandate check covers it. This signal is about what is *not*
            # visible.
            continue

        severity = (
            Severity.CRITICAL
            if exposure.pct_of_household >= config.HOUSEHOLD_CONCENTRATION_HIGH_PCT
            else Severity.HIGH
        )
        score, reasons = priority(
            severity,
            materiality_pct=exposure.pct_of_household,
            amount_usd=exposure.attributed_usd,
        )

        wrappers = ", ".join(sorted({leg.wrapper for leg in exposure.legs}))
        facts = [
            Fact(
                "Total exposure to this issuer",
                f"USD {exposure.attributed_usd:,.0f}",
                exposure.attributed_usd,
                "USD",
            ),
            Fact(
                "Share of household wealth",
                f"{exposure.pct_of_household:.1f}%",
                exposure.pct_of_household,
                "%",
            ),
            Fact("Number of separate line items", str(len(exposure.legs)), len(exposure.legs)),
            Fact("Wrappers involved", wrappers),
        ]
        for leg in exposure.legs:
            facts.append(
                Fact(
                    leg.instrument_name,
                    f"USD {leg.attributed_usd:,.0f} ({ctx.view.weight(leg.attributed_usd):.1f}%)",
                    leg.attributed_usd,
                    "USD",
                )
            )

        yield Insight(
            id=f"{ctx.client_id}-issuer-{exposure.key.lower()}",
            client_id=ctx.client_id,
            category=Category.CONCENTRATION,
            severity=severity,
            headline=(
                f"{exposure.pct_of_household:.0f}% of household wealth sits with "
                f"{exposure.name}, across {len(exposure.legs)} line items"
            ),
            summary=(
                f"{exposure.name} appears as {wrappers}. Each line looks moderate on "
                f"its own; together they are USD {exposure.attributed_usd:,.0f}, or "
                f"{exposure.pct_of_household:.1f}% of everything the client holds. "
                f"A single credit or price event on this issuer hits all of them at once."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=facts,
            client_relevance=(
                "The positions rank differently in a stress: the perpetual is "
                "subordinated, the accumulator obliges further purchases below strike, "
                "and the equity is the first to move."
                if any("perpetual" in leg.wrapper.lower() for leg in exposure.legs)
                else "The exposure is spread across wrappers with different payoffs."
            ),
            suggested_next_step=(
                "Show the client the aggregated figure before discussing any single "
                "position, then agree a ceiling for total issuer exposure."
            ),
            evidence=exposure.evidence(),
            assumptions=[WORST_OF_ASSUMPTION]
            if any(leg.basis_field == "underlying_reference" for leg in exposure.legs)
            else [],
            confidence=Confidence.MEASURED,
            instrument_ids=[leg.instrument_id for leg in exposure.legs],
            portfolio_ids=sorted(
                {p for leg in exposure.legs for p in leg.portfolio_ids}
            ),
            amount_usd=exposure.attributed_usd,
            open_questions=unresolved_notes(ctx.view),
        )


@signal("theme_concentration")
def theme_concentration(ctx: SignalContext) -> Iterable[Insight]:
    """Exposure to one market theme across every wrapper it hides in."""
    for exposure in ctx.theme_exposures:
        if exposure.pct_of_household < 30.0:
            continue
        if len(exposure.legs) < 2:
            continue

        severity = Severity.HIGH if exposure.pct_of_household < 45 else Severity.CRITICAL
        score, reasons = priority(
            severity,
            materiality_pct=exposure.pct_of_household,
            amount_usd=exposure.attributed_usd,
        )
        events = [
            ctx.book.events_by_id[e]
            for e in exposure.event_ids
            if e in ctx.book.events_by_id
        ]

        yield Insight(
            id=f"{ctx.client_id}-theme-{exposure.key}",
            client_id=ctx.client_id,
            category=Category.CONCENTRATION,
            severity=severity,
            headline=(
                f"{exposure.pct_of_household:.0f}% of the household moves with "
                f"{exposure.name}"
            ),
            summary=(
                f"USD {exposure.attributed_usd:,.0f} across "
                f"{len(exposure.legs)} positions responds to the same driver. "
                + (
                    f"The dataset records {len(events)} events on this theme in 2026."
                    if events
                    else "This is a structural exposure rather than an event-driven one."
                )
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact(
                    leg.instrument_name,
                    f"USD {leg.attributed_usd:,.0f} ({ctx.view.weight(leg.attributed_usd):.1f}%) via {leg.wrapper}",
                    leg.attributed_usd,
                    "USD",
                )
                for leg in exposure.legs
            ],
            client_relevance=exposure.legs[0].basis_note,
            suggested_next_step=(
                "Frame the review around the driver rather than the instruments: one "
                "decision covers all of them."
            ),
            evidence=exposure.evidence()
            + [
                Evidence(
                    source_file="event_log.csv",
                    row_or_id=e["event_id"],
                    field="description",
                    value=e["description"],
                    snapshot_date=e["event_date"],
                    note=f"Transmission: {e['primary_transmission']}",
                )
                for e in events[:4]
            ],
            confidence=Confidence.MEASURED,
            related_event_ids=list(exposure.event_ids),
            instrument_ids=[leg.instrument_id for leg in exposure.legs],
            amount_usd=exposure.attributed_usd,
        )


@signal("wealth_and_portfolio_same_bet")
def wealth_and_portfolio_same_bet(ctx: SignalContext) -> Iterable[Insight]:
    """The portfolio is the same bet as the money that created it.

    Diversification away from the source of wealth is the reason many of these
    clients opened the relationship. Where the portfolio has drifted back onto
    the same driver, that is a stated-objective failure, not a market view.
    """
    source = (ctx.client.get("source_of_wealth") or "").lower()
    objectives = (ctx.client.get("objectives") or "").lower()

    for exposure in ctx.theme_exposures:
        terms = _WEALTH_THEME_TERMS.get(exposure.key, ())
        matched = [t for t in terms if t in source]
        if not matched or exposure.pct_of_household < 20.0:
            continue

        wants_diversification = any(
            phrase in objectives
            for phrase in (
                "diversify",
                "outside",
                "uncorrelated",
                "reduce dependence",
                "away from",
            )
        )
        severity = Severity.HIGH if wants_diversification else Severity.MEDIUM
        score, reasons = priority(
            severity,
            materiality_pct=exposure.pct_of_household,
            amount_usd=exposure.attributed_usd,
        )
        if wants_diversification:
            reasons.append("Client has a stated diversification objective")

        yield Insight(
            id=f"{ctx.client_id}-samebet-{exposure.key}",
            client_id=ctx.client_id,
            category=Category.SUITABILITY,
            severity=severity,
            headline=(
                f"The portfolio and the client's source of wealth are the same bet "
                f"({exposure.pct_of_household:.0f}% on {exposure.name})"
            ),
            summary=(
                f"Source of wealth is recorded as \"{ctx.client.get('source_of_wealth')}\". "
                f"USD {exposure.attributed_usd:,.0f} of the portfolio "
                f"({exposure.pct_of_household:.1f}%) responds to the same driver, so "
                f"the business and the portfolio would come under pressure together."
                + (
                    " The client's stated objective is to diversify away from exactly this."
                    if wants_diversification
                    else ""
                )
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact("Source of wealth", ctx.client.get("source_of_wealth", "")),
                Fact("Stated objectives", ctx.client.get("objectives", "")),
                Fact(
                    "Portfolio exposure to the same theme",
                    f"USD {exposure.attributed_usd:,.0f} ({exposure.pct_of_household:.1f}%)",
                    exposure.attributed_usd,
                    "USD",
                ),
            ],
            client_relevance=(
                "Total household risk is higher than the portfolio alone suggests, "
                "because the operating business is not in the portfolio view."
            ),
            suggested_next_step=(
                "Put the combined picture in front of the client and agree what share "
                "of the theme belongs in the portfolio given the business exposure."
            ),
            evidence=[
                Evidence(
                    source_file="clients.csv",
                    row_or_id=ctx.client_id,
                    field="source_of_wealth",
                    value=ctx.client.get("source_of_wealth"),
                    note=f"Matched on '{matched[0]}'.",
                ),
                Evidence(
                    source_file="clients.csv",
                    row_or_id=ctx.client_id,
                    field="objectives",
                    value=ctx.client.get("objectives"),
                ),
            ]
            + exposure.evidence(),
            confidence=Confidence.DERIVED,
            assumptions=[
                Assumption(
                    statement=(
                        "The link between source of wealth and theme is matched on "
                        f"the term '{matched[0]}' in clients.source_of_wealth."
                    ),
                    basis="The dataset holds no direct mapping between the two.",
                    impact_if_wrong="The RM can dismiss the insight in one click.",
                )
            ],
            instrument_ids=[leg.instrument_id for leg in exposure.legs],
            amount_usd=exposure.attributed_usd,
        )


# ---------------------------------------------------------------------------
# Liquidity
# ---------------------------------------------------------------------------


@signal("liquidity_cover")
def liquidity_cover(ctx: SignalContext) -> Iterable[Insight]:
    """Can the client actually fund what they have already committed to?"""
    lq = ctx.liquidity
    if not lq.obligations or lq.coverage_ratio is None:
        return
    if lq.coverage_ratio >= config.LIQUIDITY_COVER_WARN:
        return

    severity = (
        Severity.CRITICAL
        if lq.coverage_ratio < config.LIQUIDITY_COVER_CRITICAL
        else Severity.HIGH
    )
    nearest = min(
        (o for o in lq.obligations if o.due_from), key=lambda o: o.due_from, default=None
    )
    days = ctx.days_until(nearest.due_from) if nearest else None

    score, reasons = priority(
        severity,
        materiality_pct=ctx.view.weight(lq.obligations_total_usd),
        days_until=days,
        amount_usd=lq.obligations_total_usd,
    )

    facts = [
        Fact(
            "Obligations inside the horizon",
            f"USD {lq.obligations_total_usd:,.0f}",
            lq.obligations_total_usd,
            "USD",
        ),
        Fact(
            "Of which confirmed",
            f"USD {lq.obligations_confirmed_usd:,.0f}",
            lq.obligations_confirmed_usd,
            "USD",
        ),
        Fact(
            "Daily and weekly assets",
            f"USD {lq.readily_realisable_usd:,.0f}",
            lq.readily_realisable_usd,
            "USD",
        ),
        Fact(
            "Withdrawable after collateral constraints",
            f"USD {lq.withdrawable_usd:,.0f}",
            lq.withdrawable_usd,
            "USD",
        ),
        Fact(
            "Coverage",
            f"{lq.coverage_ratio:.2f}x",
            lq.coverage_ratio,
            "x",
            "down",
        ),
        Fact("Shortfall", f"USD {lq.shortfall_usd:,.0f}", lq.shortfall_usd, "USD"),
    ]
    for o in lq.obligations[:5]:
        facts.append(
            Fact(
                o.description,
                f"{o.currency} {o.amount_ccy:,.0f}"
                + (f" x{o.occurrences}" if o.occurrences > 1 else "")
                + f" - {o.certainty}",
                o.total_usd,
                "USD",
            )
        )

    coverage_pct = (lq.coverage_ratio * 100) if lq.coverage_ratio is not None else 0.0
    primary_ob = lq.obligations[0] if lq.obligations else None
    ob_desc = (
        f"{primary_ob.description} ({primary_ob.currency} {primary_ob.amount_ccy:,.0f} - {primary_ob.certainty})"
        if primary_ob
        else f"obligations totaling USD {lq.obligations_total_usd:,.0f}"
    )

    summary_parts = [
        f"Severe liquidity shortfall of USD {lq.shortfall_usd:,.0f}: "
        f"The client has only USD {lq.withdrawable_usd:,.0f} in unencumbered, withdrawable cash against "
        f"USD {lq.obligations_total_usd:,.0f} in obligations falling due inside the planning horizon "
        f"(coverage is just {coverage_pct:.1f}%, primarily driven by {ob_desc})."
    ]
    if lq.encumbered_cap_usd:
        summary_parts.append(
            f"While holding USD {lq.encumbered_cap_usd:,.0f} in readily realisable liquid securities, "
            f"these are fully pledged as collateral backing the active credit facility and cannot be withdrawn or sold "
            f"without triggering an immediate loan margin-call breach."
        )
    if lq.illiquid_usd:
        summary_parts.append(
            f"The remaining USD {lq.illiquid_usd:,.0f} of wealth is locked in illiquid real estate and private investments "
            f"that cannot be liquidated quickly."
        )
    if lq.gated_usd:
        summary_parts.append(
            f"USD {lq.gated_usd:,.0f} sits behind redemption gates that cannot guarantee fixed-date settlement."
        )

    client_name = ctx.client.get("client_name", "The client")
    wealth_source = ctx.client.get("source_of_wealth", "")
    relevance_parts = [
        f"Client & Situation Context: {client_name}"
        + (f" ({wealth_source})" if wealth_source else "")
        + " faces a concrete funding deadline rather than a market performance problem."
    ]
    if primary_ob:
        relevance_parts.append(
            f"The impending commitment is {primary_ob.description} for {primary_ob.currency} {primary_ob.amount_ccy:,.0f} "
            f"(approx. USD {primary_ob.total_usd:,.0f}, status: {primary_ob.certainty.lower()})."
        )
    if lq.encumbered_cap_usd and ctx.facilities:
        fac = ctx.facilities[0]
        relevance_parts.append(
            f"Because the liquid portfolio is pledged to credit facility {fac.facility_id} "
            f"(operating with narrow headroom at {fac.current.ltv_pct:.2f}% LTV against a {fac.margin_call_ltv_pct:.0f}% trigger), "
            f"selling assets from the pledged account reduces collateral value and accelerates a margin call. "
            f"The RM must discuss options—such as staging contributions, pledging alternative unencumbered collateral, or adjusting facility terms—well before the payment deadline."
        )
    elif lq.encumbered_cap_usd:
        relevance_parts.append(
            "Because the liquid portfolio is pledged as collateral, attempting to withdraw funds directly will trigger a loan covenant breach. "
            "A structured funding strategy must be agreed before the deadline approaches."
        )
    else:
        relevance_parts.append(
            "Funding options narrow as the deadline approaches, requiring proactive planning to avoid selling assets into unfavorable market conditions."
        )

    yield Insight(
        id=f"{ctx.client_id}-liquidity-cover",
        client_id=ctx.client_id,
        category=Category.LIQUIDITY,
        severity=severity,
        headline=(
            f"Known obligations of USD {lq.obligations_total_usd:,.0f} against "
            f"USD {lq.withdrawable_usd:,.0f} the client can actually withdraw"
        ),
        summary=" ".join(summary_parts),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=facts,
        client_relevance=" ".join(relevance_parts),
        suggested_next_step=(
            "Produce a dated liquidity map: what is sellable, by when, and what it "
            "costs to raise the shortfall each way."
        ),
        evidence=lq.evidence(),
        assumptions=[ANNUAL_ASSUMPTION, ENCUMBRANCE_ASSUMPTION],
        suitability_checks=[
            SuitabilityCheck(
                check="Stated liquidity needs",
                result="attention",
                detail=(
                    f"clients.liquidity_needs is recorded as "
                    f"{ctx.client.get('liquidity_needs')}."
                ),
                reference="clients.csv",
            )
        ],
        confidence=Confidence.DERIVED,
        amount_usd=lq.obligations_total_usd,
        open_questions=[
            "Is the client willing to reduce the facility rather than sell?",
            "Can any obligation be deferred or staged?",
        ],
    )


@signal("sleeve_commitment_cover")
def sleeve_commitment_cover(ctx: SignalContext) -> Iterable[Insight]:
    """Uncalled commitments against the cash of the *sleeve that owes them*.

    A household can be liquid in aggregate while the account carrying the
    commitments is not. Moving money between a discretionary core mandate and an
    alternatives sleeve is a governance decision, not a transfer, so the two
    should not be netted before anyone has agreed to it.
    """
    commitments = ctx.book.commitments_by_client.get(ctx.client_id, [])
    if not commitments:
        return

    by_portfolio: dict[str, list[dict]] = {}
    for c in commitments:
        by_portfolio.setdefault(c.get("portfolio_id", ""), []).append(c)

    for portfolio_id, rows in by_portfolio.items():
        pf = ctx.book.portfolios.get(portfolio_id)
        if pf is None:
            continue

        uncalled_usd = sum(
            ctx.book.to_usd(c.get("uncalled") or 0.0, c.get("currency", "USD"), ctx.snapshot)
            or 0.0
            for c in rows
        )
        if uncalled_usd <= 0:
            continue

        holdings = ctx.book.holdings_by_portfolio_date.get((portfolio_id, ctx.snapshot), [])
        sleeve_total = sum(h.get("market_value_usd") or 0.0 for h in holdings)
        liquid = sum(
            h.get("market_value_usd") or 0.0
            for h in holdings
            if h.get("liquidity_tier") in config.READILY_REALISABLE
        )
        cash = sum(
            h.get("market_value_usd") or 0.0
            for h in holdings
            if h.get("asset_class") == "Cash and Equivalents"
        )
        cover = liquid / uncalled_usd if uncalled_usd else None
        if cover is None or cover >= 1.5:
            continue

        severity = Severity.CRITICAL if cover < 0.5 else Severity.HIGH
        window = rows[0].get("expected_call_window", "")
        score, reasons = priority(
            severity,
            materiality_pct=ctx.view.weight(uncalled_usd),
            days_until=90 if "2026 Q4" in window else 180,
            amount_usd=uncalled_usd,
        )
        reasons.append(
            f"Measured against {pf.get('portfolio_name')} alone, not the household"
        )

        yield Insight(
            id=f"{ctx.client_id}-sleeve-{portfolio_id}",
            client_id=ctx.client_id,
            category=Category.LIQUIDITY,
            severity=severity,
            headline=(
                f"{pf.get('portfolio_name')} owes USD {uncalled_usd:,.0f} in uncalled "
                f"commitments against USD {liquid:,.0f} it can sell"
            ),
            summary=(
                f"The sleeve holds USD {sleeve_total:,.0f}, of which "
                f"USD {cash:,.0f} is cash and USD {liquid:,.0f} is realisable within a "
                f"week. Uncalled commitments are USD {uncalled_usd:,.0f}, expected "
                f"{window}. Cover is {cover:.2f}x. Meeting a call from elsewhere in the "
                "household is possible but is an investment committee decision, not an "
                "operational transfer."
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact("Sleeve value", f"USD {sleeve_total:,.0f}", sleeve_total, "USD"),
                Fact("Sleeve cash", f"USD {cash:,.0f}", cash, "USD"),
                Fact(
                    "Realisable within a week",
                    f"USD {liquid:,.0f}",
                    liquid,
                    "USD",
                ),
                Fact(
                    "Uncalled commitments",
                    f"USD {uncalled_usd:,.0f}",
                    uncalled_usd,
                    "USD",
                ),
                Fact("Cover", f"{cover:.2f}x", cover, "x", "down"),
            ]
            + [
                Fact(
                    c.get("fund_name", ""),
                    f"{c.get('currency')} {c.get('uncalled'):,.0f} uncalled of "
                    f"{c.get('committed'):,.0f} committed, expected "
                    f"{c.get('expected_call_window')}",
                    c.get("uncalled"),
                    c.get("currency"),
                )
                for c in rows
            ],
            client_relevance=(
                "Capital calls arrive at the manager's discretion. A sleeve that has to "
                "sell its remaining liquid assets to meet one stops being able to meet "
                "the next."
            ),
            suggested_next_step=(
                "Produce the liquidity map by account and by date, showing which "
                "account funds each call and what that leaves behind."
            ),
            evidence=[
                Evidence(
                    source_file="commitments.csv",
                    row_or_id=c["commitment_id"],
                    field="uncalled",
                    value=f"{c.get('currency')} {c.get('uncalled'):,.0f}",
                    note=f"{c.get('fund_name')}, expected {c.get('expected_call_window')}.",
                )
                for c in rows
            ]
            + [
                Evidence(
                    source_file="holdings.csv",
                    row_or_id=h["instrument_id"],
                    field="liquidity_tier",
                    value=h.get("liquidity_tier"),
                    snapshot_date=ctx.snapshot,
                    note=f"{h.get('instrument_name')}: USD {h.get('market_value_usd'):,.0f}",
                )
                for h in sorted(
                    holdings, key=lambda h: -(h.get("market_value_usd") or 0)
                )[:6]
            ],
            confidence=Confidence.MEASURED,
            portfolio_ids=[portfolio_id],
            amount_usd=uncalled_usd,
            open_questions=[
                "Which account is nominated to fund the next call?",
                "Has the manager indicated the size or timing of the next call?",
            ],
        )


@signal("gated_vehicles")
def gated_vehicles(ctx: SignalContext) -> Iterable[Insight]:
    """Semi-liquid funds that have stopped behaving as semi-liquid."""
    gated = [
        p for p in ctx.view.positions if p.liquidity_tier == "Quarterly Gate"
    ]
    if not gated:
        return
    total = sum(p.market_value_usd for p in gated)
    pct = ctx.view.weight(total)
    gate_notes = ctx.notes_matching("gate", "gated", "redemption")
    if pct < 5 and not gate_notes:
        return

    severity = Severity.HIGH if gate_notes or pct >= 10 else Severity.MEDIUM
    score, reasons = priority(severity, materiality_pct=pct, amount_usd=total)

    event = ctx.book.events_by_id.get("EVT-14")
    yield Insight(
        id=f"{ctx.client_id}-gated",
        client_id=ctx.client_id,
        category=Category.LIQUIDITY,
        severity=severity,
        headline=(
            f"USD {total:,.0f} sits in vehicles that can refuse a redemption"
        ),
        summary=(
            f"{len(gated)} position(s) carry a Quarterly Gate liquidity tier, "
            f"{pct:.1f}% of household wealth. A submitted redemption is a request, "
            "not a settlement date."
            + (
                f" RM notes record this: \"{gate_notes[-1]['note'][:180]}\""
                if gate_notes
                else ""
            )
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact(
                p.instrument_name,
                f"USD {p.market_value_usd:,.0f} ({p.weight_pct:.1f}%), advance rate "
                f"{p.advance_rate_pct:.0f}%",
                p.market_value_usd,
                "USD",
            )
            for p in gated
        ],
        client_relevance=(
            "These positions also contribute nothing to borrowing capacity where the "
            "advance rate is zero, so they cannot be used to bridge a cash need either."
        ),
        suggested_next_step=(
            "Confirm the current gate terms with the manager and treat the position as "
            "unavailable until cash is received."
        ),
        evidence=[
            Evidence(
                source_file="holdings.csv",
                row_or_id=p.instrument_id,
                field="liquidity_tier",
                value=p.liquidity_tier,
                snapshot_date=ctx.snapshot,
                note=f"USD {p.market_value_usd:,.0f}",
            )
            for p in gated
        ]
        + (
            [
                Evidence(
                    source_file="event_log.csv",
                    row_or_id=event["event_id"],
                    field="description",
                    value=event["description"],
                    snapshot_date=event["event_date"],
                )
            ]
            if event
            else []
        )
        + [
            Evidence(
                source_file="rm_notes.json",
                row_or_id=n["note_id"],
                field="note",
                value=n["note"],
                snapshot_date=n["note_date"],
                note="RM note. Relationship context, not independently verified.",
            )
            for n in gate_notes[-2:]
        ],
        confidence=Confidence.MEASURED if not gate_notes else Confidence.REPORTED,
        related_event_ids=["EVT-14"] if event else [],
        instrument_ids=[p.instrument_id for p in gated],
        amount_usd=total,
    )


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------


@signal("currency_mismatch")
def currency_mismatch(ctx: SignalContext) -> Iterable[Insight]:
    """Obligations in a currency the portfolio does not hold."""
    lq = ctx.liquidity
    if not lq.obligations:
        return

    by_currency: dict[str, float] = {}
    for o in lq.obligations:
        by_currency[o.currency] = by_currency.get(o.currency, 0.0) + o.total_usd

    for currency, needed_usd in sorted(by_currency.items(), key=lambda kv: -kv[1]):
        held_usd = ctx.view.by_currency.get(currency, 0.0)
        if needed_usd < 500_000 or held_usd >= needed_usd:
            continue
        held_pct = ctx.view.weight(held_usd)
        gap = needed_usd - held_usd
        severity = Severity.MEDIUM if held_pct > 10 else Severity.HIGH
        score, reasons = priority(
            severity,
            materiality_pct=ctx.view.weight(gap),
            days_until=ctx.days_until(
                min(
                    (o.due_from for o in lq.obligations if o.currency == currency and o.due_from),
                    default=None,
                )
            ),
            amount_usd=gap,
        )

        rate_now = ctx.book.usd_per_unit(currency, ctx.snapshot)
        rate_then = ctx.book.usd_per_unit(currency, config.BASELINE_SNAPSHOT)
        move = (
            None
            if not rate_now or not rate_then
            else (rate_now / rate_then - 1) * 100
        )

        yield Insight(
            id=f"{ctx.client_id}-fx-{currency}",
            client_id=ctx.client_id,
            category=Category.CURRENCY,
            severity=severity,
            headline=(
                f"{currency} obligations of USD {needed_usd:,.0f} against "
                f"{currency} assets of USD {held_usd:,.0f}"
            ),
            summary=(
                f"The client owes {currency} but holds {held_pct:.1f}% of the "
                f"household in it. The balance would have to be converted at whatever "
                f"rate applies on the day."
                + (
                    f" {currency} has moved {move:+.1f}% against USD since "
                    f"{config.BASELINE_SNAPSHOT}."
                    if move is not None
                    else ""
                )
            ),
            priority_score=score,
            priority_reasons=reasons,
            observed_facts=[
                Fact(
                    f"{currency} obligations in horizon",
                    f"USD {needed_usd:,.0f}",
                    needed_usd,
                    "USD",
                ),
                Fact(
                    f"{currency} assets held",
                    f"USD {held_usd:,.0f} ({held_pct:.1f}%)",
                    held_usd,
                    "USD",
                ),
                Fact("Unhedged gap", f"USD {gap:,.0f}", gap, "USD"),
            ],
            client_relevance=(
                f"Base currency is {ctx.client.get('base_currency')}, so this is a "
                "translation risk the client may not see on their statement."
            ),
            suggested_next_step=(
                "Decide whether to pre-fund the obligation in its own currency or "
                "accept the spot risk, and record the decision."
            ),
            evidence=[
                Evidence(
                    source_file="market_context.csv",
                    row_or_id=f"USD{currency}",
                    field="value",
                    value=f"{rate_then} -> {rate_now} USD per {currency}",
                    snapshot_date=ctx.snapshot,
                )
            ]
            + [
                Evidence(
                    source_file="planned_cash_needs.csv"
                    if o.source == "planned_cash_needs"
                    else "commitments.csv",
                    row_or_id=o.id,
                    field="currency",
                    value=o.currency,
                    note=o.description,
                )
                for o in lq.obligations
                if o.currency == currency
            ],
            confidence=Confidence.DERIVED,
            amount_usd=gap,
        )
