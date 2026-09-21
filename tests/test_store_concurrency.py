"""Concurrency & Multi-Threaded Stress Tests for Persistent Storage (Layer 6).

Source:
- docs/08_system_architecture.md ADR-006
- docs/09_technical_design.md §4
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-01, OD-P6-08)
"""

from concurrent.futures import ThreadPoolExecutor
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


def test_concurrent_case_saves(tmp_path: Path):
    """Verifies thread-safe concurrent case writes without data loss or corruption."""
    store_file = tmp_path / "concurrent_cases.json"
    store = CaseStore(store_path=store_file)
    num_threads = 20

    def save_worker(idx: int):
        cid = f"CASE-CONCURRENT-{idx:03d}"
        c = _create_mock_case(cid, f"WTG-{idx%10:02d}")
        store.save_case(c)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(save_worker, i) for i in range(num_threads)]
        for f in futures:
            f.result()

    assert store.count() == num_threads

    # Verify reload from disk contains all 20 cases
    reloaded_store = CaseStore(store_path=store_file)
    assert reloaded_store.count() == num_threads


def test_concurrent_decision_appends(tmp_path: Path):
    """Verifies thread-safe concurrent decision appends to a shared case."""
    store_file = tmp_path / "concurrent_decisions.json"
    store = CaseStore(store_path=store_file)
    case_id = "CASE-SHARED-001"
    store.save_case(_create_mock_case(case_id, "WTG-07"))

    num_decisions = 15

    def decision_worker(idx: int):
        dec = OperatorDecision(
            decision_id=f"DEC-{idx:03d}",
            action=HITLAction.INVESTIGATE,
            operator_id=f"OPERATOR_{idx}",
            timestamp=f"2026-09-20T12:{idx:02d}:00Z",
            notes=f"Concurrent decision note #{idx}",
        )
        store.record_decision(case_id, dec)

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(decision_worker, i) for i in range(num_decisions)]
        for f in futures:
            f.result()

    final_case = store.get_case(case_id)
    assert final_case is not None
    assert len(final_case.operator_decisions) == num_decisions
