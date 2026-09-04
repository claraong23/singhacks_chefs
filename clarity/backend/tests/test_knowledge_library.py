"""Approved synthetic knowledge retrieval and controlled document lifecycle."""

from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clarity.api import ClarityHandler
from clarity.knowledge_store import KnowledgeRepository


class TestKnowledgeLibrary(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.store = KnowledgeRepository(Path(self.temp.name) / "knowledge.json")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_anchor_retrieval_is_cited_and_reference_only(self) -> None:
        lau = self.store.search(query="Lau collateral funding", category=None, tag=None, role="rm", location="action_review")
        margarethe = self.store.search(query="tax planning Margarethe", category=None, tag=None, role="rm", location="meeting_studio")
        fong = self.store.search(query="Fong commitments gated liquidity", category=None, tag=None, role="rm", location="knowledge_library")
        self.assertEqual(lau[0]["citation"]["document_id"], "KN-COLLATERAL-001")
        self.assertEqual(margarethe[0]["citation"]["document_id"], "KN-TAX-001")
        self.assertEqual(fong[0]["citation"]["document_id"], "KN-COMMITMENTS-001")
        self.assertTrue(all(item["citation"]["source_refs"] for item in lau + margarethe + fong))
        self.assertIn("not a trade instruction", lau[0]["excerpt"].lower())
        self.assertIn("do not calculate", margarethe[0]["excerpt"].lower())
        self.assertIn("uncertain capital-call window is not a confirmed payment date", fong[0]["excerpt"].lower())

    def test_drafts_are_hidden_until_compliance_approval_and_versions_are_immutable(self) -> None:
        payload = {"title": "Synthetic funding reference", "category": "collateral_liquidity", "tags": ["funding", "liquidity"], "owner": "Credit", "effective_date": "2026-08-26", "source_refs": ["clarity/docs/METHOD.md"], "body": "SYNTHETIC PROTOTYPE REFERENCE — not policy. Confirm funding facts.", "rationale": "Add controlled reference."}
        document = self.store.create(payload, "operations")
        self.assertNotIn(document["id"], {item["id"] for item in self.store.list("rm")})
        with self.assertRaises(KeyError):
            self.store.get(document["id"], "rm")
        self.store.submit(document["id"], "Ready for review.", "operations")
        self.store.review(document["id"], True, "Approved synthetic wording.", "compliance_audit")
        self.assertIn(document["id"], {item["id"] for item in self.store.list("investment")})
        original = self.store.get(document["id"], "compliance_audit")["versions"][0]["body"]
        revision = {**payload, "body": "SYNTHETIC PROTOTYPE REFERENCE — revised approved reference.", "rationale": "Clarify controlled language."}
        self.store.revise(document["id"], revision, "operations")
        self.store.submit(document["id"], "Review revision.", "operations")
        updated = self.store.review(document["id"], True, "Approved revision.", "compliance_audit")
        self.assertEqual(updated["versions"][0]["body"], original)
        self.assertEqual(updated["versions"][0]["status"], "superseded")
        self.assertEqual(updated["versions"][1]["status"], "approved")

    def test_raw_client_or_external_sources_and_unauthorised_changes_are_rejected(self) -> None:
        with self.assertRaises(PermissionError):
            self.store.create({}, "rm")
        payload = {"title": "Bad source", "category": "evidence", "tags": ["evidence"], "owner": "Operations", "effective_date": "2026-08-26", "source_refs": ["data/clients.csv"], "body": "Synthetic reference", "rationale": "Bad source test."}
        with self.assertRaises(ValueError):
            self.store.create(payload, "operations")
        self.assertEqual(self.store.search(query="unmatched phrase", category=None, tag=None, role="rm", location="knowledge_library"), [])
        result = self.store.search(query="collateral unmatched", category=None, tag=None, role="rm", location="knowledge_library")[0]
        self.assertEqual(result["matched_terms"], ["collateral"])
        event = self.store.audit()[0]
        self.assertEqual(event["action"], "retrieval_served")
        self.assertEqual(event["detail"]["location"], "knowledge_library")


class TestKnowledgeHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from http.server import ThreadingHTTPServer
        from clarity import knowledge_store

        cls.temp = TemporaryDirectory()
        cls.previous = knowledge_store._STORE
        knowledge_store._STORE = KnowledgeRepository(Path(cls.temp.name) / "knowledge.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import knowledge_store

        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        knowledge_store._STORE = cls.previous
        cls.temp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(
            f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_api_limits_results_to_approved_documents_and_audits_retrieval(self) -> None:
        code, searched = self.request("/api/knowledge/search?q=Fong%20commitments&role=rm&location=meeting_studio")
        self.assertEqual(code, 200)
        self.assertEqual(searched["results"][0]["citation"]["document_id"], "KN-COMMITMENTS-001")

        payload = {"role": "operations", "title": "Synthetic draft", "category": "evidence", "tags": ["evidence"],
                   "owner": "Product Operations", "effective_date": "2026-08-26", "source_refs": ["clarity/docs/METHOD.md"],
                   "body": "SYNTHETIC PROTOTYPE REFERENCE. Draft only.", "rationale": "Test controlled authoring."}
        code, created = self.request("/api/knowledge-documents", payload)
        self.assertEqual(code, 201)
        draft_id = created["document"]["id"]
        code, public = self.request("/api/knowledge-documents?role=rm")
        self.assertEqual(code, 200)
        self.assertNotIn(draft_id, {item["id"] for item in public["documents"]})
        code, audit = self.request("/api/audit")
        self.assertEqual(code, 200)
        retrieval = next(event for event in audit["audit"] if event["action"] == "retrieval_served")
        self.assertEqual(retrieval["detail"]["location"], "meeting_studio")


if __name__ == "__main__":
    unittest.main()
