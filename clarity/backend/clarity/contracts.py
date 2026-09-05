"""Shared contracts.

These shapes are the interface between the four workstreams. Analytics writes
them, the API serialises them unchanged, and the UI renders them. Mirror any
change here in ``frontend/src/contracts.ts``.

Two rules hold everywhere:

1. Anything a judge could challenge carries ``evidence`` -- a source file, a row
   or id, a snapshot date, a field and a value. No claim without a citation.
2. Computed numbers and AI wording live in different fields. ``headline`` and
   ``observed_facts`` are produced by deterministic Python. Narrative prose is
   generated from those facts and is always attributed.
"""

from __future__ import annotations

import dataclasses
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


_PENDING_PRIORITY_FACTORS: ContextVar["PriorityFactors | None"] = ContextVar(
    "pending_priority_factors", default=None
)


def capture_priority_factors(factors: "PriorityFactors") -> None:
    """Associate a score calculation with the immediately-created insight."""
    _PENDING_PRIORITY_FACTORS.set(factors)


def consume_priority_factors() -> "PriorityFactors | None":
    factors = _PENDING_PRIORITY_FACTORS.get()
    _PENDING_PRIORITY_FACTORS.set(None)
    return factors

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> float:
        return {
            Severity.CRITICAL: 1.0,
            Severity.HIGH: 0.78,
            Severity.MEDIUM: 0.52,
            Severity.LOW: 0.30,
            Severity.INFO: 0.15,
        }[self]


class Category(str, Enum):
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    COLLATERAL = "collateral"
    MANDATE = "mandate"
    CURRENCY = "currency"
    SUITABILITY = "suitability"
    TAX = "tax"
    LIFE_EVENT = "life_event"
    PERFORMANCE = "performance"
    OPPORTUNITY = "opportunity"
    DATA_QUALITY = "data_quality"
    ADMIN = "admin"


class InsightStatus(str, Enum):
    NEW = "new"
    OPENED = "opened"
    UNDER_REVIEW = "under_review"
    RM_EDITED = "rm_edited"
    RM_REVIEWED = "rm_reviewed"
    ESCALATED = "escalated"
    RETURNED_FOR_REVIEW = "returned_for_review"
    CLIENT_READY = "client_ready"
    DEFERRED = "deferred"
    DISMISSED = "dismissed"


class Confidence(str, Enum):
    #: Arithmetic on source rows. Nothing assumed.
    MEASURED = "measured"
    #: Arithmetic plus a stated modelling assumption.
    DERIVED = "derived"
    #: Depends on an RM note or a client statement that structured data does
    #: not independently confirm.
    REPORTED = "reported"


# ---------------------------------------------------------------------------
# Priority calibration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorityFactors:
    """Immutable deterministic inputs to an insight's published priority score."""

    severity_weight: float
    materiality_pct: float | None = None
    days_until: int | None = None
    amount_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class PriorityPolicy:
    """A versioned, transparent set of score weights; never a predictive model."""

    id: str
    name: str
    weights: dict[str, float]
    status: Literal["draft", "submitted", "active", "rejected", "retired"]
    rationale: str
    created_by: str
    created_at: str
    activation_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class RMFeedback:
    """An RM's governed assessment of a final finding disposition."""

    id: str
    client_id: str
    insight_id: str
    decision_status: str
    usefulness: Literal["useful", "partly_useful", "not_useful"]
    urgency_assessment: Literal["right", "overstated", "understated"]
    rationale: str
    actor: str
    timestamp: str
    evidence_version: str | None
    policy_id: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class PriorityPolicyEvaluation:
    """A deterministic candidate-versus-active scoring comparison."""

    policy_id: str
    active_policy_id: str
    feedback_count: int
    anchor_coverage: list[str]
    activation_eligible: bool
    warnings: list[str]
    top_five_relevance_rate: float | None = None
    urgency_alignment_rate: float | None = None
    rank_changes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    """One citable fact, traceable to a row in the source data."""

    source_file: str
    row_or_id: str
    field: str
    value: Any
    snapshot_date: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class Assumption:
    """A modelling choice the reader is entitled to disagree with."""

    statement: str
    basis: str
    impact_if_wrong: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class SuitabilityCheck:
    """A guardrail evaluated before an action may be proposed."""

    check: str
    result: Literal["pass", "fail", "attention", "not_assessed"]
    detail: str
    reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class DecisionGate:
    """One explicit control that must pass before an RM can mark work client-ready."""

    id: Literal["evidence", "suitability", "tax_planning", "data_model", "human_decision"]
    label: str
    status: Literal["pass", "block"]
    detail: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class DecisionReadiness:
    """Deterministic preflight for the irreversible client-ready workflow step."""

    can_mark_client_ready: bool
    gates: list[DecisionGate]
    evidence_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_mark_client_ready": self.can_mark_client_ready,
            "gates": [gate.to_dict() for gate in self.gates],
            "evidence_version": self.evidence_version,
        }


