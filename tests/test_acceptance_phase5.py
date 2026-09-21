"""Phase 5 Formal Acceptance Test Suite (SCEN-01 to SCEN-20).

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011, FR-012, NFR-001, NFR-004)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/PHASE_5_SCOPE_REVIEW.md §11
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §11
"""

import time
import pytest

from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.loss_calculator import LossEligibility, RecordLossResult
from backend.engine.prioritization import PriorityScoreBreakdown, SeverityLevel
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.engine.tariff_registry import TariffMode, TariffProvenance
from backend.llm.advisory_engine import AdvisoryEngine
from backend.llm.fallback import LocalTemplateSynthesizer
from backend.llm.guardrails import GuardrailValidator
from backend.llm.prompts import MANDATORY_SAFETY_DISCLAIMER
from backend.llm.providers import BaseAdvisoryProvider
from backend.llm.schema import (
    AdvisoryStatus,
    CitationItem,
    EvidenceType,
    GuardrailVerdict,
    OperatorAdvisory,
    ReviewStatus,
    SourceType,
)
from backend.models.residual_engine import ResidualVector
from backend.rag.schema import ContentType, DocumentChunk, RetrievalMode, RetrievalResult


# Helper fixtures & providers
class CustomPayloadProvider(BaseAdvisoryProvider):
    def __init__(self, payload_dict: dict, mode: str = "MODE_CUSTOM"):
        self.payload = payload_dict
        self._mode = mode

    @property
    def provider_mode(self) -> str:
        return self._mode

    def generate_candidate(self, prompt_context_xml: str, structured_context: dict) -> dict:
        return self.payload


class TimeoutMockProvider(BaseAdvisoryProvider):
    @property
    def provider_mode(self) -> str:
        return "MODE_TIMEOUT_MOCK"

    def generate_candidate(self, prompt_context_xml: str, structured_context: dict) -> dict:
        raise TimeoutError("LLM invocation timed out after 5000 ms limit")


@pytest.fixture
def engine():
    return AdvisoryEngine()


def make_provenance(rate: float = 4.50) -> TariffProvenance:
    return TariffProvenance(
        applied_rate_inr_per_kwh=rate,
        mode=TariffMode.CONFIGURED_BASELINE,
        source_reference="BENCHMARK_TARIFF_ORDER",
        effective_date="2026-01-01",
        is_baseline_assumption=True,
    )


def make_chunk(
    chunk_id: str = "CHK-001",
    source_id: str = "SRC-001",
    source_type: SourceType = SourceType.SOURCE_AUTHENTIC,
    title: str = "OEM Manual",
    locator: str = "Sec 1.0",
    content: str = "Sample technical text",
    content_hash: str = "hash123",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_title=title,
        document_filename="doc.md",
        source_id=source_id,
        source_type=source_type,
        publisher="WindOEM",
        publication_date="2023-01-01",
        chapter="Ch 1",
        section="Sec 1",
        source_locator=locator,
        content=content,
        content_type=ContentType.VERBATIM_SOURCE,
        token_count=10,
        content_hash=content_hash,
        provenance_status="VERIFIED",
    )


