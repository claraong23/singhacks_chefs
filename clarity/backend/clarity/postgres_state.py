"""Shared PostgreSQL persistence for mutable Task 3 workflow repositories.

The domain repositories deliberately retain their small dictionary-shaped APIs.
This adapter makes those state documents durable, versioned, and reconstructable
without moving financial source data into the database.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from typing import Any, Iterator


SCHEMA_VERSION = "task3-workflow-v1"


class StateConflictError(RuntimeError):
    """Another serverless instance wrote the same workflow document first."""


class PostgresState:
    def __init__(self, database_url: str, namespace: str, default: dict[str, Any]) -> None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - deployment configuration
            raise RuntimeError("DATABASE_URL is set but psycopg is unavailable. Run pip install -r requirements.txt.") from exc
        self.psycopg, self.database_url, self.namespace = psycopg, database_url, namespace
        self.lock = threading.RLock()
        self.revision = 0
        self._deferred = 0
        self._dirty = False
        self._ensure_schema()
        self.payload = self.load(default)

    def _connect(self):
        return self.psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('clarity-task3-workflow-schema-v1'))")
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS clarity_workflow_state ("
                "namespace TEXT PRIMARY KEY, revision BIGINT NOT NULL, payload JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS clarity_workflow_audit ("
                "event_id TEXT PRIMARY KEY, namespace TEXT NOT NULL, timestamp TEXT NOT NULL, origin TEXT NOT NULL, "
                "object_type TEXT NOT NULL, object_id TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL, "
                "client_id TEXT, insight_id TEXT, detail JSONB NOT NULL)"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS clarity_workflow_audit_client_time ON clarity_workflow_audit (client_id, timestamp DESC)")

    @staticmethod
    def _decode(value: Any) -> dict[str, Any]:
        return json.loads(value) if isinstance(value, str) else dict(value)

    def load(self, default: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT revision, payload FROM clarity_workflow_state WHERE namespace = %s", (self.namespace,))
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    "INSERT INTO clarity_workflow_state (namespace, revision, payload) VALUES (%s, 0, %s::jsonb)",
                    (self.namespace, json.dumps(default)),
                )
                self.revision = 0
                return json.loads(json.dumps(default))
        self.revision = int(row[0])
        return self._decode(row[1])

    def _mirror_audit(self, cursor, payload: dict[str, Any]) -> None:
        for event in payload.get("audit", payload.get("events", [])):
            if not isinstance(event, dict) or not event.get("id"):
                continue
            cursor.execute(
                "INSERT INTO clarity_workflow_audit (event_id, namespace, timestamp, origin, object_type, object_id, action, actor, client_id, insight_id, detail) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (event_id) DO NOTHING",
                (str(event["id"]), self.namespace, str(event.get("timestamp", "")), str(event.get("origin", "system")),
                 str(event.get("object_type", self.namespace)), str(event.get("object_id", "")), str(event.get("action", "updated")),
                 str(event.get("actor", "Clarity")), event.get("client_id"), event.get("insight_id"), json.dumps(event.get("detail") or {})),
            )

    def save(self, payload: dict[str, Any]) -> None:
        with self.lock:
            if self._deferred:
                self.payload, self._dirty = payload, True
                return
            self._commit_one(payload)

    def _commit_one(self, payload: dict[str, Any]) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE clarity_workflow_state SET payload = %s::jsonb, revision = revision + 1, updated_at = now() "
                "WHERE namespace = %s AND revision = %s RETURNING revision",
                (json.dumps(payload), self.namespace, self.revision),
            )
            row = cursor.fetchone()
            if not row:
                raise StateConflictError(f"Concurrent update detected for {self.namespace}; reload and retry.")
            self._mirror_audit(cursor, payload)
            self.revision, self.payload = int(row[0]), payload

    @classmethod
    @contextmanager
    def transaction(cls, *states: "PostgresState") -> Iterator[None]:
        """Commit several mutated state documents in one PostgreSQL transaction."""
        states = tuple(sorted({state for state in states}, key=lambda item: item.namespace))
        original = {state: json.loads(json.dumps(state.payload)) for state in states}
        for state in states:
            state.lock.acquire(); state._deferred += 1
        try:
            yield
            dirty = [state for state in states if state._dirty]
            if not dirty:
                return
            first = dirty[0]
            with first._connect() as connection, connection.cursor() as cursor:
                for state in dirty:
                    cursor.execute("SELECT revision FROM clarity_workflow_state WHERE namespace = %s FOR UPDATE", (state.namespace,))
                    row = cursor.fetchone()
                    if not row or int(row[0]) != state.revision:
                        raise StateConflictError(f"Concurrent update detected for {state.namespace}; reload and retry.")
                for state in dirty:
                    cursor.execute("UPDATE clarity_workflow_state SET payload = %s::jsonb, revision = revision + 1, updated_at = now() WHERE namespace = %s RETURNING revision", (json.dumps(state.payload), state.namespace))
                    state.revision = int(cursor.fetchone()[0])
                    state._mirror_audit(cursor, state.payload)
                    state._dirty = False
        except Exception:
            for state in states:
                state.payload, state._dirty = original[state], False
            raise
        finally:
            for state in reversed(states):
                state._deferred -= 1; state.lock.release()

    def status(self) -> dict[str, Any]:
        return {"namespace": self.namespace, "revision": self.revision, "schema_version": SCHEMA_VERSION}
