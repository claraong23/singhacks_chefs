"""Deterministic, evidence-first Meeting Studio package generation and controls."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

from .actions import options_for
from .contracts import CommunicationPreflight, CommunicationVariant, MeetingSection, MeetingVersion
from .loaders import DataBook, get_book
from .meeting_store import new_id
from .review import ReviewStore, get_store
from .scenario_store import ScenarioStore, get_scenario_store
from .signals.base import SignalContext, run_for_client

CHANNELS = {
    "email": "Concise email",
    "formal_briefing": "Formal briefing",
    "call_notes": "Call notes",
    "client_app": "Client-app copy",
}
SECTION_TITLES = {
    "objective": "Meeting objective",
    "agenda": "Agenda",
    "questions": "Discovery questions",
    "talking_points": "Talking points",
    "option_summary": "Approved option summary",
    "risks_caveats": "Risks and caveats",
    "follow_up_tasks": "Follow-up tasks",
}
_PROHIBITED = (
    r"\bwe recommend\b",
    r"\byou should (buy|sell)\b",
    r"\bwill (buy|sell|execute|trade)\b",
    r"\bguarantee(?:d)?\b",
    r"\btax (payable|rate|outcome|liability)\b",
    r"\bredemption (will|date|is guaranteed)\b",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _refs(evidence: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(
        f"{item.get('source_file', 'source')}:{item.get('row_or_id', 'unknown')}"
        for item in evidence
    ))


def _subject(
    client_id: str,
    insight_id: str,
    book: DataBook | None = None,
    review_store: ReviewStore | None = None,
    scenario_store: ScenarioStore | None = None,
) -> dict[str, Any]:
    """Resolve one still-client-ready finding and its frozen input lineage."""
    book = book or get_book()
    review_store = review_store or get_store()
    scenario_store = scenario_store or get_scenario_store()
    if client_id not in book.clients:
        raise KeyError(f"Unknown client {client_id}")
    decision = review_store.get(insight_id)
    if not decision or decision.client_id != client_id or decision.status != "client_ready":
        raise PermissionError("A Meeting Studio package requires this finding to be client-ready.")

    ctx = SignalContext(book=book, client_id=client_id)
    insight = next((item for item in run_for_client(client_id, book) if item.id == insight_id), None)
    if insight is None:
        raise KeyError(f"Unknown finding {insight_id}")
    option = next(
        (item for item in options_for(ctx, insight) if item.id == decision.selected_option_id), None
    )
    if option is None:
        raise ValueError("The client-ready finding has no valid selected option.")

    scenario = None
    if decision.selected_scenario_id:
        scenario = scenario_store.get(decision.selected_scenario_id)
        if not scenario:
            raise ValueError("The client-ready finding references a missing saved scenario.")
        result = scenario.get("result", {})
        if (
            result.get("client_id") != client_id
            or result.get("insight_id") != insight_id
            or result.get("option_id") != option.id
            or result.get("calculation_version") != decision.scenario_calculation_version
        ):
            raise ValueError("The saved scenario no longer matches the client-ready decision.")

    evidence = [item.to_dict() for item in insight.evidence] + [item.to_dict() for item in option.evidence]
    if scenario:
        evidence.extend(scenario["result"].get("evidence", []))
    return {
        "ctx": ctx,
        "insight": insight,
        "option": option,
        "decision": decision,
        "scenario": scenario,
        "evidence": evidence,
    }


def _source(subject: dict[str, Any], audit: list[Any]) -> dict[str, Any]:
    decision = subject["decision"]
    gate_snapshot: list[dict[str, Any]] = []
    for entry in reversed(audit):
        if entry.insight_id == decision.insight_id and entry.action == "status:client_ready":
            gate_snapshot = entry.detail.get("gates", [])
            break
    return {
        "decision_status": decision.status,
        "selected_option_id": decision.selected_option_id,
        "selected_scenario_id": decision.selected_scenario_id,
        "scenario_calculation_version": decision.scenario_calculation_version,
        "evidence_version": decision.evidence_version,
        "gate_snapshot": gate_snapshot,
        "evidence": subject["evidence"],
    }


def _sections(subject: dict[str, Any]) -> list[MeetingSection]:
    ctx, insight, option, decision = (
        subject["ctx"], subject["insight"], subject["option"], subject["decision"]
    )
    refs = _refs(subject["evidence"])
    questions = insight.open_questions or [
        f"Are the recorded objectives still current: {ctx.client.get('objectives', '')}?",
        "Has anything material changed in your circumstances or liquidity needs?",
    ]
    caveats = [
        check.detail for check in option.suitability_checks if check.result != "pass"
    ] + [assumption.statement for assumption in insight.assumptions]
    caveats += [
        "This is a conversation package, not a recommendation, consent request, or trade instruction.",
        "Use values only as at the recorded source date and confirm any changed client facts.",
    ]
    scenario_line = ""
    if subject["scenario"]:
        scenario_line = (
            " A saved current-state comparison is attached; use its stated assumptions and "
            "do not present it as a forecast."
        )
    return [
        MeetingSection("objective", SECTION_TITLES["objective"], f"Discuss {insight.client_relevance} {insight.headline}.{scenario_line}", refs),
        MeetingSection("agenda", SECTION_TITLES["agenda"], "\n".join([
            f"1. Confirm the client objective and current circumstances.",
            f"2. Review the observed finding: {insight.headline}.",
            f"3. Discuss the approved option for review: {option.label}.",
            "4. Agree owners, evidence still needed, and the next review point.",
        ]), refs),
        MeetingSection("questions", SECTION_TITLES["questions"], "\n".join(f"• {item}" for item in questions[:8]), refs),
        MeetingSection("talking_points", SECTION_TITLES["talking_points"], "\n".join([
            f"• {insight.headline}. {insight.summary}",
            *[f"• {fact.label}: {fact.value}" for fact in insight.observed_facts[:5]],
        ]), refs),
        MeetingSection("option_summary", SECTION_TITLES["option_summary"], "\n".join([
            f"Option for RM-led discussion: {option.label}.", option.rationale,
            *[f"• {item}" for item in option.mechanics],
            *[f"Trade-off: {item}" for item in option.trade_offs],
        ]), refs),
        MeetingSection("risks_caveats", SECTION_TITLES["risks_caveats"], "\n".join(f"• {item}" for item in caveats), refs),
        MeetingSection("follow_up_tasks", SECTION_TITLES["follow_up_tasks"], "\n".join([
            f"• RM: {decision.edited_next_step or insight.suggested_next_step}",
            *[f"• Confirm with: {item}" for item in option.requires],
        ]), refs),
    ]


def _communications(subject: dict[str, Any], sections: list[MeetingSection]) -> list[CommunicationVariant]:
    by_key = {section.key: section for section in sections}
    client = subject["ctx"].client
    name = client.get("client_name") or "Client"
    rm_name = client.get("rm_name") or "Relationship Manager"
    as_of = subject["ctx"].snapshot
    objective = by_key["objective"].content
    option_text = by_key["option_summary"].content.splitlines()[0]
    caveat = "This is not a recommendation to buy or sell, and no action will be taken without your confirmation."
    base = f"{objective}\n\n{option_text}\n\n{caveat}\nFigures and information are as at {as_of}."
    refs = by_key["objective"].evidence_refs
    return [
        CommunicationVariant("email", CHANNELS["email"], f"Dear {name},\n\n{base}\n\nKind regards,\n{rm_name}", refs),
        CommunicationVariant("formal_briefing", CHANNELS["formal_briefing"], f"Client discussion summary\n\n{base}", refs),
        CommunicationVariant("call_notes", CHANNELS["call_notes"], f"Call preparation — {name}\n\n{objective}\n\nConfirm before discussing: {caveat}\nInformation is as at {as_of}.", refs),
        CommunicationVariant("client_app", CHANNELS["client_app"], f"Your RM would like to discuss: {objective}\n\n{caveat}\nAs at {as_of}.", refs),
    ]


def generated_version(subject: dict[str, Any], *, version: int = 1, actor: str = "RM-SG-014", reason: str = "generated") -> dict[str, Any]:
    sections = _sections(subject)
    variants = _communications(subject, sections)
    return MeetingVersion(new_id(), version, _now(), actor, reason, sections, variants).to_dict()


def create_package(
    client_id: str, insight_id: str, *, actor: str = "RM-SG-014", book: DataBook | None = None,
    review_store: ReviewStore | None = None, scenario_store: ScenarioStore | None = None,
) -> dict[str, Any]:
    review_store = review_store or get_store()
    subject = _subject(client_id, insight_id, book, review_store, scenario_store)
    version = generated_version(subject, actor=actor)
    return {
        "id": new_id(), "client_id": client_id, "insight_id": insight_id,
        "state": "draft", "created_at": _now(), "created_by": actor,
        "client_reporting_language": subject["ctx"].client.get("reporting_language", "English"),
        "source": _source(subject, review_store.audit(client_id, limit=500)),
        "current_version": 1, "versions": [version], "handoffs": [], "preflights": [],
    }


def current_version(package: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in package["versions"] if item["version"] == package["current_version"])


def update_section(package: dict[str, Any], key: str, content: str, evidence_refs: list[str], *, actor: str, reason: str = "RM edit") -> dict[str, Any]:
    if key not in SECTION_TITLES and key not in CHANNELS:
        raise ValueError("Unknown meeting section or communication channel.")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Meeting content is required.")
    allowed = set(_refs(package["source"]["evidence"]))
    if not isinstance(evidence_refs, list) or not evidence_refs or not set(evidence_refs).issubset(allowed):
        raise ValueError("Edited content must retain one or more package evidence references.")
    previous = current_version(package)
    sections = deepcopy(previous["sections"])
    communications = deepcopy(previous["communications"])
    target = sections if key in SECTION_TITLES else communications
    for item in target:
        identity = item.get("key") or item.get("channel")
        if identity == key:
            item["content"] = content.strip()
            item["evidence_refs"] = evidence_refs
            break
    else:
        raise ValueError("Meeting package is missing the requested section.")
    return MeetingVersion(
        new_id(), previous["version"] + 1, _now(), actor, reason,
        [MeetingSection(**item) for item in sections],
        [CommunicationVariant(**item) for item in communications],
    ).to_dict()


def regenerate_section(package: dict[str, Any], *, actor: str, book: DataBook | None = None,
                       review_store: ReviewStore | None = None, scenario_store: ScenarioStore | None = None,
                       key: str) -> dict[str, Any]:
    subject = _subject(package["client_id"], package["insight_id"], book, review_store, scenario_store)
    regenerated = generated_version(subject, version=current_version(package)["version"] + 1, actor=actor, reason=f"regenerated:{key}")
    candidate = next(
        (item for item in regenerated["sections"] + regenerated["communications"] if (item.get("key") or item.get("channel")) == key),
        None,
    )
    if candidate is None:
        raise ValueError("Unknown meeting section or communication channel.")
    return update_section(package, key, candidate["content"], candidate["evidence_refs"], actor=actor, reason=f"regenerated:{key}")


def restore_version(package: dict[str, Any], version_number: int, *, actor: str) -> dict[str, Any]:
    source = next((item for item in package["versions"] if item["version"] == version_number), None)
    if source is None:
        raise KeyError(f"Unknown meeting version {version_number}")
    previous = current_version(package)
    return MeetingVersion(
        new_id(), previous["version"] + 1, _now(), actor, f"restored version {version_number}",
        [MeetingSection(**item) for item in source["sections"]],
        [CommunicationVariant(**item) for item in source["communications"]],
    ).to_dict()


def preflight(package: dict[str, Any], *, book: DataBook | None = None,
              review_store: ReviewStore | None = None, scenario_store: ScenarioStore | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        subject = _subject(package["client_id"], package["insight_id"], book, review_store, scenario_store)
        current_source = _source(subject, (review_store or get_store()).audit(package["client_id"], limit=500))
        matches = all(package["source"].get(key) == current_source.get(key) for key in (
            "selected_option_id", "selected_scenario_id", "scenario_calculation_version", "evidence_version"
        ))
        gates_pass = bool(current_source["gate_snapshot"]) and all(
            gate.get("status") == "pass" for gate in current_source["gate_snapshot"]
        )
        checks.append({"id": "client_ready", "label": "Client-ready decision and gate snapshot", "status": "pass" if matches and gates_pass else "block", "detail": "The selected option, evidence and passing controls still match." if matches and gates_pass else "The client-ready source changed or cannot be reconstructed."})
    except (KeyError, ValueError, PermissionError) as exc:
        checks.append({"id": "client_ready", "label": "Client-ready decision and gate snapshot", "status": "block", "detail": str(exc)})

    current = current_version(package)
    for variant in current["communications"]:
        content = variant["content"].lower()
        refs = variant.get("evidence_refs", [])
        blocked_term = next((pattern for pattern in _PROHIBITED if re.search(pattern, content)), None)
        has_caveats = "not a recommendation" in content and "as at" in content
        checks.append({
            "id": f"content:{variant['channel']}", "label": f"{variant['label']} evidence and wording",
            "status": "pass" if refs and not blocked_term and has_caveats else "block",
            "detail": "Evidence references and required caveats are present." if refs and not blocked_term and has_caveats else "Retain evidence references and the 'not a recommendation' and 'as at' caveats; remove prohibited claims.",
        })

    language = package.get("client_reporting_language")
    checks.append({
        "id": "language", "label": "Client language", "status": "pass" if language in (None, "", "English") else "block",
        "detail": "English is recorded as the reporting language." if language in (None, "", "English") else f"Draft is English; route through approved translation for {language} before hand-off.",
    })
    result = CommunicationPreflight(all(item["status"] == "pass" for item in checks), checks, _now()).to_dict()
    return result