# -----------------------------------------------------------------------------
# SCEN-01: Healthy Baseline Operation (S1)
# -----------------------------------------------------------------------------
def test_scen_01_healthy_baseline_operation(engine):
    tel = TelemetryRecord(
        timestamp="2026-01-01T00:00:00Z",
        turbine_id="WTG01",
        wind_speed=9.0,
        wind_direction=180.0,
        ambient_temp=20.0,
        active_power=1600.0,
        reactive_power=50.0,
        rotor_speed=13.5,
        generator_speed=1380.0,
        gearbox_bearing_temp=65.0,
        generator_stator_temp=65.0,
        nacelle_temp=25.0,
        pitch_angle=0.0,
        operating_status=OperatingStatus.RUNNING,
    )
    res = ResidualVector(
        expected_power_kw=1600.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=65.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    ctx = ContextResult(state=OperationalContextState.NORMAL, is_suppressed=False, explanation="Normal", precedence_level=5)
    attr = AttributionResult(
        subsystem=SubsystemLabel.NORMAL_OPERATION,
        rule_confidence=1.0,
        is_persistent=False,
        excursion_count=0,
        window_size=6,
        matched_rule="RULE-NOMINAL",
        explanation="Nominal operation",
    )
    loss = RecordLossResult(
        power_expected_kw=1600.0,
        power_actual_kw=1600.0,
        power_deficit_kw=0.0,
        energy_deficit_kwh=0.0,
        eligibility=LossEligibility.NOMINAL_NO_DEFICIT,
        eligible_degradation_energy_kwh=0.0,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=0.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.0, s_pers=0.0, s_conf=0.0, s_crit=0.0, s_loss=0.0, priority_score=0.0, severity=SeverityLevel.LOW)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-01",
        turbine_id="WTG01",
        telemetry=tel,
        residuals=res,
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
    )

    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.loss_summary_inr == 0.0
    assert advisory.priority_score == 0.0
    assert advisory.primary_attribution == "NORMAL_OPERATION"
    assert advisory.review_status == ReviewStatus.AUTOMATIC
    assert any("nominal" in h.hypothesis.lower() or "normal" in h.hypothesis.lower() for h in advisory.hypotheses)


# -----------------------------------------------------------------------------
# SCEN-02: Gearbox Bearing Fault (S2)
# -----------------------------------------------------------------------------
def test_scen_02_gearbox_bearing_fault(engine):
    chunk = make_chunk(chunk_id="CHK-GB-01", source_id="SRC-GB-01", title="Gearbox Service Manual")
    rag = RetrievalResult(query="gearbox", top_k=1, retrieval_mode=RetrievalMode.HYBRID_LOCAL, chunks=[chunk], scores=[0.95], query_latency_ms=1.0)
    ctx = ContextResult(state=OperationalContextState.NORMAL, is_suppressed=False, explanation="Normal", precedence_level=5)
    attr = AttributionResult(
        subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
        rule_confidence=0.92,
        is_persistent=True,
        matched_rule="RULE-GB-01",
        explanation="Thermal rise",
    )
    loss = RecordLossResult(
        power_expected_kw=1500.0,
        power_actual_kw=1450.0,
        power_deficit_kw=50.0,
        energy_deficit_kwh=8.33,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=8.33,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=37.50,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.8, s_pers=0.8, s_conf=0.9, s_crit=0.9, s_loss=0.2, priority_score=75.0, severity=SeverityLevel.HIGH)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-02",
        turbine_id="WTG01",
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
        rag_result=rag,
    )

    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.primary_attribution == "DRIVETRAIN_GEARBOX"
    assert len(advisory.citations) == 1
    assert advisory.citations[0].source_id == "SRC-GB-01"
    assert "gearbox" in advisory.summary.lower()


# -----------------------------------------------------------------------------
# SCEN-03: Generator Overheating Fault
# -----------------------------------------------------------------------------
def test_scen_03_generator_overheating_fault(engine):
    chunk = make_chunk(chunk_id="CHK-GEN-01", source_id="SRC-GEN-01", title="Generator Manual")
    rag = RetrievalResult(query="generator", top_k=1, retrieval_mode=RetrievalMode.HYBRID_LOCAL, chunks=[chunk], scores=[0.88], query_latency_ms=1.0)
    ctx = ContextResult(state=OperationalContextState.NORMAL, is_suppressed=False, explanation="Normal", precedence_level=5)
    attr = AttributionResult(
        subsystem=SubsystemLabel.GENERATOR_COOLING,
        rule_confidence=0.88,
        is_persistent=True,
        matched_rule="RULE-GEN-01",
        explanation="Stator overheating",
    )
    loss = RecordLossResult(
        power_expected_kw=1500.0,
        power_actual_kw=1400.0,
        power_deficit_kw=100.0,
        energy_deficit_kwh=16.67,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=16.67,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=75.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.8, s_pers=0.8, s_conf=0.85, s_crit=0.85, s_loss=0.3, priority_score=72.0, severity=SeverityLevel.HIGH)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-03",
        turbine_id="WTG02",
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
        rag_result=rag,
    )

    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.primary_attribution == "GENERATOR_COOLING"
    assert any("generator" in h.hypothesis.lower() or "cooling" in h.hypothesis.lower() for h in advisory.hypotheses)


