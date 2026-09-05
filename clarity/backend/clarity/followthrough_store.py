"""Local, append-only collaboration and follow-through repository."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import config
from .postgres_state import PostgresState

PATH = config.REPO_ROOT / "clarity" / "state" / "follow_through.json"
WORK_STATUSES = ("open", "in_progress", "waiting", "completed", "cancelled")
REEVALUATION_STATUSES = ("queued", "acknowledged", "complete")

ACTORS = {
    "rm": "RM-SG-014",
    "credit": "CREDIT-HK-001",
    "wealth_planning": "PLANNING-SG-001",
    "investment": "INVESTMENT-SG-001",
    "compliance_audit": "COMPLIANCE-SG-001",
    "operations": "OPS-SG-001",
}
SPECIALIST_ROLES = {"credit", "wealth_planning", "investment"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid4())


def actor_for(role: str) -> str:
    if role not in ACTORS:
        raise ValueError("Unknown simulated role.")
    return ACTORS[role]


def can_create(role: str, kind: str) -> bool:
    return (role == "rm" and kind in {"task", "referral", "outcome"}) or (
        role == "operations" and kind == "evidence_update"
    )


def can_update(role: str, record: dict[str, Any]) -> bool:
    if role == "rm":
        return record.get("kind") != "reevaluation"
    if role in SPECIALIST_ROLES:
        return record.get("owner_role") == role
    if role == "operations":
        return record.get("kind") == "reevaluation"
    return False


class FollowThroughStore:
    def __init__(self, path: Path = PATH) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {
            "tasks": {}, "referrals": {}, "outcomes": {}, "evidence_updates": {},
            "reevaluations": {}, "audit": [],
        }
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.update({key: saved.get(key, self.data[key]) for key in self.data})
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _event(self, *, origin: str, object_type: str, object_id: str, action: str,
               actor: str, client_id: str | None, insight_id: str | None,
               detail: dict[str, Any]) -> dict[str, Any]:
        event = {"id": new_id(), "timestamp": now(), "origin": origin,
                 "object_type": object_type, "object_id": object_id, "action": action,
                 "actor": actor, "client_id": client_id, "insight_id": insight_id,
                 "detail": detail}
        self.data["audit"].append(event)
        return event

    def create(self, collection: str, record: dict[str, Any], *, origin: str, actor: str) -> dict[str, Any]:
        with self.lock:
            record = {**record, "id": new_id(), "created_at": now(), "created_by": actor,
                      "history": []}
            record["history"].append({"timestamp": record["created_at"], "actor": actor, "action": "created", "reason": record.get("summary") or record.get("title") or record.get("statement", "")})
            self.data[collection][record["id"]] = record
            self._event(origin=origin, object_type=collection[:-1], object_id=record["id"], action="created", actor=actor, client_id=record.get("client_id"), insight_id=record.get("insight_id"), detail={"status": record.get("status"), "owner_role": record.get("owner_role")})
            self._save()
            return record

    def update(self, collection: str, record_id: str, changes: dict[str, Any], *, actor: str, action: str, reason: str) -> dict[str, Any]:
        with self.lock:
            record = self.data[collection].get(record_id)
            if not record:
                raise KeyError(f"Unknown {collection[:-1]} {record_id}")
            prior = {key: record.get(key) for key in changes}
            record.update(changes)
            record["history"].append({"timestamp": now(), "actor": actor, "action": action, "reason": reason, "prior": prior, "next": changes})
            self._event(origin="user_decision" if collection != "evidence_updates" else "source_data", object_type=collection[:-1], object_id=record_id, action=action, actor=actor, client_id=record.get("client_id"), insight_id=record.get("insight_id"), detail={"reason": reason, "prior": prior, "next": changes})
            self._save()
            return record

    def list(self, collection: str, *, client_id: str | None = None) -> list[dict[str, Any]]:
        records = list(self.data[collection].values())
        if client_id:
            records = [item for item in records if item.get("client_id") == client_id]
        return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)

    def audit(self, client_id: str | None = None) -> list[dict[str, Any]]:
        events = self.data["audit"]
        if client_id:
            events = [item for item in events if item.get("client_id") == client_id]
        return list(reversed(events))

    def reset(self) -> None:
        with self.lock:
            for key in self.data:
                self.data[key] = [] if key == "audit" else {}
            self._save()


class PostgresFollowThroughStore(FollowThroughStore):
    def __init__(self, database_url: str) -> None:
        self._pg = PostgresState(database_url, "follow_through", {"tasks": {}, "referrals": {}, "outcomes": {}, "evidence_updates": {}, "reevaluations": {}, "audit": []})
        super().__init__(PATH)

    def _load(self) -> None:
        self.data.update({key: self._pg.payload.get(key, self.data[key]) for key in self.data})

    def _save(self) -> None:
        self._pg.save(self.data)


_STORE: FollowThroughStore | None = None


def get_followthrough_store() -> FollowThroughStore:
    global _STORE
    if _STORE is None:
        _STORE = PostgresFollowThroughStore(config.DATABASE_URL) if config.DATABASE_URL else FollowThroughStore()
    return _STORE
