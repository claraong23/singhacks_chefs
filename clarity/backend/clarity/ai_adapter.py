"""Optional, controlled AI narrative adapter for deterministic insights.

The adapter receives only an already-computed Insight. It never calculates a
financial fact, changes a severity, or creates a recommendation.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .ai_drafting import rewrite_with_configured_provider
from .contracts import Insight

PROMPT_VERSION = "insight-narrative-v2"
_NUMBER_TOKEN = re.compile(r"\b(?:[A-Z]{3}\s*)?\d[\d,./-]*(?:\.\d+)?%?(?:[kmb])?\b", re.IGNORECASE)
_PROHIBITED = (
    r"\bwe recommend\b",
    r"\byou should (buy|sell)\b",
    r"\b(buy|sell|execute|trade) (this|the|a|an)\b",
    r"\bguarantee(?:d)?\b",
    r"\btax (payable|rate|outcome|liability)\b",
)


def _numeric_tokens(value: str) -> set[str]:
    return {token.lower().replace(" ", "") for token in _NUMBER_TOKEN.findall(value)}


def _guardrails(source: str, narrative: str) -> list[dict[str, str]]:
    new_numbers = _numeric_tokens(narrative) - _numeric_tokens(source)
    prohibited = next((pattern for pattern in _PROHIBITED if re.search(pattern, narrative, re.IGNORECASE)), None)
    concise = len(narrative.split()) <= 80
    return [
        {
            "id": "facts",
            "label": "No new numerical claim",
            "status": "block" if new_numbers else "pass",
            "detail": "Remove numbers, dates, currencies or percentages absent from the computed insight." if new_numbers else "No new numerical claim was detected.",
        },
        {
            "id": "advice",
            "label": "No recommendation or execution language",
            "status": "block" if prohibited else "pass",
            "detail": "Remove recommendation, trading, guarantee or tax-outcome language." if prohibited else "No prohibited recommendation or execution language was detected.",
        },
        {
            "id": "length",
            "label": "Concise RM briefing",
            "status": "pass" if concise else "block",
            "detail": "The preview stays within 80 words." if concise else "Shorten the preview to 80 words or fewer.",
        },
    ]


def draft_insight_narrative(insight: Insight) -> dict[str, Any]:
    """Generate an ephemeral, guarded explanation of one computed insight."""
    payload = insight.to_dict()
    facts = {
        "headline": payload["headline"],
        "summary": payload["summary"],
        "observed_facts": payload["observed_facts"],
        "client_relevance": payload["client_relevance"],
        "assumptions": payload["assumptions"],
        "evidence_references": [
            {
                "source_file": item["source_file"],
                "row_or_id": item["row_or_id"],
                "field": item["field"],
            }
            for item in payload["evidence"]
        ],
    }
    source = json.dumps(facts, ensure_ascii=False)
    prompt = (
        "Rewrite one already-computed wealth-risk insight as a neutral RM briefing. "
        "Use only the supplied facts. Do not add or alter numbers, dates, currencies, "
        "events, causes or client preferences. Do not recommend, advise, buy, sell, "
        "trade, execute, guarantee or state a tax outcome. If assumptions exist, say "
        "the impact is an estimate. Return one plain-text paragraph of 60 words or fewer; "
        "do not return markdown, JSON or a heading.\n\nComputed insight:\n"
        f"{source}"
    )
    narrative, provider, model = rewrite_with_configured_provider(prompt)
    if not narrative:
        raise RuntimeError("The configured AI provider returned an empty narrative.")
    checks = _guardrails(source, narrative)
    can_use = all(item["status"] == "pass" for item in checks)
    return {
        "narrative": narrative if can_use else None,
        "can_use": can_use,
        "guardrails": checks,
        "provenance": {
            "provider": provider,
            "model": model,
            "prompt_version": PROMPT_VERSION,
        },
    }
