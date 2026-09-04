"""Optional PostgreSQL implementation of the RM review repository."""

from __future__ import annotations

import json
from typing import Any

from . import config
from .contracts import Insight
from .review import (
    VALID_STATUSES,
    AuditEntry,
    Decision,
    _now,
    _require_reason,
    _severity_rank,
    alert_evidence_version,
    validate_transition,
)


class PostgresReviewStore:
    """Durable drop-in counterpart to the local JSON ``ReviewStore``."""

    def __init__(self, database_url: str) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg is not installed. Run pip install -r requirements.txt."
            ) from exc
        self._psycopg = psycopg
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return self._psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS clarity_decisions ("
                "insight_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, decision JSONB NOT NULL)"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS clarity_audit ("
                "audit_id BIGSERIAL PRIMARY KEY, timestamp TEXT NOT NULL, actor TEXT NOT NULL, "
                "action TEXT NOT NULL, insight_id TEXT NOT NULL, client_id TEXT NOT NULL, "
                "detail JSONB NOT NULL DEFAULT '{}'::jsonb)"
            )

    @staticmethod
    def _decode(value: Any) -> dict[str, Any]:
        return json.loads(value) if isinstance(value, str) else dict(value)

    def _insert_audit(self, cursor, entry: AuditEntry) -> None:
        cursor.execute(
            "INSERT INTO clarity_audit (timestamp, actor, action, insight_id, client_id, detail) "
            "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (entry.timestamp, entry.actor, entry.action, entry.insight_id, entry.client_id, json.dumps(entry.detail)),
        )

    def get(self, insight_id: str) -> Decision | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT decision FROM clarity_decisions WHERE insight_id = %s", (insight_id,))
            row = cursor.fetchone()
        return Decision(**self._decode(row[0])) if row else None

    def status_of(self, insight_id: str) -> str:
        decision = self.get(insight_id)
        return decision.status if decision else "new"

    def effective_status(self, insight: Insight) -> tuple[str, str | None]:
        decision = self.get(insight.id)
        if decision is None:
            return "new", None
        if decision.status != "dismissed":
            return decision.status, None
        if decision.severity_at_decision and _severity_rank(insight.severity.value) > _severity_rank(decision.severity_at_decision):
            return "new", f"Severity increased from {decision.severity_at_decision} to {insight.severity.value}."
        if decision.amount_usd_at_decision is not None and insight.amount_usd is not None:
            change_pct = abs(insight.amount_usd - decision.amount_usd_at_decision) / max(abs(decision.amount_usd_at_decision), 1.0) * 100.0
            if change_pct >= config.ALERT_REOPEN_CHANGE_PCT:
                return "new", f"Measured amount changed by {change_pct:.1f}% since dismissal (reopen threshold {config.ALERT_REOPEN_CHANGE_PCT:.0f}%)."
        if decision.alert_evidence_version and decision.alert_evidence_version != alert_evidence_version(insight):
            return "new", "The supporting evidence changed since dismissal."
        return "dismissed", None

    def for_client(self, client_id: str) -> list[Decision]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT decision FROM clarity_decisions WHERE client_id = %s", (client_id,))
            return [Decision(**self._decode(row[0])) for row in cursor.fetchall()]

    def audit(self, client_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
        sql = "SELECT timestamp, actor, action, insight_id, client_id, detail FROM clarity_audit"
        if client_id is None:
            sql += " ORDER BY audit_id DESC LIMIT %s"
            params: tuple[Any, ...] = (limit,)
        else:
            sql += " WHERE client_id = %s ORDER BY audit_id DESC LIMIT %s"
            params = (client_id, limit)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [AuditEntry(row[0], row[1], row[2], row[3], row[4], self._decode(row[5])) for row in cursor.fetchall()]

    def counts(self) -> dict[str, int]:
        out = {status: 0 for status in VALID_STATUSES}
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT decision->>'status', COUNT(*) FROM clarity_decisions GROUP BY decision->>'status'")
            for status, count in cursor.fetchall():
                out[status] = count
        return out

    def record(
        self, *, insight_id: str, client_id: str, status: str,
        actor: str = "RM-SG-014", rm_note: str | None = None,
        selected_option_id: str | None = None, edited_headline: str | None = None,
        edited_next_step: str | None = None,
        gate_results: list[dict[str, Any]] | None = None,
        evidence_version: str | None = None, selected_scenario_id: str | None = None,
        scenario_calculation_version: str | None = None,
        feedback: dict[str, Any] | None = None, insight: Insight | None = None,
    ) -> Decision:
        previous = self.get(insight_id)
        prior_status = previous.status if previous else "new"
        validate_transition(prior_status, status)
        actual_note = rm_note if rm_note is not None else (previous.rm_note if previous else "")
        _require_reason(status, actual_note)
        decision = Decision(
            insight_id=insight_id, client_id=client_id, status=status, rm_note=actual_note,
            selected_option_id=selected_option_id if selected_option_id is not None else (previous.selected_option_id if previous else None),
            edited_headline=edited_headline if edited_headline is not None else (previous.edited_headline if previous else None),
            edited_next_step=edited_next_step if edited_next_step is not None else (previous.edited_next_step if previous else None),
            evidence_version=evidence_version if evidence_version is not None else (previous.evidence_version if previous else None),
            selected_scenario_id=selected_scenario_id if selected_scenario_id is not None else (previous.selected_scenario_id if previous else None),
            scenario_calculation_version=scenario_calculation_version if scenario_calculation_version is not None else (previous.scenario_calculation_version if previous else None),
            decided_by=actor, decided_at=_now(),
            severity_at_decision=insight.severity.value if insight else (previous.severity_at_decision if previous else None),
            amount_usd_at_decision=insight.amount_usd if insight else (previous.amount_usd_at_decision if previous else None),
            alert_evidence_version=alert_evidence_version(insight) if insight else (previous.alert_evidence_version if previous else None),
        )
        detail = {
            "from": prior_status, "to": status, "rm_note": actual_note,
            "selected_option_id": selected_option_id, "edited_headline": edited_headline,
            "edited_next_step": edited_next_step, "gates": gate_results or [],
            "evidence_version": evidence_version, "selected_scenario_id": selected_scenario_id,
            "scenario_calculation_version": scenario_calculation_version, "feedback": feedback or None,
        }
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO clarity_decisions (insight_id, client_id, decision) VALUES (%s,%s,%s::jsonb) "
                "ON CONFLICT (insight_id) DO UPDATE SET client_id=EXCLUDED.client_id, decision=EXCLUDED.decision",
                (insight_id, client_id, json.dumps(decision.to_dict())),
            )
            self._insert_audit(cursor, AuditEntry(decision.decided_at or _now(), actor, f"status:{status}", insight_id, client_id, detail))
        return decision

    def reset_decision(self, insight_id: str, actor: str = "RM-SG-014") -> None:
        previous = self.get(insight_id)
        if previous is None:
            return
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM clarity_decisions WHERE insight_id = %s", (insight_id,))
            self._insert_audit(cursor, AuditEntry(_now(), actor, "decision:reset", insight_id, previous.client_id, {"prior_status": previous.status, "prior_note": previous.rm_note}))

    def record_blocked_transition(self, *, insight_id: str, client_id: str, target_status: str, actor: str, gate_results: list[dict[str, Any]], evidence_version: str, selected_scenario_id: str | None = None, scenario_calculation_version: str | None = None) -> None:
        previous = self.get(insight_id)
        detail = {"from": previous.status if previous else "new", "to": target_status, "gates": gate_results, "evidence_version": evidence_version, "selected_scenario_id": selected_scenario_id, "scenario_calculation_version": scenario_calculation_version}
        with self._connect() as connection, connection.cursor() as cursor:
            self._insert_audit(cursor, AuditEntry(_now(), actor, f"transition_blocked:{target_status}", insight_id, client_id, detail))

    def _context_event(self, action: str, insight_id: str, client_id: str, actor: str, detail: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection, connection.cursor() as cursor:
            self._insert_audit(cursor, AuditEntry(_now(), actor, action, insight_id, client_id, detail))
        return detail

    def add_note(self, *, client_id: str, note: str, channel: str = "Meeting", actor: str = "RM-SG-014") -> dict[str, Any]:
        timestamp = _now()
        entry = {"note_id": f"N-USR-{timestamp.replace(':', '').replace('-', '')}", "client_id": client_id, "note_date": timestamp[:10], "rm_id": actor, "rm_name": "Priscilla Ong", "channel": channel, "note": note}
        return self._context_event("note:add", entry["note_id"], client_id, actor, entry)

    def propose_objective(self, *, client_id: str, proposed_objective: str, rationale: str = "", actor: str = "RM-SG-014") -> dict[str, Any]:
        entry = {"client_id": client_id, "proposed_objective": proposed_objective, "rationale": rationale, "proposed_by": actor, "proposed_at": _now()}
        return self._context_event("objective:propose", f"OBJ-{client_id}", client_id, actor, entry)

    def add_draft_to_meeting_brief(self, *, client_id: str, draft: dict[str, Any], actor: str = "RM-SG-014") -> dict[str, Any]:
        entry = {"client_id": client_id, "draft": draft, "added_by": actor, "added_at": _now()}
        return self._context_event("meeting_brief:add_draft", f"MB-DRAFT-{client_id}", client_id, actor, entry)

    def reset(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM clarity_audit")
            cursor.execute("DELETE FROM clarity_decisions")
