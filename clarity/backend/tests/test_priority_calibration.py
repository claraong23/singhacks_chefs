"""Governed RM feedback and deterministic priority-policy calibration."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clarity.api import ClarityHandler
from clarity.calibration import evaluate, validate_weights
from clarity.calibration_store import CalibrationStore
from clarity.loaders import get_book
from clarity.review import ReviewStore
from clarity.signals import run_for_book, run_for_client


class TestPriorityCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from http.server import ThreadingHTTPServer
        from clarity import calibration_store, followthrough_store, meeting_store, review, scenario_store
        from clarity.followthrough_store import FollowThroughStore
        from clarity.meeting_store import MeetingStore
        from clarity.scenario_store import ScenarioStore
        cls.temp = TemporaryDirectory()
        cls.previous = review._STORE, scenario_store._STORE, meeting_store._STORE, followthrough_store._STORE, calibration_store._STORE
        review._STORE = ReviewStore(Path(cls.temp.name) / "decisions.json")
        scenario_store._STORE = ScenarioStore(Path(cls.temp.name) / "scenarios.json")
        meeting_store._STORE = MeetingStore(Path(cls.temp.name) / "meetings.json")
        followthrough_store._STORE = FollowThroughStore(Path(cls.temp.name) / "follow.json")
        calibration_store._STORE = CalibrationStore(Path(cls.temp.name) / "calibration.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import calibration_store, followthrough_store, meeting_store, review, scenario_store
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        review._STORE, scenario_store._STORE, meeting_store._STORE, followthrough_store._STORE, calibration_store._STORE = cls.previous
        cls.temp.cleanup()

    def setUp(self) -> None:
        from clarity.calibration_store import get_calibration_store
        from clarity.review import get_store
        get_calibration_store().reset(); get_store().reset()

    def request(self, path: str, payload: dict | None = None):
        request = Request(f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request) as response: return response.status, json.loads(response.read())
        except HTTPError as error: return error.code, json.loads(error.read())

    def test_weight_validation_and_candidate_shadow_comparison(self) -> None:
        with self.assertRaises(ValueError): validate_weights({"severity": .4, "materiality": .3, "urgency": .4})
        baseline = run_for_client("CL-0014", get_book())
        self.assertTrue(all(item.priority_factors is not None for item in baseline))
        urgency_first = run_for_book(get_book(), priority_weights={"severity": .35, "materiality": .20, "urgency": .45})["CL-0014"]
        self.assertEqual({item.id for item in baseline}, {item.id for item in urgency_first})
        code, created = self.request("/api/priority-policies", {"role": "rm", "template": "urgency_first", "rationale": "Test a dated-obligation emphasis."})
        self.assertEqual(code, 201)
        evaluation = created["evaluation"]
        self.assertEqual(evaluation["feedback_count"], 0)
        self.assertFalse(evaluation["activation_eligible"])
        self.assertEqual(len(evaluation["rank_changes"]), len(get_book().clients))
        code, denied = self.request(f"/api/priority-policies/{created['policy']['id']}/submit", {"role": "operations", "rationale": "No authority"})
        self.assertEqual(code, 409)

    def test_final_decision_requires_feedback_and_policy_activation_requires_anchor_coverage(self) -> None:
        insight = run_for_client("CL-0014", get_book())[0]
        base = {"role": "rm", "client_id": "CL-0014", "selected_option_id": None, "rm_note": "Initial file review."}
        self.assertEqual(self.request(f"/api/insights/{insight.id}/decision", {**base, "status": "opened"})[0], 200)
        self.assertEqual(self.request(f"/api/insights/{insight.id}/decision", {**base, "status": "under_review"})[0], 200)
        self.assertEqual(self.request(f"/api/insights/{insight.id}/decision", {**base, "status": "rm_reviewed"})[0], 400)
        code, saved = self.request(f"/api/insights/{insight.id}/decision", {**base, "status": "rm_reviewed", "feedback": {"usefulness": "useful", "urgency_assessment": "right", "rationale": "The credit discussion is relevant now."}})
        self.assertEqual(code, 200); self.assertEqual(saved["feedback"]["client_id"], "CL-0014")

        code, candidate = self.request("/api/priority-policies", {"role": "rm", "template": "materiality_first", "rationale": "Evaluate household materiality."})
        policy_id = candidate["policy"]["id"]
        self.assertEqual(self.request(f"/api/priority-policies/{policy_id}/submit", {"role": "rm", "rationale": "Submit with current evidence."})[0], 200)
        self.assertEqual(self.request(f"/api/priority-policies/{policy_id}/approve", {"role": "compliance_audit", "rationale": "Not enough coverage."})[0], 409)

        from clarity.calibration_store import get_calibration_store
        store = get_calibration_store()
        for client_id in ("CL-0003", "CL-0017"):
            anchor = run_for_client(client_id, get_book())[0]
            store.feedback(client_id=client_id, insight_id=anchor.id, decision_status="rm_reviewed", usefulness="partly_useful", urgency_assessment="right", rationale="Anchor journey review.", actor="RM-SG-014", evidence_version="fixture", policy_id="baseline-v1")
        self.assertTrue(evaluate(policy_id)["activation_eligible"])
        code, approved = self.request(f"/api/priority-policies/{policy_id}/approve", {"role": "compliance_audit", "rationale": "Three anchor journeys have reviewed feedback."})
        self.assertEqual(code, 200); self.assertEqual(approved["policy"]["status"], "active")
        code, policies = self.request("/api/priority-policies")
        self.assertEqual(code, 200); self.assertEqual(policies["active_policy"]["id"], policy_id)
        self.assertEqual(next(item for item in policies["policies"] if item["id"] == "baseline-v1")["status"], "retired")
        code, audit = self.request("/api/audit")
        self.assertEqual(code, 200); self.assertTrue(any(event["object_type"] == "priority_policy" for event in audit["audit"]))


if __name__ == "__main__":
    unittest.main()
