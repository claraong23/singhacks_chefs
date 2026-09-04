"""JSON persistence adapter for saved Scenario Studio comparisons."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .review import STATE_DIR

SCENARIOS_PATH = STATE_DIR / "scenarios.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ScenarioRepository(Protocol):
    def save(self, *, name: str, result: dict[str, Any], saved_by: str) -> dict[str, Any]: ...

    def list_for_client(self, client_id: str) -> list[dict[str, Any]]: ...

    def get(self, scenario_id: str) -> dict[str, Any] | None: ...


class ScenarioStore:
    """Thread-safe local-demo adapter; replaceable by a database repository."""

    def __init__(self, path: Path = SCENARIOS_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._scenarios: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._scenarios = {str(key): value for key, value in payload.get("scenarios", {}).items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"scenarios": self._scenarios}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save(self, *, name: str, result: dict[str, Any], saved_by: str = "RM-SG-014") -> dict[str, Any]:
        if not name.strip():
            raise ValueError("A scenario name is required.")
        with self._lock:
            scenario = {
                "id": f"scn-{uuid.uuid4().hex[:12]}",
                "name": name.strip(),
                "saved_by": saved_by,
                "saved_at": _now(),
                "result": result,
            }
            self._scenarios[scenario["id"]] = scenario
            self._save()
            return scenario

    def list_for_client(self, client_id: str) -> list[dict[str, Any]]:
        rows = [
            value
            for value in self._scenarios.values()
            if value.get("result", {}).get("client_id") == client_id
        ]
        return sorted(rows, key=lambda item: item.get("saved_at", ""), reverse=True)

    def get(self, scenario_id: str) -> dict[str, Any] | None:
        return self._scenarios.get(scenario_id)

    def reset(self) -> None:
        with self._lock:
            self._scenarios.clear()
            self._save()


_STORE: ScenarioStore | None = None


def get_scenario_store() -> ScenarioStore:
    global _STORE
    if _STORE is None:
        _STORE = ScenarioStore()
    return _STORE
