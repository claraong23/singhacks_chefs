"""RM review state and append-only audit trail.

The JSON store is deliberately a local-demo adapter. ``ReviewRepository`` is
the narrow boundary a durable database implementation will later satisfy; the
workflow and decision gates are independent of its storage mechanism.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from . import config
from .contracts import Insight

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
    "under_review": {"under_review", "opened", "rm_edited", "rm_reviewed", "escalated", "deferred", "dismissed"},
    "rm_edited": {"rm_edited", "under_review", "opened", "rm_reviewed", "escalated", "deferred", "dismissed"},
    "rm_reviewed": {"rm_reviewed", "rm_edited", "under_review", "opened", "client_ready", "escalated", "deferred", "dismissed"},
    "escalated": {"escalated", "returned_for_review", "under_review", "opened"},
    "returned_for_review": {"under_review", "rm_reviewed", "opened"},
    "client_ready": {"client_ready", "rm_reviewed", "rm_edited", "under_review", "opened"},
    "deferred": {"deferred", "under_review", "opened"},
    "dismissed": {"dismissed", "under_review", "opened"},
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
    severity_at_decision: str | None = None
    amount_usd_at_decision: float | None = None
    alert_evidence_version: str | None = None

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

    def effective_status(self, insight: Insight) -> tuple[str, str | None]: ...

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

    def effective_status(self, insight: Insight) -> tuple[str, str | None]:
        """Reopen a dismissal only when its measured basis changes materially."""
        decision = self._decisions.get(insight.id)
        if decision is None:
            return "new", None
        if decision.status != "dismissed":
            return decision.status, None
        old_severity = decision.severity_at_decision
        if old_severity and _severity_rank(insight.severity.value) > _severity_rank(old_severity):
            return "new", f"Severity increased from {old_severity} to {insight.severity.value}."
        if decision.amount_usd_at_decision is not None and insight.amount_usd is not None:
            change_pct = (
                abs(insight.amount_usd - decision.amount_usd_at_decision)
                / max(abs(decision.amount_usd_at_decision), 1.0)
                * 100.0
            )
            if change_pct >= config.ALERT_REOPEN_CHANGE_PCT:
                return "new", (
                    f"Measured amount changed by {change_pct:.1f}% since dismissal "
                    f"(reopen threshold {config.ALERT_REOPEN_CHANGE_PCT:.0f}%)."
                )
        current_version = alert_evidence_version(insight)
        if decision.alert_evidence_version and decision.alert_evidence_version != current_version:
            return "new", "The supporting evidence changed since dismissal."
        return "dismissed", None

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
        rm_note: str | None = None,
        selected_option_id: str | None = None,
        edited_headline: str | None = None,
        edited_next_step: str | None = None,
        gate_results: list[dict[str, Any]] | None = None,
        evidence_version: str | None = None,
        selected_scenario_id: str | None = None,
        scenario_calculation_version: str | None = None,
        feedback: dict[str, Any] | None = None,
        insight: Insight | None = None,
    ) -> Decision:
        with self._lock:
            previous = self._decisions.get(insight_id)
            prior_status = previous.status if previous else "new"
            validate_transition(prior_status, status)
            actual_note = rm_note if rm_note is not None else (previous.rm_note if previous else "")
            _require_reason(status, actual_note)
            decision = Decision(
                insight_id=insight_id,
                client_id=client_id,
                status=status,
                rm_note=actual_note,
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
                severity_at_decision=(
                    insight.severity.value if insight else (previous.severity_at_decision if previous else None)
                ),
                amount_usd_at_decision=(
                    insight.amount_usd if insight else (previous.amount_usd_at_decision if previous else None)
                ),
                alert_evidence_version=(
                    alert_evidence_version(insight)
                    if insight
                    else (previous.alert_evidence_version if previous else None)
                ),
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
                        "rm_note": actual_note,
                        "selected_option_id": selected_option_id,
                        "edited_headline": edited_headline,
                        "edited_next_step": edited_next_step,
                        "gates": gate_results or [],
                        "evidence_version": evidence_version,
                        "selected_scenario_id": selected_scenario_id,
                        "scenario_calculation_version": scenario_calculation_version,
                        "feedback": feedback or None,
                    },
                )
            )
            self._save()
            return decision

    def reset_decision(self, insight_id: str, actor: str = "RM-SG-014") -> None:
        with self._lock:
            previous = self._decisions.get(insight_id)
            if not previous:
                return
            client_id = previous.client_id
            del self._decisions[insight_id]
            self._audit.append(
                AuditEntry(
                    timestamp=_now(),
                    actor=actor,
                    action="decision:reset",
                    insight_id=insight_id,
                    client_id=client_id,
                    detail={"prior_status": previous.status, "prior_note": previous.rm_note},
                )
            )
            self._save()

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
        if config.DATABASE_URL:
            from .postgres_review import PostgresReviewStore

            _STORE = PostgresReviewStore(config.DATABASE_URL)  # type: ignore[assignment]
        else:
            _STORE = ReviewStore()
    return _STORE


_SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _severity_rank(value: str) -> int:
    return _SEVERITY_ORDER.get(value, 0)


def alert_evidence_version(insight: Insight) -> str:
    """Fingerprint evidence identity; amount changes are tested separately."""
    payload = [
        {
            "source_file": item.source_file,
            "row_or_id": item.row_or_id,
            "field": item.field,
            "snapshot_date": item.snapshot_date,
        }
        for item in insight.evidence
    ]
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
