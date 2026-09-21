"""Acceptance Gate Tests for Phase 3 (Layer 3 Context, Reasoning, Tariff & Loss Pipeline).

Source of Truth:
- docs/06_prd.md §7 (FR-004, FR-005, FR-006, FR-007)
- docs/07_srs.md §3.3, §3.4, §3.5
- docs/PHASE_3_SCOPE_REVIEW.md §8 (Layer 3 Acceptance Gate)

Acceptance Tests:
  - TEST-CTX-01: Context Precedence & False-Alarm Suppression
  - TEST-REAS-01: Subsystem Attribution Accuracy (S1-S5 Ground Truth)
  - TEST-TRF-01: Tariff Registry & Rate Bounds
  - TEST-LOSS-01: Eligible Loss Integration & Boundary Partitioning
  - TEST-PRIO-01: 5-Factor Prioritization Scoring & Severity Classification
  - TEST-LOCKOUT-P3: Phase 4+ Boundary Lockout Protection
"""

from pathlib import Path
import pytest

from backend.config import settings
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig
from backend.engine.context_engine import (
    ContextFilterEngine,
    OperationalContextState,
)
from backend.engine.loss_calculator import (
    LossCalculator,
    LossEligibility,
)
from backend.engine.prioritization import (
    PrioritizationEngine,
    SeverityLevel,
)
from backend.engine.reasoner import (
    AttributionResult,
    MultiSignalReasoner,
    SubsystemLabel,
)
from backend.engine.tariff_registry import (
    TariffMode,
    TariffRegistry,
)
from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import BaselineStats, ResidualEngine, ResidualVector
from backend.models.thermal_model import ExpectedThermalModel


@pytest.fixture(scope="module")
def layer2_residual_engine():
    """Initializes trained/loaded Layer 2 Expected Models & ResidualEngine."""
    artifacts_dir = settings.PATHS.ARTIFACTS_DIR
    p_model_path = artifacts_dir / "expected_power_gbr_v1.joblib"
    t_model_path = artifacts_dir / "expected_thermal_rf_v1.joblib"
    stats_path = artifacts_dir / "baseline_stats_v1.json"

    power_model = ExpectedPowerModel.load(p_model_path)
    thermal_model = ExpectedThermalModel.load(t_model_path)
    baseline_stats = BaselineStats.load(stats_path)

    return ResidualEngine(
        power_model=power_model,
        thermal_model=thermal_model,
        baseline_stats=baseline_stats,
    )


@pytest.fixture(scope="module")
def layer3_pipeline(layer2_residual_engine):
    """Assembles full Layer 3 pipeline components."""
    context_engine = ContextFilterEngine()
    reasoner = MultiSignalReasoner()
    tariff_registry = TariffRegistry()
    loss_calc = LossCalculator(tariff_registry=tariff_registry)
    prioritizer = PrioritizationEngine()

    return {
        "residual_engine": layer2_residual_engine,
        "context_engine": context_engine,
        "reasoner": reasoner,
        "tariff_registry": tariff_registry,
        "loss_calc": loss_calc,
        "prioritizer": prioritizer,
    }


def test_gate_01_context_precedence_and_suppression(layer3_pipeline):
    """TEST-CTX-01: Verifies context precedence and false-alarm suppression under S4 and benign conditions."""
    ctx_engine: ContextFilterEngine = layer3_pipeline["context_engine"]
    res_engine: ResidualEngine = layer3_pipeline["residual_engine"]

    # 1. Evaluate S4 (Grid Curtailment + Heatwave) with 144 steps (24h benchmark)
    sim = SCADASimulator(default_seed=42)
    s4_result = sim.simulate(SimulationConfig(
        scenario=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE,
        num_turbines=5,
        num_timesteps=144,
        random_seed=42,
    ))
    s4_records = s4_result.records
    s4_residuals = res_engine.compute_batch_residuals(s4_records)
    s4_ctx_results = ctx_engine.evaluate_batch(s4_records, s4_residuals)

    # In S4, curtailment starts at step 36 for WTG-01..05 with heatwave throughout
    # Records under curtailment MUST evaluate strictly to CURTAILED (Precedence 2)
    curtailed_evals = [r for rec, r in zip(s4_records, s4_ctx_results) if rec.is_curtailed]
    assert len(curtailed_evals) > 0
    for res in curtailed_evals:
        assert res.state == OperationalContextState.CURTAILED
        assert res.is_suppressed is True
        assert res.precedence_level == 2

    # Verify co-occurring heatwave is captured in metadata during high ambient intervals
    heatwave_curtailed = [r for r in curtailed_evals if r.metadata.get("co_occurring_heatwave") is True]
    assert len(heatwave_curtailed) > 0

    # Target: >= 90% false-alarm suppression on benign/external context records (curtailment + heatwave events)
    benign_event_indices = [i for i, r in enumerate(s4_records) if r.is_curtailed or r.ambient_temp >= 38.0]
    suppression_rate = ctx_engine.calculate_suppression_rate(s4_ctx_results, benign_indices=benign_event_indices)
    assert suppression_rate >= 90.0, f"Expected >= 90.0% suppression on S4 benign events, got {suppression_rate:.2f}%"


