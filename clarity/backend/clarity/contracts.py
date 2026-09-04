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
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

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
