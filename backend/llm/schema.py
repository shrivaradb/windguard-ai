"""Pydantic v2 Schemas for Layer 5: Advisory Reasoning & Guardrail Subsystem.

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011, FR-012)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/10_data_architecture.md §4.5
- docs/PHASE_5_SCOPE_REVIEW.md §6.2
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §5, §7, §8
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.rag.schema import SourceType


class AdvisoryStatus(str, Enum):
    """Formal Four-State Advisory Output Model."""

    NORMAL_ADVISORY = "NORMAL_ADVISORY"
    FALLBACK_ADVISORY = "FALLBACK_ADVISORY"
    ABSTENTION = "ABSTENTION"
    BLOCKED_OUTPUT = "BLOCKED_OUTPUT"


class GuardrailVerdict(str, Enum):
    """Guardrail Action Evaluation State."""

    PASS = "PASS"
    FALLBACK_APPLIED = "FALLBACK_APPLIED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"


class EvidenceType(str, Enum):
    """Classification of Upstream Grounding Evidence."""

    SCADA_TELEMETRY = "SCADA_TELEMETRY"
    ML_RESIDUAL = "ML_RESIDUAL"
    CONTEXT_CLASSIFICATION = "CONTEXT_CLASSIFICATION"
    FINANCIAL_LOSS = "FINANCIAL_LOSS"
    RAG_TECHNICAL_CHUNK = "RAG_TECHNICAL_CHUNK"
    PRIORITY_SCORE = "PRIORITY_SCORE"


class ReviewStatus(str, Enum):
    """Operator Human-in-the-Loop Review Escalation Status."""

    AUTOMATIC = "AUTOMATIC"
    MANDATORY_HUMAN_REVIEW_REQUIRED = "MANDATORY_HUMAN_REVIEW_REQUIRED"


class PlausibilityRating(str, Enum):
    """Epistemic Uncertainty Plausibility Level (OD-P5-06 Initial Design Parameter)."""

    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class EvidenceItem(BaseModel):
    """Individual Grounded Evidence Datum."""

    evidence_id: str = Field(..., description="Unique evidence identifier within case context")
    evidence_type: EvidenceType = Field(..., description="Upstream subsystem origin type")
    field_name: str = Field(..., description="Authoritative variable or metric name")
    value: Any = Field(..., description="Authoritative upstream numerical or categorical value")
    unit: Optional[str] = Field(default=None, description="Engineering physical unit if applicable")
    source_reference: str = Field(..., description="Upstream generator or chunk locator reference")
    content_hash: Optional[str] = Field(default=None, description="Cryptographic hash for provenance tracking")

    model_config = ConfigDict(extra="forbid", frozen=True)


class CitationItem(BaseModel):
    """Technical Knowledge Citation with Cryptographic Provenance."""

    source_id: str = Field(..., description="Unique source identifier (e.g. SRC-AUTHENTIC-GB-01)")
    source_type: SourceType = Field(..., description="Authenticity provenance classification")
    title: str = Field(..., description="Canonical document title")
    chapter: Optional[str] = Field(default=None, description="Chapter or major division")
    section: Optional[str] = Field(default=None, description="Section heading")
    source_locator: Optional[str] = Field(default=None, description="Deterministic locator anchor")
    source_page: Optional[int] = Field(default=None, ge=1, description="Page number if paginated")
    content_hash: str = Field(..., description="Cryptographic SHA-256 hash of source content")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Hybrid retrieval relevance score")

    model_config = ConfigDict(extra="forbid", frozen=True)


class HypothesisItem(BaseModel):
    """Evidence-Grounded Candidate Explanation (OD-P5-06 Structured Uncertainty)."""

    hypothesis: str = Field(..., description="Evidence-grounded candidate physical explanation")
    plausibility: PlausibilityRating = Field(..., description="Qualitative epistemic rating")
    grounding_evidence: List[str] = Field(
        default_factory=list,
        description="References to evidence_ids or chunk_ids supporting this explanation",
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Checklist of absent physical signals or tests required for certainty",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class RecommendedActionItem(BaseModel):
    """Non-Actuating Diagnostic Maintenance Recommendation."""

    action_id: str = Field(..., description="Unique action identifier")
    action_text: str = Field(..., description="Descriptive diagnostic instruction for human engineer")
    urgency: str = Field(..., description="Urgency classification (IMMEDIATE, SCHEDULED, MONITORING)")
    target_subsystem: str = Field(..., description="Target physical component or subsystem")
    requires_human_approval: bool = Field(
        default=True,
        description="Mandatory assertion that human engineer must approve and execute action",
    )
    is_non_actuating: bool = Field(
        default=True,
        description="Mandatory assertion that action is an advisory instruction, NOT a control command",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class GuardrailStatusBlock(BaseModel):
    """Detailed Execution Audit of Independent Guardrail Checks."""

    verdict: GuardrailVerdict = Field(..., description="Overall guardrail verdict")
    schema_valid: bool = Field(..., description="Pydantic extra='forbid' schema conformance")
    numerical_consistency_valid: bool = Field(..., description="Exact numerical pass-through assertion")
    citation_whitelist_valid: bool = Field(..., description="Provenance and hash integrity assertion")
    lexicon_scan_passed: bool = Field(..., description="Absence of prohibited control/actuation language")
    context_consistency_valid: bool = Field(..., description="Consistency with Phase 3 operational context")
    attribution_consistency_valid: bool = Field(..., description="Consistency with Phase 3 subsystem attribution")
    safety_disclaimer_present: bool = Field(..., description="Presence of mandatory safety disclaimer")
    violations: List[str] = Field(default_factory=list, description="List of detected rule violations if any")

    model_config = ConfigDict(extra="forbid", frozen=True)


class OperatorAdvisory(BaseModel):
    """Complete Validated Structured Operator Advisory."""

    case_id: str = Field(..., description="Unique case identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp of evaluation")
    turbine_id: str = Field(..., description="Turbine identifier (e.g. WTG01)")
    status: AdvisoryStatus = Field(..., description="Formal advisory output status")
    primary_attribution: str = Field(..., description="Authoritative Phase 3 subsystem attribution")
    context_classification: str = Field(..., description="Authoritative Phase 3 context classification")
    summary: str = Field(..., description="Executive diagnostic summary of anomaly and operational state")
    evidence_synthesis: List[EvidenceItem] = Field(
        default_factory=list, description="Structured synthesis of authoritative upstream evidence"
    )
    hypotheses: List[HypothesisItem] = Field(
        default_factory=list, description="Evidence-grounded candidate explanations"
    )
    recommended_actions: List[RecommendedActionItem] = Field(
        default_factory=list, description="Non-actuating recommended diagnostic actions"
    )
    citations: List[CitationItem] = Field(
        default_factory=list, description="Verified technical citations with SHA-256 provenance"
    )
    loss_summary_inr: float = Field(..., ge=0.0, description="Authoritative financial loss impact in INR")
    energy_loss_kwh: float = Field(..., ge=0.0, description="Authoritative eligible energy loss in kWh")
    priority_score: float = Field(..., ge=0.0, le=100.0, description="Authoritative 0-100 priority score")
    review_status: ReviewStatus = Field(..., description="Human-in-the-loop review escalation status")
    guardrail_status: GuardrailStatusBlock = Field(..., description="Independent guardrail evaluation block")
    safety_disclaimer: str = Field(..., description="Mandatory non-actuating safety and liability disclaimer")
    missing_evidence_summary: Optional[str] = Field(
        default=None, description="Detailed articulation of absent evidence in case of uncertainty/abstention"
    )
    abstention_reason: Optional[str] = Field(
        default=None, description="Specific reason for diagnostic abstention if applicable"
    )
    fallback_reason: Optional[str] = Field(
        default=None, description="Specific reason for engaging deterministic fallback if applicable"
    )
    blocked_reason: Optional[str] = Field(
        default=None, description="Specific reason for blocking advisory generation if applicable"
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class AuditSnapshot(BaseModel):
    """Immutable Audit Trail Snapshot for Advisory Evaluation."""

    audit_id: str = Field(..., description="Unique audit event identifier")
    timestamp: str = Field(..., description="ISO 8601 audit creation timestamp")
    case_id: str = Field(..., description="Target case identifier")
    turbine_id: str = Field(..., description="Target turbine identifier")
    provider_mode: str = Field(..., description="Advisory provider mode used")
    raw_input_snapshot: Dict[str, Any] = Field(..., description="Snapshot of all upstream input data")
    candidate_output: Optional[Dict[str, Any]] = Field(
        default=None, description="Candidate payload before guardrail evaluation"
    )
    guardrail_results: GuardrailStatusBlock = Field(..., description="Full guardrail verification results")
    final_status: AdvisoryStatus = Field(..., description="Final dispatched advisory status")
    final_advisory: Optional[Dict[str, Any]] = Field(
        default=None, description="Final structured advisory payload if not blocked"
    )
    duration_ms: float = Field(..., ge=0.0, description="Total end-to-end execution duration in ms")

    model_config = ConfigDict(extra="forbid", frozen=True)