# -----------------------------------------------------------------------------
# SCEN-04: Pitch Asymmetry Fault (S3)
# -----------------------------------------------------------------------------
def test_scen_04_pitch_asymmetry_fault(engine):
    chunk = make_chunk(chunk_id="CHK-PIT-01", source_id="SRC-PIT-01", title="Pitch System Manual")
    rag = RetrievalResult(query="pitch", top_k=1, retrieval_mode=RetrievalMode.HYBRID_LOCAL, chunks=[chunk], scores=[0.90], query_latency_ms=1.0)
    ctx = ContextResult(state=OperationalContextState.NORMAL, is_suppressed=False, explanation="Normal", precedence_level=5)
    attr = AttributionResult(
        subsystem=SubsystemLabel.AERODYNAMIC_PITCH,
        rule_confidence=0.95,
        is_persistent=True,
        matched_rule="RULE-PITCH-01",
        explanation="Aerodynamic deficit",
    )
    loss = RecordLossResult(
        power_expected_kw=1800.0,
        power_actual_kw=1400.0,
        power_deficit_kw=400.0,
        energy_deficit_kwh=66.67,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=66.67,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=300.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.7, s_pers=0.9, s_conf=0.95, s_crit=0.7, s_loss=0.4, priority_score=74.0, severity=SeverityLevel.HIGH)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-04",
        turbine_id="WTG03",
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
        rag_result=rag,
    )

    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.primary_attribution == "AERODYNAMIC_PITCH"
    assert "pitch" in advisory.summary.lower() or "aerodynamic" in advisory.summary.lower()


# -----------------------------------------------------------------------------
# SCEN-05: Grid Curtailment Case (S4)
# -----------------------------------------------------------------------------
def test_scen_05_grid_curtailment_case(engine):
    ctx = ContextResult(state=OperationalContextState.CURTAILED, is_suppressed=True, explanation="Curtailment active", precedence_level=2)
    attr = AttributionResult(
        subsystem=SubsystemLabel.GRID_CURTAILMENT,
        rule_confidence=1.0,
        is_persistent=True,
        matched_rule="RULE-CURTAIL-01",
        explanation="Grid curtailment setpoint",
    )
    loss = RecordLossResult(
        power_expected_kw=1800.0,
        power_actual_kw=1000.0,
        power_deficit_kw=800.0,
        energy_deficit_kwh=133.33,
        eligibility=LossEligibility.CURTAILED_CAPACITY,
        eligible_degradation_energy_kwh=0.0,
        curtailed_capacity_kwh=133.33,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=0.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.0, s_pers=0.5, s_conf=1.0, s_crit=0.0, s_loss=0.0, priority_score=30.0, severity=SeverityLevel.LOW)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-05",
        turbine_id="WTG04",
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
    )

    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.context_classification == "CURTAILED"
    assert advisory.loss_summary_inr == 0.0
    assert "curtailment" in advisory.summary.lower()


# -----------------------------------------------------------------------------
# SCEN-06: Low-Wind Idling Case
# -----------------------------------------------------------------------------
def test_scen_06_low_wind_idling_case(engine):
    ctx = ContextResult(state=OperationalContextState.LOW_WIND_IDLE, is_suppressed=True, explanation="Wind speed < 3.0 m/s", precedence_level=3)
    attr = AttributionResult(
        subsystem=SubsystemLabel.NORMAL_OPERATION,
        rule_confidence=1.0,
        is_persistent=False,
        matched_rule="RULE-LOWWIND",
        explanation="Idling below cut-in",
    )
    loss = RecordLossResult(
        power_expected_kw=0.0,
        power_actual_kw=0.0,
        power_deficit_kw=0.0,
        energy_deficit_kwh=0.0,
        eligibility=LossEligibility.LOW_WIND_IDLE,
        eligible_degradation_energy_kwh=0.0,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=0.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.0, s_pers=0.0, s_conf=1.0, s_crit=0.0, s_loss=0.0, priority_score=0.0, severity=SeverityLevel.LOW)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-06",
        turbine_id="WTG05",
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
    )

    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.context_classification == "LOW_WIND_IDLE"
    assert "idling" in advisory.summary.lower() or "low-wind" in advisory.summary.lower()


