"""RM review state and the audit trail.

Human oversight is the product, not a feature of it, so the decision record is a
first-class object: who decided, when, on what, and what they changed. Every
mutation appends to an immutable audit log. Nothing is ever overwritten in place
without leaving the previous value behind.

Storage is a JSON file. In a bank this is a database with retention controls;
the shape of the record is what matters for the prototype.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

STATE_DIR = config.REPO_ROOT / "clarity" / "state"
DECISIONS_PATH = STATE_DIR / "decisions.json"

VALID_STATUSES = ("new", "reviewed", "dismissed", "actioned")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Decision:
    insight_id: str
    client_id: str
    status: str = "new"
    rm_note: str = ""
    selected_option_id: str | None = None
    edited_headline: str | None = None
    edited_next_step: str | None = None
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


class ReviewStore:
    """Thread-safe JSON-backed store for RM decisions."""

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
        self._decisions = {
            k: Decision(**v) for k, v in payload.get("decisions", {}).items()
        }
        self._audit = [AuditEntry(**e) for e in payload.get("audit", [])]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "decisions": {k: v.to_dict() for k, v in self._decisions.items()},
            "audit": [e.to_dict() for e in self._audit],
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
        return [d for d in self._decisions.values() if d.client_id == client_id]

    def audit(self, client_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
        entries = [
            e for e in self._audit if client_id is None or e.client_id == client_id
        ]
        return list(reversed(entries))[:limit]

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in VALID_STATUSES}
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
    ) -> Decision:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_STATUSES}, received {status!r}"
            )
        with self._lock:
            previous = self._decisions.get(insight_id)
            decision = Decision(
                insight_id=insight_id,
                client_id=client_id,
                status=status,
                rm_note=rm_note or (previous.rm_note if previous else ""),
                selected_option_id=selected_option_id
                or (previous.selected_option_id if previous else None),
                edited_headline=edited_headline
                if edited_headline is not None
                else (previous.edited_headline if previous else None),
                edited_next_step=edited_next_step
                if edited_next_step is not None
                else (previous.edited_next_step if previous else None),
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
                        "from": previous.status if previous else "new",
                        "to": status,
                        "rm_note": rm_note,
                        "selected_option_id": selected_option_id,
                        "edited_headline": edited_headline,
                        "edited_next_step": edited_next_step,
                    },
                )
            )
            self._save()
            return decision

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
