"""Assembly: the payloads the UI renders.

Two shapes:

* :func:`book_view` -- the ranked workbench across all 20 clients.
* :func:`client_dossier` -- everything about one client, in the order the RM
  reads it: why now, what changed and why, what could happen next, what to
  discuss.

Nothing is computed here. This module joins the analytics, the signals, the
action options and the RM's own decisions into stable JSON.
"""

from __future__ import annotations

from typing import Any

from . import config
from .actions import options_for
from .analytics import income as income_mod
from .analytics import lookthrough
from .analytics.valuation import household_view, household_timeseries
from .brief import build_brief
from .contracts import Insight, InsightStatus
from .loaders import DataBook, get_book
from .review import ReviewStore, get_store
from .signals.base import SignalContext, run_for_client
from .signals.explain import build_explanation


def _apply_decisions(
    insights: list[Insight], store: ReviewStore
) -> list[dict[str, Any]]:
    """Overlay the RM's decisions onto the engine output, without losing either."""
    out: list[dict[str, Any]] = []
    for insight in insights:
        decision = store.get(insight.id)
        payload = insight.to_dict()
        if decision:
            payload["status"] = decision.status
            payload["rm_note"] = decision.rm_note
            payload["selected_option_id"] = decision.selected_option_id
            payload["selected_scenario_id"] = decision.selected_scenario_id
            payload["scenario_calculation_version"] = decision.scenario_calculation_version
            payload["decided_by"] = decision.decided_by
            payload["decided_at"] = decision.decided_at
            if decision.edited_headline:
                payload["headline_original"] = insight.headline
                payload["headline"] = decision.edited_headline
                payload["edited"] = True
            if decision.edited_next_step:
                payload["suggested_next_step_original"] = insight.suggested_next_step
                payload["suggested_next_step"] = decision.edited_next_step
                payload["edited"] = True
        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------


