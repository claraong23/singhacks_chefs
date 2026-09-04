"""Append-only local persistence for transparent priority-policy calibration."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import config

PATH = config.REPO_ROOT / "clarity" / "state" / "priority_calibration.json"
BASELINE = {
    "id": "baseline-v1", "name": "Published baseline", "weights": {
        "severity": 0.45, "materiality": 0.30, "urgency": 0.25,
    }, "status": "active", "rationale": "Published deterministic scoring policy.",
    "created_by": "Clarity deterministic controls", "created_at": config.AS_OF,
    "activation_history": [{"timestamp": config.AS_OF, "actor": "Clarity deterministic controls", "action": "baseline"}],
}
TEMPLATES = {
    "baseline": {"name": "Published baseline", "weights": BASELINE["weights"]},
    "urgency_first": {"name": "Urgency-first", "weights": {"severity": 0.35, "materiality": 0.20, "urgency": 0.45}},
    "materiality_first": {"name": "Materiality-first", "weights": {"severity": 0.35, "materiality": 0.45, "urgency": 0.20}},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid4())


class CalibrationStore:
    def __init__(self, path: Path = PATH) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {"policies": {}, "feedback": {}, "audit": []}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.update({key: payload.get(key, self.data[key]) for key in self.data})
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _event(self, *, origin: str, object_type: str, object_id: str, action: str,
               actor: str, client_id: str | None = None, insight_id: str | None = None,
               detail: dict[str, Any] | None = None) -> None:
        self.data["audit"].append({
            "id": new_id(), "timestamp": now(), "origin": origin, "object_type": object_type,
            "object_id": object_id, "action": action, "actor": actor, "client_id": client_id,
            "insight_id": insight_id, "detail": detail or {},
        })

    def active(self) -> dict[str, Any]:
        active = next((item for item in self.data["policies"].values() if item["status"] == "active"), None)
        return dict(active or BASELINE)

    def get(self, policy_id: str) -> dict[str, Any] | None:
        if policy_id == BASELINE["id"]:
            return self.active() if self.active()["id"] == BASELINE["id"] else dict(BASELINE)
        return self.data["policies"].get(policy_id)

    def list(self) -> list[dict[str, Any]]:
        policies = list(self.data["policies"].values())
        if not any(item["id"] == BASELINE["id"] for item in policies):
            policies.append(self.active() if self.active()["id"] == BASELINE["id"] else dict(BASELINE))
        return sorted(policies, key=lambda item: item.get("created_at", ""), reverse=True)

    def create(self, *, name: str, weights: dict[str, float], rationale: str, actor: str, template: str | None = None) -> dict[str, Any]:
        with self.lock:
            record = {
                "id": new_id(), "name": name, "weights": weights, "status": "draft", "rationale": rationale,
                "created_by": actor, "created_at": now(), "template": template, "history": [], "activation_history": [],
            }
            record["history"].append({"timestamp": record["created_at"], "actor": actor, "action": "created", "reason": rationale})
            self.data["policies"][record["id"]] = record
            self._event(origin="user_decision", object_type="priority_policy", object_id=record["id"], action="created", actor=actor, detail={"weights": weights, "template": template})
            self._save()
            return record

    def revise(self, policy_id: str, *, name: str, weights: dict[str, float], rationale: str, actor: str) -> dict[str, Any]:
        with self.lock:
            record = self.data["policies"].get(policy_id)
            if not record:
                raise KeyError("Unknown priority policy.")
            if record["status"] != "draft":
                raise ValueError("Only draft policies can be revised.")
            prior = {"name": record["name"], "weights": record["weights"], "rationale": record["rationale"]}
            record.update({"name": name, "weights": weights, "rationale": rationale})
            record["history"].append({"timestamp": now(), "actor": actor, "action": "revised", "reason": rationale, "prior": prior})
            self._event(origin="user_decision", object_type="priority_policy", object_id=policy_id, action="revised", actor=actor, detail={"prior": prior, "weights": weights})
            self._save()
            return record

    def transition(self, policy_id: str, *, status: str, actor: str, rationale: str) -> dict[str, Any]:
        with self.lock:
            record = self.data["policies"].get(policy_id)
            if not record:
                raise KeyError("Unknown priority policy.")
            prior = record["status"]
            if status == "submitted" and prior != "draft":
                raise ValueError("Only draft policies can be submitted.")
            if status == "rejected" and prior != "submitted":
                raise ValueError("Only submitted policies can be rejected.")
            record["status"] = status
            record["history"].append({"timestamp": now(), "actor": actor, "action": status, "reason": rationale, "prior_status": prior})
            self._event(origin="user_decision", object_type="priority_policy", object_id=policy_id, action=status, actor=actor, detail={"from": prior, "to": status, "reason": rationale})
            self._save()
            return record

    def activate(self, policy_id: str, *, actor: str, rationale: str) -> dict[str, Any]:
        with self.lock:
            record = self.data["policies"].get(policy_id)
            if not record:
                raise KeyError("Unknown priority policy.")
            if record["status"] != "submitted":
                raise ValueError("Only submitted policies can be activated.")
            active = next((item for item in self.data["policies"].values() if item["status"] == "active"), None)
            timestamp = now()
            if active is None:
                active = {**BASELINE, "history": list(BASELINE["activation_history"]), "activation_history": list(BASELINE["activation_history"])}
                self.data["policies"][active["id"]] = active
            if active:
                active["status"] = "retired"
                active["history"].append({"timestamp": timestamp, "actor": actor, "action": "retired", "reason": f"Superseded by {policy_id}"})
            record["status"] = "active"
            record["activation_history"].append({"timestamp": timestamp, "actor": actor, "action": "activated", "reason": rationale})
            record["history"].append({"timestamp": timestamp, "actor": actor, "action": "activated", "reason": rationale})
            self._event(origin="user_decision", object_type="priority_policy", object_id=policy_id, action="activated", actor=actor, detail={"prior_active_policy_id": active["id"] if active else BASELINE["id"], "reason": rationale})
            self._save()
            return record

    def feedback(self, *, client_id: str, insight_id: str, decision_status: str, usefulness: str,
                 urgency_assessment: str, rationale: str, actor: str, evidence_version: str | None,
                 policy_id: str) -> dict[str, Any]:
        with self.lock:
            record = {"id": new_id(), "client_id": client_id, "insight_id": insight_id,
                      "decision_status": decision_status, "usefulness": usefulness,
                      "urgency_assessment": urgency_assessment, "rationale": rationale, "actor": actor,
                      "timestamp": now(), "evidence_version": evidence_version, "policy_id": policy_id}
            self.data["feedback"][record["id"]] = record
            self._event(origin="user_decision", object_type="rm_feedback", object_id=record["id"], action="recorded", actor=actor, client_id=client_id, insight_id=insight_id, detail={"usefulness": usefulness, "urgency_assessment": urgency_assessment, "policy_id": policy_id})
            self._save()
            return record

    def feedback_for(self, client_id: str | None = None) -> list[dict[str, Any]]:
        rows = list(self.data["feedback"].values())
        if client_id:
            rows = [row for row in rows if row["client_id"] == client_id]
        return sorted(rows, key=lambda row: row["timestamp"], reverse=True)

    def audit(self, client_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.data["audit"]
        if client_id:
            rows = [row for row in rows if row.get("client_id") == client_id]
        return list(reversed(rows))

    def reset(self) -> None:
        with self.lock:
            self.data = {"policies": {}, "feedback": {}, "audit": []}
            self._save()


_STORE: CalibrationStore | None = None


def get_calibration_store() -> CalibrationStore:
    global _STORE
    if _STORE is None:
        _STORE = CalibrationStore()
    return _STORE
