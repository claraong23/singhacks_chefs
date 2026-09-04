from __future__ import annotations

import unittest
from types import SimpleNamespace

from clarity.analytics.valuation import household_view
from clarity.contracts import Category, Insight, Severity
from clarity.loaders import get_book
from clarity.signals.base import SignalContext
from clarity.signals.filtering import filter_insights


BOOK = get_book()
CTX = SignalContext(BOOK, "CL-0001")


def insight(
    insight_id: str,
    *,
    severity: Severity = Severity.LOW,
    category: Category = Category.CONCENTRATION,
    priority_score: float = 20.0,
    amount_usd: float | None = None,
) -> Insight:
    return Insight(
        id=insight_id,
        client_id=CTX.client_id,
        category=category,
        severity=severity,
        headline="Test finding",
        summary="Test",
        priority_score=priority_score,
        priority_reasons=["Test reason"],
        amount_usd=amount_usd,
    )


class TestFiltering(unittest.TestCase):
    def test_duplicate_ids_keep_the_highest_priority_version(self) -> None:
        low = insight("duplicate", priority_score=10)
        high = insight("duplicate", priority_score=40)
        result = filter_insights(CTX, [low, high])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].priority_score, 40)

    def test_tiny_low_severity_market_finding_is_suppressed(self) -> None:
        tiny = insight("tiny", amount_usd=CTX.view.total_usd * 0.0005)
        self.assertEqual(filter_insights(CTX, [tiny]), [])

    def test_high_severity_finding_is_never_suppressed_for_size(self) -> None:
        tiny_high = insight(
            "tiny-high",
            severity=Severity.HIGH,
            amount_usd=1,
        )
        self.assertEqual(filter_insights(CTX, [tiny_high]), [tiny_high])

    def test_data_quality_finding_is_not_suppressed_by_materiality(self) -> None:
        quality = insight(
            "quality",
            category=Category.DATA_QUALITY,
            amount_usd=1,
        )
        self.assertEqual(filter_insights(CTX, [quality]), [quality])

    def test_awareness_note_adds_context_without_hiding_alert(self) -> None:
        aware = insight(
            "known-concentration",
            severity=Severity.HIGH,
            amount_usd=CTX.view.total_usd * 0.2,
        )
        context = SimpleNamespace(
            client_id=CTX.client_id,
            view=CTX.view,
            notes=[
                {
                    "note_id": "N-TEST",
                    "note_date": "2026-08-01",
                    "note": "Client is aware of the concentration and understands the exposure.",
                }
            ],
        )
        result = filter_insights(context, [aware])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].severity, Severity.HIGH)
        self.assertTrue(any("already knows" in r for r in result[0].priority_reasons))
        self.assertTrue(result[0].open_questions)


if __name__ == "__main__":
    unittest.main()