# ---------------------------------------------------------------------------
# Meeting Studio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeetingSection:
    """One editable, evidence-linked block in an RM meeting package."""

    key: str
    title: str
    content: str
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class CommunicationVariant:
    """A channel-specific client draft. It is never sent by Clarity."""

    channel: Literal["email", "formal_briefing", "call_notes", "client_app"]
    label: str
    content: str
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MeetingVersion:
    """Immutable snapshot created for generation, editing, or restoration."""

    id: str
    version: int
    created_at: str
    actor: str
    reason: str
    sections: list[MeetingSection]
    communications: list[CommunicationVariant]
    provenance: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "created_at": self.created_at,
            "actor": self.actor,
            "reason": self.reason,
            "sections": [section.to_dict() for section in self.sections],
            "communications": [variant.to_dict() for variant in self.communications],
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class CommunicationPreflight:
    """Deterministic control result before an RM copies or hands off a draft."""

    can_hand_off: bool
    checks: list[dict[str, Any]]
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MeetingHandoffEvent:
    """Audit event for a simulated, never external, communication hand-off."""

    id: str
    package_id: str
    channel: str
    actor: str
    created_at: str
    preflight_version: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MeetingPackage:
    """Persisted, one-finding communication package with immutable versions."""

    id: str
    client_id: str
    insight_id: str
    state: Literal["draft", "preflight_passed", "handed_off"]
    created_at: str
    created_by: str
    source: dict[str, Any]
    current_version: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class AIDraftingProviderStatus:
    """Safe-to-display availability of the optional server-side drafting adapter."""

    available: bool
    provider: Literal["disabled", "gemini", "openai_compatible"]
    model: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class AIDraftRequest:
    package_id: str
    target_key: str
    style: Literal["clear_concise", "warm_respectful", "formal_concise"]
    source_version: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class AIDraftGuardrail:
    id: str
    label: str
    status: Literal["pass", "block"]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class AIDraftProvenance:
    provider: Literal["gemini", "openai_compatible"]
    model: str
    prompt_version: str
    source_version: int
    target_key: str
    candidate_digest: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class AIDraftCandidate:
    id: str
    package_id: str
    target_key: str
    style: str
    content: str | None
    can_apply: bool
    guardrails: list[AIDraftGuardrail]
    expires_at: str
    provenance: AIDraftProvenance | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **dataclasses.asdict(self),
            "guardrails": [item.to_dict() for item in self.guardrails],
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


# ---------------------------------------------------------------------------
# Follow-through and audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FollowUpTask:
    id: str
    client_id: str
    title: str
    owner_role: str
    due_date: str
    status: str
    insight_id: str | None = None
    meeting_package_id: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    description: str = ""
    created_by: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class SpecialistReferral:
    id: str
    client_id: str
    referral_type: str
    owner_role: str
    due_date: str
    status: str
    summary: str
    insight_id: str | None = None
    meeting_package_id: str | None = None
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class MeetingOutcome:
    id: str
    client_id: str
    outcome_type: str
    statement: str
    actor: str
    recorded_at: str
    insight_id: str | None = None
    meeting_package_id: str | None = None
    requested_documents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class EvidenceUpdate:
    id: str
    client_id: str
    source_type: str
    source_ref: str
    summary: str
    received_at: str
    actor: str
    affected_insight_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ReevaluationRequest:
    id: str
    client_id: str
    evidence_update_id: str
    affected_insight_ids: list[str]
    owner_role: str
    status: Literal["queued", "acknowledged", "complete"]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class KnowledgeCitation:
    """A precise citation to an approved synthetic internal reference."""

    document_id: str
    version: int
    title: str
    effective_date: str
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class KnowledgeDocumentVersion:
    version: int
    status: Literal["draft", "submitted", "approved", "rejected", "superseded"]
    body: str
    source_refs: list[str]
    effective_date: str
    created_at: str
    created_by: str
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    title: str
    category: str
    tags: list[str]
    owner: str
    current_version: int
    versions: list[KnowledgeDocumentVersion]

    def to_dict(self) -> dict[str, Any]:
        return {**dataclasses.asdict(self), "versions": [item.to_dict() for item in self.versions]}


