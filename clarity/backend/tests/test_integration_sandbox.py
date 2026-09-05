"""Replayable integration boundary tests; all calls stay on the local test server."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clarity.api import ClarityHandler
from clarity.followthrough_store import FollowThroughStore
from clarity.integration_store import IntegrationStore
from clarity.loaders import get_book
from clarity.meeting_store import MeetingStore
from clarity.review import ReviewStore
from clarity.scenario_store import ScenarioStore
from clarity.signals import run_for_client

BOOK = get_book()


class TestIntegrationSandboxHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from http.server import ThreadingHTTPServer
        from clarity import followthrough_store, integration_store, meeting_store, review, scenario_store

        cls.temp = TemporaryDirectory()
        cls.previous = review._STORE, scenario_store._STORE, meeting_store._STORE, followthrough_store._STORE, integration_store._STORE
        review._STORE = ReviewStore(Path(cls.temp.name) / "decisions.json")
        scenario_store._STORE = ScenarioStore(Path(cls.temp.name) / "scenarios.json")
        meeting_store._STORE = MeetingStore(Path(cls.temp.name) / "meetings.json")
        followthrough_store._STORE = FollowThroughStore(Path(cls.temp.name) / "follow.json")
        integration_store._STORE = IntegrationStore(Path(cls.temp.name) / "integrations.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import followthrough_store, integration_store, meeting_store, review, scenario_store
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        review._STORE, scenario_store._STORE, meeting_store._STORE, followthrough_store._STORE, integration_store._STORE = cls.previous
        cls.temp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def setUp(self) -> None:
        from clarity import followthrough_store, integration_store, review
        followthrough_store.get_followthrough_store().reset(); integration_store.get_integration_store().reset(); review.get_store().reset()

    @staticmethod
    def inbound(client_id: str, event_id: str) -> dict:
        return {"role": "operations", "source_system": "lending_credit", "external_event_id": event_id, "schema_version": "v1", "client_id": client_id, "affected_insight_ids": [run_for_client(client_id, BOOK)[0].id], "source_ref": f"sandbox:{event_id}", "summary": "Synthetic source update for controlled re-evaluation.", "occurred_at": "2026-08-26"}

    def test_inbound_is_validated_idempotent_and_acceptance_creates_existing_workflow(self) -> None:
        code, created = self.request("/api/integrations/inbound", self.inbound("CL-0014", "LEND-001"))
        self.assertEqual(code, 201); event_id = created["event"]["id"]
        self.assertEqual(created["event"]["validation_state"], "validated")
        code, replay = self.request("/api/integrations/inbound", self.inbound("CL-0014", "LEND-001"))
        self.assertEqual(code, 200); self.assertTrue(replay["replayed"]); self.assertEqual(replay["event"]["id"], event_id)
        code, denied = self.request(f"/api/integrations/inbound/{event_id}/accept", {"role": "rm", "rationale": "No authority."})
        self.assertEqual(code, 409)
        code, missing = self.request(f"/api/integrations/inbound/{event_id}/accept", {"role": "operations", "rationale": ""})
        self.assertEqual(code, 400)
        code, accepted = self.request(f"/api/integrations/inbound/{event_id}/accept", {"role": "operations", "rationale": "Source reference passed local schema and linkage review."})
        self.assertEqual(code, 200); self.assertEqual(accepted["event"]["operations_disposition"], "accepted")
        self.assertEqual(accepted["reevaluation"]["status"], "queued")
        code, accepted_replay = self.request(f"/api/integrations/inbound/{event_id}/accept", {"role": "operations", "rationale": "Replay."})
        self.assertEqual(code, 200); self.assertTrue(accepted_replay["replayed"])
        code, audit = self.request("/api/audit?client_id=CL-0014")
        self.assertEqual(code, 200)
        event = next(item for item in audit["audit"] if item["action"] == "inbound_accepted")
        self.assertFalse(event["detail"]["model_readiness"]["training_eligible"])
        self.assertEqual(event["detail"]["model_readiness"]["feature_schema_version"], "deterministic-priority-factors-v1")

    def test_outbound_work_orders_are_idempotent_and_specialist_scoped(self) -> None:
        insight = run_for_client("CL-0014", BOOK)[0]
        code, task = self.request("/api/follow-through/tasks", {"role": "rm", "client_id": "CL-0014", "insight_id": insight.id, "title": "Confirm credit funding sequence", "owner_role": "credit", "due_date": "2026-09-10", "evidence_refs": ["event_log.csv:EV-001"]})
        self.assertEqual(code, 201); task_id = task["task"]["id"]
        payload = {"role": "rm", "destination": "specialist_queue", "work_record_type": "task", "work_record_id": task_id, "client_id": "CL-0014", "owner_role": "credit"}
        code, created = self.request("/api/integrations/work-orders", payload)
        self.assertEqual(code, 201); order_id = created["work_order"]["id"]
        code, replay = self.request("/api/integrations/work-orders", payload)
        self.assertEqual(code, 200); self.assertTrue(replay["replayed"]); self.assertEqual(replay["work_order"]["id"], order_id)
        code, dispatched = self.request(f"/api/integrations/work-orders/{order_id}/dispatch", {"role": "rm"})
        self.assertEqual(code, 200); self.assertEqual(dispatched["work_order"]["status"], "dispatched")
        self.assertTrue(dispatched["work_order"]["external_reference"].startswith("SIM-SPECIALIST-"))
        code, denied = self.request(f"/api/integrations/work-orders/{order_id}/acknowledge", {"role": "wealth_planning"})
        self.assertEqual(code, 409)
        code, acknowledged = self.request(f"/api/integrations/work-orders/{order_id}/acknowledge", {"role": "credit"})
        self.assertEqual(code, 200); self.assertEqual(acknowledged["work_order"]["status"], "acknowledged")

    def test_all_anchor_links_validate_without_changing_financial_facts(self) -> None:
        for index, client_id in enumerate(("CL-0014", "CL-0003", "CL-0017"), start=1):
            with self.subTest(client_id=client_id):
                code, response = self.request("/api/integrations/inbound", self.inbound(client_id, f"ANCHOR-{index}"))
                self.assertEqual(code, 201, response)
                self.assertEqual(response["event"]["client_id"], client_id)
        code, capabilities = self.request("/api/integrations/capabilities")
        self.assertEqual(code, 200); self.assertTrue(capabilities["local_simulation"])
        self.assertFalse(capabilities["model_readiness"]["training_eligible"])


if __name__ == "__main__":
    unittest.main()