# -----------------------------------------------------------------------------
# SCEN-07: Sensor Dropout Case (S5)
# -----------------------------------------------------------------------------
def test_scen_07_sensor_dropout_case(engine):
    ctx = ContextResult(state=OperationalContextState.SENSOR_ANOMALY, is_suppressed=True, explanation="Sensor dropout", precedence_level=1)
    attr = AttributionResult(
        subsystem=SubsystemLabel.SENSOR_ANOMALY,
        rule_confidence=1.0,
        is_persistent=False,
        matched_rule="RULE-SENSOR-01",
        explanation="Thermocouple dropout",
    )
    loss = RecordLossResult(
        power_expected_kw=1500.0,
        power_actual_kw=1500.0,
        power_deficit_kw=0.0,
        energy_deficit_kwh=0.0,
        eligibility=LossEligibility.EXCLUDED_SENSOR_ERROR,
        eligible_degradation_energy_kwh=0.0,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=0.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.0, s_pers=0.0, s_conf=1.0, s_crit=0.0, s_loss=0.0, priority_score=20.0, severity=SeverityLevel.LOW)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-07",
        turbine_id="WTG06",
        context=ctx,
        attribution=attr,
        loss=loss,
        priority=prio,
        is_abstention=True,
        abstention_reason="Sensor dropout detected on gearbox thermocouple",
    )

    assert advisory.status == AdvisoryStatus.ABSTENTION
    assert advisory.abstention_reason is not None
    assert advisory.missing_evidence_summary is not None
    assert "abstention" in advisory.summary.lower() or "sensor dropout" in advisory.summary.lower()


# -----------------------------------------------------------------------------
# SCEN-08: Insufficient Evidence Case
# -----------------------------------------------------------------------------
def test_scen_08_insufficient_evidence_case(engine):
    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-08",
        turbine_id="WTG07",
        is_abstention=True,
        abstention_reason="0 matching technical chunks retrieved and telemetry variance high",
    )
    assert advisory.status == AdvisoryStatus.ABSTENTION
    assert advisory.abstention_reason is not None


# -----------------------------------------------------------------------------
# SCEN-09: Conflicting Evidence Case
# -----------------------------------------------------------------------------
def test_scen_09_conflicting_evidence_case(engine):
    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-09",
        turbine_id="WTG08",
        conflicting_signals=True,
    )
    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert "conflicting" in advisory.summary.lower()
    assert len(advisory.hypotheses) > 0
    assert len(advisory.hypotheses[0].missing_evidence) > 0


# -----------------------------------------------------------------------------
# SCEN-10: Missing / Empty RAG Result
# -----------------------------------------------------------------------------
def test_scen_10_missing_empty_rag_result(engine):
    empty_rag = RetrievalResult(
        query="nonexistent query",
        top_k=3,
        retrieval_mode=RetrievalMode.HYBRID_LOCAL,
        chunks=[],
        scores=[],
        query_latency_ms=0.5,
    )
    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-10",
        turbine_id="WTG09",
        rag_result=empty_rag,
    )
    assert advisory.status in [AdvisoryStatus.NORMAL_ADVISORY, AdvisoryStatus.ABSTENTION]
    assert len(advisory.citations) == 0