@dataclass(frozen=True)
class KnowledgeSearchResult:
    citation: KnowledgeCitation
    category: str
    tags: list[str]
    excerpt: str
    matched_terms: list[str]
    matched_fields: list[str]
    score: int

    def to_dict(self) -> dict[str, Any]:
        return {"citation": self.citation.to_dict(), "category": self.category, "tags": self.tags,
                "excerpt": self.excerpt, "matched_terms": self.matched_terms,
                "matched_fields": self.matched_fields, "score": self.score}


@dataclass(frozen=True)
class AuditTimelineEvent:
    id: str
    timestamp: str
    origin: Literal["source_data", "system", "user_decision"]
    object_type: str
    object_id: str
    action: str
    actor: str
    client_id: str | None = None
    insight_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class Fact:
    """A computed statement plus the number behind it."""

    label: str
    value: str
    numeric: float | None = None
    unit: str | None = None
    trend: Literal["up", "down", "flat"] | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Insight
# ---------------------------------------------------------------------------


@dataclass
class Insight:
    """A single reviewable observation about one client.

    ``priority_score`` is a transparent 0-100 blend of severity, money at risk
    and time pressure. ``priority_reasons`` spells out how it was reached -- an
    opaque AI score is worth less to an RM than a defensible ranking.
    """

    id: str
    client_id: str
    category: Category
    severity: Severity
    headline: str
    summary: str
    priority_score: float
    priority_reasons: list[str] = field(default_factory=list)
    priority_factors: PriorityFactors | None = None
    observed_facts: list[Fact] = field(default_factory=list)
    client_relevance: str = ""
    suggested_next_step: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    suitability_checks: list[SuitabilityCheck] = field(default_factory=list)
    confidence: Confidence = Confidence.MEASURED
    open_questions: list[str] = field(default_factory=list)
    related_event_ids: list[str] = field(default_factory=list)
    portfolio_ids: list[str] = field(default_factory=list)
    instrument_ids: list[str] = field(default_factory=list)
    amount_usd: float | None = None
    status: InsightStatus = InsightStatus.NEW

    def __post_init__(self) -> None:
        if self.priority_factors is None:
            self.priority_factors = consume_priority_factors()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "headline": self.headline,
            "summary": self.summary,
            "priority_score": round(self.priority_score, 1),
            "priority_reasons": list(self.priority_reasons),
            "priority_factors": self.priority_factors.to_dict() if self.priority_factors else None,
            "observed_facts": [f.to_dict() for f in self.observed_facts],
            "client_relevance": self.client_relevance,
            "suggested_next_step": self.suggested_next_step,
            "evidence": [e.to_dict() for e in self.evidence],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "suitability_checks": [s.to_dict() for s in self.suitability_checks],
            "confidence": self.confidence.value,
            "open_questions": list(self.open_questions),
            "related_event_ids": list(self.related_event_ids),
            "portfolio_ids": list(self.portfolio_ids),
            "instrument_ids": list(self.instrument_ids),
            "amount_usd": self.amount_usd,
            "status": self.status.value,
        }


# ---------------------------------------------------------------------------
# Actions and the RM decision
# ---------------------------------------------------------------------------


@dataclass
class ActionOption:
    """One option for the RM to consider. Never an instruction."""

    id: str
    label: str
    rationale: str
    mechanics: list[str] = field(default_factory=list)
    trade_offs: list[str] = field(default_factory=list)
    suitability_checks: list[SuitabilityCheck] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    estimated_impact: str | None = None
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "rationale": self.rationale,
            "mechanics": list(self.mechanics),
            "trade_offs": list(self.trade_offs),
            "suitability_checks": [s.to_dict() for s in self.suitability_checks],
            "requires": list(self.requires),
            "estimated_impact": self.estimated_impact,
            "evidence": [e.to_dict() for e in self.evidence],
        }


# ---------------------------------------------------------------------------
# Scenario studio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioInput:
    """A bounded lever the RM may adjust in a deterministic scenario."""

    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float
    default: float
    help_text: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ScenarioTemplate:
    """A supported current-state comparison for one anchor-client finding."""

    id: str
    client_id: str
    insight_id: str
    title: str
    description: str
    inputs: list[ScenarioInput]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "client_id": self.client_id,
            "insight_id": self.insight_id,
            "title": self.title,
            "description": self.description,
            "inputs": [item.to_dict() for item in self.inputs],
        }


