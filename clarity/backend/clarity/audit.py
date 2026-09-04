"""Reconstruct a chronological, origin-labelled audit timeline from local adapters."""

from __future__ import annotations

from typing import Any

from .followthrough_store import get_followthrough_store
from .calibration_store import get_calibration_store
from .loaders import get_book
from .meeting_store import get_meeting_store
from .review import get_store
from .scenario_store import get_scenario_store


def _event(*, timestamp: str, origin: str, object_type: str, object_id: str, action: str,
           actor: str, client_id: str | None, insight_id: str | None, detail: dict[str, Any]) -> dict[str, Any]:
    return {"id": f"{origin}:{object_type}:{object_id}:{timestamp}", "timestamp": timestamp,
            "origin": origin, "object_type": object_type, "object_id": object_id,
            "action": action, "actor": actor, "client_id": client_id,
            "insight_id": insight_id, "detail": detail}


def timeline(client_id: str | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for entry in get_store().audit(client_id, limit=1000):
        events.append(_event(timestamp=entry.timestamp, origin="user_decision", object_type="decision", object_id=entry.insight_id, action=entry.action, actor=entry.actor, client_id=entry.client_id, insight_id=entry.insight_id, detail=entry.detail))
    for package in (get_meeting_store().list_for_client(client_id) if client_id else [item for cid in get_book().clients for item in get_meeting_store().list_for_client(cid)]):
        for version in package.get("versions", []):
            origin = "system" if version.get("reason", "").startswith(("generated", "regenerated")) else "user_decision"
            events.append(_event(timestamp=version["created_at"], origin=origin, object_type="meeting_package", object_id=package["id"], action=f"version:{version['reason']}", actor=version["actor"], client_id=package["client_id"], insight_id=package["insight_id"], detail={"version": version["version"]}))
        for result in package.get("preflights") or ([package["last_preflight"]] if package.get("last_preflight") else []):
            events.append(_event(timestamp=result["checked_at"], origin="system", object_type="meeting_package", object_id=package["id"], action="communication_preflight", actor="Clarity deterministic controls", client_id=package["client_id"], insight_id=package["insight_id"], detail={"can_hand_off": result["can_hand_off"]}))
        for handoff in package.get("handoffs", []):
            events.append(_event(timestamp=handoff["created_at"], origin="user_decision", object_type="meeting_package", object_id=package["id"], action="simulated_handoff", actor=handoff["actor"], client_id=package["client_id"], insight_id=package["insight_id"], detail={"channel": handoff["channel"]}))
    for cid in ([client_id] if client_id else list(get_book().clients)):
        for scenario in get_scenario_store().list_for_client(cid):
            result = scenario["result"]
            events.append(_event(timestamp=scenario["saved_at"], origin="system", object_type="scenario", object_id=scenario["id"], action="saved_current_state_comparison", actor=scenario["saved_by"], client_id=cid, insight_id=result["insight_id"], detail={"calculation_version": result["calculation_version"]}))
    events.extend(get_followthrough_store().audit(client_id))
    events.extend(get_calibration_store().audit(client_id))
    return sorted(events, key=lambda item: item["timestamp"], reverse=True)
