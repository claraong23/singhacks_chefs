"""Tests for guarded Block 2 AI insight narratives."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from clarity.ai_adapter import draft_insight_narrative
from clarity.contracts import Category, Confidence, Evidence, Fact, Insight, Severity


def _insight() -> Insight:
    return Insight(
        id="CL-0001-concentration-test",
        client_id="CL-0001",
        category=Category.CONCENTRATION,
        severity=Severity.HIGH,
        headline="Technology exposure is concentrated",
        summary="Technology represents 42% of household wealth.",
        priority_score=80,
        observed_facts=[Fact("Technology exposure", "42%")],
        client_relevance="A large share of household wealth may move with one sector.",
        suggested_next_step="Discuss the exposure and the client's tolerance with the RM.",
        evidence=[Evidence("holdings.csv", "H-1", "market_value_usd", "420000", "2026-08-26")],
        confidence=Confidence.MEASURED,
        portfolio_ids=["P-1"],
        instrument_ids=["I-1"],
        amount_usd=420000,
    )


class TestInsightNarrativeAdapter(unittest.TestCase):
    def test_returns_shared_provider_provenance_and_passing_checks(self) -> None:
        text = "Technology represents 42% of household wealth, creating material exposure to one sector for RM review."
        with patch(
            "clarity.ai_adapter.rewrite_with_configured_provider",
            return_value=(text, "openai_compatible", "test-model"),
        ):
            result = draft_insight_narrative(_insight())
        self.assertTrue(result["can_use"])
        self.assertEqual(result["narrative"], text)
        self.assertEqual(result["provenance"]["provider"], "openai_compatible")
        self.assertTrue(all(check["status"] == "pass" for check in result["guardrails"]))

    def test_blocks_new_numbers_and_recommendation_language(self) -> None:
        unsafe = "We recommend you sell 75% of the portfolio."
        with patch(
            "clarity.ai_adapter.rewrite_with_configured_provider",
            return_value=(unsafe, "gemini", "test-model"),
        ):
            result = draft_insight_narrative(_insight())
        self.assertFalse(result["can_use"])
        self.assertIsNone(result["narrative"])
        blocked = {
            check["id"] for check in result["guardrails"] if check["status"] == "block"
        }
        self.assertEqual(blocked, {"facts", "advice"})


if __name__ == "__main__":
    unittest.main()
