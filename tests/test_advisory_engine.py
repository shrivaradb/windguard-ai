"""Unit Tests for AdvisoryEngine Master Coordinator and Output Dispatcher (Layer 5).

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011, FR-012)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/PHASE_5_SCOPE_REVIEW.md §6.4, §6.5
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §5, §10
"""

import pytest

from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.loss_calculator import LossEligibility, RecordLossResult
from backend.engine.prioritization import PriorityScoreBreakdown, SeverityLevel
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.engine.tariff_registry import TariffMode, TariffProvenance
from backend.llm.advisory_engine import AdvisoryEngine
from backend.llm.prompts import MANDATORY_SAFETY_DISCLAIMER
from backend.llm.providers import BaseAdvisoryProvider
from backend.llm.schema import (
    AdvisoryStatus,
    GuardrailVerdict,
    ReviewStatus,
    SourceType,
)
from backend.models.residual_engine import ResidualVector
from backend.rag.schema import ContentType, DocumentChunk, RetrievalMode, RetrievalResult


def make_provenance(rate: float = 4.50) -> TariffProvenance:
    return TariffProvenance(
        applied_rate_inr_per_kwh=rate,
        mode=TariffMode.CONFIGURED_BASELINE,
        source_reference="DEFAULT_PPA",
        effective_date="2026-01-01",
        is_baseline_assumption=True,
    )


class FailingProvider(BaseAdvisoryProvider):
    @property
    def provider_mode(self) -> str:
        return "MODE_FAILING_MOCK"

    def generate_candidate(self, prompt_context_xml: str, structured_context: dict) -> dict:
        raise RuntimeError("Simulated cloud provider timeout or network disconnection")


class MalformedOutputProvider(BaseAdvisoryProvider):
    @property
    def provider_mode(self) -> str:
        return "MODE_MALFORMED_MOCK"

    def generate_candidate(self, prompt_context_xml: str, structured_context: dict) -> dict:
        return {"invalid_key": 12345}  # Fails Pydantic validation


class ActuationInjectingProvider(BaseAdvisoryProvider):
    @property
    def provider_mode(self) -> str:
        return "MODE_INJECTING_MOCK"

    def generate_candidate(self, prompt_context_xml: str, structured_context: dict) -> dict:
        return {
            "case_id": structured_context.get("case_id"),
            "timestamp": structured_context.get("timestamp"),
            "turbine_id": structured_context.get("turbine_id"),
            "status": AdvisoryStatus.NORMAL_ADVISORY.value,
            "primary_attribution": structured_context.get("subsystem_attribution"),
            "context_classification": structured_context.get("context_state"),
            "summary": "Automatic remediation: Adjust pitch angle to 5 degrees immediately.",
            "evidence_synthesis": [],
            "hypotheses": [],
            "recommended_actions": [],
            "citations": [],
            "loss_summary_inr": structured_context.get("financial_loss_inr", 0.0),
            "energy_loss_kwh": structured_context.get("energy_loss_kwh", 0.0),
            "priority_score": structured_context.get("priority_score", 0.0),
            "review_status": ReviewStatus.AUTOMATIC.value,
            "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
        }


@pytest.fixture
def engine():
    return AdvisoryEngine()


@pytest.fixture
def standard_case_inputs():
    tel = TelemetryRecord(
        timestamp="2026-01-01T12:00:00Z",
        turbine_id="WTG01",
        wind_speed=8.5,
        wind_direction=210.0,
        ambient_temp=25.0,
        active_power=1420.0,
        reactive_power=120.0,
        rotor_speed=13.2,
        generator_speed=1350.0,
        gearbox_bearing_temp=82.5,
        generator_stator_temp=68.0,
        nacelle_temp=32.0,
        pitch_angle=1.2,
        operating_status=OperatingStatus.RUNNING,
    )
    res = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=-80.0,
        z_power=-1.2,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=17.5,
        z_gb=3.5,
        expected_gen_temp_c=66.0,
        residual_gen_temp_c=2.0,
        z_gen=0.4,
    )
    ctx = ContextResult(
        state=OperationalContextState.NORMAL,
        is_suppressed=False,
        explanation="Normal operating regime",
        precedence_level=5,
    )
    attr = AttributionResult(
        subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
        rule_confidence=0.90,
        is_persistent=True,
        excursion_count=5,
        window_size=6,
        matched_rule="RULE-GB-01",
        explanation="High gearbox bearing thermal residual",
    )
    loss = RecordLossResult(
        power_expected_kw=1500.0,
        power_actual_kw=1420.0,
        power_deficit_kw=80.0,
        energy_deficit_kwh=13.33,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=13.33,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=60.0,
        tariff_provenance=make_provenance(4.50),
    )
    prio = PriorityScoreBreakdown(
        s_sev=0.85,
        s_pers=0.80,
        s_conf=0.90,
        s_crit=0.90,
        s_loss=0.20,
        priority_score=74.5,
        severity=SeverityLevel.HIGH,
    )
    chunk = DocumentChunk(
        chunk_id="CHK-GB-001",
        document_title="OEM Gearbox Maintenance Manual",
        document_filename="gb_manual.md",
        source_id="SRC-AUTHENTIC-GB-01",
        source_type=SourceType.SOURCE_AUTHENTIC,
        publisher="WindOEM Inc.",
        publication_date="2023-01-01",
        chapter="Chapter 4",
        section="Section 4.2",
        source_locator="Sec 4.2 Bearing Overheating",
        content="Bearing thermal rises above 15°C indicate lubrication breakdown.",
        content_type=ContentType.VERBATIM_SOURCE,
        token_count=12,
        content_hash="abc123hash",
        provenance_status="VERIFIED",
    )
    rag = RetrievalResult(
        query="gearbox bearing thermal rise",
        top_k=1,
        retrieval_mode=RetrievalMode.HYBRID_LOCAL,
        chunks=[chunk],
        scores=[0.92],
        query_latency_ms=2.5,
    )
    return {
        "case_id": "CASE-S2-GB-01",
        "turbine_id": "WTG01",
        "timestamp": "2026-01-01T12:00:00Z",
        "telemetry": tel,
        "residuals": res,
        "context": ctx,
        "attribution": attr,
        "loss": loss,
        "priority": prio,
        "rag_result": rag,
    }


