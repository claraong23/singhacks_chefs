"""Deterministic current-state scenario comparisons for the three anchor journeys.

This module intentionally does not forecast markets, choose securities, model
tax outcomes, or optimise a portfolio.  It applies bounded RM inputs to facts
already calculated by Tasks 1 and 2, then makes assumptions and limitations
visible beside the arithmetic.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import config
from .actions import options_for
from .analytics import mandate as mandate_mod
from .contracts import (
    Assumption,
    Evidence,
    ScenarioInput,
    ScenarioMetric,
    ScenarioResult,
    ScenarioTemplate,
)
from .loaders import DataBook, get_book
from .signals.base import SignalContext, run_for_client

LAU_TEMPLATE = "lau-collateral-liquidity"
MARGARETHE_TEMPLATE = "margarethe-mandate-tax-reserve"
FONG_TEMPLATE = "fong-commitment-liquidity"


def _insight(ctx: SignalContext, insight_id: str):
    return next((item for item in run_for_client(ctx.client_id, ctx.book) if item.id == insight_id), None)


def _input(template: ScenarioTemplate, raw: dict[str, Any] | None) -> dict[str, float]:
    raw = raw or {}
    allowed = {item.key: item for item in template.inputs}
    unexpected = set(raw) - set(allowed)
    if unexpected:
        raise ValueError(f"Unsupported scenario input(s): {', '.join(sorted(unexpected))}")
    values: dict[str, float] = {}
    for key, definition in allowed.items():
        value = raw.get(key, definition.default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{definition.label} must be numeric.")
        numeric = float(value)
        if numeric < definition.minimum or numeric > definition.maximum:
            raise ValueError(
                f"{definition.label} must be between {definition.minimum:g} and {definition.maximum:g} {definition.unit}."
            )
        # Inputs step in the UI; permit harmless float representation noise.
        values[key] = numeric
    return values


def _version(template_id: str, inputs: dict[str, float], evidence: list[Evidence]) -> str:
    raw = json.dumps(
        {
            "template": template_id,
            "as_of": config.AS_OF,
            "inputs": inputs,
            "evidence": [item.to_dict() for item in evidence],
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _metric(
    key: str,
    label: str,
    baseline: float | None,
    scenario: float | None,
    unit: str,
    detail: str = "",
) -> ScenarioMetric:
    return ScenarioMetric(key, label, baseline, scenario, unit, True, detail)


def _unavailable(key: str, label: str, detail: str) -> ScenarioMetric:
    return ScenarioMetric(key, label, None, None, "", False, detail)


def templates_for_client(client_id: str, book: DataBook | None = None) -> list[ScenarioTemplate]:
    book = book or get_book()
    if client_id not in book.clients:
        raise ValueError(f"Unknown client {client_id}")
    ctx = SignalContext(book=book, client_id=client_id)

    if client_id == "CL-0014":
        facility = next((item for item in ctx.facilities if item.facility_id == "CF-0002"), None)
        insight_id = "CL-0014-collateral-CF-0002"
        if facility and _insight(ctx, insight_id):
            current_ltv = facility.current.ltv_pct or facility.margin_call_ltv_pct
            safe_ceiling = min(current_ltv, facility.margin_call_ltv_pct - config.LTV_WARN_HEADROOM_PP)
            need = next((item for item in book.cash_needs_by_client[client_id] if item["need_id"] == "CN-013"), None)
            if need:
                return [
                    ScenarioTemplate(
                        LAU_TEMPLATE,
                        client_id,
                        insight_id,
                        "Collateral and redevelopment funding",
                        "Compare a cash repayment and a ring-fenced redevelopment reserve against current collateral and liquidity.",
                        [
                            ScenarioInput(
                                "target_ltv_pct", "Target loan-to-value", "%", 10.0,
                                round(safe_ceiling, 2), 0.5, round(safe_ceiling, 2),
                                "Bounded below the current level and the facility warning ceiling.",
                            ),
                            ScenarioInput(
                                "redevelopment_reserve_hkd", "Redevelopment reserve", "HKD", 0.0,
                                float(need["amount"]), 1_000_000.0, float(need["amount"]) * 0.25,
                                "Cannot exceed the confirmed HKD 60m contribution.",
                            ),
                        ],
                    )
                ]

    if client_id == "CL-0003":
        review = next((item for item in ctx.mandate_reviews if item.portfolio_id == "PF-0005"), None)
        insight_id = "CL-0003-bands-PF-0005"
        need = next((item for item in book.cash_needs_by_client[client_id] if item["need_id"] == "CN-004"), None)
        if review and need and _insight(ctx, insight_id):
            equity = next((item for item in review.band_breaches if item.asset_class == "Equity"), None)
            band = book.mandates[review.mandate_code]["bands"].get("Equity", {})
            if equity and band:
                return [
                    ScenarioTemplate(
                        MARGARETHE_TEMPLATE,
                        client_id,
                        insight_id,
                        "Mandate correction and tax-installment reserve",
                        "Compare a governed equity-band correction with a ring-fenced cash reserve; no tax consequence is calculated.",
                        [
                            ScenarioInput(
                                "equity_target_pct", "Equity allocation target", "%", float(band["min_pct"]),
                                float(band["max_pct"]), 1.0, float(band["target_pct"]),
                                "Constrained to the recorded Conservative mandate band.",
                            ),
                            ScenarioInput(
                                "tax_reserve_eur", "Tax-installment reserve", "EUR", 0.0,
                                float(need["amount"]), 100_000.0, float(need["amount"]),
                                "Cannot exceed the confirmed German inheritance-tax instalment.",
                            ),
                        ],
                    )
                ]

    if client_id == "CL-0017":
        insight_id = "CL-0017-sleeve-PF-0020"
        if _insight(ctx, insight_id):
            return [
                ScenarioTemplate(
                    FONG_TEMPLATE,
                    client_id,
                    insight_id,
                    "Commitment reserve and funding sequence",
                    "Compare the current liquidity map with a reserve for uncalled commitments; gated assets remain unavailable.",
                    [
                        ScenarioInput(
                            "commitment_reserve_pct", "Commitment reserve", "%", 0.0, 100.0,
                            5.0, 50.0, "Percentage of current uncalled commitments to ring-fence.",
                        ),
                        ScenarioInput(
                            "review_horizon_months", "Funding-plan review horizon", "months", 3.0,
                            24.0, 1.0, 12.0, "A planning horizon, not a capital-call forecast.",
                        ),
                        ScenarioInput(
                            "funding_tranches", "Funding-plan tranches", "tranches", 1.0, 4.0,
                            1.0, 2.0, "Number of planned review tranches within the selected horizon.",
                        ),
                    ],
                )
            ]
    return []


def _assert_option(ctx: SignalContext, insight_id: str, option_id: str) -> None:
    insight = _insight(ctx, insight_id)
    if insight is None:
        raise ValueError(f"Unknown insight {insight_id} for client {ctx.client_id}")
    if option_id not in {option.id for option in options_for(ctx, insight)}:
        raise ValueError(f"Unknown action option {option_id} for insight {insight_id}")


def evaluate_scenario(
    *,
    client_id: str,
    template_id: str,
    insight_id: str,
    option_id: str,
    inputs: dict[str, Any] | None,
    book: DataBook | None = None,
) -> ScenarioResult:
    """Evaluate one bounded anchor-client scenario from the current source data."""
    book = book or get_book()
    templates = templates_for_client(client_id, book)
    template = next((item for item in templates if item.id == template_id), None)
    if template is None or template.insight_id != insight_id:
        raise ValueError(f"Scenario template {template_id!r} is not supported for this finding.")
    ctx = SignalContext(book=book, client_id=client_id)
    _assert_option(ctx, insight_id, option_id)
    values = _input(template, inputs)

    if template_id == LAU_TEMPLATE:
        return _lau(ctx, template, option_id, values)
    if template_id == MARGARETHE_TEMPLATE:
        return _margarethe(ctx, template, option_id, values)
    if template_id == FONG_TEMPLATE:
        return _fong(ctx, template, option_id, values)
    raise ValueError(f"No evaluator is registered for {template_id}")


def _lau(ctx: SignalContext, template: ScenarioTemplate, option_id: str, values: dict[str, float]) -> ScenarioResult:
    facility = next(item for item in ctx.facilities if item.facility_id == "CF-0002")
    need = next(item for item in ctx.book.cash_needs_by_client[ctx.client_id] if item["need_id"] == "CN-013")
    current = facility.current
    lending_value = current.lending_value or 0.0
    drawn = current.drawn or 0.0
    target = values["target_ltv_pct"] / 100
    repayment = max(0.0, drawn - target * lending_value)
    resulting_ltv = ((drawn - repayment) / lending_value * 100) if lending_value else None
    reserve_usd = ctx.book.to_usd(values["redevelopment_reserve_hkd"], "HKD", ctx.snapshot) or 0.0
    obligation_usd = ctx.book.to_usd(need["amount"], "HKD", ctx.snapshot) or 0.0
    evidence = [*facility.evidence()[:3], Evidence("planned_cash_needs.csv", "CN-013", "amount", need["amount"], note=need["description"])]
    metrics = [
        _metric("ltv", "Loan-to-value", current.ltv_pct, resulting_ltv, "%", "Cash repayment leaves lending value unchanged in this current-state comparison."),
        _metric("lending_value", "Lending value", lending_value, lending_value, facility.currency),
        _metric("repayment", "Cash repayment required", 0.0, repayment, facility.currency),
        _metric("withdrawable", "Unreserved withdrawable liquidity", ctx.liquidity.withdrawable_usd, max(0.0, ctx.liquidity.withdrawable_usd - reserve_usd), "USD"),
        _metric("redevelopment_coverage", "Redevelopment reserve coverage", 0.0, reserve_usd / obligation_usd * 100 if obligation_usd else None, "%"),
        _unavailable("market_impact", "Market-price impact", "Not modelled: no market-price or execution forecast is used."),
    ]
    assumptions = [
        Assumption("Repayment is funded without selling pledged collateral.", "The model does not choose assets or forecast execution.", "A collateral sale would also change lending value and requires separate credit review."),
        Assumption("The redevelopment contribution remains HKD 60m.", "planned_cash_needs.csv CN-013", "The reserve must be refreshed if the contribution or timing changes."),
    ]
    return ScenarioResult(template.id, ctx.client_id, template.insight_id, option_id, template.title, ctx.snapshot, values, assumptions, metrics, evidence, [], _version(template.id, values, evidence))


def _margarethe(ctx: SignalContext, template: ScenarioTemplate, option_id: str, values: dict[str, float]) -> ScenarioResult:
    review = next(item for item in ctx.mandate_reviews if item.portfolio_id == "PF-0005")
    equity = next(item for item in review.band_breaches if item.asset_class == "Equity")
    need = next(item for item in ctx.book.cash_needs_by_client[ctx.client_id] if item["need_id"] == "CN-004")
    reserve_usd = ctx.book.to_usd(values["tax_reserve_eur"], "EUR", ctx.snapshot) or 0.0
    due_usd = ctx.book.to_usd(need["amount"], "EUR", ctx.snapshot) or 0.0
    target = values["equity_target_pct"]
    evidence = [
        Evidence("mandates.csv", review.mandate_code, "Equity band", {"min": equity.min_pct, "target": equity.target_pct, "max": equity.max_pct}, snapshot_date=ctx.snapshot),
        Evidence("planned_cash_needs.csv", "CN-004", "amount", need["amount"], note=need["description"]),
    ]
    metrics = [
        _metric("equity_allocation", "Governed equity allocation", equity.actual_pct, target, "%"),
        _metric("equity_band_gap", "Distance above maximum equity band", max(0.0, equity.actual_pct - equity.max_pct), max(0.0, target - equity.max_pct), "pp"),
        _metric("reserve_coverage", "Tax-installment reserve coverage", 0.0, reserve_usd / due_usd * 100 if due_usd else None, "%"),
        _metric("withdrawable", "Unreserved withdrawable liquidity", ctx.liquidity.withdrawable_usd, max(0.0, ctx.liquidity.withdrawable_usd - reserve_usd), "USD"),
        _unavailable("tax_outcome", "Tax outcome", "Not modelled: tax lots and jurisdictional calculations are incomplete and require wealth-planning review."),
    ]
    assumptions = [
        Assumption("The allocation correction transfers the equity weight to cash for comparison only.", "No target security or execution route is selected.", "Actual implementation needs client instruction and mandate/suitability checks."),
        Assumption("The EUR reserve is ring-fenced from currently withdrawable liquidity.", "planned_cash_needs.csv CN-004", "It does not establish tax treatment or confirm funding availability."),
    ]
    blockers = ["Tax outcome remains blocked pending wealth-planning review and complete tax-lot data."]
    return ScenarioResult(template.id, ctx.client_id, template.insight_id, option_id, template.title, ctx.snapshot, values, assumptions, metrics, evidence, blockers, _version(template.id, values, evidence))


def _fong(ctx: SignalContext, template: ScenarioTemplate, option_id: str, values: dict[str, float]) -> ScenarioResult:
    commitments = ctx.book.commitments_by_client[ctx.client_id]
    uncalled_usd = sum(
        ctx.book.to_usd(item["uncalled"], item["currency"], ctx.snapshot) or 0.0
        for item in commitments
    )
    reserve = uncalled_usd * values["commitment_reserve_pct"] / 100
    evidence = [
        Evidence("commitments.csv", item["commitment_id"], "uncalled", item["uncalled"], note=item["expected_call_window"])
        for item in commitments
    ] + ctx.liquidity.evidence()[:3]
    metrics = [
        _metric("uncalled_commitments", "Uncalled commitments", uncalled_usd, uncalled_usd, "USD"),
        _metric("reserve", "Ring-fenced commitment reserve", 0.0, reserve, "USD"),
        _metric("reserve_coverage", "Commitment reserve coverage", 0.0, values["commitment_reserve_pct"], "%"),
        _metric("uncovered", "Uncovered commitments", uncalled_usd, max(0.0, uncalled_usd - reserve), "USD"),
        _metric("withdrawable", "Unreserved withdrawable liquidity", ctx.liquidity.withdrawable_usd, max(0.0, ctx.liquidity.withdrawable_usd - reserve), "USD", "Uses withdrawable liquidity only; gated assets are excluded."),
        _metric("gated", "Gated assets excluded from funding", ctx.liquidity.gated_usd, ctx.liquidity.gated_usd, "USD"),
        _unavailable("call_dates", "Capital-call dates", "Not modelled: commitment windows are not deterministic capital-call dates."),
    ]
    assumptions = [
        Assumption("Reserve is set against uncalled commitments, not a forecast of call timing.", "commitments.csv", "Actual calls may differ in amount and date within the manager's window."),
        Assumption("Gated assets are unavailable for the funding plan.", "holdings.csv liquidity tiers", "Manager confirmation is required before relying on any redemption."),
    ]
    blockers = ["Funding sequence requires manager confirmation for gated holdings and RM/specialist review before commitment funding is represented to the client."]
    return ScenarioResult(template.id, ctx.client_id, template.insight_id, option_id, template.title, ctx.snapshot, values, assumptions, metrics, evidence, blockers, _version(template.id, values, evidence))