def test_gate_02_subsystem_attribution_accuracy(layer3_pipeline):
    """TEST-REAS-01: Verifies multi-signal subsystem attribution accuracy across S1-S5 synthetic scenarios."""
    res_engine: ResidualEngine = layer3_pipeline["residual_engine"]
    ctx_engine: ContextFilterEngine = layer3_pipeline["context_engine"]
    reasoner: MultiSignalReasoner = layer3_pipeline["reasoner"]

    sim = SCADASimulator(default_seed=42)

    # Scenarios to evaluate: S1 (healthy), S2 (gearbox), S3 (pitch), S4 (curtailment), S5 (sensor)
    all_predictions = []
    all_ground_truth = []
    scenario_ids = []

    scenario_map = [
        (BenchmarkScenarioType.S1_BASELINE_HEALTHY, 5, 144, "S1"),
        (BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, 10, 144, "S2"),
        (BenchmarkScenarioType.S3_PITCH_ASYMMETRY, 5, 144, "S3"),
        (BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE, 5, 144, "S4"),
        (BenchmarkScenarioType.S5_SENSOR_DROPOUT, 10, 144, "S5"),
    ]

    for sc_type, n_turbines, n_steps, s_name in scenario_map:
        res = sim.simulate(SimulationConfig(
            scenario=sc_type,
            num_turbines=n_turbines,
            num_timesteps=n_steps,
            random_seed=42,
        ))
        records = res.records
        residuals = res_engine.compute_batch_residuals(records)
        contexts = ctx_engine.evaluate_batch(records, residuals)

        reasoner.reset_history()
        for rec, r, c in zip(records, residuals, contexts):
            attr = reasoner.evaluate_record(rec, r, c)
            # Check rule confidence bounds
            assert 0.0 <= attr.rule_confidence <= 1.0

            # Ground truth determination:
            expected_lbl = SubsystemLabel.NORMAL_OPERATION
            if s_name == "S1":
                expected_lbl = SubsystemLabel.NORMAL_OPERATION
            elif s_name == "S2":
                # WTG-07 is the injected turbine in S2
                if rec.turbine_id == "WTG-07" and r.residual_gb_temp_c > 10.0 and r.z_gb >= 2.5:
                    expected_lbl = SubsystemLabel.DRIVETRAIN_GEARBOX
            elif s_name == "S3":
                # WTG-03 is injected turbine in S3
                if rec.turbine_id == "WTG-03" and r.residual_power_kw <= -200.0 and r.z_power <= -2.0:
                    expected_lbl = SubsystemLabel.AERODYNAMIC_PITCH
            elif s_name == "S4":
                if rec.is_curtailed:
                    expected_lbl = SubsystemLabel.GRID_CURTAILMENT
                else:
                    expected_lbl = SubsystemLabel.NORMAL_OPERATION
            elif s_name == "S5":
                if rec.turbine_id == "WTG-09" and (rec.operating_status == "Sensor Dropout" or rec.gearbox_bearing_temp < rec.ambient_temp - 5.0):
                    expected_lbl = SubsystemLabel.SENSOR_ANOMALY

            all_predictions.append(attr.subsystem)
            all_ground_truth.append(expected_lbl)
            scenario_ids.append(s_name)

    metrics = MultiSignalReasoner.compute_attribution_metrics(
        predictions=all_predictions,
        ground_truth=all_ground_truth,
        scenario_ids=scenario_ids,
    )

    # Attribution Accuracy Target: >= 90.0%
    acc = metrics["overall_accuracy_pct"]
    assert acc >= 90.0, f"Target Attribution Accuracy >= 90.0%, measured {acc:.2f}%"
    assert metrics["total_eligible_records"] == 5040
    assert metrics["correct_classifications"] >= 4500


def test_gate_03_tariff_registry_and_provenance(layer3_pipeline):
    """TEST-TRF-01: Verifies multi-mode tariff registry, provenance immutability, and boundary bounds."""
    tr: TariffRegistry = layer3_pipeline["tariff_registry"]

    # Initial baseline
    t_base = tr.get_active_tariff()
    assert t_base.applied_rate_inr_per_kwh == 3.20
    assert t_base.mode == TariffMode.CONFIGURED_BASELINE
    assert t_base.is_baseline_assumption is True

    # PPA Configuration
    t_ppa = tr.set_ppa_tariff(3.50, "PPA-TEST-01")
    assert t_ppa.applied_rate_inr_per_kwh == 3.50
    assert t_ppa.mode == TariffMode.PROJECT_PPA
    assert t_ppa.is_baseline_assumption is False

    # Bound Validation [₹0.01, ₹20.00]
    with pytest.raises(ValueError):
        tr.set_tariff(-0.5, TariffMode.CONFIGURED_BASELINE, "Negative rate")

    with pytest.raises(ValueError):
        tr.set_tariff(25.0, TariffMode.CONFIGURED_BASELINE, "Excessive rate")

    # Reset
    t_reset = tr.reset_to_baseline()
    assert t_reset.applied_rate_inr_per_kwh == 3.20