def book_view(book: DataBook | None = None, store: ReviewStore | None = None) -> dict[str, Any]:
    """The morning list: 20 clients ranked by what needs attention first."""
    book = book or get_book()
    store = store or get_store()

    rows: list[dict[str, Any]] = []
    total_aum = 0.0
    for client_id, client in book.clients.items():
        insights = run_for_client(client_id, book)
        live = [i for i in insights if store.status_of(i.id) != "dismissed"]
        view = household_view(book, client_id)
        total_aum += view.total_usd

        top = live[0] if live else None
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        categories: dict[str, int] = {}
        for insight in live:
            severities[insight.severity.value] += 1
            categories[insight.category.value] = (
                categories.get(insight.category.value, 0) + 1
            )

        reviewed = sum(
            1
            for i in insights
            if store.status_of(i.id) in ("rm_reviewed", "client_ready")
        )

        rows.append(
            {
                "client_id": client_id,
                "client_name": client.get("client_name"),
                "booking_centre": client.get("booking_centre"),
                "base_currency": client.get("base_currency"),
                "wealth_band": client.get("wealth_band"),
                "risk_profile": client.get("risk_profile"),
                "life_stage": client.get("life_stage"),
                "total_usd": view.total_usd,
                "priority_score": top.priority_score if top else 0.0,
                "top_headline": top.headline if top else "Nothing outstanding",
                "top_category": top.category.value if top else None,
                "top_severity": top.severity.value if top else "info",
                "why_now": top.priority_reasons if top else [],
                "insight_count": len(live),
                "severity_counts": severities,
                "categories": categories,
                "reviewed_count": reviewed,
                "kyc_review_due": client.get("kyc_review_due"),
            }
        )

    rows.sort(key=lambda r: (-r["priority_score"], r["client_id"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    return {
        "as_of": config.AS_OF,
        "snapshots": [
            {"date": d, "label": config.SNAPSHOT_LABELS.get(d, d)}
            for d in config.SNAPSHOTS
        ],
        "rm": {
            "rm_id": next(iter(book.clients.values())).get("rm_id"),
            "rm_name": next(iter(book.clients.values())).get("rm_name"),
            "rm_desk": next(iter(book.clients.values())).get("rm_desk"),
        },
        "totals": {
            "clients": len(rows),
            "aum_usd": total_aum,
            "insights": sum(r["insight_count"] for r in rows),
            "critical": sum(r["severity_counts"]["critical"] for r in rows),
            "high": sum(r["severity_counts"]["high"] for r in rows),
            "decisions": store.counts(),
        },
        "clients": rows,
        "data_warnings": book.warnings,
        "scoring": {
            "formula": "0.45 x severity + 0.30 x materiality + 0.25 x urgency, scaled to 100",
            "materiality": "share of household wealth affected, capped at 30%",
            "urgency": "days until the driving date, banded",
            "note": (
                "The weights are a judgement, not a discovery. They are stated so they "
                "can be argued with."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Client dossier
# ---------------------------------------------------------------------------


def client_dossier(
    client_id: str, book: DataBook | None = None, store: ReviewStore | None = None
) -> dict[str, Any]:
    book = book or get_book()
    store = store or get_store()
    ctx = SignalContext(book=book, client_id=client_id)
    client = ctx.client

    insights = run_for_client(client_id, book)
    insight_payloads = _apply_decisions(insights, store)

    options: dict[str, list[dict[str, Any]]] = {}
    for insight in insights:
        options[insight.id] = [o.to_dict() for o in options_for(ctx, insight)]

    view = ctx.view
    timeseries = household_timeseries(book, client_id)
    income = income_mod.income_view(book, client_id, view.total_usd)

    portfolios = []
    for pf in book.portfolios_by_client.get(client_id, []):
        review = next(
            (r for r in ctx.mandate_reviews if r.portfolio_id == pf["portfolio_id"]),
            None,
        )
        portfolios.append(
            {
                "portfolio_id": pf["portfolio_id"],
                "portfolio_name": pf.get("portfolio_name"),
                "mandate_code": pf.get("mandate_code"),
                "mandate_name": pf.get("mandate_name"),
                "service_model": pf.get("service_model"),
                "base_currency": pf.get("base_currency"),
                "benchmark": pf.get("benchmark"),
                "inception_date": pf.get("inception_date"),
                "value_usd": view.by_portfolio.get(pf["portfolio_id"], 0.0),
                "aum_series": [
                    {
                        "snapshot": s,
                        "label": config.SNAPSHOT_LABELS.get(s, s),
                        "value_base": book.dated(pf, "aum", s),
                    }
                    for s in config.SNAPSHOTS
                ],
                "mandate_review": review.to_dict() if review else None,
                "bands": (book.mandate_for(pf["portfolio_id"]) or {}).get("bands", {}),
                "mandate_notes": (book.mandate_for(pf["portfolio_id"]) or {}).get("notes"),
            }
        )

    return {
        "as_of": config.AS_OF,
        "client": {
            **{
                key: client.get(key)
                for key in (
                    "client_id",
                    "client_name",
                    "age",
                    "nationality",
                    "country_of_residence",
                    "tax_domicile",
                    "booking_centre",
                    "base_currency",
                    "wealth_band",
                    "life_stage",
                    "source_of_wealth",
                    "risk_profile",
                    "risk_tolerance_score",
                    "investment_horizon_years",
                    "liquidity_needs",
                    "objectives",
                    "client_since",
                    "kyc_review_due",
                    "reporting_language",
                    "rm_name",
                )
            },
            "total_usd": view.total_usd,
        },
        "portfolios": portfolios,
        "wealth": {
            "total_usd": view.total_usd,
            "timeseries": [
                {
                    "snapshot": p.snapshot,
                    "label": p.label,
                    "total_usd": p.total_usd,
                    "change_usd": p.change_usd,
                    "change_pct": p.change_pct,
                }
                for p in timeseries
            ],
            "by_asset_class": view.by_asset_class,
            "by_liquidity_tier": view.by_liquidity_tier,
            "by_currency": view.by_currency,
            "by_region": view.by_region,
            "by_sector": view.by_sector,
            "positions": [p.to_dict() for p in view.positions],
        },
        "income": income.to_dict(),
        "explanation": {
            "ytd": build_explanation(ctx, "ytd"),
            "recent": build_explanation(ctx, "recent"),
        },
        "exposures": {
            "issuers": [e.to_dict() for e in ctx.issuer_exposures],
            "themes": [e.to_dict() for e in ctx.theme_exposures],
            "unresolved": lookthrough.unresolved_notes(view),
        },
        "liquidity": ctx.liquidity.to_dict(),
        "facilities": [f.to_dict() for f in ctx.facilities],
        "insights": insight_payloads,
        "options": options,
        "brief": build_brief(ctx, insights).to_dict(),
        "notes": [
            {
                "note_id": n["note_id"],
                "note_date": n["note_date"],
                "channel": n["channel"],
                "rm_name": n["rm_name"],
                "note": n["note"],
            }
            for n in ctx.notes
        ],
        "events": [
            {
                "event_id": e["event_id"],
                "event_date": e["event_date"],
                "event_type": e["event_type"],
                "region": e["region"],
                "description": e["description"],
                "primary_transmission": e["primary_transmission"],
                "severity": e["severity"],
            }
            for e in lookthrough.events_for_themes(book, ctx.theme_exposures)
        ],
        "market": {
            "series": [
                {
                    **book.market_meta[series_id],
                    "points": [
                        {"snapshot": s, "value": book.market_value(series_id, s)}
                        for s in config.SNAPSHOTS
                    ],
                }
                for series_id in (
                    "BRENT_USD_BBL",
                    "GOLD_USD_OZ",
                    "UST_10Y_PCT",
                    "NASDAQ_COMP",
                    "HSI",
                    "VIX",
                )
                if series_id in book.market_meta
            ]
        },
        "audit": [e.to_dict() for e in store.audit(client_id)],
    }


def all_events(book: DataBook | None = None) -> list[dict[str, Any]]:
    book = book or get_book()
    return [
        {
            "event_id": e["event_id"],
            "event_date": e["event_date"],
            "event_type": e["event_type"],
            "region": e["region"],
            "description": e["description"],
            "primary_transmission": e["primary_transmission"],
            "transmission_channels": e["transmission_channels"],
            "severity": e["severity"],
        }
        for e in book.events
    ]
