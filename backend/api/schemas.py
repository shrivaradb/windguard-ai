"""Pydantic v2 Unified API Schemas for WindGuard AI REST Service (Layer 6).

Source of Truth:
- docs/06_prd.md §7 (FR-001 through FR-013)
- docs/07_srs.md §3, §4
- docs/08_system_architecture.md §3.7
- docs/09_technical_design.md §2.6
- docs/10_data_architecture.md §3, §4
- docs/PHASE_6_SCOPE_REVIEW.md §8, §11
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6, §8

All schemas strictly enforce Pydantic v2 validation with extra="forbid" and frozen immutability where appropriate.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.data.schema import (
    BenchmarkScenarioType,
    GroundTruthLabel,
    OperatingStatus,
    TelemetryRecord,
    ValidationSummary,
)
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.loss_calculator import LossEligibility, RecordLossResult
from backend.engine.prioritization import PriorityScoreBreakdown, SeverityLevel
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.engine.tariff_registry import TariffMode, TariffProvenance
from backend.llm.schema import (
    AdvisoryStatus,
    AuditSnapshot,
    CitationItem,
    EvidenceItem,
    GuardrailStatusBlock,
    HypothesisItem,
    OperatorAdvisory,
    PlausibilityRating,
    RecommendedActionItem,
    ReviewStatus,
)
from backend.models.residual_engine import BaselineStats, ResidualVector
from backend.rag.schema import DocumentChunk, RetrievalMode, SourceType


# ==============================================================================
# 1. System Health & Readiness Schemas
# ==============================================================================

class HealthResponse(BaseModel):
    """System health check liveness response."""

    status: str = Field(..., description="Service health status ('healthy')")
    service: str = Field(..., description="Canonical service name")
    version: str = Field(..., description="Software release version")
    phase: int = Field(default=6, description="Active governance phase")
    uptime_seconds: float = Field(..., ge=0.0, description="Process uptime in seconds")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of check")

    model_config = ConfigDict(extra="forbid", frozen=True)


class SubsystemHealth(BaseModel):
    """Health indicator for an individual internal dependency."""

    name: str = Field(..., description="Subsystem identifier")
    ready: bool = Field(..., description="True if subsystem is operational")
    message: str = Field(..., description="Status message or failure reason")
    latency_ms: Optional[float] = Field(default=None, ge=0.0, description="Probe latency in ms")

    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadinessResponse(BaseModel):
    """Comprehensive readiness probe response."""

    ready: bool = Field(..., description="True if all critical subsystems are initialized")
    status: str = Field(..., description="'READY' or 'UNAVAILABLE'")
    phase: int = Field(default=6, description="Active governance phase")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")
    subsystems: Dict[str, SubsystemHealth] = Field(..., description="Status map of critical dependencies")

    model_config = ConfigDict(extra="forbid", frozen=True)


class SystemStatusResponse(BaseModel):
    """Detailed operational configuration and layer status summary."""

    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="Release version")
    host: str = Field(..., description="Server host interface binding")
    active_tariff: TariffProvenance = Field(..., description="Active electricity tariff configuration")
    model_version: str = Field(..., description="Layer 2 analytical model version")
    rag_corpus_version: str = Field(..., description="Layer 4 technical corpus version")
    total_indexed_chunks: int = Field(..., ge=0, description="Number of indexed RAG chunks")
    active_turbines_cached: int = Field(..., ge=0, description="Count of turbines with cached telemetry")
    total_cases_stored: int = Field(..., ge=0, description="Count of persisted maintenance cases")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 2. Fleet & Telemetry Query Schemas
# ==============================================================================

class FleetStatusResponse(BaseModel):
    """Aggregated operational health and financial overview across the active fleet."""

    total_turbines: int = Field(..., ge=0, description="Total active turbines monitored")
    active_turbines: List[str] = Field(..., description="List of active turbine identifiers")
    latest_timestamp: Optional[str] = Field(default=None, description="Most recent telemetry timestamp in cache")
    total_fleet_power_kw: float = Field(..., description="Sum of active power across fleet (kW)")
    average_wind_speed_mps: float = Field(..., ge=0.0, description="Average wind speed across fleet (m/s)")
    curtailed_turbines_count: int = Field(..., ge=0, description="Number of turbines under grid curtailment")
    active_anomalies_count: int = Field(..., ge=0, description="Number of turbines with active persistent anomalies")
    open_cases_count: int = Field(..., ge=0, description="Number of open/unresolved maintenance cases")
    critical_cases_count: int = Field(..., ge=0, description="Number of cases with CRITICAL severity")
    total_fleet_energy_loss_kwh: float = Field(default=0.0, ge=0.0, description="Cumulative eligible energy loss")
    total_fleet_financial_loss_inr: float = Field(default=0.0, ge=0.0, description="Cumulative financial loss (INR)")

    model_config = ConfigDict(extra="forbid", frozen=True)


class IngestRequest(BaseModel):
    """Payload for direct JSON telemetry batch ingestion."""

    records: List[Dict[str, Any]] = Field(..., description="List of raw or formatted telemetry dictionaries")

    model_config = ConfigDict(extra="forbid")


class IngestResponse(BaseModel):
    """Response payload after processing telemetry ingestion."""

    status: str = Field(..., description="'success' or 'rejected'")
    summary: ValidationSummary = Field(..., description="Data cleaning and validation summary")
    ingested_count: int = Field(..., ge=0, description="Number of valid accepted records cached")
    message: str = Field(..., description="Human-readable status summary")

    model_config = ConfigDict(extra="forbid", frozen=True)


class ScenarioCatalogItem(BaseModel):
    """Metadata describing an available benchmark simulation scenario."""

    scenario_id: BenchmarkScenarioType = Field(..., description="Scenario identifier enum")
    name: str = Field(..., description="Scenario display name")
    category: str = Field(..., description="Operational domain category")
    description: str = Field(..., description="Detailed physical scenario description")
    injected_subsystem: Optional[str] = Field(default=None, description="Injected fault subsystem label")
    is_fault: bool = Field(..., description="True if scenario represents equipment failure")

    model_config = ConfigDict(extra="forbid", frozen=True)


class SimulateResponse(BaseModel):
    """Response payload after executing a physics-informed simulation run."""

    status: str = Field(..., description="Simulation execution status")
    scenario: BenchmarkScenarioType = Field(..., description="Executed benchmark scenario")
    total_records: int = Field(..., ge=1, description="Total telemetry records generated")
    ground_truth: GroundTruthLabel = Field(..., description="Ground-truth labeling metadata")
    generated_at: str = Field(..., description="ISO-8601 generation timestamp")
    persisted_file: Optional[str] = Field(default=None, description="Synthetic output filename")
    sample_records: List[TelemetryRecord] = Field(..., description="Sample initial records")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 3. Layer 2 ML Model Schemas
# ==============================================================================

class ModelStatusResponse(BaseModel):
    """Operational status and configuration of Layer 2 analytical baselines."""

    is_trained: bool = Field(default=True, description="True if model artifacts are loaded")
    model_version: str = Field(default="1.0.0", description="Model artifact release version")
    power_algorithm: str = Field(default="GradientBoostingRegressor", description="Power curve algorithm")
    thermal_algorithm: str = Field(default="RandomForestRegressor", description="Thermal model algorithm")
    baseline_stats: BaselineStats = Field(..., description="Calibrated residual baseline statistics")
    persistence_threshold_sigma: float = Field(..., description="Statistical persistence sigma cutoff")
    persistence_window_steps: int = Field(..., description="Sliding persistence window length")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 4. Human-in-the-Loop (HITL) Decision Schemas
# ==============================================================================

class HITLAction(str, Enum):
    """Canonical Operator Human-in-the-Loop Review Actions."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    INVESTIGATE = "INVESTIGATE"
    ESCALATE = "ESCALATE"
    DISMISS = "DISMISS"


