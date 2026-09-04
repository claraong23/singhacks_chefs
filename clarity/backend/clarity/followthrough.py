"""Governed local workflows after the RM meeting; no source data is rewritten."""

from __future__ import annotations

from datetime import date
from typing import Any

from . import config
from .followthrough_store import (
    REEVALUATION_STATUSES, WORK_STATUSES, actor_for, can_create, can_update,
)

OWNER_ROLES = {"rm", "credit", "wealth_planning", "investment", "operations"}
REFERRAL_TYPES = {"credit", "wealth_planning", "compliance", "investment", "operations"}
OUTCOME_TYPES = {"discussed", "preference_confirmed", "preference_changed", "document_requested", "document_received", "meeting_cancelled"}
SOURCE_TYPES = {"client_statement", "document", "specialist_response"}


def actor(role: str) -> str:
    return actor_for(role)


def ensure_create(role: str, kind: str) -> None:
    if not can_create(role, kind):
        raise PermissionError(f"The {role} role cannot create {kind} records.")


def ensure_update(role: str, record: dict[str, Any]) -> None:
    if not can_update(role, record):
        raise PermissionError("This simulated role cannot update that record.")


def due_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("A due_date in YYYY-MM-DD format is required.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must use YYYY-MM-DD format.") from exc
    if parsed < date.fromisoformat(config.AS_OF):
        raise ValueError(f"due_date cannot precede {config.AS_OF}.")
    return value


def required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    return value.strip()


def work_record(payload: dict[str, Any], *, kind: str) -> dict[str, Any]:
    owner = payload.get("owner_role")
    if owner not in OWNER_ROLES:
        raise ValueError("owner_role must be a known accountable role.")
    base = {
        "kind": kind, "client_id": required_text(payload, "client_id"),
        "insight_id": payload.get("insight_id") or None,
        "meeting_package_id": payload.get("meeting_package_id") or None,
        "owner_role": owner, "due_date": due_date(payload.get("due_date")),
        "status": "open", "evidence_refs": payload.get("evidence_refs") or [],
    }
    if not all(isinstance(item, str) and item for item in base["evidence_refs"]):
        raise ValueError("evidence_refs must be non-empty source identifiers.")
    if kind == "task":
        return {**base, "title": required_text(payload, "title"), "description": payload.get("description", "")}
    referral_type = payload.get("referral_type")
    if referral_type not in REFERRAL_TYPES:
        raise ValueError("referral_type must be a supported specialist type.")
    return {**base, "referral_type": referral_type, "summary": required_text(payload, "summary")}


def outcome_record(payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    outcome_type = payload.get("outcome_type")
    if outcome_type not in OUTCOME_TYPES:
        raise ValueError("outcome_type must be a supported meeting outcome.")
    documents = payload.get("requested_documents") or []
    if not all(isinstance(item, str) and item.strip() for item in documents):
        raise ValueError("requested_documents must be strings.")
    return {"kind": "outcome", "client_id": required_text(payload, "client_id"),
            "insight_id": payload.get("insight_id") or None, "meeting_package_id": payload.get("meeting_package_id") or None,
            "outcome_type": outcome_type, "statement": required_text(payload, "statement"),
            "requested_documents": documents, "actor": actor_id, "status": "recorded"}


def evidence_record(payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    source_type = payload.get("source_type")
    if source_type not in SOURCE_TYPES:
        raise ValueError("source_type must be client_statement, document, or specialist_response.")
    affected = payload.get("affected_insight_ids") or []
    if not affected or not all(isinstance(item, str) and item for item in affected):
        raise ValueError("At least one affected_insight_id is required.")
    return {"kind": "evidence_update", "client_id": required_text(payload, "client_id"),
            "source_type": source_type, "source_ref": required_text(payload, "source_ref"),
            "summary": required_text(payload, "summary"), "received_at": payload.get("received_at") or config.AS_OF,
            "actor": actor_id, "affected_insight_ids": affected, "status": "recorded"}


def status_update(record: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    status = payload.get("status")
    if status not in WORK_STATUSES:
        raise ValueError("status must be a valid work status.")
    reason = required_text(payload, "reason") if status in {"completed", "cancelled"} else payload.get("reason", "")
    changes = {"status": status}
    if payload.get("owner_role"):
        if payload["owner_role"] not in OWNER_ROLES:
            raise ValueError("owner_role must be a known accountable role.")
        changes["owner_role"] = payload["owner_role"]
    if payload.get("due_date"):
        changes["due_date"] = due_date(payload["due_date"])
    return changes, reason


def reevaluation_update(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    status = payload.get("status")
    if status not in REEVALUATION_STATUSES:
        raise ValueError("status must be queued, acknowledged, or complete.")
    return {"status": status}, required_text(payload, "reason") if status == "complete" else payload.get("reason", "")
