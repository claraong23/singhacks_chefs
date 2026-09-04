"""Scenario Studio arithmetic, persistence, and HTTP contract tests."""

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
from clarity.loaders import get_book
from clarity.review import ReviewStore
from clarity.scenario_store import ScenarioStore
from clarity.scenarios import evaluate_scenario, templates_for_client
from clarity.signals import run_for_client
from clarity.signals.base import SignalContext


BOOK = get_book()


def subject(client_id: str):
    template = templates_for_client(client_id, BOOK)[0]
    ctx = SignalContext(book=BOOK, client_id=client_id)
    insight = next(item for item in run_for_client(client_id, BOOK) if item.id == template.insight_id)
    option = options_for(ctx, insight)[0]
    return template, option


def metric(result, key: str):
    return next(item for item in result.metrics if item.key == key)


class TestScenarioArithmetic(unittest.TestCase):
    def evaluate(self, client_id: str, inputs=None):
        template, option = subject(client_id)
        return evaluate_scenario(
            client_id=client_id,
            template_id=template.id,
            insight_id=template.insight_id,
            option_id=option.id,
            inputs=inputs,
            book=BOOK,
        )

    def test_all_anchor_templates_are_deterministic_and_evidenced(self) -> None:
        for client_id in ("CL-0014", "CL-0003", "CL-0017"):
            with self.subTest(client_id=client_id):
                first = self.evaluate(client_id)
                second = self.evaluate(client_id)
                self.assertTrue(first.evidence)
                self.assertEqual(first.calculation_version, second.calculation_version)

    def test_lau_repayment_reduces_ltv_without_claiming_market_impact(self) -> None:
        result = self.evaluate("CL-0014")
        self.assertLess(metric(result, "ltv").scenario or 100, metric(result, "ltv").baseline or 0)
        self.assertGreater(metric(result, "repayment").scenario or 0, 0)
        self.assertEqual(metric(result, "lending_value").baseline, metric(result, "lending_value").scenario)
        self.assertFalse(metric(result, "market_impact").available)

    def test_margarethe_reserve_has_no_tax_outcome_and_uses_governed_band(self) -> None:
        result = self.evaluate("CL-0003")
        self.assertLessEqual(metric(result, "equity_allocation").scenario or 100, 30.0)
        self.assertEqual(metric(result, "equity_band_gap").scenario, 0.0)
        self.assertFalse(metric(result, "tax_outcome").available)
        self.assertTrue(result.blocked_checks)

    def test_fong_excludes_gated_assets_and_does_not_turn_windows_into_dates(self) -> None:
        result = self.evaluate("CL-0017", {"commitment_reserve_pct": 50, "review_horizon_months": 12, "funding_tranches": 2})
        self.assertGreater(metric(result, "gated").baseline or 0, 0)
        self.assertEqual(metric(result, "gated").baseline, metric(result, "gated").scenario)
        self.assertEqual(metric(result, "reserve_coverage").scenario, 50.0)
        self.assertFalse(metric(result, "call_dates").available)

    def test_invalid_bounded_input_and_unknown_option_are_rejected(self) -> None:
        template, option = subject("CL-0017")
        with self.assertRaises(ValueError):
            evaluate_scenario(client_id="CL-0017", template_id=template.id, insight_id=template.insight_id, option_id=option.id, inputs={"commitment_reserve_pct": 101}, book=BOOK)
        with self.assertRaises(ValueError):
            evaluate_scenario(client_id="CL-0017", template_id=template.id, insight_id=template.insight_id, option_id="not-an-option", inputs={}, book=BOOK)


class TestScenarioStore(unittest.TestCase):
    def test_save_and_list_are_linked_to_the_client_without_decision_state(self) -> None:
        with TemporaryDirectory() as directory:
            store = ScenarioStore(Path(directory) / "scenarios.json")
            result = TestScenarioArithmetic().evaluate("CL-0014").to_dict()
            saved = store.save(name="Lau funding comparison", result=result)
            self.assertEqual(store.get(saved["id"])["result"]["client_id"], "CL-0014")
            self.assertEqual(len(store.list_for_client("CL-0014")), 1)
            self.assertEqual(store.list_for_client("CL-0017"), [])


class TestScenarioHttpApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from clarity import review, scenario_store
        from http.server import ThreadingHTTPServer

        cls.temp = TemporaryDirectory()
        cls.previous_review, cls.previous_scenarios = review._STORE, scenario_store._STORE
        review._STORE = ReviewStore(Path(cls.temp.name) / "decisions.json")
        scenario_store._STORE = ScenarioStore(Path(cls.temp.name) / "scenarios.json")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        from clarity import review, scenario_store

        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)
        review._STORE, scenario_store._STORE = cls.previous_review, cls.previous_scenarios
        cls.temp.cleanup()

    def request(self, path: str, payload: dict | None = None):
        request = Request(
            f"{self.base}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_evaluate_save_list_and_attach_scenario(self) -> None:
        template, option = subject("CL-0014")
        body = {"template_id": template.id, "insight_id": template.insight_id, "option_id": option.id, "inputs": {}}
        status, evaluated = self.request("/api/clients/CL-0014/scenarios/evaluate", body)
        self.assertEqual(status, 200)
        self.assertTrue(evaluated["scenario"]["evidence"])

        status, saved = self.request("/api/clients/CL-0014/scenarios", {**body, "name": "Lau credit comparison"})
        self.assertEqual(status, 201)
        scenario_id = saved["scenario"]["id"]
        status, listed = self.request("/api/clients/CL-0014/scenarios")
        self.assertEqual(status, 200)
        self.assertEqual(listed["scenarios"][0]["id"], scenario_id)

        decision_path = f"/api/insights/{template.insight_id}/decision"
        base = {"client_id": "CL-0014", "selected_option_id": option.id, "rm_note": "Compare credit and liquidity paths."}
        for workflow_status in ("opened", "under_review"):
            status, _ = self.request(decision_path, {**base, "status": workflow_status})
            self.assertEqual(status, 200)
        status, attached = self.request(decision_path, {**base, "status": "rm_edited", "selected_scenario_id": scenario_id})
        self.assertEqual(status, 200)
        self.assertEqual(attached["decision"]["selected_scenario_id"], scenario_id)
        self.assertEqual(attached["decision"]["scenario_calculation_version"], saved["scenario"]["result"]["calculation_version"])


if __name__ == "__main__":
    unittest.main()