def test_mode_a_local_generation_clean(engine, standard_case_inputs):
    advisory, snapshot = engine.generate_advisory(**standard_case_inputs)

    assert advisory.case_id == "CASE-S2-GB-01"
    assert advisory.status == AdvisoryStatus.NORMAL_ADVISORY
    assert advisory.primary_attribution == "DRIVETRAIN_GEARBOX"
    assert advisory.loss_summary_inr == 60.0
    assert advisory.priority_score == 74.5
    assert advisory.guardrail_status.verdict == GuardrailVerdict.PASS
    assert len(advisory.citations) == 1
    assert advisory.citations[0].source_id == "SRC-AUTHENTIC-GB-01"
    assert MANDATORY_SAFETY_DISCLAIMER in advisory.safety_disclaimer

    assert snapshot.provider_mode == "MODE_A"
    assert snapshot.final_status == AdvisoryStatus.NORMAL_ADVISORY
    assert snapshot.duration_ms > 0.0


def test_provider_failure_recovers_to_fallback(engine, standard_case_inputs):
    inputs = dict(standard_case_inputs)
    inputs["custom_provider"] = FailingProvider()

    advisory, snapshot = engine.generate_advisory(**inputs)

    assert advisory.status == AdvisoryStatus.FALLBACK_ADVISORY
    assert "Provider invocation error" in advisory.fallback_reason
    assert advisory.guardrail_status.verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert advisory.loss_summary_inr == 60.0  # Upstream numbers preserved exactly
    assert snapshot.final_status == AdvisoryStatus.FALLBACK_ADVISORY


def test_malformed_provider_output_recovers_to_fallback(engine, standard_case_inputs):
    inputs = dict(standard_case_inputs)
    inputs["custom_provider"] = MalformedOutputProvider()

    advisory, snapshot = engine.generate_advisory(**inputs)

    assert advisory.status == AdvisoryStatus.FALLBACK_ADVISORY
    assert advisory.loss_summary_inr == 60.0
    assert snapshot.final_status == AdvisoryStatus.FALLBACK_ADVISORY


def test_actuation_injection_is_blocked(engine, standard_case_inputs):
    inputs = dict(standard_case_inputs)
    inputs["custom_provider"] = ActuationInjectingProvider()

    advisory, snapshot = engine.generate_advisory(**inputs)

    assert advisory.status == AdvisoryStatus.BLOCKED_OUTPUT
    assert advisory.guardrail_status.verdict == GuardrailVerdict.BLOCKED
    assert advisory.guardrail_status.lexicon_scan_passed is False
    assert snapshot.final_status == AdvisoryStatus.BLOCKED_OUTPUT
    assert snapshot.final_advisory is None  # Blocked payload is not returned as valid advisory


def test_mandatory_human_review_ceiling_escalation(engine, standard_case_inputs):
    inputs = dict(standard_case_inputs)
    # Set financial loss above ₹25,000 threshold
    inputs["loss"] = RecordLossResult(
        power_expected_kw=1500.0,
        power_actual_kw=800.0,
        power_deficit_kw=700.0,
        energy_deficit_kwh=116.67,
        eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
        eligible_degradation_energy_kwh=116.67,
        curtailed_capacity_kwh=0.0,
        applied_tariff_inr_per_kwh=4.50,
        financial_loss_inr=28500.0,  # > ₹25,000
        tariff_provenance=make_provenance(4.50),
    )
    advisory, _ = engine.generate_advisory(**inputs)
    assert advisory.loss_summary_inr == 28500.0
    assert advisory.review_status == ReviewStatus.MANDATORY_HUMAN_REVIEW_REQUIRED
