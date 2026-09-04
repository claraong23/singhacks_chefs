"""Task 3 workflow, gate, persistence, and HTTP contract tests."""

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
from clarity.contracts import ActionOption, Category, Evidence, Insight, Severity, SuitabilityCheck
from clarity.gates import evaluate_readiness
from clarity.loaders import get_book
from clarity.review import InvalidTransitionError, ReviewStore
from clarity.signals.base import SignalContext, run_for_client


BOOK = get_book()


def ready_subject():
    """A real deterministic finding/options pair that clears every strict gate."""
    for client_id in BOOK.clients:
        context = SignalContext(book=BOOK, client_id=client_id)
        for insight in run_for_client(client_id, BOOK):
            for option in options_for(context, insight):
                readiness = evaluate_readiness(
                    insight, [option], selected_option_id=option.id, rm_note="Reviewed with the client context in view."
                )
                if readiness.can_mark_client_ready:
                    return insight, option
    raise AssertionError("Expected at least one deterministic option to clear all gates")


def synthetic_insight(*, evidence: list[Evidence] | None = None, checks=None, questions=None) -> Insight:
    return Insight(
        id="CL-9999-demo",
        client_id="CL-9999",
        category=Category.OPPORTUNITY,
        severity=Severity.LOW,
        headline="Demo",
        summary="Demo",
        priority_score=1,
        evidence=evidence if evidence is not None else [
            Evidence("clients.csv", "CL-9999", "objectives", "Preserve capital")
        ],
        suitability_checks=checks or [],
        open_questions=questions or [],
    )


def synthetic_option(*, checks=None) -> ActionOption:
    return ActionOption("option-1", "Prepare conversation", "Demo option", suitability_checks=checks or [])


class TestDecisionReadiness(unittest.TestCase):
    def test_real_option_can_clear_all_five_gates(self) -> None:
        insight, option = ready_subject()
        readiness = evaluate_readiness(
            insight, [option], selected_option_id=option.id, rm_note="Reviewed with the client context in view."
        )
        self.assertTrue(readiness.can_mark_client_ready)
        self.assertEqual([gate.id for gate in readiness.gates], [
            "evidence", "suitability", "tax_planning", "data_model", "human_decision"
        ])
        self.assertTrue(readiness.evidence_version)

    def test_missing_evidence_blocks(self) -> None:
        readiness = evaluate_readiness(
            synthetic_insight(evidence=[]), [synthetic_option()], selected_option_id="option-1", rm_note="Reason"
        )
        self.assertFalse(readiness.can_mark_client_ready)
        self.assertEqual(readiness.gates[0].status, "block")

    def test_each_non_pass_suitability_result_blocks(self) -> None:
        for result in ("fail", "attention", "not_assessed"):
            with self.subTest(result=result):
                check = SuitabilityCheck("Required check", result, "Needs resolution")
                readiness = evaluate_readiness(
                    synthetic_insight(checks=[check]), [synthetic_option()], selected_option_id="option-1", rm_note="Reason"
                )
                self.assertFalse(readiness.can_mark_client_ready)
                self.assertEqual(readiness.gates[1].status, "block")

    def test_open_question_and_blank_rationale_block(self) -> None:
        readiness = evaluate_readiness(
            synthetic_insight(questions=["Confirm source document."]), [synthetic_option()], selected_option_id=None, rm_note=""
        )
        self.assertFalse(readiness.can_mark_client_ready)
        self.assertEqual(readiness.gates[3].status, "block")
        self.assertEqual(readiness.gates[4].status, "block")


class TestReviewStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.store = ReviewStore(Path(self.tmp.name) / "decisions.json")
        self.insight, self.option = ready_subject()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def record(self, status: str, note: str = "Reason"):
        return self.store.record(
            insight_id=self.insight.id,
            client_id=self.insight.client_id,
            status=status,
            rm_note=note,
            selected_option_id=self.option.id,
        )

    def test_primary_workflow_and_audit_are_append_only(self) -> None:
        for status in ("opened", "under_review", "rm_edited", "rm_reviewed", "client_ready"):
            self.record(status)
        self.assertEqual(self.store.status_of(self.insight.id), "client_ready")
        audit = self.store.audit(self.insight.client_id)
        self.assertEqual(len(audit), 5)
        self.assertEqual(audit[-1].detail["from"], "new")
        self.assertEqual(audit[0].detail["to"], "client_ready")

    def test_escalation_return_and_deferral_workflow(self) -> None:
        for status in ("opened", "under_review", "escalated", "returned_for_review", "under_review", "deferred"):
            self.record(status)
        self.assertEqual(self.store.status_of(self.insight.id), "deferred")

    def test_invalid_transition_and_missing_terminal_reason_are_rejected(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            self.record("rm_reviewed")
        self.record("opened")
        self.record("under_review")
        with self.assertRaises(ValueError):
            self.record("dismissed", note="")

    def test_blocked_transition_is_audited_without_changing_state(self) -> None:
        self.store.record_blocked_transition(
            insight_id=self.insight.id,
            client_id=self.insight.client_id,
            target_status="client_ready",
            actor="RM-SG-014",
            gate_results=[{"id": "human_decision", "status": "block"}],
            evidence_version="abc123",
        )
        self.assertEqual(self.store.status_of(self.insight.id), "new")
        entry = self.store.audit(self.insight.client_id)[0]
        self.assertEqual(entry.action, "transition_blocked:client_ready")
        self.assertEqual(entry.detail["evidence_version"], "abc123")

    def test_actioned_json_records_migrate_to_client_ready(self) -> None:
        path = Path(self.tmp.name) / "legacy.json"
        path.write_text(json.dumps({"decisions": {"x": {"insight_id": "x", "client_id": "CL-0001", "status": "actioned"}}, "audit": []}))
        migrated = ReviewStore(path)
        self.assertEqual(migrated.status_of("x"), "client_ready")
        self.assertIn("client_ready", path.read_text())


class TestWorkflowHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from clarity import review

        cls.tmp = TemporaryDirectory()
        cls.previous_store = review._STORE
        review._STORE = ReviewStore(Path(cls.tmp.name) / "decisions.json")
        from http.server import ThreadingHTTPServer

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import review

        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        review._STORE = cls.previous_store
        cls.tmp.cleanup()

    def post(self, path: str, payload: dict) -> tuple[int, dict]:
        request = Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def setUp(self) -> None:
        from clarity import review

        review.get_store().reset()

    def test_readiness_endpoint_and_client_ready_block(self) -> None:
        insight, option = ready_subject()
        base = {"client_id": insight.client_id, "selected_option_id": option.id}
        status, readiness = self.post(f"/api/insights/{insight.id}/readiness", {**base, "rm_note": "Reason"})
        self.assertEqual(status, 200)
        self.assertTrue(readiness["can_mark_client_ready"])

        status, blocked = self.post(f"/api/insights/{insight.id}/decision", {**base, "status": "client_ready", "rm_note": ""})
        self.assertEqual(status, 409)
        self.assertFalse(blocked["can_mark_client_ready"])
        self.assertTrue(any(gate["id"] == "human_decision" and gate["status"] == "block" for gate in blocked["gates"]))

    def test_full_valid_api_transition(self) -> None:
        insight, option = ready_subject()
        payload = {"client_id": insight.client_id, "selected_option_id": option.id, "rm_note": "Reviewed with evidence."}
        for status in ("opened", "under_review", "rm_reviewed", "client_ready"):
            feedback = {"usefulness": "useful", "urgency_assessment": "right", "rationale": "The reviewed finding is relevant."} if status in {"rm_reviewed", "client_ready"} else None
            code, body = self.post(f"/api/insights/{insight.id}/decision", {**payload, "status": status, **({"feedback": feedback} if feedback else {})})
            self.assertEqual(code, 200, body)
            self.assertEqual(body["decision"]["status"], status)


if __name__ == "__main__":
    unittest.main()
