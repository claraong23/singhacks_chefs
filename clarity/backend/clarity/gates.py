"""Deterministic client-ready controls for the RM workbench.

The gate evaluator consumes the facts and suitability checks supplied by Tasks
1 and 2.  It does not rank clients, calculate a new risk score, or generate
advice.  Its only job is to make the RM's decision boundary explicit.
"""

from __future__ import annotations

import hashlib
import json

from .contracts import ActionOption, DecisionGate, DecisionReadiness, Evidence, Insight


def _evidence_version(evidence: list[Evidence]) -> str:
    """Stable fingerprint of the evidence the RM reviewed for this decision."""
    payload = [item.to_dict() for item in evidence]
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _complete(evidence: Evidence) -> bool:
    """Static source records legitimately have no market snapshot date.

    The evidence contract still requires a source, row/id, field and raw value.
    ``snapshot_date`` remains available for time-series evidence and is shown in
    the evidence drawer; it is not fabricated for static client/instrument data.
    """
    return bool(
        evidence.source_file
        and evidence.row_or_id
        and evidence.field
        and evidence.value is not None
    )


def evaluate_readiness(
    insight: Insight,
    options: list[ActionOption],
    *,
    selected_option_id: str | None,
    rm_note: str,
    edited_next_step: str | None = None,
) -> DecisionReadiness:
    """Return the five client-ready gates for one selected action option.

    Strictness is deliberate: ``fail``, ``attention`` and ``not_assessed`` are
    all blockers.  The RM can still document review, escalate, defer or dismiss
    an item; only the client-ready transition is gated.
    """
    option = next((item for item in options if item.id == selected_option_id), None)
    cited = [*insight.evidence, *(option.evidence if option else [])]

    if not insight.evidence:
        evidence_gate = DecisionGate(
            id="evidence",
            label="Evidence",
            status="block",
            detail="The underlying insight has no cited source evidence.",
        )
    elif not all(_complete(item) for item in insight.evidence):
        evidence_gate = DecisionGate(
            id="evidence",
            label="Evidence",
            status="block",
            detail="At least one cited fact is missing a source, row/id, field or raw value.",
            evidence=insight.evidence,
        )
    else:
        evidence_gate = DecisionGate(
            id="evidence",
            label="Evidence",
            status="pass",
            detail="The insight has structured source evidence; option-specific evidence is included where available.",
            evidence=cited,
        )

    checks = [*insight.suitability_checks, *(option.suitability_checks if option else [])]
    blocked_checks = [check for check in checks if check.result != "pass"]
    if blocked_checks:
        names = "; ".join(f"{check.check} ({check.result.replace('_', ' ')})" for check in blocked_checks)
        suitability_gate = DecisionGate(
            id="suitability",
            label="Suitability",
            status="block",
            detail=f"Resolve before client-ready: {names}.",
        )
    else:
        suitability_gate = DecisionGate(
            id="suitability",
            label="Suitability",
            status="pass",
            detail="All deterministic suitability checks for the insight and selected option pass.",
        )

    tax_checks = [
        check
        for check in checks
        if insight.category.value == "tax" or "tax" in check.check.lower()
    ]
    tax_blockers = [check for check in tax_checks if check.result != "pass"]
    if tax_blockers:
        tax_gate = DecisionGate(
            id="tax_planning",
            label="Tax and planning",
            status="block",
            detail="Tax/planning review is unresolved: "
            + "; ".join(check.detail for check in tax_blockers),
        )
    else:
        tax_gate = DecisionGate(
            id="tax_planning",
            label="Tax and planning",
            status="pass",
            detail="No unresolved tax or wealth-planning control applies to this selected option.",
        )

    data_issues = list(insight.open_questions)
    if edited_next_step is not None and not edited_next_step.strip():
        data_issues.append("The edited next step is blank.")
    if data_issues:
        data_gate = DecisionGate(
            id="data_model",
            label="Data and model",
            status="block",
            detail="Resolve before client-ready: " + " ".join(data_issues),
        )
    else:
        data_gate = DecisionGate(
            id="data_model",
            label="Data and model",
            status="pass",
            detail="No unresolved questions or invalid edited wording were supplied.",
        )

    human_issues: list[str] = []
    if option is None:
        human_issues.append("Select an action option.")
    if not rm_note.strip():
        human_issues.append("Record the RM rationale.")
    human_gate = DecisionGate(
        id="human_decision",
        label="Human decision",
        status="block" if human_issues else "pass",
        detail=(
            " ".join(human_issues)
            if human_issues
            else "An RM selected an option and recorded a rationale for the file."
        ),
    )

    gates = [evidence_gate, suitability_gate, tax_gate, data_gate, human_gate]
    return DecisionReadiness(
        can_mark_client_ready=all(gate.status == "pass" for gate in gates),
        gates=gates,
        evidence_version=_evidence_version(cited),
    )
