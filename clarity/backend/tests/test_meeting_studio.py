"""Meeting Studio generation, governance controls, persistence, and HTTP tests."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clarity.actions import options_for
from clarity.api import ClarityHandler
from clarity.meeting import create_package, preflight, restore_version, update_section
from clarity.meeting_store import MeetingStore
from clarity.loaders import get_book
from clarity.review import ReviewStore
from clarity.scenario_store import ScenarioStore
from clarity.signals import run_for_client
from clarity.signals.base import SignalContext
from tests.test_review_workflow import ready_subject

BOOK = get_book()


def anchor_subject(client_id: str):
    ctx = SignalContext(book=BOOK, client_id=client_id)
    insight = run_for_client(client_id, BOOK)[0]
    return insight, options_for(ctx, insight)[0]


def force_client_ready(store: ReviewStore, client_id: str):
    insight, option = anchor_subject(client_id)
    gate_results = [{"id": item, "status": "pass"} for item in (
        "evidence", "suitability", "tax_planning", "data_model", "human_decision"
    )]
    for status in ("opened", "under_review", "rm_reviewed", "client_ready"):
        store.record(
            insight_id=insight.id, client_id=client_id, status=status,
            rm_note="Controlled meeting preparation.", selected_option_id=option.id,
            gate_results=gate_results, evidence_version="meeting-test-evidence",
        )
    return insight, option


class TestMeetingGeneration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.review = ReviewStore(Path(self.tmp.name) / "decisions.json")
        self.scenarios = ScenarioStore(Path(self.tmp.name) / "scenarios.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_anchor_packages_are_deterministic_and_cited(self) -> None:
        for client_id in ("CL-0014", "CL-0003", "CL-0017"):
            with self.subTest(client_id=client_id):
                insight, _ = force_client_ready(self.review, client_id)
                package = create_package(client_id, insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
                version = package["versions"][0]
                self.assertEqual(len(version["sections"]), 7)
                self.assertEqual({item["channel"] for item in version["communications"]}, {"email", "formal_briefing", "call_notes", "client_app"})
                self.assertTrue(all(item["evidence_refs"] for item in version["sections"] + version["communications"]))

    def test_anchor_guardrails_do_not_make_unsupported_claims(self) -> None:
        terms = {"CL-0014": "forecast", "CL-0003": "tax outcome", "CL-0017": "redemption date"}
        for client_id, prohibited in terms.items():
            with self.subTest(client_id=client_id):
                insight, _ = force_client_ready(self.review, client_id)
                package = create_package(client_id, insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
                content = "\n".join(item["content"].lower() for item in package["versions"][0]["communications"])
                self.assertNotIn(prohibited, content)

    def test_edit_and_restore_are_append_only(self) -> None:
        insight, _ = force_client_ready(self.review, "CL-0014")
        package = create_package("CL-0014", insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
        refs = [f"{item['source_file']}:{item['row_or_id']}" for item in package["source"]["evidence"]]
        edited = update_section(package, "objective", "Confirm the recorded liquidity objective.", refs, actor="RM")
        store = MeetingStore(Path(self.tmp.name) / "meetings.json")
        store.create(package); package = store.append_version(package["id"], edited)
        restored = restore_version(package, 1, actor="RM")
        package = store.append_version(package["id"], restored)
        self.assertEqual([item["version"] for item in package["versions"]], [1, 2, 3])
        self.assertEqual(package["versions"][-1]["reason"], "restored version 1")

    def test_preflight_blocks_unsupported_edit_without_changing_decision(self) -> None:
        insight, _ = force_client_ready(self.review, "CL-0014")
        package = create_package("CL-0014", insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
        refs = [f"{item['source_file']}:{item['row_or_id']}" for item in package["source"]["evidence"]]
        package["versions"].append(update_section(package, "email", "We recommend you buy immediately.", refs, actor="RM"))
        package["current_version"] = 2
        result = preflight(package, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
        self.assertFalse(result["can_hand_off"])
        self.assertEqual(self.review.status_of(insight.id), "client_ready")

    def test_preflight_rejects_a_stale_source_snapshot(self) -> None:
        insight, _ = force_client_ready(self.review, "CL-0014")
        package = create_package("CL-0014", insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
        package["source"]["evidence_version"] = "stale-version"
        result = preflight(package, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
        client_ready = next(item for item in result["checks"] if item["id"] == "client_ready")
        self.assertEqual(client_ready["status"], "block")


class TestMeetingHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from clarity import meeting_store, review, scenario_store
        from http.server import ThreadingHTTPServer

        cls.temp = TemporaryDirectory()
        cls.previous = review._STORE, scenario_store._STORE, meeting_store._STORE
        review._STORE = ReviewStore(Path(cls.temp.name) / "decisions.json")
        scenario_store._STORE = ScenarioStore(Path(cls.temp.name) / "scenarios.json")
        meeting_store._STORE = MeetingStore(Path(cls.temp.name) / "meetings.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start(); cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import meeting_store, review, scenario_store
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        review._STORE, scenario_store._STORE, meeting_store._STORE = cls.previous
        cls.temp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def setUp(self) -> None:
        from clarity import meeting_store, review
        review.get_store().reset(); meeting_store.get_meeting_store().reset()

    def test_client_ready_creation_preflight_edit_restore_and_handoff(self) -> None:
        insight, option = ready_subject()
        client_id = insight.client_id
        code, body = self.request(f"/api/insights/{insight.id}/meeting-packages", {"client_id": client_id})
        self.assertEqual(code, 409)

        payload = {"client_id": client_id, "selected_option_id": option.id, "rm_note": "Controlled review."}
        for status in ("opened", "under_review", "rm_reviewed", "client_ready"):
            code, body = self.request(f"/api/insights/{insight.id}/decision", {**payload, "status": status})
            self.assertEqual(code, 200, body)
        audit_before = len(__import__("clarity.review", fromlist=["get_store"]).get_store().audit(client_id))
        code, created = self.request(f"/api/insights/{insight.id}/meeting-packages", {"client_id": client_id})
        self.assertEqual(code, 201, created)
        package = created["package"]; package_id = package["id"]
        code, listed = self.request(f"/api/clients/{client_id}/meeting-packages")
        self.assertEqual(code, 200); self.assertEqual(listed["packages"][0]["id"], package_id)
        code, check = self.request(f"/api/meeting-packages/{package_id}/preflight", {})
        self.assertEqual(code, 200); self.assertTrue(check["preflight"]["can_hand_off"], check)
        code, updated = self.request(f"/api/meeting-packages/{package_id}/versions", {"key": "email", "content": "A revised draft without caveats.", "evidence_refs": package["versions"][0]["communications"][0]["evidence_refs"]})
        self.assertEqual(code, 200)
        code, blocked = self.request(f"/api/meeting-packages/{package_id}/handoff", {"channel": "email"})
        self.assertEqual(code, 409); self.assertFalse(blocked["preflight"]["can_hand_off"])
        code, restored = self.request(f"/api/meeting-packages/{package_id}/restore", {"version": 1})
        self.assertEqual(code, 200); self.assertEqual(restored["package"]["current_version"], 3)
        code, handed = self.request(f"/api/meeting-packages/{package_id}/handoff", {"channel": "email"})
        self.assertEqual(code, 200, handed)
        self.assertEqual(len(handed["package"]["handoffs"]), 1)
        audit_after = len(__import__("clarity.review", fromlist=["get_store"]).get_store().audit(client_id))
        self.assertEqual(audit_before, audit_after)


if __name__ == "__main__":
    unittest.main()
