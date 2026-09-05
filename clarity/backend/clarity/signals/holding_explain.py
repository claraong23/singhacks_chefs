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


def _match_event_to_holding(
    event: dict[str, Any],
    instrument: dict[str, Any],
    asset_class: str,
    sector: str,
    region: str,
    underlying: str,
    name: str,
) -> tuple[bool, str]:
    """Deterministically match an event in event_log.csv to a specific holding.

    Returns (is_match, confidence_label). Strictly prevents false positives
    (e.g. oil reserve releases matching Hong Kong property accumulators, or gold rallies
    matching non-commodity funds).
    """
    trans = event.get("primary_transmission", "").lower()
    desc = event.get("description", "").lower()
    name_lower = name.lower()
    underlying_lower = underlying.lower()
    sector_lower = sector.lower()
    region_lower = region.lower()
    sub_asset = instrument.get("sub_asset_class", "").lower()
    cur = instrument.get("currency", "")

    # 1. Gold / Precious Metals (EVT-01, EVT-02, EVT-03)
    if "gold" in trans or "precious metals" in trans:
        if asset_class == "Commodities" and ("gold" in name_lower or "gold" in underlying_lower or "precious" in name_lower):
            return True, "Direct evidence"
        return False, ""

    # 2. Energy / Oil / Hormuz Shocks (EVT-04, EVT-05, EVT-06, EVT-07, EVT-08, EVT-10, EVT-16)
    if any(k in trans for k in ("energy", "brent", "crude", "oil-linked", "lng")):
        if sector_lower in ("energy", "oil & gas", "utilities"):
            return True, "Direct evidence"
        if "oil" in underlying_lower or "energy" in underlying_lower or "brent" in underlying_lower:
            return True, "Direct evidence"
        if "oil-linked structured products" in trans:
            if asset_class == "Structured Products" and any(k in underlying_lower or k in name_lower for k in ("oil", "energy", "brent", "crude")):
                return True, "Direct evidence"
            return False, ""
        if any(k in trans for k in ("airlines", "transport", "shipping")) and sector_lower in ("transportation", "industrials", "airlines"):
            return True, "Qualified market context"
        if "gulf credit" in trans and region_lower in ("middle east", "gulf") and asset_class == "Fixed Income":
            return True, "Direct evidence"
        return False, ""

    # 3. European Fixed Income / ECB Rate Hikes (EVT-09)
    if "european fixed income" in trans or "eur assets" in trans:
        if asset_class in ("Fixed Income", "Cash and Equivalents") and (region_lower in ("europe", "western europe") or cur == "EUR"):
            return True, "Direct evidence"
        return False, ""

    # 4. US Technology & AI Capex (EVT-11)
    if "us technology" in trans or "ai capital expenditure" in desc:
        if sector_lower in ("information technology", "technology", "semiconductors", "software"):
            return True, "Direct evidence"
        if "tech" in name_lower or "ai" in name_lower or "cloud" in name_lower:
            return True, "Direct evidence"
        return False, ""

    # 5. US Rates, Treasury Yields & Duration (EVT-12, EVT-13, EVT-15)
    if any(k in trans for k in ("duration", "treasury yield", "rate-sensitive credit")):
        if asset_class == "Fixed Income":
            return True, "Direct evidence"
        if "growth equity" in trans and sector_lower in ("information technology", "technology") and region_lower in ("north america", "united states", "global"):
            return True, "Qualified market context"
        return False, ""

    # 6. Private Credit / Semi-Liquid Alternatives Redemption Stress (EVT-14)
    if "private credit" in trans or "semi-liquid alternatives" in trans:
        if sub_asset in ("private credit", "direct lending", "mezzanine") or (asset_class == "Alternatives" and "credit" in name_lower):
            return True, "Direct evidence"
        if asset_class == "Alternatives" and instrument.get("liquidity_tier") in ("Quarterly Gate", "Semi-Liquid"):
            return True, "Qualified market context"
        return False, ""

    return False, ""


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

    # Detect if position was opened during the period (new subscription or acquisition)
    h_record = next(
        (
            h
            for h in book.holdings_by_client_date.get((client_id, end), [])
            if h.get("instrument_id") == instrument_id
            and (not portfolio_id or portfolio_id == "all" or h.get("portfolio_id") == portfolio_id)
        ),
        None,
    )
    is_new_position = (b is None or q0 == 0.0) and q1 > 0.0
    cost_basis_local = None
    cost_basis_usd = None
    unrealised_pnl_usd = None
    unrealised_pnl_pct = None
    acquired_date = None

    if h_record:
        acquired_date = h_record.get("acquired_date")
        if is_new_position:
            cost_basis_local = h_record.get("cost_basis_base") or (h_record.get("avg_cost_local", 0.0) * q1)
            pf = book.portfolios.get(h_record.get("portfolio_id"), {})
            pf_ccy = pf.get("base_currency", currency)
            cost_basis_usd = book.to_usd(cost_basis_local, pf_ccy, end) or val1
            unrealised_pnl_usd = round(val1 - cost_basis_usd, 2)
            unrealised_pnl_pct = h_record.get("unrealised_pnl_pct")
            if unrealised_pnl_pct is None and cost_basis_usd > 0:
                unrealised_pnl_pct = round(((val1 / cost_basis_usd) - 1.0) * 100, 2)

    # Movement classification (price-led, trade-led, combination, new-position)
    qty_diff = abs(q1 - q0)
    if is_new_position:
        movement_type = "new-position"
    elif qty_diff < 1e-5:
        movement_type = "price-led"
    elif p_ret is None or abs(p_ret) < 0.05:
        movement_type = "trade-led"
    else:
        movement_type = "combination"

    portfolio_delta = round(total_end - total_start, 2)
    portfolio_change_pct = round((portfolio_delta / total_start * 100), 2) if total_start > 0 else 0.0

    if is_new_position and unrealised_pnl_usd is not None and cost_basis_usd:
        pnl_sign = "-" if unrealised_pnl_usd < 0 else "+"
        contribution_text = (
            f"New position: {pnl_sign}USD {abs(unrealised_pnl_usd):,.0f} price return "
            f"({unrealised_pnl_pct:+.1f}%) on USD {cost_basis_usd:,.0f} capital deployed"
        )
    else:
        val_sign = "-" if val_delta < 0 else "+"
        pf_sign = "-" if portfolio_delta < 0 else "+"
        contribution_text = f"{val_sign}USD {abs(val_delta):,.0f} of portfolio's {pf_sign}USD {abs(portfolio_delta):,.0f} movement"

    portfolio_impact = {
        "start_snapshot": start,
        "end_snapshot": end,
        "portfolio_start_usd": round(total_start, 2),
        "portfolio_end_usd": round(total_end, 2),
        "portfolio_change_usd": portfolio_delta,
        "portfolio_change_pct": portfolio_change_pct,
        "holding_change_usd": round(val_delta, 2),
        "contribution_text": contribution_text,
    }

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
        "movement_type": movement_type,
        "is_new_position": is_new_position,
        "cost_basis_local": cost_basis_local,
        "cost_basis_usd": cost_basis_usd,
        "unrealised_pnl_usd": unrealised_pnl_usd,
        "unrealised_pnl_pct": unrealised_pnl_pct,
        "acquired_date": acquired_date,
    }

    # Find relevant events in event_log.csv occurring within [start, end]
    matching_events: list[dict[str, Any]] = []
    transmissions: list[str] = []
    source_evidence: list[Evidence] = []

    for event in book.events:
        e_date = event.get("event_date", "")
        if not (start <= e_date <= end):
            continue
        is_match, confidence_label = _match_event_to_holding(
            event, instrument, asset_class, sector, region, underlying, name
        )
        if is_match:
            matching_events.append({
                "event_id": event.get("event_id", f"EVT-{e_date}"),
                "event_date": e_date,
                "event_type": event.get("event_type", ""),
                "region": event.get("region", ""),
                "description": event.get("description", ""),
                "primary_transmission": event.get("primary_transmission", ""),
                "severity": event.get("severity", ""),
                "confidence": confidence_label,
            })
            transmissions.append(
                f"{e_date} [{confidence_label}] ({event.get('severity')}): {event.get('description')} "
                f"[Transmission: {event.get('primary_transmission')}]"
            )
            source_evidence.append(
                Evidence(
                    source_file="event_log.csv",
                    row_or_id=event.get("event_id", e_date),
                    field="primary_transmission",
                    value=event.get("primary_transmission", ""),
                    snapshot_date=e_date,
                    note=f"Event cited ({confidence_label}): {event.get('description')}",
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
    if is_new_position:
        source_evidence.append(
            Evidence(
                source_file="transactions.csv",
                row_or_id=f"TXN-{instrument_id}",
                field="cost_basis",
                value=f"{currency} {cost_basis_local or 0:,.0f} (USD {cost_basis_usd or 0:,.0f})",
                snapshot_date=acquired_date or end,
                note=f"Position acquired on {acquired_date} at avg cost {p0 or 100.0} {currency}",
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
                    value=f"{cn.get('currency')} {float(cn.get('amount', 0)):,.0f}",
                    snapshot_date=cn.get("due_from", ""),
                    note=f"Status: {cn.get('certainty')}",
                )
            )

    # Check RM notes for client sentiment/relationship context
    client_notes = book.notes_by_client.get(client_id, [])
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

    # Data limitations (what data can and cannot prove)
    limitations: list[str] = [
        "Data reflects point-in-time snapshot records; intraday order execution prices and market peaks/troughs are not observed.",
        "The authoritative event_log.csv captures recorded macro, geopolitical, and policy events; company-specific micro announcements may not have separate log entries.",
    ]
    if liquidity_tier in ("Illiquid", "Quarterly Gate"):
        limitations.append(
            f"As a {liquidity_tier} holding, valuation marks reflect lagged manager reporting rather than continuous mark-to-market pricing."
        )
    if underlying:
        limitations.append(
            f"Payoff is non-linear and dependent on underlying references ({underlying}). Linear attribution cannot capture knock-in barrier dynamics."
        )

    # Neutral, factual conclusion (single sentence)
    if is_new_position:
        pnl_desc = (
            f"an unrealised price loss of {unrealised_pnl_pct:+.1f}% (-USD {abs(unrealised_pnl_usd or 0):,.0f})"
            if (unrealised_pnl_usd or 0) < 0
            else f"an unrealised gain of {unrealised_pnl_pct:+.1f}% (+USD {abs(unrealised_pnl_usd or 0):,.0f})"
        )
        acq_desc = f"on {acquired_date}" if acquired_date else "during the period"
        conclusion = (
            f"{name} was entered as a new position {acq_desc} (USD {cost_basis_usd or 0:,.0f} deployed / {q1:,.0f} units), "
            f"recording {pnl_desc} to close at USD {val1:,.0f} ({wt1:.1f}% portfolio weight)."
        )
    else:
        ret_str = f" ({p_ret:+.1f}%)" if p_ret is not None else ""
        flow_str = f" with {abs(q1 - q0):,.0f} units traded" if qty_diff >= 1e-5 else " without trading activity"
        driver_str = "market price movements" if movement_type == "price-led" else ("client trading flow" if movement_type == "trade-led" else "a combination of price move and position adjustments")
        conclusion = (
            f"{name} {'declined' if val_delta < 0 else ('gained' if val_delta > 0 else 'remained unchanged')} "
            f"by USD {abs(val_delta):,.0f}{ret_str}{flow_str}, driven by {driver_str} and shifting portfolio weight from {wt0:.1f}% to {wt1:.1f}%."
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
        portfolio_impact=portfolio_impact,
        movement_type=movement_type,
        limitations=limitations,
        conclusion=conclusion,
    )