# -----------------------------------------------------------------------------
# SCEN-11: Synthetic-Source Citation
# -----------------------------------------------------------------------------
def test_scen_11_synthetic_source_citation(engine):
    synth_chunk = make_chunk(
        chunk_id="CHK-SYN-01",
        source_id="SRC-SYN-01",
        source_type=SourceType.PROJECT_SYNTHETIC,
        title="Synthetic Test Playbook",
    )
    rag = RetrievalResult(
        query="synthetic test",
        top_k=1,
        retrieval_mode=RetrievalMode.HYBRID_LOCAL,
        chunks=[synth_chunk],
        scores=[0.90],
        query_latency_ms=1.0,
    )
    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-11",
        turbine_id="WTG10",
        rag_result=rag,
    )
    assert len(advisory.citations) == 1
    assert advisory.citations[0].source_type == SourceType.PROJECT_SYNTHETIC


# -----------------------------------------------------------------------------
# SCEN-12: Unverified Source Rejection
# -----------------------------------------------------------------------------
def test_scen_12_unverified_source_rejection(engine):
    unverified_chunk = make_chunk(
        chunk_id="CHK-UNV-01",
        source_id="SRC-UNV-01",
        source_type=SourceType.UNVERIFIED,
        title="Unverified Forum Post",
    )
    rag = RetrievalResult(
        query="unverified",
        top_k=1,
        retrieval_mode=RetrievalMode.HYBRID_LOCAL,
        chunks=[unverified_chunk],
        scores=[0.95],
        query_latency_ms=1.0,
    )
    candidate = {
        "case_id": "CASE-SCEN-12",
        "timestamp": "2026-01-01T00:00:00Z",
        "turbine_id": "WTG11",
        "status": AdvisoryStatus.NORMAL_ADVISORY.value,
        "primary_attribution": "DRIVETRAIN_GEARBOX",
        "context_classification": "NORMAL",
        "summary": "Valid summary",
        "evidence_synthesis": [],
        "hypotheses": [],
        "recommended_actions": [],
        "citations": [
            {
                "source_id": "SRC-UNV-01",
                "source_type": SourceType.UNVERIFIED.value,
                "title": "Unverified Forum Post",
                "content_hash": "hash123",
                "relevance_score": 0.95,
            }
        ],
        "loss_summary_inr": 0.0,
        "energy_loss_kwh": 0.0,
        "priority_score": 0.0,
        "review_status": ReviewStatus.AUTOMATIC.value,
        "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
    }
    provider = CustomPayloadProvider(candidate)
    advisory, snapshot = engine.generate_advisory(
        case_id="CASE-SCEN-12",
        turbine_id="WTG11",
        rag_result=rag,
        custom_provider=provider,
    )
    assert advisory.status == AdvisoryStatus.FALLBACK_ADVISORY
    assert snapshot.guardrail_results.verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert snapshot.guardrail_results.citation_whitelist_valid is False


# -----------------------------------------------------------------------------
# SCEN-13: Unsupported Claim Injection
# -----------------------------------------------------------------------------
def test_scen_13_unsupported_claim_injection(engine):
    # Candidate asserts wrong attribution not supported by upstream
    candidate = {
        "case_id": "CASE-SCEN-13",
        "timestamp": "2026-01-01T00:00:00Z",
        "turbine_id": "WTG12",
        "status": AdvisoryStatus.NORMAL_ADVISORY.value,
        "primary_attribution": "GENERATOR_COOLING",  # Upstream is DRIVETRAIN_GEARBOX
        "context_classification": "NORMAL",
        "summary": "Unsupported generator cooling failure claim.",
        "evidence_synthesis": [],
        "hypotheses": [],
        "recommended_actions": [],
        "citations": [],
        "loss_summary_inr": 0.0,
        "energy_loss_kwh": 0.0,
        "priority_score": 0.0,
        "review_status": ReviewStatus.AUTOMATIC.value,
        "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
    }
    attr = AttributionResult(
        subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
        rule_confidence=0.9,
        is_persistent=True,
        matched_rule="RULE-GB-01",
        explanation="Gearbox fault",
    )
    provider = CustomPayloadProvider(candidate)
    advisory, snapshot = engine.generate_advisory(
        case_id="CASE-SCEN-13",
        turbine_id="WTG12",
        attribution=attr,
        custom_provider=provider,
    )
    assert snapshot.guardrail_results.attribution_consistency_valid is False
    assert snapshot.guardrail_results.verdict == GuardrailVerdict.FLAGGED


