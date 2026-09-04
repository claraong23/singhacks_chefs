"""Controlled, optional Meeting Studio AI drafting tests."""

from __future__ import annotations

import json
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clarity import ai_drafting
from clarity.ai_drafting import AIDraftAuditStore, AIDraftingService, _provider_rewrite, provider_status
from clarity.api import ClarityHandler
from clarity.meeting import create_package, preflight
from clarity.meeting_store import MeetingStore
from clarity.review import ReviewStore
from clarity.scenario_store import ScenarioStore
from tests.test_meeting_studio import BOOK, force_client_ready


class TestAIDraftingAdapters(unittest.TestCase):
    def test_disabled_status_never_exposes_provider_configuration(self) -> None:
        with patch.dict(os.environ, {"CLARITY_AI_PROVIDER": "disabled", "GEMINI_API_KEY": "secret-value"}, clear=False):
            status = provider_status()
        self.assertFalse(status["available"])
        self.assertEqual(status["provider"], "disabled")
        self.assertNotIn("secret-value", json.dumps(status))

    def test_gemini_and_openai_compatible_requests_are_server_side_and_bounded(self) -> None:
        with patch("clarity.ai_drafting._post_json", return_value={"candidates": [{"content": {"parts": [{"text": "Rewrite."}]}}]}) as post:
            with patch.dict(os.environ, {"CLARITY_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "gemini-secret", "CLARITY_GEMINI_MODEL": "gemini-test"}, clear=False):
                text, provider, model = _provider_rewrite("approved package only")
            self.assertEqual((text, provider, model), ("Rewrite.", "gemini", "gemini-test"))
            url, headers, payload = post.call_args.args
            self.assertIn("generateContent", url); self.assertEqual(headers["x-goog-api-key"], "gemini-secret")
            self.assertIn("approved package only", payload["contents"][0]["parts"][0]["text"])

        with patch("clarity.ai_drafting._post_json", return_value={"choices": [{"message": {"content": "Rewrite."}}]}) as post:
            with patch.dict(os.environ, {"CLARITY_AI_PROVIDER": "openai_compatible", "CLARITY_OPENAI_COMPATIBLE_API_KEY": "compatible-secret", "CLARITY_OPENAI_COMPATIBLE_BASE_URL": "https://provider.invalid/v1", "CLARITY_OPENAI_COMPATIBLE_MODEL": "draft-test"}, clear=False):
                text, provider, model = _provider_rewrite("approved package only")
            self.assertEqual((text, provider, model), ("Rewrite.", "openai_compatible", "draft-test"))
            url, headers, payload = post.call_args.args
            self.assertEqual(url, "https://provider.invalid/v1/chat/completions")
            self.assertEqual(headers["Authorization"], "Bearer compatible-secret")
            self.assertIn("approved package only", payload["messages"][1]["content"])


class TestAIDraftingService(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.review = ReviewStore(Path(self.temp.name) / "decisions.json")
        self.scenarios = ScenarioStore(Path(self.temp.name) / "scenarios.json")
        self.audit = AIDraftAuditStore(Path(self.temp.name) / "audit.json")
        self.service = AIDraftingService(self.audit, preflight_runner=lambda package: preflight(package, book=BOOK, review_store=self.review, scenario_store=self.scenarios))
        self.insight, _ = force_client_ready(self.review, "CL-0014")
        self.package = create_package("CL-0014", self.insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_only_selected_package_text_is_prompted_and_guardrails_block_new_claims(self) -> None:
        captured: list[str] = []
        source = self.package["versions"][0]["sections"][0]["content"]
        with patch("clarity.ai_drafting._provider_rewrite", side_effect=lambda prompt: (captured.append(prompt) or source, "gemini", "test-model")):
            candidate = self.service.generate(self.package, key="objective", style="clear_concise", role="rm")
        self.assertTrue(candidate["can_apply"])
        self.assertNotIn("clients.csv", captured[0])
        self.assertNotIn("rm_notes", captured[0].lower())
        self.assertNotIn("event_log.csv", captured[0])

        unsafe = "We recommend you buy a new product for USD 999m on 2027-01-01."
        with patch("clarity.ai_drafting._provider_rewrite", return_value=(unsafe, "gemini", "test-model")):
            blocked = self.service.generate(self.package, key="objective", style="clear_concise", role="rm")
        self.assertFalse(blocked["can_apply"])
        self.assertIsNone(blocked["content"])
        self.assertTrue(any(item["status"] == "block" for item in blocked["guardrails"]))
        self.assertEqual(self.review.status_of(self.insight.id), "client_ready")

    def test_apply_requires_rm_rationale_and_creates_ai_provenanced_version(self) -> None:
        source = self.package["versions"][0]["sections"][0]["content"]
        with patch("clarity.ai_drafting._provider_rewrite", return_value=(source, "gemini", "test-model")):
            candidate = self.service.generate(self.package, key="objective", style="warm_respectful", role="rm")
        with self.assertRaises(PermissionError):
            self.service.apply(self.package, draft_id=candidate["id"], rationale="RM wording review.", role="credit")
        with self.assertRaises(ValueError):
            self.service.apply(self.package, draft_id=candidate["id"], rationale="", role="rm")
        version = self.service.apply(self.package, draft_id=candidate["id"], rationale="Use clearer preparation wording.", role="rm")
        self.assertEqual(version["reason"], "ai_applied:warm_respectful")
        self.assertEqual(version["provenance"]["provider"], "gemini")
        self.assertEqual(self.review.status_of(self.insight.id), "client_ready")
        self.assertTrue(any(event["action"] == "ai_draft_applied" for event in self.audit.audit()))

    def test_client_caveats_stale_versions_and_expiry_block_application(self) -> None:
        with patch("clarity.ai_drafting._provider_rewrite", return_value=("A concise client update.", "gemini", "test-model")):
            blocked = self.service.generate(self.package, key="email", style="clear_concise", role="rm")
        self.assertFalse(blocked["can_apply"])
        self.assertEqual(next(item for item in blocked["guardrails"] if item["id"] == "client_caveats")["status"], "block")

        source = self.package["versions"][0]["sections"][0]["content"]
        with patch("clarity.ai_drafting._provider_rewrite", return_value=(source, "gemini", "test-model")):
            stale = self.service.generate(self.package, key="objective", style="clear_concise", role="rm")
        self.package["current_version"] = 2
        with self.assertRaises(PermissionError):
            self.service.apply(self.package, draft_id=stale["id"], rationale="Stale preview test.", role="rm")
        self.package["current_version"] = 1
        with patch("clarity.ai_drafting._provider_rewrite", return_value=(source, "gemini", "test-model")):
            expired = self.service.generate(self.package, key="objective", style="clear_concise", role="rm")
        self.service.candidates[expired["id"]]["expires_at"] = "2000-01-01T00:00:00+00:00"
        with self.assertRaises(PermissionError):
            self.service.apply(self.package, draft_id=expired["id"], rationale="Expiry test.", role="rm")
        self.assertTrue(any(event["action"] == "ai_draft_expired" for event in self.audit.audit()))

    def test_all_anchor_journeys_can_preview_only_their_existing_client_copy(self) -> None:
        for client_id in ("CL-0014", "CL-0003", "CL-0017"):
            with self.subTest(client_id=client_id):
                insight, _ = force_client_ready(self.review, client_id)
                package = create_package(client_id, insight.id, book=BOOK, review_store=self.review, scenario_store=self.scenarios)
                source = package["versions"][0]["communications"][0]["content"]
                with patch("clarity.ai_drafting._provider_rewrite", return_value=(source, "gemini", "test-model")):
                    candidate = self.service.generate(package, key="email", style="formal_concise", role="rm")
                self.assertTrue(candidate["can_apply"])
                self.assertEqual(candidate["content"], source)


class TestAIDraftingHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from http.server import ThreadingHTTPServer
        from clarity import meeting_store, review, scenario_store

        cls.temp = TemporaryDirectory()
        cls.previous = review._STORE, scenario_store._STORE, meeting_store._STORE, ai_drafting._AUDIT_STORE, ai_drafting._SERVICE
        review._STORE = ReviewStore(Path(cls.temp.name) / "decisions.json")
        scenario_store._STORE = ScenarioStore(Path(cls.temp.name) / "scenarios.json")
        meeting_store._STORE = MeetingStore(Path(cls.temp.name) / "meetings.json")
        ai_drafting._AUDIT_STORE = AIDraftAuditStore(Path(cls.temp.name) / "ai-audit.json")
        ai_drafting._SERVICE = AIDraftingService(ai_drafting._AUDIT_STORE)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import meeting_store, review, scenario_store

        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        review._STORE, scenario_store._STORE, meeting_store._STORE, ai_drafting._AUDIT_STORE, ai_drafting._SERVICE = cls.previous
        cls.temp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request) as response: return response.status, json.loads(response.read())
        except HTTPError as error: return error.code, json.loads(error.read())

    def setUp(self) -> None:
        from clarity import meeting_store, review
        review.get_store().reset(); meeting_store.get_meeting_store().reset(); ai_drafting.get_ai_drafting_service().reset()

    def test_preview_apply_and_audit_are_append_only(self) -> None:
        insight, _ = force_client_ready(__import__("clarity.review", fromlist=["get_store"]).get_store(), "CL-0014")
        code, created = self.request(f"/api/insights/{insight.id}/meeting-packages", {"client_id": "CL-0014"})
        self.assertEqual(code, 201, created); package = created["package"]
        source = package["versions"][0]["sections"][0]["content"]
        with patch.dict(os.environ, {"CLARITY_AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}, clear=False), patch("clarity.ai_drafting._provider_rewrite", return_value=(source, "gemini", "test-model")):
            code, draft = self.request(f"/api/meeting-packages/{package['id']}/ai-drafts", {"target_key": "objective", "style": "clear_concise", "role": "rm"})
            self.assertEqual(code, 200, draft); self.assertTrue(draft["draft"]["can_apply"])
            code, denied = self.request(f"/api/meeting-packages/{package['id']}/ai-drafts/{draft['draft']['id']}/apply", {"role": "credit", "rationale": "No authority"})
            self.assertEqual(code, 409, denied)
            code, applied = self.request(f"/api/meeting-packages/{package['id']}/ai-drafts/{draft['draft']['id']}/apply", {"role": "rm", "rationale": "Use the clearer meeting objective."})
        self.assertEqual(code, 200, applied)
        self.assertEqual(applied["package"]["current_version"], 2)
        self.assertEqual(applied["package"]["versions"][-1]["provenance"]["provider"], "gemini")
        code, audit = self.request("/api/audit?client_id=CL-0014")
        self.assertEqual(code, 200)
        self.assertTrue(any(event["action"] == "ai_draft_applied" for event in audit["audit"]))


if __name__ == "__main__":
    unittest.main()
