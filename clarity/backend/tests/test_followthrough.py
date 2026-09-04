"""Collaboration, follow-through permissions, immutable source updates, and audit."""

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
from clarity.loaders import get_book
from clarity.signals import run_for_client

BOOK = get_book()
INSIGHT = run_for_client("CL-0014", BOOK)[0]


class TestFollowThroughHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from clarity import followthrough_store, meeting_store, review, scenario_store
        from clarity.meeting_store import MeetingStore
        from clarity.review import ReviewStore
        from clarity.scenario_store import ScenarioStore
        from http.server import ThreadingHTTPServer
        cls.temp = TemporaryDirectory()
        cls.previous = review._STORE, scenario_store._STORE, meeting_store._STORE, followthrough_store._STORE
        review._STORE = ReviewStore(Path(cls.temp.name) / "decisions.json")
        scenario_store._STORE = ScenarioStore(Path(cls.temp.name) / "scenarios.json")
        meeting_store._STORE = MeetingStore(Path(cls.temp.name) / "meetings.json")
        followthrough_store._STORE = FollowThroughStore(Path(cls.temp.name) / "follow.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import followthrough_store, meeting_store, review, scenario_store
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        review._STORE, scenario_store._STORE, meeting_store._STORE, followthrough_store._STORE = cls.previous
        cls.temp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request) as response: return response.status, json.loads(response.read())
        except HTTPError as error: return error.code, json.loads(error.read())

    def setUp(self) -> None:
        from clarity import followthrough_store
        followthrough_store.get_followthrough_store().reset()

    def test_task_referral_lifecycle_role_visibility_and_audit(self) -> None:
        base = {"role": "rm", "client_id": "CL-0014", "insight_id": INSIGHT.id, "due_date": "2026-09-10", "evidence_refs": ["event_log.csv:EV-001"]}
        code, task = self.request("/api/follow-through/tasks", {**base, "title": "Confirm redevelopment funding", "owner_role": "credit"})
        self.assertEqual(code, 201); task_id = task["task"]["id"]
        code, referral = self.request("/api/follow-through/referrals", {**base, "referral_type": "credit", "summary": "Validate facility funding path", "owner_role": "credit"})
        self.assertEqual(code, 201); referral_id = referral["referral"]["id"]
        code, denied = self.request(f"/api/follow-through/tasks/{task_id}/update", {"role": "wealth_planning", "status": "completed", "reason": "No access"})
        self.assertEqual(code, 409)
        code, updated = self.request(f"/api/follow-through/tasks/{task_id}/update", {"role": "credit", "status": "completed", "reason": "Credit review completed."})
        self.assertEqual(code, 200); self.assertEqual(updated["task"]["status"], "completed")
        code, view = self.request("/api/follow-through?role=credit")
        self.assertEqual(code, 200); self.assertEqual(view["referrals"][0]["id"], referral_id)
        code, audit = self.request("/api/audit?client_id=CL-0014")
        self.assertEqual(code, 200); self.assertTrue(any(item["object_type"] == "task" for item in audit["audit"]))

    def test_outcomes_and_evidence_updates_preserve_historical_insight(self) -> None:
        code, outcome = self.request("/api/follow-through/outcomes", {"role": "rm", "client_id": "CL-0003", "insight_id": run_for_client("CL-0003", BOOK)[0].id, "outcome_type": "document_requested", "statement": "Client reports that tax documentation will be supplied.", "requested_documents": ["Inheritance-tax calculation"]})
        self.assertEqual(code, 201); self.assertEqual(outcome["outcome"]["status"], "recorded")
        code, update = self.request("/api/follow-through/evidence-updates", {"role": "operations", "client_id": "CL-0017", "source_type": "document", "source_ref": "client-upload:liquidity-map-v2", "summary": "Client supplied an updated liquidity map.", "affected_insight_ids": [run_for_client("CL-0017", BOOK)[0].id]})
        self.assertEqual(code, 201); self.assertEqual(update["reevaluation"]["status"], "queued")
        code, denied = self.request(f"/api/follow-through/reevaluations/{update['reevaluation']['id']}/update", {"role": "rm", "status": "complete", "reason": "Not operations."})
        self.assertEqual(code, 409)
        code, complete = self.request(f"/api/follow-through/reevaluations/{update['reevaluation']['id']}/update", {"role": "operations", "status": "complete", "reason": "Flagged for deterministic re-review; source files remain unchanged."})
        self.assertEqual(code, 200); self.assertEqual(complete["reevaluation"]["status"], "complete")

    def test_due_date_and_terminal_reason_are_controlled(self) -> None:
        code, bad_date = self.request("/api/follow-through/tasks", {"role": "rm", "client_id": "CL-0014", "title": "Bad date", "owner_role": "rm", "due_date": "2026-01-01", "evidence_refs": ["clients.csv:CL-0014"]})
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
