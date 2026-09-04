"""Planning signals: income, life events, tax position and dealing constraints.

These are the checks that come from reading ``objectives``, ``life_stage`` and
``planned_cash_needs.csv`` next to the portfolio. They tend not to look urgent
in a risk report and are usually the reason a client picked up the phone.
"""

from __future__ import annotations

from typing import Iterable

from .. import config
from ..analytics.income import RUN_RATE_ASSUMPTION, income_view
from ..analytics.liquidity import ANNUAL_ASSUMPTION, annual_amount
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
from ..loaders import parse_date
from .base import SignalContext, priority, signal


@signal("income_versus_drawdown")
def income_versus_drawdown(ctx: SignalContext) -> Iterable[Insight]:
    """Can the portfolio fund a recurring drawdown without selling capital?"""
    recurring = [
        n
        for n in ctx.book.cash_needs_by_client.get(ctx.client_id, [])
        if "annual" in (n.get("recurrence") or "").lower()
    ]
    if not recurring:
        return

    income = income_view(ctx.book, ctx.client_id, ctx.view.total_usd)
    required_usd = sum(
        ctx.book.to_usd(annual_amount(n), n.get("currency", "USD"), ctx.snapshot) or 0.0
        for n in recurring
    )
    if required_usd <= 0:
        return

    cover = income.annualised_net_usd / required_usd if required_usd else None
    starts = [parse_date(n.get("due_from") or "") for n in recurring]
    starts = [s for s in starts if s]
    days = ctx.days_until(min(starts).isoformat()) if starts else None

    if cover is not None and cover >= 1.25:
        severity = Severity.LOW
    elif cover is not None and cover >= 1.0:
        severity = Severity.MEDIUM
    else:
        severity = Severity.HIGH

    # A comfortable cover ratio is only worth surfacing when the client has
    # told us they are worried about it.
    worry_notes = ctx.notes_matching(
        "without touching capital", "lost money", "red", "deposits", "safe part"
    )
    if severity == Severity.LOW and not worry_notes:
        return

    score, reasons = priority(
        severity,
        materiality_pct=ctx.view.weight(required_usd),
        days_until=days,
        amount_usd=required_usd,
    )

    yield Insight(
        id=f"{ctx.client_id}-income-cover",
        client_id=ctx.client_id,
        category=Category.LIFE_EVENT,
        severity=severity,
        headline=(
            f"Portfolio income covers {cover:.2f}x the client's planned annual "
            f"drawdown"
            if cover is not None
            else "Planned drawdown against portfolio income"
        ),
        summary=(
            f"Recorded annual needs total USD {required_usd:,.0f}. Income received in "
            f"2026 annualises to USD {income.annualised_gross_usd:,.0f} gross and "
            f"USD {income.annualised_net_usd:,.0f} after fees and facility interest, "
            f"a yield of {income.yield_pct:.2f}% on household wealth."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact(
                "Annual need",
                f"USD {required_usd:,.0f}",
                required_usd,
                "USD",
            ),
            Fact(
                "Gross income run rate",
                f"USD {income.annualised_gross_usd:,.0f}",
                income.annualised_gross_usd,
                "USD",
            ),
            Fact(
                "Net of fees and facility interest",
                f"USD {income.annualised_net_usd:,.0f}",
                income.annualised_net_usd,
                "USD",
            ),
            Fact("Portfolio yield", f"{income.yield_pct:.2f}%", income.yield_pct, "%"),
            Fact(
                "Cover",
                f"{cover:.2f}x" if cover else "not computable",
                cover,
                "x",
            ),
        ]
        + [
            Fact(
                n.get("description", ""),
                f"{n.get('currency')} {annual_amount(n):,.0f} per year from "
                f"{n.get('due_from')} ({n.get('recurrence')}, {n.get('certainty')})",
                annual_amount(n),
                n.get("currency"),
            )
            for n in recurring
        ],
        client_relevance=(
            "Income that covers the drawdown means capital does not have to be sold "
            "into a weak market to fund living costs. Where cover is thin, the "
            "sequence of returns starts to matter more than the average."
        ),
        suggested_next_step=(
            "Confirm the drawdown amount and timing, then check the income is durable "
            "rather than a one-off distribution."
        ),
        evidence=income.evidence()
        + [
            Evidence(
                source_file="planned_cash_needs.csv",
                row_or_id=n["need_id"],
                field="amount",
                value=f"{n.get('currency')} {n.get('amount'):,.0f}",
                note=f"{n.get('description')} ({n.get('recurrence')}, {n.get('certainty')}).",
            )
            for n in recurring
        ]
        + [
            Evidence(
                source_file="rm_notes.json",
                row_or_id=n["note_id"],
                field="note",
                value=n["note"],
                snapshot_date=n["note_date"],
                note="RM note. Client's framing, not independently verified.",
            )
            for n in worry_notes[-1:]
        ],
        assumptions=[RUN_RATE_ASSUMPTION, ANNUAL_ASSUMPTION],
        suitability_checks=[
            SuitabilityCheck(
                check="Income objective",
                result="pass" if cover and cover >= 1 else "attention",
                detail=ctx.client.get("objectives", ""),
                reference="clients.csv",
            )
        ],
        confidence=Confidence.DERIVED,
        amount_usd=required_usd,
    )