@dataclass(frozen=True)
class ScenarioMetric:
    """One before/after measurement, or an explicit data limitation."""

    key: str
    label: str
    baseline: float | None
    scenario: float | None
    unit: str
    available: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ScenarioResult:
    template_id: str
    client_id: str
    insight_id: str
    option_id: str
    title: str
    as_of_date: str
    inputs: dict[str, float]
    assumptions: list[Assumption]
    metrics: list[ScenarioMetric]
    evidence: list[Evidence]
    blocked_checks: list[str]
    calculation_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "client_id": self.client_id,
            "insight_id": self.insight_id,
            "option_id": self.option_id,
            "title": self.title,
            "as_of_date": self.as_of_date,
            "inputs": dict(self.inputs),
            "assumptions": [item.to_dict() for item in self.assumptions],
            "metrics": [item.to_dict() for item in self.metrics],
            "evidence": [item.to_dict() for item in self.evidence],
            "blocked_checks": list(self.blocked_checks),
            "calculation_version": self.calculation_version,
        }


@dataclass(frozen=True)
class SavedScenario:
    """A persisted RM comparison; saving it never changes workflow status."""

    id: str
    name: str
    saved_by: str
    saved_at: str
    result: ScenarioResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "saved_by": self.saved_by,
            "saved_at": self.saved_at,
            "result": self.result.to_dict(),
        }


@dataclass
class MeetingBrief:
    """What Priscilla walks into the meeting with."""

    client_id: str
    generated_at: str
    as_of: str
    purpose: str
    talking_points: list[str] = field(default_factory=list)
    questions_to_ask: list[str] = field(default_factory=list)
    relationship_context: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    do_not_say: list[str] = field(default_factory=list)
    draft_follow_up: str = ""
    provenance: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Holding changes and explanation contracts (Task 1)
# ---------------------------------------------------------------------------


@dataclass
class HoldingChange:
    instrument_id: str
    instrument_name: str
    asset_class: str
    sector: str
    region: str
    currency: str
    portfolio_ids: list[str]
    start_quantity: float
    end_quantity: float
    quantity_change: float
    start_price: float | None
    end_price: float | None
    price_return_pct: float | None
    start_value_usd: float
    end_value_usd: float
    value_change_usd: float
    start_weight_pct: float
    end_weight_pct: float
    weight_change_pct: float
    trigger_badges: list[str]
    is_meaningful: bool
    valuation_lag: bool = False
    liquidity_tier: str = "Daily"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class HoldingExplanation:
    client_id: str
    instrument_id: str
    instrument_name: str
    asset_class: str
    sector: str
    region: str
    start: str
    end: str
    portfolio_id: str | None
    what_changed: dict[str, Any]
    event_evidence: list[dict[str, Any]]
    transmission_mechanisms: list[str]
    why_it_matters: list[str]
    uncertainties: list[str]
    source_evidence: list[Evidence] = field(default_factory=list)
    portfolio_impact: dict[str, Any] = field(default_factory=dict)
    movement_type: str = "price-led"
    limitations: list[str] = field(default_factory=list)
    conclusion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "asset_class": self.asset_class,
            "sector": self.sector,
            "region": self.region,
            "start": self.start,
            "end": self.end,
            "portfolio_id": self.portfolio_id,
            "what_changed": self.what_changed,
            "event_evidence": self.event_evidence,
            "transmission_mechanisms": self.transmission_mechanisms,
            "why_it_matters": self.why_it_matters,
            "uncertainties": self.uncertainties,
            "source_evidence": [e.to_dict() for e in self.source_evidence],
            "portfolio_impact": self.portfolio_impact,
            "movement_type": self.movement_type,
            "limitations": self.limitations,
            "conclusion": self.conclusion,
        }


@dataclass
class ClientAttributionDraft:
    client_id: str
    instrument_id: str
    instrument_name: str
    headline: str
    what_happened_bullet: str
    why_it_matters_bullet: str
    next_steps_bullet: str
    confidence: str
    source_chips: list[str]
    limitations: list[str]
    language_disclaimer: str | None = None
    created_at: str = ""
    id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Governed integration sandbox
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InboundIntegrationEvent:
    id: str
    source_system: str
    external_event_id: str
    schema_version: str
    client_id: str
    source_ref: str
    occurred_at: str
    received_at: str
    payload_digest: str
    validation_state: str
    operations_disposition: str | None = None


@dataclass(frozen=True)
class OutboundWorkOrder:
    id: str
    idempotency_key: str
    destination: str
    work_record_type: str
    work_record_id: str
    owner_role: str
    status: str
    evidence_refs: list[str] = field(default_factory=list)
    external_reference: str | None = None


@dataclass(frozen=True)
class IntegrationAuditEvent:
    id: str
    actor: str
    origin: str
    object_id: str
    action: str
    timestamp: str
    prior_status: str | None = None
    new_status: str | None = None
    feature_schema_version: str = "deterministic-priority-factors-v1"


@dataclass(frozen=True)
class ModelReadinessMetadata:
    feature_schema_version: str
    training_eligible: bool
    reasons: list[str]

