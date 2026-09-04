"""JSON persistence adapter for versioned Meeting Studio packages.

This is deliberately a narrow local-demo repository.  A production adapter can
replace it without changing deterministic package generation or preflight.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from . import config

STATE_DIR = config.REPO_ROOT / "clarity" / "state"
MEETINGS_PATH = STATE_DIR / "meetings.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MeetingRepository(Protocol):
    def create(self, package: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, package_id: str) -> dict[str, Any] | None: ...
    def list_for_client(self, client_id: str) -> list[dict[str, Any]]: ...
    def append_version(self, package_id: str, version: dict[str, Any]) -> dict[str, Any]: ...
    def mark_preflight(self, package_id: str, result: dict[str, Any]) -> dict[str, Any]: ...
    def append_handoff(self, package_id: str, event: dict[str, Any]) -> dict[str, Any]: ...
    def reset(self) -> None: ...


class MeetingStore:
    def __init__(self, path: Path = MEETINGS_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._packages: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._packages = {
                str(key): value for key, value in payload.get("packages", {}).items()
            }
        except (json.JSONDecodeError, OSError):
            self._packages = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"packages": self._packages}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def create(self, package: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._packages[package["id"]] = package
            self._save()
            return package

    def get(self, package_id: str) -> dict[str, Any] | None:
        return self._packages.get(package_id)

    def list_for_client(self, client_id: str) -> list[dict[str, Any]]:
        return sorted(
            [item for item in self._packages.values() if item["client_id"] == client_id],
            key=lambda item: item["created_at"],
            reverse=True,
        )

    def append_version(self, package_id: str, version: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            package = self._packages[package_id]
            package["versions"].append(version)
            package["current_version"] = version["version"]
            package["state"] = "draft"
            package.pop("last_preflight", None)
            self._save()
            return package

    def mark_preflight(self, package_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            package = self._packages[package_id]
            package["last_preflight"] = result
            package.setdefault("preflights", []).append(result)
            package["state"] = "preflight_passed" if result.get("can_hand_off") else "draft"
            self._save()
            return package

    def append_handoff(self, package_id: str, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            package = self._packages[package_id]
            package.setdefault("handoffs", []).append(event)
            package["state"] = "handed_off"
            self._save()
            return package

    def reset(self) -> None:
        with self._lock:
            self._packages.clear()
            self._save()


def new_id() -> str:
    return str(uuid4())


_STORE: MeetingStore | None = None


def get_meeting_store() -> MeetingStore:
    global _STORE
    if _STORE is None:
        _STORE = MeetingStore()
    return _STORE
