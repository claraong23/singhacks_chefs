"""Holding-level explanation service.

Links an individual holding's movement across two snapshots to:
1. Grounded events from event_log.csv during that window.
2. Transmission channels (energy shock, rate impulse, technology capex, etc.).
3. The specific client's context (risk profile, mandate limits, planned cash needs).
4. Explicit uncertainties (unverified links, stale valuation marks).
"""

from __future__ import annotations

from typing import Any

from .. import config
from ..analytics.attribution import _positions
from ..contracts import Evidence, HoldingExplanation
from ..loaders import DataBook


def explain_holding(
    book: DataBook,
    client_id: str,
    instrument_id: str,
    start: str = config.BASELINE_SNAPSHOT,
    end: str = config.AS_OF,
    portfolio_id: str | None = None,
) -> HoldingExplanation:
    """Produce a deterministic, evidence-backed explanation for a single holding's move."""
    client = book.clients.get(client_id, {})
    instrument = book.instrument(instrument_id)
    name = instrument.get("instrument_name", instrument_id)
    asset_class = instrument.get("asset_class", "")
    sector = instrument.get("sector", "")
    region = instrument.get("region", "")
    currency = instrument.get("currency", "USD")
    underlying = instrument.get("underlying_reference", "")
    liquidity_tier = instrument.get("liquidity_tier", "Daily")

    before = _positions(book, client_id, start, portfolio_id)
    after = _positions(book, client_id, end, portfolio_id)

    total_start = sum(p["market_value_usd"] for p in before.values())
    total_end = sum(p["market_value_usd"] for p in after.values())

    b = before.get(instrument_id, {})
    a = after.get(instrument_id, {})

    q0 = b.get("quantity", 0.0)
    q1 = a.get("quantity", 0.0)
    p0 = b.get("price_local") or instrument.get(f"price_{start}")
    p1 = a.get("price_local") or instrument.get(f"price_{end}")
    val0 = b.get("market_value_usd", 0.0)
    val1 = a.get("market_value_usd", 0.0)
    val_delta = val1 - val0
    wt0 = round(val0 / total_start * 100, 2) if total_start > 0 else 0.0
    wt1 = round(val1 / total_end * 100, 2) if total_end > 0 else 0.0
    wt_delta = round(wt1 - wt0, 2)
    p_ret = round(((p1 / p0) - 1.0) * 100, 2) if p0 and p1 and p0 > 0 else None

    what_changed = {
        "start_snapshot": start,
        "end_snapshot": end,
        "start_quantity": q0,
        "end_quantity": q1,
        "quantity_change": round(q1 - q0, 4),
        "start_price": p0,
        "end_price": p1,
        "price_return_pct": p_ret,
        "start_value_usd": round(val0, 2),
        "end_value_usd": round(val1, 2),
        "value_change_usd": round(val_delta, 2),
        "start_weight_pct": wt0,
        "end_weight_pct": wt1,
        "weight_change_pct": wt_delta,
        "currency": currency,
        "liquidity_tier": liquidity_tier,
    }

    # Find relevant events in event_log.csv occurring within [start, end]
    matching_events: list[dict[str, Any]] = []
    transmissions: list[str] = []
    source_evidence: list[Evidence] = []

    # Keywords for matching
    keywords = set()
    for item in [sector, region, asset_class, underlying, name]:
        if item:
            for word in item.replace("-", " ").replace("/", " ").split():
                clean = word.strip(" ,.").lower()
                if len(clean) >= 4 and clean not in ("fund", "equity", "global", "group", "core", "index"):
                    keywords.add(clean)

    for event in book.events:
        e_date = event.get("event_date", "")
        if not (start <= e_date <= end):
            continue
        e_trans = event.get("primary_transmission", "").lower()
        e_desc = event.get("description", "").lower()
        matched_kw = [kw for kw in keywords if kw in e_trans or kw in e_desc]
        if matched_kw or (asset_class == "Commodities" and "gold" in e_trans and "gold" in name.lower()):
            matching_events.append({
                "event_id": event.get("event_id", f"EVT-{e_date}"),
                "event_date": e_date,
                "event_type": event.get("event_type", ""),
                "region": event.get("region", ""),
                "description": event.get("description", ""),
                "primary_transmission": event.get("primary_transmission", ""),
                "severity": event.get("severity", ""),
            })
            transmissions.append(
                f"{e_date} ({event.get('severity')}): {event.get('description')} "
                f"[Transmission: {event.get('primary_transmission')}]"
            )
            source_evidence.append(
                Evidence(
                    source_file="event_log.csv",
                    row_or_id=event.get("event_id", e_date),
                    field="primary_transmission",
                    value=event.get("primary_transmission", ""),
                    snapshot_date=e_date,
                    note=f"Event cited: {event.get('description')}",
                )
            )

    # Add holdings evidence
    source_evidence.append(
        Evidence(
            source_file="holdings.csv",
            row_or_id=instrument_id,
            field="market_value_usd",
            value=f"USD {val0:,.0f} -> USD {val1:,.0f} ({val_delta:+,.0f})",
            snapshot_date=end,
            note=f"Position weight: {wt0}% -> {wt1}% ({wt_delta:+0.2f}pp)",
        )
    )

    # Build "Why it matters to this client"
    why_it_matters: list[str] = []
    risk_profile = client.get("risk_profile", "")
    risk_score = client.get("risk_tolerance_score", "")
    objectives = client.get("objectives", "")

    why_it_matters.append(
        f"Client risk profile is {risk_profile} (tolerance score: {risk_score}/10). Stated objectives: '{objectives}'."
    )

    # Check mandate limits
    mandate_code = ""
    for p in book.portfolios_by_client.get(client_id, []):
        if p.get("service_model") != "Custody":
            mandate_code = p.get("mandate_code", "")
            break
    if mandate_code and mandate_code in book.mandates:
        mandate = book.mandates[mandate_code]
        single_cap = mandate.get("max_single_position_pct") or 10.0
        if wt1 > single_cap and instrument.get("concentration_limit_applies") == "Y":
            why_it_matters.append(
                f"Concentration breach: Current position weight of {wt1:.1f}% exceeds mandate single-stock maximum of {single_cap:.1f}%."
            )
            source_evidence.append(
                Evidence(
                    source_file="mandates.csv",
                    row_or_id=mandate_code,
                    field="max_single_position_pct",
                    value=str(single_cap),
                    snapshot_date=end,
                    note=f"Mandate {mandate_code} single-position ceiling is {single_cap}%",
                )
            )

    # Check planned cash needs
    cash_needs = [
        cn
        for cn in book.cash_needs
        if cn.get("client_id") == client_id and cn.get("due_from", "") <= "2027-01-01"
    ]
    if cash_needs:
        for cn in cash_needs:
            why_it_matters.append(
                f"Impending cash requirement: {cn.get('description')} ({cn.get('currency')} {float(cn.get('amount', 0)):,.0f}) "
                f"due between {cn.get('due_from')} and {cn.get('due_to')} ({cn.get('certainty')})."
            )
            source_evidence.append(
                Evidence(
                    source_file="planned_cash_needs.csv",
                    row_or_id=cn.get("need_id", ""),
                    field="amount",
                    value=f"{cn.get('currency')} {cn.get('amount')}",
                    snapshot_date=end,
                    note=cn.get("description", ""),
                )
            )

    # Check RM notes for client sentiment or statements
    client_notes = [n for n in book.notes if n.get("client_id") == client_id]
    if client_notes:
        recent_note = client_notes[-1]
        why_it_matters.append(
            f"RM note record ({recent_note.get('note_date')}): \"{recent_note.get('note')}\""
        )
        source_evidence.append(
            Evidence(
                source_file="rm_notes.json",
                row_or_id=recent_note.get("note_id", ""),
                field="note",
                value=recent_note.get("note", "")[:120] + "...",
                snapshot_date=recent_note.get("note_date", ""),
                note=f"Logged via {recent_note.get('channel')}",
            )
        )

    # Identify uncertainties
    uncertainties: list[str] = []
    if not matching_events:
        uncertainties.append(
            "No direct event transmission link found in event_log.csv for this period. Move appears driven by general market momentum or security-specific factors."
        )
    if liquidity_tier in ("Illiquid", "Quarterly Gate"):
        uncertainties.append(
            f"Holding is {liquidity_tier}. Valuation marks may lag underlying private-market or structured asset fundamentals by up to a quarter."
        )
    if underlying:
        uncertainties.append(
            f"Structured product look-through depends on underlying basket: {underlying}. Payout may be nonlinear or subject to knock-in barrier risk."
        )

    return HoldingExplanation(
        client_id=client_id,
        instrument_id=instrument_id,
        instrument_name=name,
        asset_class=asset_class,
        sector=sector,
        region=region,
        start=start,
        end=end,
        portfolio_id=portfolio_id,
        what_changed=what_changed,
        event_evidence=matching_events,
        transmission_mechanisms=transmissions,
        why_it_matters=why_it_matters,
        uncertainties=uncertainties,
        source_evidence=source_evidence,
    )