# -----------------------------------------------------------------------------
# SCEN-14: Prohibited Control Command
# -----------------------------------------------------------------------------
def test_scen_14_prohibited_control_command(engine):
    candidate = {
        "case_id": "CASE-SCEN-14",
        "timestamp": "2026-01-01T00:00:00Z",
        "turbine_id": "WTG13",
        "status": AdvisoryStatus.NORMAL_ADVISORY.value,
        "primary_attribution": "DRIVETRAIN_GEARBOX",
        "context_classification": "NORMAL",
        "summary": "Remediation: Issue control command to adjust pitch by 5 degrees.",
        "evidence_synthesis": [],
        "hypotheses": [],
        "recommended_actions": [],
        "citations": [],
        "loss_summary_inr": 0.0,
        "energy_loss_kwh": 0.0,
        "priority_score": 0.0,
        "review_status": ReviewStatus.AUTOMATIC.value,
        "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
    }
    provider = CustomPayloadProvider(candidate)
    advisory, snapshot = engine.generate_advisory(
        case_id="CASE-SCEN-14",
        turbine_id="WTG13",
        custom_provider=provider,
    )
    assert advisory.status == AdvisoryStatus.BLOCKED_OUTPUT
    assert snapshot.guardrail_results.verdict == GuardrailVerdict.BLOCKED
    assert snapshot.guardrail_results.lexicon_scan_passed is False


# -----------------------------------------------------------------------------
# SCEN-15: Malformed JSON Output
# -----------------------------------------------------------------------------
def test_scen_15_malformed_json_output(engine):
    candidate = {"corrupted_schema": True}
    provider = CustomPayloadProvider(candidate)
    advisory, snapshot = engine.generate_advisory(
        case_id="CASE-SCEN-15",
        turbine_id="WTG14",
        custom_provider=provider,
    )
    assert advisory.status == AdvisoryStatus.FALLBACK_ADVISORY
    assert snapshot.guardrail_results.schema_valid is False
    assert snapshot.guardrail_results.verdict == GuardrailVerdict.FALLBACK_APPLIED


# -----------------------------------------------------------------------------
# SCEN-16: Numerical Value Drift
# -----------------------------------------------------------------------------
def test_scen_16_numerical_value_drift(engine):
    loss = RecordLossResult(
        power_expected_kw=1500.0,
        power_actual_kw=1400.0,
        power_deficit_kw=100.0,
        energy_deficit_kwh=16.67,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=16.67,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=75.0,  # Authoritative = 75.0
        tariff_provenance=make_provenance(4.50),
    )
    candidate = {
        "case_id": "CASE-SCEN-16",
        "timestamp": "2026-01-01T00:00:00Z",
        "turbine_id": "WTG15",
        "status": AdvisoryStatus.NORMAL_ADVISORY.value,
        "primary_attribution": "NORMAL_OPERATION",
        "context_classification": "NORMAL",
        "summary": "Valid summary",
        "evidence_synthesis": [],
        "hypotheses": [],
        "recommended_actions": [],
        "citations": [],
        "loss_summary_inr": 85.0,  # Altered numerical value (+10.0 drift)
        "energy_loss_kwh": 16.67,
        "priority_score": 0.0,
        "review_status": ReviewStatus.AUTOMATIC.value,
        "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
    }
    provider = CustomPayloadProvider(candidate)
    advisory, snapshot = engine.generate_advisory(
        case_id="CASE-SCEN-16",
        turbine_id="WTG15",
        loss=loss,
        custom_provider=provider,
    )
    assert advisory.status == AdvisoryStatus.FALLBACK_ADVISORY
    assert advisory.loss_summary_inr == 75.0  # Fallback restores authoritative 75.0
    assert snapshot.guardrail_results.numerical_consistency_valid is False


