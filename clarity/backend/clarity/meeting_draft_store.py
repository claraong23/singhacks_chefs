"""JSON persistence adapter for saved client attribution talking points in Meeting Studio."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

STATE_DIR = config.REPO_ROOT / "clarity" / "state"
MEETING_DRAFTS_PATH = STATE_DIR / "meeting_drafts.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MeetingDraftStore:
    """Thread-safe local-demo adapter for client conversation talking point drafts."""

    def __init__(self, path: Path = MEETING_DRAFTS_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._drafts: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._drafts = {str(key): value for key, value in payload.get("drafts", {}).items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"drafts": self._drafts}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save(self, client_id: str, draft: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            draft_id = draft.get("id") or f"draft-{uuid.uuid4().hex[:12]}"
            record = {
                **draft,
                "id": draft_id,
                "client_id": client_id,
                "created_at": draft.get("created_at") or _now(),
                "updated_at": _now(),
            }
            self._drafts[draft_id] = record
            self._save()
            return record

    def list_for_client(self, client_id: str) -> list[dict[str, Any]]:
        with self._lock:
            items = [
                draft
                for draft in self._drafts.values()
                if draft.get("client_id") == client_id
            ]
            items.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
            return items

    def update(self, client_id: str, draft_id: str, draft: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            if draft_id not in self._drafts:
                return None
            record = {
                **self._drafts[draft_id],
                **draft,
                "id": draft_id,
                "client_id": client_id,
                "updated_at": _now(),
            }
            self._drafts[draft_id] = record
            self._save()
            return record

    def delete(self, client_id: str, draft_id: str) -> bool:
        with self._lock:
            if draft_id in self._drafts and self._drafts[draft_id].get("client_id") == client_id:
                del self._drafts[draft_id]
                self._save()
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._drafts = {}
            self._save()


_STORE: MeetingDraftStore | None = None


def get_meeting_draft_store() -> MeetingDraftStore:
    global _STORE
    if _STORE is None:
        _STORE = MeetingDraftStore()
    return _STORE