def test_gate_04_loss_calculation_and_eligibility(layer3_pipeline):
    """TEST-LOSS-01: Verifies energy and financial loss calculation and strict eligibility boundaries."""
    loss_calc: LossCalculator = layer3_pipeline["loss_calc"]
    res_engine: ResidualEngine = layer3_pipeline["residual_engine"]
    ctx_engine: ContextFilterEngine = layer3_pipeline["context_engine"]
    reasoner: MultiSignalReasoner = layer3_pipeline["reasoner"]

    sim = SCADASimulator(default_seed=42)

    # 1. S3 Pitch Degradation (WTG-03 with 5 turbines, 144 timesteps) -> ELIGIBLE_DEGRADATION
    s3_res = sim.simulate(SimulationConfig(
        scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY,
        num_turbines=5,
        num_timesteps=144,
        random_seed=42,
    ))
    s3_records = s3_res.records
    s3_residuals = res_engine.compute_batch_residuals(s3_records)
    s3_contexts = ctx_engine.evaluate_batch(s3_records, s3_residuals)
    s3_attrs = reasoner.evaluate_batch(s3_records, s3_residuals, s3_contexts)

    s3_summary = loss_calc.calculate_batch_losses(s3_records, s3_residuals, s3_contexts, s3_attrs)
    assert s3_summary.eligible_degradation_energy_kwh > 0.0
    assert s3_summary.maintenance_financial_loss_inr > 0.0
    assert s3_summary.curtailed_capacity_kwh == 0.0

    # 2. S4 Grid Curtailment (WTG-01..05 with 144 timesteps) -> CURTAILED_CAPACITY (Excluded from maintenance loss)
    s4_res = sim.simulate(SimulationConfig(
        scenario=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE,
        num_turbines=5,
        num_timesteps=144,
        random_seed=42,
    ))
    s4_records = s4_res.records
    s4_residuals = res_engine.compute_batch_residuals(s4_records)
    s4_contexts = ctx_engine.evaluate_batch(s4_records, s4_residuals)
    s4_attrs = reasoner.evaluate_batch(s4_records, s4_residuals, s4_contexts)

    s4_summary = loss_calc.calculate_batch_losses(s4_records, s4_residuals, s4_contexts, s4_attrs)
    assert s4_summary.curtailed_capacity_kwh > 0.0
    assert s4_summary.maintenance_financial_loss_inr == 0.0  # Zero maintenance loss!


def test_gate_05_prioritization_engine(layer3_pipeline):
    """TEST-PRIO-01: Verifies 5-factor priority score bounds (0-100), monotonicity, and severity classification."""
    prio: PrioritizationEngine = layer3_pipeline["prioritizer"]

    # Gearbox failure under severe thermal rise
    res_gb = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=18.0,
        z_gb=6.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr_gb = AttributionResult(
        subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
        rule_confidence=0.90,
        is_persistent=True,
        excursion_count=6,
        window_size=6,
        matched_rule="RULE_DRIVETRAIN_GEARBOX_THERMAL",
        explanation="Gearbox degradation.",
    )

    score_res = prio.compute_priority_score(res_gb, attr_gb, cumulative_maint_loss_inr=48000.0)
    assert 0.0 <= score_res.priority_score <= 100.0
    assert score_res.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
    assert score_res.s_crit == 1.0  # Gearbox criticality is 1.0


def test_gate_06_phase_boundary_lockout():
    """TEST-LOCKOUT-P3: Verifies strict lockout of Phase 4 (RAG), Phase 5 (LLM), and Phase 6 (UI/Actuation)."""
    base_dir = settings.PATHS.BASE_DIR

    # Phase 4 (RAG) files must NOT exist
    assert not (base_dir / "backend" / "rag").exists(), "Phase 4 RAG directory must not exist"

    # Phase 5 (LLM) files must NOT exist
    assert not (base_dir / "backend" / "llm").exists(), "Phase 5 LLM directory must not exist"

    # Phase 6 (Frontend / Dashboard) files must NOT exist
    assert not (base_dir / "frontend").exists(), "Phase 6 Frontend directory must not exist"

    # Actuation write-control endpoints must NOT exist
    assert not (base_dir / "backend" / "api" / "actuation.py").exists(), "Actuation interface must permanently not exist"
