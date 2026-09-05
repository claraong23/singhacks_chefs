"""Optional isolated PostgreSQL integration contract for durable workflow state."""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

from clarity.ai_drafting import PostgresAIDraftAuditStore
from clarity.calibration_store import PostgresCalibrationStore
from clarity.followthrough_store import PostgresFollowThroughStore
from clarity.integration_store import PostgresIntegrationStore
from clarity.knowledge_store import PostgresKnowledgeRepository
from clarity.meeting_store import PostgresMeetingStore
from clarity.postgres_state import PostgresState, StateConflictError
from clarity.postgres_review import PostgresReviewStore
from clarity.scenario_store import PostgresScenarioStore


@unittest.skipUnless(os.environ.get("CLARITY_TEST_DATABASE_URL"), "set CLARITY_TEST_DATABASE_URL for PostgreSQL integration tests")
class TestPostgresState(unittest.TestCase):
    def test_state_survives_new_adapter_and_transaction_commits_together(self) -> None:
        url, suffix = os.environ["CLARITY_TEST_DATABASE_URL"], uuid4().hex
        first = PostgresState(url, f"test-first-{suffix}", {"audit": [], "value": 0})
        second = PostgresState(url, f"test-second-{suffix}", {"audit": [], "value": 0})
        with PostgresState.transaction(first, second):
            first.payload["value"] = 1; first.save(first.payload)
            second.payload["value"] = 2; second.save(second.payload)
        restored = PostgresState(url, first.namespace, {})
        self.assertEqual(restored.payload["value"], 1)
        self.assertEqual(PostgresState(url, second.namespace, {}).payload["value"], 2)

    def test_every_mutable_task3_adapter_uses_the_isolated_database(self) -> None:
        url = os.environ["CLARITY_TEST_DATABASE_URL"]
        scenario = PostgresScenarioStore(url); scenario.reset()
        saved = scenario.save(name="Lau test", result={"client_id": "CL-0014"}, saved_by="RM-SG-014")
        meeting = PostgresMeetingStore(url); meeting.reset(); meeting.create({"id": "pg-meeting", "client_id": "CL-0003", "created_at": "2026-08-26", "versions": [], "current_version": 0, "state": "draft"})
        follow = PostgresFollowThroughStore(url); follow.reset(); follow.create("tasks", {"client_id": "CL-0017", "title": "Test", "status": "open"}, origin="user_decision", actor="RM-SG-014")
        calibration = PostgresCalibrationStore(url); calibration.reset(); self.assertEqual(calibration.active()["id"], "baseline-v1")
        knowledge = PostgresKnowledgeRepository(url); knowledge.reset(); self.assertEqual(len(knowledge.list("rm")), 5)
        integration = PostgresIntegrationStore(url); integration.reset(); integration.receive({"source_system": "lending_credit", "external_event_id": "pg-test", "schema_version": "v1", "client_id": "CL-0014", "affected_insight_ids": ["pg-insight"], "source_ref": "sandbox:pg", "summary": "Test", "occurred_at": "2026-08-26"}, "operations")
        ai_audit = PostgresAIDraftAuditStore(url); ai_audit.reset(); ai_audit.record(origin="system", action="test", package={"id": "pg-package", "client_id": "CL-0014", "insight_id": "pg-insight"}, actor="RM-SG-014", detail={})
        review = PostgresReviewStore(url); review.reset(); review.record(insight_id="pg-review", client_id="CL-0014", status="opened")

        self.assertIsNotNone(PostgresScenarioStore(url).get(saved["id"]))
        self.assertIsNotNone(PostgresMeetingStore(url).get("pg-meeting"))
        self.assertEqual(len(PostgresFollowThroughStore(url).list("tasks")), 1)
        self.assertEqual(len(PostgresIntegrationStore(url).list("operations")["inbound"]), 1)
        self.assertEqual(len(PostgresAIDraftAuditStore(url).audit()), 1)
        self.assertEqual(PostgresReviewStore(url).status_of("pg-review"), "opened")

    def test_conflicts_and_failed_transactions_leave_no_partial_state(self) -> None:
        url, suffix = os.environ["CLARITY_TEST_DATABASE_URL"], uuid4().hex
        first = PostgresState(url, f"test-conflict-{suffix}", {"audit": [], "value": 0})
        stale = PostgresState(url, first.namespace, {"audit": [], "value": 0})
        first.payload["value"] = 1; first.save(first.payload)
        stale.payload["value"] = 2
        with self.assertRaises(StateConflictError):
            stale.save(stale.payload)
        self.assertEqual(PostgresState(url, first.namespace, {}).payload["value"], 1)

        left = PostgresState(url, f"test-rollback-left-{suffix}", {"audit": [], "value": 0})
        right = PostgresState(url, f"test-rollback-right-{suffix}", {"audit": [], "value": 0})
        with self.assertRaisesRegex(RuntimeError, "simulated failure"):
            with PostgresState.transaction(left, right):
                left.payload["value"] = 1; left.save(left.payload)
                right.payload["value"] = 2; right.save(right.payload)
                raise RuntimeError("simulated failure")
        self.assertEqual(PostgresState(url, left.namespace, {}).payload["value"], 0)
        self.assertEqual(PostgresState(url, right.namespace, {}).payload["value"], 0)

    def test_integration_acceptance_and_policy_activation_are_atomic(self) -> None:
        url, suffix = os.environ["CLARITY_TEST_DATABASE_URL"], uuid4().hex
        integration = PostgresIntegrationStore(url); integration.reset()
        follow = PostgresFollowThroughStore(url); follow.reset()
        event, _ = integration.receive({
            "source_system": "lending_credit", "external_event_id": f"atomic-{suffix}",
            "schema_version": "v1", "client_id": "CL-0014", "affected_insight_ids": ["pg-insight"],
            "source_ref": "sandbox:atomic", "summary": "Synthetic atomic acceptance test.",
            "occurred_at": "2026-08-26",
        }, "operations")
        with self.assertRaisesRegex(RuntimeError, "simulate re-evaluation failure"):
            with PostgresState.transaction(integration._pg, follow._pg):
                follow.create("evidence_updates", {"client_id": "CL-0014", "status": "recorded"}, origin="source_data", actor="OPS-SG-001")
                raise RuntimeError("simulate re-evaluation failure")
        reloaded_integration, reloaded_follow = PostgresIntegrationStore(url), PostgresFollowThroughStore(url)
        self.assertIsNone(reloaded_integration.data["inbound"][event["id"]]["operations_disposition"])
        self.assertEqual(reloaded_follow.list("evidence_updates"), [])

        with PostgresState.transaction(integration._pg, follow._pg):
            update = follow.create("evidence_updates", {"client_id": "CL-0014", "status": "recorded"}, origin="source_data", actor="OPS-SG-001")
            reevaluation = follow.create("reevaluations", {"client_id": "CL-0014", "status": "queued"}, origin="source_data", actor="OPS-SG-001")
            integration.disposition(event["id"], accepted=True, rationale="Validated synthetic source update.", role="operations", evidence_update_id=update["id"], reevaluation_id=reevaluation["id"])
        persisted = PostgresIntegrationStore(url).data["inbound"][event["id"]]
        self.assertEqual(persisted["operations_disposition"], "accepted")
        self.assertEqual(len(PostgresFollowThroughStore(url).list("evidence_updates")), 1)
        self.assertEqual(len(PostgresFollowThroughStore(url).list("reevaluations")), 1)

        calibration = PostgresCalibrationStore(url); calibration.reset()
        candidate = calibration.create(name="Atomic policy", weights={"severity": 0.35, "materiality": 0.20, "urgency": 0.45}, rationale="Synthetic activation test.", actor="RM-SG-014")
        calibration.transition(candidate["id"], status="submitted", actor="RM-SG-014", rationale="Submit synthetic policy.")
        calibration.activate(candidate["id"], actor="COMPLIANCE-SG-001", rationale="Approve synthetic policy.")
        policies = PostgresCalibrationStore(url).list()
        self.assertEqual([policy["id"] for policy in policies if policy["status"] == "active"], [candidate["id"]])
        self.assertEqual(next(policy for policy in policies if policy["id"] == "baseline-v1")["status"], "retired")


if __name__ == "__main__":
    unittest.main()
