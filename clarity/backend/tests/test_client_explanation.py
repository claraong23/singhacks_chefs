"""Unit tests for Task 1: Client Explanation, Meaningful Changes, and Attribution."""

from __future__ import annotations

import unittest

from clarity import config
from clarity.analytics.attribution import detect_meaningful_changes
from clarity.attribution_ai import generate_client_attribution
from clarity.loaders import get_book
from clarity.review import get_store
from clarity.signals.holding_explain import explain_holding

BOOK = get_book()


class TestClientExplanation(unittest.TestCase):
    def test_meaningful_changes_cl0003(self) -> None:
        """CL-0003 Margarethe Voss-Brenner should have meaningful changes detected."""
        changes = detect_meaningful_changes(
            BOOK, "CL-0003", config.BASELINE_SNAPSHOT, config.AS_OF
        )
        self.assertTrue(len(changes) > 0)
        # Check Nordvind Industrial AB is flagged
        nordvind = next((c for c in changes if c.instrument_id == "SYN-ST-0107"), None)
        self.assertIsNotNone(nordvind)
        self.assertTrue(nordvind.is_meaningful)
        self.assertIn("mandate_breach", nordvind.trigger_badges)
        # Weight should be ~18% which breaches conservative single-stock cap (10%)
        self.assertGreater(nordvind.end_weight_pct, 10.0)

    def test_explain_holding_links_events(self) -> None:
        """Explaining Nordvind for CL-0003 links to event log."""
        explanation = explain_holding(
            BOOK, "CL-0003", "SYN-ST-0107", config.BASELINE_SNAPSHOT, config.AS_OF
        )
        self.assertEqual(explanation.instrument_id, "SYN-ST-0107")
        self.assertEqual(explanation.client_id, "CL-0003")
        # Should link events from event_log.csv
        self.assertTrue(len(explanation.event_evidence) > 0)
        # Should cite EUR 3.4m inheritance tax in why_it_matters
        matters_text = " ".join(explanation.why_it_matters)
        self.assertIn("3,400,000", matters_text)
        self.assertIn("German inheritance tax", matters_text)

    def test_generate_client_attribution_draft(self) -> None:
        """Client attribution draft contains headline, bullets, and language disclaimer."""
        explanation = explain_holding(
            BOOK, "CL-0003", "SYN-ST-0107", config.BASELINE_SNAPSHOT, config.AS_OF
        )
        client = BOOK.clients["CL-0003"]
        draft = generate_client_attribution(explanation, client)
        self.assertTrue(draft.headline)
        self.assertTrue(draft.what_happened_bullet)
        self.assertTrue(draft.why_it_matters_bullet)
        self.assertTrue(draft.next_steps_bullet)
        # Since Margarethe's reporting language is German, it must attach the disclaimer
        self.assertEqual(
            draft.language_disclaimer,
            "English RM preview — client-language version requires review.",
        )

    def test_review_store_notes_and_proposals(self) -> None:
        """ReviewStore persists notes and proposed objectives."""
        store = get_store()
        note = store.add_note(
            client_id="CL-0003",
            note="Client confirmed she wishes to prioritize German tax liquidity.",
            channel="Call",
        )
        self.assertEqual(note["client_id"], "CL-0003")
        self.assertIn("tax liquidity", note["note"])

        prop = store.propose_objective(
            client_id="CL-0003",
            proposed_objective="Conservative capital preservation with tax reserve funding",
            rationale="Inheritance received, widow prefers low risk.",
        )
        self.assertEqual(prop["client_id"], "CL-0003")


if __name__ == "__main__":
    unittest.main()
