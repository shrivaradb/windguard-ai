"""Unit Tests for Persistent CaseStore and Atomic File Locking (Layer 6).

Source:
- docs/08_system_architecture.md ADR-006
- docs/09_technical_design.md §2.6, §4
- docs/10_data_architecture.md §6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-01, OD-P6-05)
"""

from pathlib import Path
import pytest

from backend.api.schemas import (
    CaseStatus,
    DerivedAnalyticsSummary,
    HITLAction,
    MaintenanceCase,
    OperatorDecision,
    SourceTelemetrySummary,
)
from backend.data.schema import OperatingStatus
from backend.engine.context_engine import OperationalContextState
from backend.engine.loss_calculator import LossEligibility
from backend.engine.prioritization import PriorityScoreBreakdown, SeverityLevel
from backend.engine.reasoner import SubsystemLabel
from backend.engine.tariff_registry import TariffMode, TariffProvenance
from backend.llm.schema import (
    AdvisoryStatus,
    GuardrailStatusBlock,
    GuardrailVerdict,
    OperatorAdvisory,
    ReviewStatus,
)
from backend.storage.case_store import CaseStore


def _create_mock_case(case_id: str, turbine_id: str = "WTG-07") -> MaintenanceCase:
    """Helper to generate a complete valid MaintenanceCase fixture."""
    source = SourceTelemetrySummary(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id=turbine_id,
        wind_speed=8.5,
        active_power=1640.0,
        ambient_temp=28.0,
        gearbox_bearing_temp=78.4,
        generator_stator_temp=70.0,
        pitch_angle=0.5,
        rotor_speed=14.5,
        is_curtailed=False,
        operating_status=OperatingStatus.RUNNING,
        source_provenance="SOURCE_AUTHENTIC",
    )
    prio_breakdown = PriorityScoreBreakdown(
        s_sev=0.8,
        s_pers=0.8,
        s_conf=0.9,
        s_crit=1.0,
        s_loss=0.5,
        priority_score=78.5,
        severity=SeverityLevel.HIGH,
    )
    tariff = TariffProvenance(
        applied_rate_inr_per_kwh=3.20,
        mode=TariffMode.CONFIGURED_BASELINE,
        source_reference="Demo Baseline",
        effective_date="2026-09-20T00:00:00Z",
        is_baseline_assumption=True,
    )
    derived = DerivedAnalyticsSummary(
        expected_power_kw=1750.0,
        residual_power_kw=-110.0,
        z_power=-1.5,
        expected_gb_temp_c=62.0,
        residual_gb_temp_c=16.4,
        z_gb=3.2,
        expected_gen_temp_c=68.0,
        residual_gen_temp_c=2.0,
        z_gen=0.5,
        context_state=OperationalContextState.NORMAL,
        is_context_suppressed=False,
        subsystem_attribution=SubsystemLabel.DRIVETRAIN_GEARBOX,
        attribution_confidence=0.88,
        energy_loss_kwh=220.0,
        financial_loss_inr=704.0,
        tariff_provenance=tariff,
        priority_score=78.5,
        severity=SeverityLevel.HIGH,
        priority_breakdown=prio_breakdown,
    )
    guardrail = GuardrailStatusBlock(
        verdict=GuardrailVerdict.PASS,
        schema_valid=True,
        numerical_consistency_valid=True,
        citation_whitelist_valid=True,
        lexicon_scan_passed=True,
        context_consistency_valid=True,
        attribution_consistency_valid=True,
        safety_disclaimer_present=True,
        violations=[],
    )
    advisory = OperatorAdvisory(
        case_id=case_id,
        timestamp="2026-09-20T12:00:00Z",
        turbine_id=turbine_id,
        status=AdvisoryStatus.NORMAL_ADVISORY,
        primary_attribution="DRIVETRAIN_GEARBOX",
        context_classification="NORMAL",
        summary="Gearbox bearing temperature excursion (+16.4°C).",
        loss_summary_inr=704.0,
        energy_loss_kwh=220.0,
        priority_score=78.5,
        review_status=ReviewStatus.MANDATORY_HUMAN_REVIEW_REQUIRED,
        guardrail_status=guardrail,
        safety_disclaimer="Non-actuating advisory.",
    )
    return MaintenanceCase(
        case_id=case_id,
        turbine_id=turbine_id,
        created_at="2026-09-20T12:05:00Z",
        status=CaseStatus.OPEN,
        severity=SeverityLevel.HIGH,
        priority_score=78.5,
        source_telemetry=source,
        derived_analytics=derived,
        evidence_table=[],
        citations=[],
        advisory=advisory,
        guardrails=guardrail,
        review_status=ReviewStatus.MANDATORY_HUMAN_REVIEW_REQUIRED,
        operator_decisions=[],
        schema_version="1.0.0",
    )


def test_case_store_save_get_and_count(tmp_path: Path):
    """Verifies saving and retrieving a case from CaseStore."""
    store_file = tmp_path / "test_cases.json"
    store = CaseStore(store_path=store_file)

    case = _create_mock_case("CASE-TEST-001", "WTG-07")
    store.save_case(case)

    assert store.count() == 1
    retrieved = store.get_case("CASE-TEST-001")
    assert retrieved is not None
    assert retrieved.case_id == "CASE-TEST-001"
    assert retrieved.turbine_id == "WTG-07"
    assert retrieved.status == CaseStatus.OPEN


def test_case_store_record_decision(tmp_path: Path):
    """Verifies that recording an operator decision updates status and appends decision."""
    store_file = tmp_path / "test_cases.json"
    store = CaseStore(store_path=store_file)

    case = _create_mock_case("CASE-TEST-002", "WTG-07")
    store.save_case(case)

    decision = OperatorDecision(
        decision_id="DEC-001",
        action=HITLAction.INVESTIGATE,
        operator_id="TECH_ALICE",
        timestamp="2026-09-20T12:10:00Z",
        notes="Inspecting lube filter.",
    )
    updated = store.record_decision("CASE-TEST-002", decision)

    assert updated.status == CaseStatus.INVESTIGATING
    assert len(updated.operator_decisions) == 1
    assert updated.operator_decisions[0].operator_id == "TECH_ALICE"


def test_case_store_load_from_disk(tmp_path: Path):
    """Verifies that a new CaseStore instance cleanly loads existing cases from disk."""
    store_file = tmp_path / "test_cases.json"
    store1 = CaseStore(store_path=store_file)
    case = _create_mock_case("CASE-TEST-003", "WTG-03")
    store1.save_case(case)

    # Instantiate second store pointing to same file
    store2 = CaseStore(store_path=store_file)
    assert store2.count() == 1
    loaded = store2.get_case("CASE-TEST-003")
    assert loaded is not None
    assert loaded.turbine_id == "WTG-03"


def test_case_store_immutability_violation_raises_error(tmp_path: Path):
    """Verifies that attempting to overwrite a case with divergent telemetry/turbine raises ValueError."""
    store_file = tmp_path / "test_cases.json"
    store = CaseStore(store_path=store_file)

    case1 = _create_mock_case("CASE-TEST-004", "WTG-07")
    store.save_case(case1)

    # Attempt to overwrite with different turbine_id
    case2 = _create_mock_case("CASE-TEST-004", "WTG-01")
    with pytest.raises(ValueError, match="Cannot overwrite immutable historical case"):
        store.save_case(case2)