# -----------------------------------------------------------------------------
# SCEN-17: Guardrail Action Routing
# -----------------------------------------------------------------------------
def test_scen_17_guardrail_action_routing(engine):
    validator = GuardrailValidator(numerical_tolerance=0.01)
    upstream = {"financial_loss_inr": 10.0, "energy_loss_kwh": 2.0, "priority_score": 10.0}

    # PASS case
    c_pass = {
        "case_id": "C1",
        "timestamp": "2026-01-01T00:00:00Z",
        "turbine_id": "WTG01",
        "status": AdvisoryStatus.NORMAL_ADVISORY.value,
        "primary_attribution": "NORMAL_OPERATION",
        "context_classification": "NORMAL",
        "summary": "Normal",
        "evidence_synthesis": [],
        "hypotheses": [],
        "recommended_actions": [],
        "citations": [],
        "loss_summary_inr": 10.0,
        "energy_loss_kwh": 2.0,
        "priority_score": 10.0,
        "review_status": ReviewStatus.AUTOMATIC.value,
        "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
    }
    v_pass, _, _ = validator.validate_candidate(c_pass, upstream)
    assert v_pass == GuardrailVerdict.PASS

    # FALLBACK case
    c_fallback = dict(c_pass)
    c_fallback["loss_summary_inr"] = 999.0
    v_fb, _, _ = validator.validate_candidate(c_fallback, upstream)
    assert v_fb == GuardrailVerdict.FALLBACK_APPLIED

    # BLOCKED case
    c_block = dict(c_pass)
    c_block["summary"] = "Adjust pitch immediately."
    v_blk, _, _ = validator.validate_candidate(c_block, upstream)
    assert v_blk == GuardrailVerdict.BLOCKED


# -----------------------------------------------------------------------------
# SCEN-18: Provider Timeout Recovery
# -----------------------------------------------------------------------------
def test_scen_18_provider_timeout_recovery(engine):
    timeout_provider = TimeoutMockProvider()
    advisory, snapshot = engine.generate_advisory(
        case_id="CASE-SCEN-18",
        turbine_id="WTG17",
        custom_provider=timeout_provider,
    )
    assert advisory.status == AdvisoryStatus.FALLBACK_ADVISORY
    assert "timed out" in advisory.fallback_reason
    assert snapshot.final_status == AdvisoryStatus.FALLBACK_ADVISORY


# -----------------------------------------------------------------------------
# SCEN-19: Deterministic Fallback Mode (100% Offline CPU & Target Latency)
# -----------------------------------------------------------------------------
def test_scen_19_deterministic_fallback_mode_latency(engine):
    # Performance Acceptance Criterion: Mode A execution target < 100 ms
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        advisory, snapshot = engine.generate_advisory(
            case_id="CASE-SCEN-19",
            turbine_id="WTG18",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        times.append(elapsed_ms)
        assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY

    avg_latency = sum(times) / len(times)
    assert avg_latency < 100.0, f"Mode A latency target < 100 ms, measured {avg_latency:.2f} ms"


# -----------------------------------------------------------------------------
# SCEN-20: Mandatory Human Escalation
# -----------------------------------------------------------------------------
def test_scen_20_mandatory_human_escalation(engine):
    loss = RecordLossResult(
        power_expected_kw=2000.0,
        power_actual_kw=1000.0,
        power_deficit_kw=1000.0,
        energy_deficit_kwh=166.67,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=166.67,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=35000.0,  # > ₹25,000 ceiling
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(s_sev=0.9, s_pers=0.9, s_conf=0.9, s_crit=0.9, s_loss=0.8, priority_score=88.0, severity=SeverityLevel.CRITICAL)

    advisory, _ = engine.generate_advisory(
        case_id="CASE-SCEN-20",
        turbine_id="WTG20",
        loss=loss,
        priority=prio,
    )
    assert advisory.loss_summary_inr == 35000.0
    assert advisory.priority_score == 88.0
    assert advisory.review_status == ReviewStatus.MANDATORY_HUMAN_REVIEW_REQUIRED
