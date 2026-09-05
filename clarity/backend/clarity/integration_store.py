"""Local, replayable integration contracts.  No external systems are called."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import config
from .followthrough_store import ACTORS, SPECIALIST_ROLES

PATH = config.REPO_ROOT / "clarity" / "state" / "integrations.json"
FEATURE_SCHEMA_VERSION = "deterministic-priority-factors-v1"
MODEL_READINESS = {
    "feature_schema_version": FEATURE_SCHEMA_VERSION,
    "training_eligible": False,
    "reasons": [
        "The 20-client synthetic book is not representative training data.",
        "No representative observed client-outcome labels are available.",
        "Bias review and out-of-sample evaluation have not been completed.",
    ],
}
SOURCE_SYSTEMS = ("portfolio_custody", "lending_credit", "client_document", "private_markets")
DESTINATIONS = ("crm", "specialist_queue")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IntegrationStore:
    """Append-only records for a simulated bank-system boundary."""

    def __init__(self, path: Path = PATH) -> None:
        self.path, self.lock = path, threading.Lock()
        self.data: dict[str, Any] = {"inbound": {}, "work_orders": {}, "audit": []}
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

    def _audit(self, *, origin: str, object_type: str, object_id: str, action: str,
               actor: str, client_id: str | None, insight_id: str | None,
               detail: dict[str, Any]) -> None:
        self.data["audit"].append({
            "id": str(uuid4()), "timestamp": now(), "origin": origin,
            "object_type": object_type, "object_id": object_id, "action": action,
            "actor": actor, "client_id": client_id, "insight_id": insight_id,
            "detail": {**detail, "model_readiness": MODEL_READINESS},
        })

    @staticmethod
    def _actor(role: str) -> str:
        if role not in ACTORS:
            raise ValueError("Unknown simulated role.")
        return ACTORS[role]

    @staticmethod
    def _required(payload: dict[str, Any], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required.")
        return value.strip()

    def capabilities(self) -> dict[str, Any]:
        return {
            "source_systems": list(SOURCE_SYSTEMS), "destinations": list(DESTINATIONS),
            "feature_schema_version": FEATURE_SCHEMA_VERSION, "local_simulation": True,
            "model_readiness": MODEL_READINESS,
        }

    def list(self, role: str, client_id: str | None = None) -> dict[str, Any]:
        self._actor(role)
        inbound = list(self.data["inbound"].values())
        orders = list(self.data["work_orders"].values())
        if client_id:
            inbound = [item for item in inbound if item["client_id"] == client_id]
            orders = [item for item in orders if item["client_id"] == client_id]
        if role == "rm":
            inbound = []
            orders = [item for item in orders if item["created_by_role"] == "rm"]
        elif role in SPECIALIST_ROLES:
            inbound = []
            orders = [item for item in orders if item["destination"] == "specialist_queue" and item["owner_role"] == role]
        elif role not in {"operations", "compliance_audit"}:
            inbound, orders = [], []
        return {
            "inbound": sorted(inbound, key=lambda item: item["received_at"], reverse=True),
            "work_orders": sorted(orders, key=lambda item: item["created_at"], reverse=True),
            "capabilities": self.capabilities(),
        }

    def receive(self, payload: dict[str, Any], role: str) -> tuple[dict[str, Any], bool]:
        if role != "operations":
            raise PermissionError("Only Product Operations can receive inbound integration events.")
        source_system = self._required(payload, "source_system")
        if source_system not in SOURCE_SYSTEMS:
            raise ValueError("source_system must be a supported simulated source.")
        external_event_id = self._required(payload, "external_event_id")
        schema_version = self._required(payload, "schema_version")
        client_id = self._required(payload, "client_id")
        source_ref = self._required(payload, "source_ref")
        summary = self._required(payload, "summary")
        occurred_at = self._required(payload, "occurred_at")
        affected = payload.get("affected_insight_ids") or []
        if not affected or not all(isinstance(item, str) and item.strip() for item in affected):
            raise ValueError("At least one affected_insight_id is required.")
        key = f"{source_system}:{external_event_id}"
        with self.lock:
            existing_id = next((item_id for item_id, item in self.data["inbound"].items() if item["idempotency_key"] == key), None)
            if existing_id:
                existing = self.data["inbound"][existing_id]
                self._audit(origin="source_data", object_type="inbound_integration_event", object_id=existing_id,
                            action="inbound_replayed", actor=self._actor(role), client_id=existing["client_id"],
                            insight_id=existing["affected_insight_ids"][0], detail={"idempotency_key": key, "replayed": True})
                self._save()
                return existing, True
            received_at = now()
            event_id = str(uuid4())
            event = {
                "id": event_id, "source_system": source_system, "external_event_id": external_event_id,
                "idempotency_key": key, "schema_version": schema_version, "client_id": client_id,
                "affected_insight_ids": affected, "source_ref": source_ref, "summary": summary,
                "occurred_at": occurred_at, "received_at": received_at,
                "payload_digest": digest({k: v for k, v in payload.items() if k not in {"role"}}),
                "validation_state": "validated", "operations_disposition": None,
                "evidence_update_id": None, "reevaluation_id": None,
                "history": [
                    {"timestamp": received_at, "actor": self._actor(role), "action": "received"},
                    {"timestamp": received_at, "actor": "Clarity schema validation", "action": "validated"},
                ],
            }
            self.data["inbound"][event_id] = event
            self._audit(origin="source_data", object_type="inbound_integration_event", object_id=event_id,
                        action="inbound_received", actor=self._actor(role), client_id=client_id, insight_id=affected[0],
                        detail={"source_system": source_system, "schema_version": schema_version, "idempotency_key": key})
            self._audit(origin="system", object_type="inbound_integration_event", object_id=event_id,
                        action="inbound_validated", actor="Clarity schema validation", client_id=client_id, insight_id=affected[0],
                        detail={"validation_state": "validated", "payload_digest": event["payload_digest"]})
            self._save()
            return event, False

    def disposition(self, event_id: str, *, accepted: bool, rationale: str, role: str,
                    evidence_update_id: str | None = None, reevaluation_id: str | None = None) -> dict[str, Any]:
        if role != "operations":
            raise PermissionError("Only Product Operations can accept or reject inbound integration events.")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("An Operations rationale is required.")
        with self.lock:
            event = self.data["inbound"].get(event_id)
            if event is None:
                raise KeyError(f"Unknown inbound integration event {event_id}")
            if event["operations_disposition"] is not None:
                if event["operations_disposition"] == ("accepted" if accepted else "rejected"):
                    return event
                raise PermissionError("An inbound event already has an immutable Operations disposition.")
            disposition = "accepted" if accepted else "rejected"
            event.update({"operations_disposition": disposition, "evidence_update_id": evidence_update_id, "reevaluation_id": reevaluation_id})
            event["history"].append({"timestamp": now(), "actor": self._actor(role), "action": disposition, "reason": rationale.strip()})
            self._audit(origin="source_data", object_type="inbound_integration_event", object_id=event_id,
                        action=f"inbound_{disposition}", actor=self._actor(role), client_id=event["client_id"],
                        insight_id=event["affected_insight_ids"][0], detail={"rationale": rationale.strip(), "evidence_update_id": evidence_update_id, "reevaluation_id": reevaluation_id})
            self._save()
            return event

    def prepare_work_order(self, payload: dict[str, Any], role: str) -> tuple[dict[str, Any], bool]:
        if role != "rm":
            raise PermissionError("Only the RM can prepare simulated work orders.")
        destination = self._required(payload, "destination")
        if destination not in DESTINATIONS:
            raise ValueError("destination must be crm or specialist_queue.")
        client_id = self._required(payload, "client_id")
        record_type = self._required(payload, "work_record_type")
        if record_type not in {"task", "referral", "meeting_package", "client_ready_finding"}:
            raise ValueError("work_record_type must link a task, referral, meeting package, or client-ready finding.")
        record_id = self._required(payload, "work_record_id")
        version = self._required(payload, "work_record_version")
        owner_role = self._required(payload, "owner_role")
        if destination == "crm" and owner_role != "rm":
            raise ValueError("CRM work orders must remain RM-owned.")
        if destination == "specialist_queue" and owner_role not in SPECIALIST_ROLES:
            raise ValueError("Specialist-queue work orders require an assigned specialist owner.")
        evidence_refs = payload.get("evidence_refs") or []
        if not evidence_refs or not all(isinstance(item, str) and item.strip() for item in evidence_refs):
            raise ValueError("At least one evidence reference is required.")
        key = digest({"destination": destination, "record_type": record_type, "record_id": record_id, "version": version})
        with self.lock:
            existing_id = next((item_id for item_id, item in self.data["work_orders"].items() if item["idempotency_key"] == key), None)
            if existing_id:
                existing = self.data["work_orders"][existing_id]
                self._audit(origin="system", object_type="outbound_work_order", object_id=existing_id,
                            action="work_order_replayed", actor=self._actor(role), client_id=existing["client_id"], insight_id=existing.get("insight_id"), detail={"idempotency_key": key, "replayed": True})
                self._save()
                return existing, True
            order_id, created_at = str(uuid4()), now()
            order = {
                "id": order_id, "idempotency_key": key, "destination": destination,
                "work_record_type": record_type, "work_record_id": record_id, "work_record_version": version,
                "client_id": client_id, "insight_id": payload.get("insight_id") or None,
                "meeting_package_id": payload.get("meeting_package_id") or None, "owner_role": owner_role,
                "evidence_refs": evidence_refs, "status": "prepared", "external_reference": None,
                "created_at": created_at, "created_by": self._actor(role), "created_by_role": role,
                "history": [{"timestamp": created_at, "actor": self._actor(role), "action": "prepared"}],
            }
            self.data["work_orders"][order_id] = order
            self._audit(origin="user_decision", object_type="outbound_work_order", object_id=order_id,
                        action="work_order_prepared", actor=self._actor(role), client_id=client_id, insight_id=order["insight_id"],
                        detail={"destination": destination, "idempotency_key": key, "work_record_type": record_type, "work_record_id": record_id, "work_record_version": version})
            self._save()
            return order, False

    def dispatch(self, order_id: str, role: str) -> tuple[dict[str, Any], bool]:
        if role != "rm":
            raise PermissionError("Only the RM can dispatch simulated work orders.")
        with self.lock:
            order = self.data["work_orders"].get(order_id)
            if order is None:
                raise KeyError(f"Unknown work order {order_id}")
            if order["status"] in {"dispatched", "acknowledged"}:
                return order, True
            if order["status"] != "prepared":
                raise ValueError("Only prepared work orders can be dispatched.")
            reference = f"SIM-{'CRM' if order['destination'] == 'crm' else 'SPECIALIST'}-{order_id[:8].upper()}"
            order.update({"status": "dispatched", "external_reference": reference})
            order["history"].append({"timestamp": now(), "actor": self._actor(role), "action": "simulated_dispatched", "external_reference": reference})
            self._audit(origin="user_decision", object_type="outbound_work_order", object_id=order_id,
                        action="simulated_work_order_dispatched", actor=self._actor(role), client_id=order["client_id"], insight_id=order.get("insight_id"),
                        detail={"destination": order["destination"], "external_reference": reference, "local_simulation": True})
            self._save()
            return order, False

    def acknowledge(self, order_id: str, role: str) -> dict[str, Any]:
        if role not in SPECIALIST_ROLES:
            raise PermissionError("Only assigned specialists can acknowledge specialist work orders.")
        with self.lock:
            order = self.data["work_orders"].get(order_id)
            if order is None:
                raise KeyError(f"Unknown work order {order_id}")
            if order["destination"] != "specialist_queue" or order["owner_role"] != role:
                raise PermissionError("This specialist is not assigned to the work order.")
            if order["status"] == "acknowledged":
                return order
            if order["status"] != "dispatched":
                raise ValueError("Only dispatched specialist work orders can be acknowledged.")
            order["status"] = "acknowledged"
            order["history"].append({"timestamp": now(), "actor": self._actor(role), "action": "acknowledged"})
            self._audit(origin="user_decision", object_type="outbound_work_order", object_id=order_id,
                        action="specialist_work_order_acknowledged", actor=self._actor(role), client_id=order["client_id"], insight_id=order.get("insight_id"), detail={"owner_role": role})
            self._save()
            return order

    def audit(self, client_id: str | None = None) -> list[dict[str, Any]]:
        records = self.data["audit"]
        if client_id:
            records = [item for item in records if item.get("client_id") == client_id]
        return list(reversed(records))

    def reset(self) -> None:
        with self.lock:
            self.data = {"inbound": {}, "work_orders": {}, "audit": []}
            self._save()


_STORE: IntegrationStore | None = None


def get_integration_store() -> IntegrationStore:
    global _STORE
    if _STORE is None:
        _STORE = IntegrationStore()
    return _STORE
