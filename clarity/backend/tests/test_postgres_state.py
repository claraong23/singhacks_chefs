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
from clarity.postgres_state import PostgresState
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


if __name__ == "__main__":
    unittest.main()
