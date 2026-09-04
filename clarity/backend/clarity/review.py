"""RM review state and append-only audit trail.

The JSON store is deliberately a local-demo adapter. ``ReviewRepository`` is
the narrow boundary a durable database implementation will later satisfy; the
workflow and decision gates are independent of its storage mechanism.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from . import config

STATE_DIR = config.REPO_ROOT / "clarity" / "state"
DECISIONS_PATH = STATE_DIR / "decisions.json"

VALID_STATUSES = (
    "new",
    "opened",
    "under_review",
    "rm_edited",
    "rm_reviewed",
    "escalated",
    "returned_for_review",
    "client_ready",
    "deferred",
    "dismissed",
)

_TRANSITIONS: dict[str, set[str]] = {
    "new": {"opened"},
    "opened": {"under_review"},
    "under_review": {"rm_edited", "rm_reviewed", "escalated", "deferred", "dismissed"},
    "rm_edited": {"rm_edited", "rm_reviewed", "escalated", "deferred", "dismissed"},
    "rm_reviewed": {"client_ready", "escalated", "deferred", "dismissed"},
    "escalated": {"returned_for_review"},
    "returned_for_review": {"under_review"},
    "client_ready": set(),
    "deferred": set(),
    "dismissed": set(),
}


class InvalidTransitionError(ValueError):
    """Raised when a requested workflow transition is not allowed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_reason(status: str, rm_note: str) -> None:
    if status in {"client_ready", "escalated", "deferred", "dismissed"} and not rm_note.strip():
        raise ValueError(f"An RM rationale is required for {status}.")


def validate_transition(previous: str, target: str) -> None:
    if target not in VALID_STATUSES:
        raise InvalidTransitionError(
            f"status must be one of {VALID_STATUSES}, received {target!r}"
        )
    if target not in _TRANSITIONS.get(previous, set()):
        raise InvalidTransitionError(f"Cannot transition from {previous!r} to {target!r}.")


@dataclass
class Decision:
    insight_id: str
    client_id: str
    status: str = "new"
    rm_note: str = ""
    selected_option_id: str | None = None
    edited_headline: str | None = None
    edited_next_step: str | None = None
    evidence_version: str | None = None
    selected_scenario_id: str | None = None
    scenario_calculation_version: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEntry:
    timestamp: str
    actor: str
    action: str
    insight_id: str
    client_id: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReviewRepository(Protocol):
    """Storage boundary for the Task 3 workflow."""

    def get(self, insight_id: str) -> Decision | None: ...

    def status_of(self, insight_id: str) -> str: ...

    def record(self, **kwargs: Any) -> Decision: ...

    def record_blocked_transition(self, **kwargs: Any) -> None: ...