class CaseStatus(str, Enum):
    """Authoritative Maintenance Case Lifecycle States."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    DISMISSED = "DISMISSED"


class OperatorDecision(BaseModel):
    """Immutable Human-in-the-Loop Operator Action Record."""

    decision_id: str = Field(..., description="Unique decision audit identifier")
    action: HITLAction = Field(..., description="Recorded human review action")
    operator_id: str = Field(default="OPERATOR_LOCAL", description="Attributed operator or reviewer identity")
    timestamp: str = Field(..., description="ISO-8601 timestamp of decision")
    notes: str = Field(..., min_length=1, max_length=2000, description="Mandatory operator engineering notes")

    model_config = ConfigDict(extra="forbid", frozen=True)


class OperatorDecisionRequest(BaseModel):
    """Request payload for logging an operator triage action on a case."""

    action: HITLAction = Field(..., description="Triage action ('ACKNOWLEDGE', 'INVESTIGATE', 'ESCALATE', 'DISMISS')")
    operator_id: Optional[str] = Field(default="OPERATOR_LOCAL", max_length=64, description="Operator username or badge ID")
    notes: str = Field(..., min_length=1, max_length=2000, description="Required rationale or site work order notes")
    timestamp: Optional[str] = Field(default=None, description="Optional client ISO timestamp")

    model_config = ConfigDict(extra="forbid")


# ==============================================================================
# 5. Authoritative Maintenance Case Schemas
# ==============================================================================

class SourceTelemetrySummary(BaseModel):
    """Summary of authoritative source telemetry evaluated in diagnostic case."""

    timestamp: str = Field(..., description="SCADA observation timestamp")
    turbine_id: str = Field(..., description="Turbine identifier")
    wind_speed: float = Field(..., description="Observed wind speed (m/s)")
    active_power: float = Field(..., description="Observed active power (kW)")
    ambient_temp: float = Field(..., description="Observed ambient temperature (°C)")
    gearbox_bearing_temp: float = Field(..., description="Observed gearbox bearing temperature (°C)")
    generator_stator_temp: float = Field(..., description="Observed generator stator temperature (°C)")
    pitch_angle: float = Field(..., description="Observed blade pitch angle (°)")
    rotor_speed: float = Field(..., description="Observed rotor speed (RPM)")
    is_curtailed: bool = Field(..., description="Observed grid curtailment flag")
    operating_status: OperatingStatus = Field(default=OperatingStatus.RUNNING, description="Turbine state")
    source_provenance: str = Field(default="SOURCE_AUTHENTIC", description="Data provenance classification")

    model_config = ConfigDict(extra="forbid", frozen=True)


class DerivedAnalyticsSummary(BaseModel):
    """Summary of deterministic Phase 2 & Phase 3 analytical outputs."""

    expected_power_kw: float = Field(..., description="Expected healthy power output (kW)")
    residual_power_kw: float = Field(..., description="Power deficit residual (kW)")
    z_power: float = Field(..., description="Standardized power z-score")
    expected_gb_temp_c: float = Field(..., description="Expected gearbox bearing temperature (°C)")
    residual_gb_temp_c: float = Field(..., description="Gearbox thermal residual (°C)")
    z_gb: float = Field(..., description="Standardized gearbox temperature z-score")
    expected_gen_temp_c: float = Field(..., description="Expected generator stator temperature (°C)")
    residual_gen_temp_c: float = Field(..., description="Generator thermal residual (°C)")
    z_gen: float = Field(..., description="Standardized generator temperature z-score")
    context_state: OperationalContextState = Field(..., description="Phase 3 operational context classification")
    is_context_suppressed: bool = Field(..., description="True if alarm was suppressed by context engine")
    subsystem_attribution: SubsystemLabel = Field(..., description="Phase 3 isolated faulty subsystem")
    attribution_confidence: float = Field(..., ge=0.0, le=1.0, description="Heuristic rule confidence")
    energy_loss_kwh: float = Field(..., ge=0.0, description="Eligible degradation energy loss (kWh)")
    financial_loss_inr: float = Field(..., ge=0.0, description="Eligible maintenance financial loss (INR)")
    tariff_provenance: TariffProvenance = Field(..., description="Active tariff rate and provenance applied")
    priority_score: float = Field(..., ge=0.0, le=100.0, description="0-100 Multi-criteria priority score")
    severity: SeverityLevel = Field(..., description="Categorical severity classification tier")
    priority_breakdown: PriorityScoreBreakdown = Field(..., description="Detailed 5-factor priority score breakdown")

    model_config = ConfigDict(extra="forbid", frozen=True)


class MaintenanceCase(BaseModel):
    """Complete Authoritative Maintenance Diagnostic Case.

    Encapsulates source telemetry, derived deterministic analytics, technical evidence,
    synthesized advisory recommendations, guardrail verification block, and append-only HITL audit history.
    """

    case_id: str = Field(..., description="Unique case identifier (e.g. CASE-WTG07-20260920-UUID)")
    turbine_id: str = Field(..., description="Turbine identifier (e.g. WTG-07)")
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp")
    status: CaseStatus = Field(default=CaseStatus.OPEN, description="Active case review lifecycle status")
    severity: SeverityLevel = Field(..., description="Overall severity tier")
    priority_score: float = Field(..., ge=0.0, le=100.0, description="0-100 priority score")
    source_telemetry: SourceTelemetrySummary = Field(..., description="Authoritative observed SCADA inputs")
    derived_analytics: DerivedAnalyticsSummary = Field(..., description="Deterministic ML & context outputs")
    evidence_table: List[EvidenceItem] = Field(default_factory=list, description="Grounding evidence items")
    citations: List[CitationItem] = Field(default_factory=list, description="Verified technical RAG citations")
    advisory: OperatorAdvisory = Field(..., description="Synthesized and guardrail-verified advisory")
    guardrails: GuardrailStatusBlock = Field(..., description="Independent guardrail verification audit")
    review_status: ReviewStatus = Field(..., description="Human review escalation requirement")
    operator_decisions: List[OperatorDecision] = Field(default_factory=list, description="Append-only HITL decision history")
    schema_version: str = Field(default="1.0.0", description="Case schema version")

    model_config = ConfigDict(extra="forbid")


class DiagnoseRequest(BaseModel):
    """Payload for executing an end-to-end diagnostic evaluation."""

    telemetry_record: Optional[TelemetryRecord] = Field(
        default=None,
        description="Optional direct telemetry record. If omitted, uses latest cached record for turbine.",
    )
    force_recompute: bool = Field(
        default=False,
        description="If True, executes fresh evaluation even if identical timestamp was previously diagnosed.",
    )
    custom_notes: Optional[str] = Field(default=None, max_length=500, description="Optional diagnostic request context")

    model_config = ConfigDict(extra="forbid")


class PaginatedCasesResponse(BaseModel):
    """Paginated list of maintenance cases."""

    total_count: int = Field(..., ge=0, description="Total matching cases in store")
    limit: int = Field(..., ge=1, le=100, description="Maximum cases requested")
    offset: int = Field(..., ge=0, description="Pagination offset")
    cases: List[MaintenanceCase] = Field(..., description="Array of matching maintenance cases")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 6. Tariff Registry API Schemas
# ==============================================================================

class TariffUpdateRequest(BaseModel):
    """Payload for updating active electricity tariff configuration."""

    rate_inr_per_kwh: float = Field(
        ...,
        ge=0.01,
        le=20.0,
        description="New electricity tariff rate in INR/kWh (Bounded: ₹0.01 - ₹20.00/kWh)",
    )
    mode: TariffMode = Field(..., description="Tariff mode ('PROJECT_PPA', 'REGULATORY_BENCHMARK', 'CONFIGURED_BASELINE', 'SCENARIO_OVERRIDE')")
    source_reference: str = Field(..., min_length=1, max_length=256, description="Contract order, PPA ID, or regulatory reference")
    effective_date: Optional[str] = Field(default=None, description="Optional effective date string")
    notes: Optional[str] = Field(default=None, max_length=500, description="Optional engineering/audit notes")

    model_config = ConfigDict(extra="forbid")


class TariffRegistryResponse(BaseModel):
    """Active tariff configuration and historical provenance records."""

    active_tariff: TariffProvenance = Field(..., description="Currently active electricity tariff")
    available_modes: List[str] = Field(..., description="Supported tariff mode classifications")
    history_count: int = Field(..., ge=1, description="Total logged tariff configuration updates")
    history: List[TariffProvenance] = Field(..., description="Immutable chronological history of tariff configurations")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 7. Layer 4 Technical Knowledge (RAG) Schemas
# ==============================================================================

class RAGQueryRequest(BaseModel):
    """Request payload for searching the technical knowledge base."""

    query: str = Field(..., min_length=1, max_length=500, description="Natural language or fault signature query")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of top-ranked document chunks to retrieve")
    mode: RetrievalMode = Field(default=RetrievalMode.HYBRID_LOCAL, description="Requested retrieval mode")

    model_config = ConfigDict(extra="forbid")


class RAGQueryResponse(BaseModel):
    """Structured response containing ranked technical citations with SHA-256 provenance."""

    query: str = Field(..., description="Original input query")
    top_k: int = Field(..., ge=1, le=10, description="Requested top-k ranking count")
    retrieval_mode: RetrievalMode = Field(..., description="Executed retrieval mode (with fallback if triggered)")
    corpus_version: str = Field(..., description="Technical document corpus version")
    chunks: List[DocumentChunk] = Field(..., description="Ranked technical document chunks")
    scores: List[float] = Field(..., description="Relevance similarity scores")
    query_latency_ms: float = Field(..., ge=0.0, description="Query execution latency in ms")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 8. Demo Stepper Schemas
# ==============================================================================

class DemoStageResponse(BaseModel):
    """Pre-configured telemetry and ground-truth state for 10-stage interactive demonstration."""

    stage_id: int = Field(..., ge=1, le=10, description="Demo stage number (1 to 10)")
    stage_name: str = Field(..., description="Demonstration scenario title")
    scenario_type: str = Field(..., description="Benchmark scenario category")
    description: str = Field(..., description="Engineering explanation of stage state")
    telemetry: TelemetryRecord = Field(..., description="Deterministic telemetry record for stage")
    expected_status: str = Field(..., description="Expected operational / alarm status")
    injected_fault: Optional[str] = Field(default=None, description="Fault description if applicable")

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==============================================================================
# 9. Standardized Error Envelopes
# ==============================================================================

class StandardErrorEnvelope(BaseModel):
    """Standardized deterministic machine-readable API error response."""

    error_code: str = Field(..., description="Standardized error category code (e.g. ERR_RESOURCE_NOT_FOUND)")
    message: str = Field(..., description="Safe, sanitized operator-facing message")
    timestamp: str = Field(..., description="ISO-8601 UTC error timestamp")
    request_id: str = Field(..., description="Unique request tracing identifier")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Structured contextual error details")

    model_config = ConfigDict(extra="forbid", frozen=True)
