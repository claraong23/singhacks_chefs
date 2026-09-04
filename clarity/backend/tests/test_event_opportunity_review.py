from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clarity.analytics.event_impact import event_impact_view
from clarity.contracts import Category, Evidence, Insight, Severity
from clarity.loaders import get_book
from clarity.review import ReviewStore
from clarity.signals import run_for_book


BOOK = get_book()


def sample_insight(amount: float, severity: Severity = Severity.MEDIUM) -> Insight:
    return Insight(
        id="CL-TEST-concentration",
        client_id="CL-TEST",
        category=Category.CONCENTRATION,
        severity=severity,
        headline="Measured concentration",
        summary="Test",
        priority_score=50,
        amount_usd=amount,
        evidence=[Evidence("holdings.csv", "ROW-1", "market_value_usd", amount, "2026-08-26")],
    )


def dismiss(store: ReviewStore, insight: Insight) -> None:
    """Follow the governed Task 3 workflow before recording a dismissal."""
    common = {"insight_id": insight.id, "client_id": insight.client_id, "insight": insight}
    store.record(status="opened", **common)
    store.record(status="under_review", **common)
    store.record(status="dismissed", rm_note="Reviewed and dismissed for this test.", **common)


class TestEventImpact(unittest.TestCase):
    def test_technology_event_maps_to_ranked_clients_and_holdings(self) -> None:
        result = event_impact_view(BOOK, "EVT-11")
        self.assertEqual(result["event"]["event_id"], "EVT-11")
        self.assertTrue(result["affected_clients"])
        self.assertEqual(result["affected_clients"][0]["client_id"], "CL-0002")
        self.assertTrue(result["affected_clients"][0]["instrument_ids"])
        self.assertLess(result["affected_clients"][0]["estimated_impact_usd"], 0)

    def test_unmapped_event_has_no_invented_clients(self) -> None:
        # Every supplied event currently maps, so verify unknown identifiers fail
        # instead of falling back to model inference.
        with self.assertRaises(KeyError):
            event_impact_view(BOOK, "EVT-99")


class TestGuardedOpportunity(unittest.TestCase):
    def test_opportunity_is_conversation_only_and_guardrails_pass(self) -> None:
        opportunities = [
            insight
            for insights in run_for_book(BOOK).values()
            for insight in insights
            if "-opportunity-" in insight.id
        ]
        self.assertTrue(opportunities)
        for insight in opportunities:
            self.assertIn("not a recommendation", insight.summary.lower())
            self.assertTrue(insight.related_event_ids)
            self.assertTrue(all(check.result == "pass" for check in insight.suitability_checks))


class TestReviewReopening(unittest.TestCase):
    def test_dismissal_stays_closed_when_facts_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ReviewStore(Path(directory) / "decisions.json")
            insight = sample_insight(1_000_000)
            dismiss(store, insight)
            self.assertEqual(store.effective_status(insight), ("dismissed", None))

    def test_dismissal_reopens_after_material_amount_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ReviewStore(Path(directory) / "decisions.json")
            original = sample_insight(1_000_000)
            dismiss(store, original)
            status, reason = store.effective_status(sample_insight(1_200_000))
            self.assertEqual(status, "new")
            self.assertIn("20.0%", reason or "")

    def test_dismissal_reopens_after_severity_increase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ReviewStore(Path(directory) / "decisions.json")
            original = sample_insight(1_000_000)
            dismiss(store, original)
            status, reason = store.effective_status(sample_insight(1_000_000, Severity.HIGH))
            self.assertEqual(status, "new")
            self.assertIn("increased", reason or "")


if __name__ == "__main__":
    unittest.main()