class ReviewStore:
    """Thread-safe JSON-backed implementation of :class:`ReviewRepository`."""

    def __init__(self, path: Path = DECISIONS_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._decisions: dict[str, Decision] = {}
        self._audit: list[AuditEntry] = []
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        migrated = False
        for key, raw in payload.get("decisions", {}).items():
            raw = dict(raw)
            if raw.get("status") == "actioned":
                raw["status"] = "client_ready"
                migrated = True
            self._decisions[key] = Decision(**raw)
        self._audit = [AuditEntry(**entry) for entry in payload.get("audit", [])]
        if migrated:
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "decisions": {key: value.to_dict() for key, value in self._decisions.items()},
            "audit": [entry.to_dict() for entry in self._audit],
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- reads --------------------------------------------------------------

    def get(self, insight_id: str) -> Decision | None:
        return self._decisions.get(insight_id)

    def status_of(self, insight_id: str) -> str:
        decision = self._decisions.get(insight_id)
        return decision.status if decision else "new"

    def for_client(self, client_id: str) -> list[Decision]:
        return [decision for decision in self._decisions.values() if decision.client_id == client_id]

    def audit(self, client_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
        entries = [
            entry for entry in self._audit if client_id is None or entry.client_id == client_id
        ]
        return list(reversed(entries))[:limit]

    def counts(self) -> dict[str, int]:
        out = {status: 0 for status in VALID_STATUSES}
        for decision in self._decisions.values():
            out[decision.status] = out.get(decision.status, 0) + 1
        return out

    # -- writes -------------------------------------------------------------

    def record(
        self,
        *,
        insight_id: str,
        client_id: str,
        status: str,
        actor: str = "RM-SG-014",
        rm_note: str = "",
        selected_option_id: str | None = None,
        edited_headline: str | None = None,
        edited_next_step: str | None = None,
        gate_results: list[dict[str, Any]] | None = None,
        evidence_version: str | None = None,
        selected_scenario_id: str | None = None,
        scenario_calculation_version: str | None = None,
    ) -> Decision:
        _require_reason(status, rm_note)
        with self._lock:
            previous = self._decisions.get(insight_id)
            prior_status = previous.status if previous else "new"
            validate_transition(prior_status, status)
            decision = Decision(
                insight_id=insight_id,
                client_id=client_id,
                status=status,
                rm_note=rm_note or (previous.rm_note if previous else ""),
                selected_option_id=selected_option_id
                if selected_option_id is not None
                else (previous.selected_option_id if previous else None),
                edited_headline=edited_headline
                if edited_headline is not None
                else (previous.edited_headline if previous else None),
                edited_next_step=edited_next_step
                if edited_next_step is not None
                else (previous.edited_next_step if previous else None),
                evidence_version=evidence_version
                if evidence_version is not None
                else (previous.evidence_version if previous else None),
                selected_scenario_id=selected_scenario_id
                if selected_scenario_id is not None
                else (previous.selected_scenario_id if previous else None),
                scenario_calculation_version=scenario_calculation_version
                if scenario_calculation_version is not None
                else (previous.scenario_calculation_version if previous else None),
                decided_by=actor,
                decided_at=_now(),
            )
            self._decisions[insight_id] = decision
            self._audit.append(
                AuditEntry(
                    timestamp=decision.decided_at,
                    actor=actor,
                    action=f"status:{status}",
                    insight_id=insight_id,
                    client_id=client_id,
                    detail={
                        "from": prior_status,
                        "to": status,
                        "rm_note": rm_note,
                        "selected_option_id": selected_option_id,
                        "edited_headline": edited_headline,
                        "edited_next_step": edited_next_step,
                        "gates": gate_results or [],
                        "evidence_version": evidence_version,
                        "selected_scenario_id": selected_scenario_id,
                        "scenario_calculation_version": scenario_calculation_version,
                    },
                )
            )
            self._save()
            return decision

    def record_blocked_transition(
        self,
        *,
        insight_id: str,
        client_id: str,
        target_status: str,
        actor: str,
        gate_results: list[dict[str, Any]],
        evidence_version: str,
        selected_scenario_id: str | None = None,
        scenario_calculation_version: str | None = None,
    ) -> None:
        with self._lock:
            previous = self._decisions.get(insight_id)
            self._audit.append(
                AuditEntry(
                    timestamp=_now(),
                    actor=actor,
                    action=f"transition_blocked:{target_status}",
                    insight_id=insight_id,
                    client_id=client_id,
                    detail={
                        "from": previous.status if previous else "new",
                        "to": target_status,
                        "gates": gate_results,
                        "evidence_version": evidence_version,
                        "selected_scenario_id": selected_scenario_id,
                        "scenario_calculation_version": scenario_calculation_version,
                    },
                )
            )
            self._save()

    def add_note(
        self,
        *,
        client_id: str,
        note: str,
        channel: str = "Meeting",
        actor: str = "RM-SG-014",
    ) -> dict[str, Any]:
        with self._lock:
            ts = _now()
            entry = {
                "note_id": f"N-USR-{len(self._audit) + 1:04d}",
                "client_id": client_id,
                "note_date": ts[:10],
                "rm_id": actor,
                "rm_name": "Priscilla Ong",
                "channel": channel,
                "note": note,
            }
            self._audit.append(
                AuditEntry(
                    timestamp=ts,
                    actor=actor,
                    action="note:add",
                    insight_id=entry["note_id"],
                    client_id=client_id,
                    detail=entry,
                )
            )
            self._save()
            return entry

    def propose_objective(
        self,
        *,
        client_id: str,
        proposed_objective: str,
        rationale: str = "",
        actor: str = "RM-SG-014",
    ) -> dict[str, Any]:
        with self._lock:
            ts = _now()
            entry = {
                "client_id": client_id,
                "proposed_objective": proposed_objective,
                "rationale": rationale,
                "proposed_by": actor,
                "proposed_at": ts,
            }
            self._audit.append(
                AuditEntry(
                    timestamp=ts,
                    actor=actor,
                    action="objective:propose",
                    insight_id=f"OBJ-{client_id}",
                    client_id=client_id,
                    detail=entry,
                )
            )
            self._save()
            return entry

    def add_draft_to_meeting_brief(
        self,
        *,
        client_id: str,
        draft: dict[str, Any],
        actor: str = "RM-SG-014",
    ) -> dict[str, Any]:
        with self._lock:
            ts = _now()
            entry = {
                "client_id": client_id,
                "draft": draft,
                "added_by": actor,
                "added_at": ts,
            }
            self._audit.append(
                AuditEntry(
                    timestamp=ts,
                    actor=actor,
                    action="meeting_brief:add_draft",
                    insight_id=f"MB-DRAFT-{client_id}",
                    client_id=client_id,
                    detail=entry,
                )
            )
            self._save()
            return entry

    def reset(self) -> None:
        with self._lock:
            self._decisions.clear()
            self._audit.clear()
            self._save()



_STORE: ReviewStore | None = None


def get_store() -> ReviewStore:
    global _STORE
    if _STORE is None:
        _STORE = ReviewStore()
    return _STORE
