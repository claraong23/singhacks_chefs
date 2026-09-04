"""Deterministic validation and shadow evaluation for priority policies."""

from __future__ import annotations

from typing import Any

from .calibration_store import TEMPLATES, get_calibration_store
from .loaders import DataBook, get_book
from .signals.base import run_for_book

# These anchor journeys are product-acceptance coverage, not a training set.
ANCHOR_CLIENTS = {"CL-0014", "CL-0003", "CL-0017"}
WEIGHT_KEYS = {"severity", "materiality", "urgency"}
USEFULNESS = {"useful", "partly_useful", "not_useful"}
URGENCY = {"right", "overstated", "understated"}
FINAL_STATUSES = {"rm_reviewed", "client_ready", "deferred", "dismissed"}


def validate_weights(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != WEIGHT_KEYS:
        raise ValueError("weights must contain severity, materiality, and urgency.")
    try:
        weights = {key: float(raw[key]) for key in WEIGHT_KEYS}
    except (TypeError, ValueError) as exc:
        raise ValueError("priority weights must be numbers.") from exc
    if any(value < 0 for value in weights.values()) or abs(sum(weights.values()) - 1.0) > 0.00001:
        raise ValueError("priority weights must be non-negative and sum exactly to 1.0.")
    return weights


def proposal(payload: dict[str, Any]) -> tuple[str, dict[str, float], str | None]:
    template = payload.get("template")
    if template:
        if template not in TEMPLATES:
            raise ValueError("Unknown priority-policy template.")
        return payload.get("name") or TEMPLATES[template]["name"], validate_weights(TEMPLATES[template]["weights"]), template
    return str(payload.get("name") or "").strip(), validate_weights(payload.get("weights")), None


def validate_feedback(payload: dict[str, Any], status: str) -> dict[str, str]:
    if status not in FINAL_STATUSES:
        return {}
    feedback = payload.get("feedback")
    if not isinstance(feedback, dict):
        raise ValueError("Structured RM feedback is required for a final disposition.")
    usefulness = feedback.get("usefulness")
    urgency = feedback.get("urgency_assessment")
    rationale = str(feedback.get("rationale") or "").strip()
    if usefulness not in USEFULNESS or urgency not in URGENCY or not rationale:
        raise ValueError("Feedback needs usefulness, urgency assessment, and a rationale.")
    return {"usefulness": usefulness, "urgency_assessment": urgency, "rationale": rationale}


def _ranks(book: DataBook, weights: dict[str, float]) -> list[dict[str, Any]]:
    insights = run_for_book(book, priority_weights=weights)
    rows = []
    for client_id, client_insights in insights.items():
        top = client_insights[0] if client_insights else None
        rows.append({"client_id": client_id, "insight_id": top.id if top else None,
                     "headline": top.headline if top else "Nothing outstanding",
                     "score": round(top.priority_score, 1) if top else 0.0})
    rows.sort(key=lambda row: (-row["score"], row["client_id"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def evaluate(policy_id: str, book: DataBook | None = None) -> dict[str, Any]:
    store = get_calibration_store()
    policy = store.get(policy_id)
    if not policy:
        raise KeyError("Unknown priority policy.")
    active = store.active()
    book = book or get_book()
    baseline = {row["client_id"]: row for row in _ranks(book, active["weights"])}
    candidate = _ranks(book, policy["weights"])
    feedback = store.feedback_for()
    anchors = sorted({row["client_id"] for row in feedback} & ANCHOR_CLIENTS)
    warnings: list[str] = []
    eligible = len(feedback) >= 3 and set(anchors) == ANCHOR_CLIENTS
    if len(feedback) < 3:
        warnings.append("At least three final RM feedback records are required before activation.")
    missing = sorted(ANCHOR_CLIENTS - set(anchors))
    if missing:
        warnings.append("Feedback is still required for " + ", ".join(missing) + ".")
    by_insight = {row["insight_id"]: row for row in feedback}
    labelled_top = [by_insight[row["insight_id"]] for row in candidate[:5] if row["insight_id"] in by_insight]
    relevance = None if not labelled_top else round(sum(item["usefulness"] != "not_useful" for item in labelled_top) / len(labelled_top), 3)
    urgency_alignment = None if not feedback else round(sum(item["urgency_assessment"] == "right" for item in feedback) / len(feedback), 3)
    rank_changes = [{
        "client_id": row["client_id"], "headline": row["headline"], "candidate_rank": row["rank"],
        "active_rank": baseline[row["client_id"]]["rank"], "rank_delta": baseline[row["client_id"]]["rank"] - row["rank"],
        "candidate_score": row["score"], "active_score": baseline[row["client_id"]]["score"],
    } for row in candidate]
    return {"policy_id": policy_id, "active_policy_id": active["id"], "feedback_count": len(feedback),
            "anchor_coverage": anchors, "activation_eligible": eligible, "warnings": warnings,
            "top_five_relevance_rate": relevance, "urgency_alignment_rate": urgency_alignment,
            "rank_changes": rank_changes}


def create_policy(payload: dict[str, Any], actor: str) -> dict[str, Any]:
    name, weights, template = proposal(payload)
    rationale = str(payload.get("rationale") or "").strip()
    if not name or not rationale:
        raise ValueError("A policy name and RM rationale are required.")
    return get_calibration_store().create(name=name, weights=weights, rationale=rationale, actor=actor, template=template)