@signal("loss_aversion_and_horizon")
def loss_aversion_and_horizon(ctx: SignalContext) -> Iterable[Insight]:
    """A client refusing to sell at a loss, against the maturity they would wait for.

    The arithmetic here is deliberately plain: a client's age and the maturity of
    the position they intend to hold to par. Where the second outlives the first,
    "wait for it to come back" is not a plan.
    """
    notes = ctx.notes_matching(
        "does not want to sell", "not want to sell at a loss", "wait for the bonds"
    )
    if not notes:
        return

    losers = [
        p
        for p in ctx.view.positions
        if p.unrealised_pnl_usd < 0 and abs(p.unrealised_pnl_usd) > 250_000
    ]
    if not losers:
        return

    total_loss = sum(p.unrealised_pnl_usd for p in losers)
    age = ctx.client.get("age")
    horizon = ctx.client.get("investment_horizon_years")

    # Maturity years mentioned in instrument names, e.g. "due 2045".
    long_dated = []
    for p in losers:
        for token in p.instrument_name.replace(",", " ").split():
            if token.isdigit() and 2026 < int(token) < 2100:
                long_dated.append((p, int(token)))
                break
        else:
            if "perpetual" in p.instrument_name.lower():
                long_dated.append((p, None))

    severity = Severity.HIGH
    score, reasons = priority(
        severity,
        materiality_pct=ctx.view.weight(abs(total_loss)),
        amount_usd=abs(total_loss),
    )

    facts = [
        Fact(
            "Unrealised loss on affected positions",
            f"USD {total_loss:,.0f}",
            total_loss,
            "USD",
            "down",
        ),
        Fact("Client age", str(age), age),
        Fact("Recorded investment horizon", f"{horizon} years", horizon, "years"),
    ]
    for p, maturity in long_dated:
        if maturity and age:
            facts.append(
                Fact(
                    p.instrument_name,
                    f"USD {p.unrealised_pnl_usd:,.0f} unrealised "
                    f"({p.unrealised_pnl_pct:.1f}%); matures {maturity}, when the "
                    f"client would be {age + (maturity - 2026)}",
                    p.unrealised_pnl_usd,
                    "USD",
                )
            )
        else:
            facts.append(
                Fact(
                    p.instrument_name,
                    f"USD {p.unrealised_pnl_usd:,.0f} unrealised "
                    f"({p.unrealised_pnl_pct:.1f}%); perpetual, no maturity date",
                    p.unrealised_pnl_usd,
                    "USD",
                )
            )

    yield Insight(
        id=f"{ctx.client_id}-loss-aversion",
        client_id=ctx.client_id,
        category=Category.SUITABILITY,
        severity=severity,
        headline=(
            "Client intends to hold losing positions to recovery, but the recovery "
            "date outlasts the plan"
        ),
        summary=(
            f"USD {abs(total_loss):,.0f} of unrealised losses sits in positions the "
            f"client has said they will not sell. "
            + (
                "At least one has no maturity date at all, so par recovery is not a "
                "date that can be waited for."
                if any(m is None for _, m in long_dated)
                else ""
            )
            + " The conversation is about whether holding is a decision or an avoidance."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=facts,
        client_relevance=(
            "Duration losses recover as bonds pull to par, but only if the client is "
            "still holding them at maturity and does not need the capital first."
        ),
        suggested_next_step=(
            "Show the recovery path with dates attached, then offer a partial switch "
            "that shortens duration without crystallising the whole loss at once."
        ),
        evidence=[
            Evidence(
                source_file="holdings.csv",
                row_or_id=p.instrument_id,
                field="unrealised_pnl_base",
                value=f"USD {p.unrealised_pnl_usd:,.0f} ({p.unrealised_pnl_pct:.1f}%)",
                snapshot_date=ctx.snapshot,
                note=p.instrument_name,
            )
            for p in losers
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
            for n in notes[-1:]
        ]
        + [
            Evidence(
                source_file="clients.csv",
                row_or_id=ctx.client_id,
                field="age",
                value=age,
            )
        ],
        assumptions=[
            Assumption(
                statement="Maturity is read from the instrument name.",
                basis="instruments.csv does not carry a separate maturity column.",
                impact_if_wrong="Check the term sheet before quoting a date to a client.",
            )
        ],
        confidence=Confidence.REPORTED,
        instrument_ids=[p.instrument_id for p in losers],
        amount_usd=abs(total_loss),
        open_questions=[
            "Would the client accept a switch that keeps the coupon but shortens duration?",
        ],
    )


@signal("tax_domicile_planning")
def tax_domicile_planning(ctx: SignalContext) -> Iterable[Insight]:
    """Flag a tax-sensitive decision without pretending to compute a tax outcome."""
    domicile = ctx.client.get("tax_domicile")
    residence = ctx.client.get("country_of_residence")
    objectives = (ctx.client.get("objectives") or "").lower()

    tax_needs = [
        n
        for n in ctx.book.cash_needs_by_client.get(ctx.client_id, [])
        if "tax" in (n.get("description") or "").lower()
        or "succession" in (n.get("description") or "").lower()
        or "estate" in (n.get("description") or "").lower()
    ]
    tax_objective = any(
        word in objectives for word in ("tax", "inheritance", "succession", "estate")
    )
    if not tax_needs and not tax_objective:
        return

    gains = sum(p.unrealised_pnl_usd for p in ctx.view.positions if p.unrealised_pnl_usd > 0)
    losses = sum(p.unrealised_pnl_usd for p in ctx.view.positions if p.unrealised_pnl_usd < 0)

    nearest = min(
        (n for n in tax_needs if n.get("due_from")),
        key=lambda n: n["due_from"],
        default=None,
    )
    days = ctx.days_until(nearest["due_from"]) if nearest else None
    severity = Severity.HIGH if days is not None and days < 180 else Severity.MEDIUM

    amount_usd = (
        ctx.book.to_usd(
            nearest.get("amount") or 0.0, nearest.get("currency", "USD"), ctx.snapshot
        )
        if nearest
        else None
    )
    score, reasons = priority(
        severity,
        materiality_pct=ctx.view.weight(amount_usd or 0.0) if amount_usd else None,
        days_until=days,
        amount_usd=amount_usd,
    )

    yield Insight(
        id=f"{ctx.client_id}-tax",
        client_id=ctx.client_id,
        category=Category.TAX,
        severity=severity,
        headline=(
            f"Tax-sensitive decision ahead under {domicile} domicile"
            + (
                f", with {nearest['currency']} {nearest['amount']:,.0f} due from "
                f"{nearest['due_from']}"
                if nearest
                else ""
            )
        ),
        summary=(
            f"Tax domicile is {domicile} while country of residence is {residence}. "
            "Domicile governs the treatment, and this engine does not calculate tax "
            "outcomes: it flags that funding this from the portfolio is a decision "
            "with a tax dimension that needs the wealth planning team."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact("Tax domicile", domicile),
            Fact("Country of residence", residence),
            Fact(
                "Unrealised gains in the household",
                f"USD {gains:,.0f}",
                gains,
                "USD",
            ),
            Fact(
                "Unrealised losses in the household",
                f"USD {losses:,.0f}",
                losses,
                "USD",
            ),
        ]
        + [
            Fact(
                n.get("description", ""),
                f"{n.get('currency')} {n.get('amount'):,.0f}, "
                f"{n.get('due_from')} to {n.get('due_to')} ({n.get('certainty')})",
                n.get("amount"),
                n.get("currency"),
            )
            for n in tax_needs
        ],
        client_relevance=(
            "Which positions are sold, and in what order, changes the outcome. Gains "
            "and losses within the household can be considered together."
        ),
        suggested_next_step=(
            "Involve wealth planning before any disposal, and prepare a funding "
            "shortlist ranked by tax impact rather than by liquidity alone."
        ),
        evidence=[
            Evidence(
                source_file="clients.csv",
                row_or_id=ctx.client_id,
                field="tax_domicile",
                value=domicile,
                note="Domicile, not residence, governs the treatment.",
            )
        ]
        + [
            Evidence(
                source_file="planned_cash_needs.csv",
                row_or_id=n["need_id"],
                field="amount",
                value=f"{n.get('currency')} {n.get('amount'):,.0f}",
                note=f"{n.get('description')} ({n.get('certainty')}).",
            )
            for n in tax_needs
        ],
        assumptions=[
            Assumption(
                statement="No tax figure is calculated.",
                basis=(
                    "The dataset does not carry the residency history, allowances or "
                    "acquisition dates a calculation would need."
                ),
                impact_if_wrong="None. The gap is stated rather than filled.",
            )
        ],
        suitability_checks=[
            SuitabilityCheck(
                check="Tax advice boundary",
                result="attention",
                detail=(
                    "Clarity does not give tax advice. This routes to wealth planning."
                ),
            )
        ],
        confidence=Confidence.MEASURED,
        amount_usd=amount_usd,
        open_questions=[
            "Has the wealth planning team already been engaged on this?",
            "Are there prior-year losses available within the household?",
        ],
    )


@signal("dealing_restrictions")
def dealing_restrictions(ctx: SignalContext) -> Iterable[Insight]:
    """Positions the client cannot trade freely, whatever the analysis says."""
    notes = ctx.notes_matching(
        "dealing restrictions", "closed period", "open window", "board position"
    )
    if not notes:
        return

    score, reasons = priority(Severity.MEDIUM, materiality_pct=None)
    yield Insight(
        id=f"{ctx.client_id}-dealing-restrictions",
        client_id=ctx.client_id,
        category=Category.SUITABILITY,
        severity=Severity.MEDIUM,
        headline="Trading in at least one position is restricted by the client's role",
        summary=(
            "An RM note records dealing restrictions. Any recommendation touching the "
            "affected position has to be timed around the permitted window, so it "
            "belongs in the plan rather than in the next call."
        ),
        priority_score=score,
        priority_reasons=reasons,
        observed_facts=[
            Fact("RM note", n["note"], None, None) for n in notes[-1:]
        ],
        client_relevance=(
            "A restriction is a constraint on execution, not on planning. The decision "
            "can be agreed now and executed when the window opens."
        ),
        suggested_next_step=(
            "Confirm the next open window in writing and diarise the action against it."
        ),
        evidence=[
            Evidence(
                source_file="rm_notes.json",
                row_or_id=n["note_id"],
                field="note",
                value=n["note"],
                snapshot_date=n["note_date"],
                note="RM note. Not independently verified against a compliance record.",
            )
            for n in notes
        ],
        confidence=Confidence.REPORTED,
    )
