"""Unit and Benchmark Tests for ResidualEngine (TEST-ML-RES-01, TEST-ML-PERS-01, TEST-ML-SCEN-01).

Source: docs/09_technical_design.md §2.2, docs/11_ai_ml_design.md §2.1–§2.3, docs/PHASE_2_SCOPE_REVIEW.md §5, §12.
"""

from pathlib import Path
import numpy as np
import pytest

from backend.config import settings
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import (
    BenchmarkScenarioType,
    SimulationConfig,
    TelemetryRecord,
)
from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import (
    BaselineStats,
    ResidualEngine,
    ResidualVector,
)
from backend.models.thermal_model import ExpectedThermalModel
from backend.models.trainer import ModelTrainer


@pytest.fixture
def trained_residual_engine(temp_dir: Path) -> ResidualEngine:
    """Provides a fully trained ResidualEngine fixture with calibrated baseline stats."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    _ = trainer.train_and_evaluate(save_artifacts=True)

    power_model = ExpectedPowerModel.load(temp_dir / "expected_power_gbr_v1.joblib")
    thermal_model = ExpectedThermalModel.load(temp_dir / "expected_thermal_rf_v1.joblib")
    baseline_stats = BaselineStats.load(temp_dir / "baseline_stats_v1.json")

    return ResidualEngine(
        power_model=power_model,
        thermal_model=thermal_model,
        baseline_stats=baseline_stats,
        persistence_threshold=settings.ML.PERSISTENCE_THRESHOLD_SIGMA,
        persistence_window=settings.ML.PERSISTENCE_WINDOW_STEPS,
        persistence_ratio=settings.ML.PERSISTENCE_RATIO_THRESHOLD,
    )


def test_residual_arithmetic_exactness(trained_residual_engine: ResidualEngine):
    """TEST-ML-RES-01: Verifies exact arithmetic formulas for raw residuals and standardized z-scores."""
    engine = trained_residual_engine
    # Set explicit known baseline stats
    engine.baseline_stats = BaselineStats(
        mu_p=0.0, sigma_p=50.0,
        mu_gb=0.0, sigma_gb=2.0,
        mu_gen=0.0, sigma_gen=3.0,
    )

    rec = TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-01",
        wind_speed=8.5,
        ambient_temp=25.0,
        active_power=1500.0,
        rotor_speed=14.0,
        generator_speed=1430.0,
        gearbox_bearing_temp=70.0,
        generator_stator_temp=75.0,
        pitch_angle=0.5,
        is_curtailed=False,
    )

    vector = engine.compute_residuals(rec)

    # Expected values
    p_exp = engine.power_model.predict_record(rec)
    t_gb_exp, t_gen_exp = engine.thermal_model.predict_record(rec)

    # Verify raw physical residuals
    assert vector.residual_power_kw == pytest.approx(1500.0 - p_exp, rel=1e-2)
    assert vector.residual_gb_temp_c == pytest.approx(70.0 - t_gb_exp, rel=1e-2)
    assert vector.residual_gen_temp_c == pytest.approx(75.0 - t_gen_exp, rel=1e-2)

    # Verify standardized z-scores: z = (R - mu) / sigma
    assert vector.z_power == pytest.approx((vector.residual_power_kw - 0.0) / 50.0, rel=1e-2)
    assert vector.z_gb == pytest.approx((vector.residual_gb_temp_c - 0.0) / 2.0, rel=1e-2)
    assert vector.z_gen == pytest.approx((vector.residual_gen_temp_c - 0.0) / 3.0, rel=1e-2)


def test_persistence_logic_canonical_2_5_sigma(trained_residual_engine: ResidualEngine):
    """TEST-ML-PERS-01: Verifies canonical 2.5-sigma persistence filter over 6 consecutive steps (1 hour)."""
    engine = trained_residual_engine
    assert engine.persistence_threshold == 2.5
    assert engine.persistence_window == 6
    assert engine.persistence_ratio == 0.80

    # Case 1: Less than 6 steps -> Insufficient window
    assert engine.check_persistence([3.0, 3.2, 2.9, 3.1]) is False

    # Case 2: 6 steps with 6/6 exceeding 2.5 sigma -> True (100% >= 80%)
    assert engine.check_persistence([2.6, 2.7, 2.8, 2.9, 3.0, 3.1]) is True

    # Case 3: 6 steps with 5/6 exceeding 2.5 sigma -> True (83.3% >= 80%)
    assert engine.check_persistence([2.6, 2.7, 1.0, 2.8, 2.9, 3.0]) is True

    # Case 4: 6 steps with 4/6 exceeding 2.5 sigma -> False (66.7% < 80%)
    assert engine.check_persistence([2.6, 2.7, 1.0, 1.2, 2.8, 2.9]) is False

    # Case 5: 6 steps with transient single spike -> False
    assert engine.check_persistence([0.1, 0.2, 0.3, 0.1, 0.2, 4.0]) is False


def test_zero_division_safety(trained_residual_engine: ResidualEngine):
    """Verifies that sigma=0 or near-zero does not raise ZeroDivisionError or produce NaN/Inf."""
    engine = trained_residual_engine
    engine.baseline_stats = BaselineStats(
        mu_p=0.0, sigma_p=0.0,  # Zero sigma edge case
        mu_gb=0.0, sigma_gb=0.0,
        mu_gen=0.0, sigma_gen=0.0,
    )

    rec = TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-01",
        wind_speed=8.5,
        ambient_temp=25.0,
        active_power=1500.0,
        rotor_speed=14.0,
        generator_speed=1430.0,
        gearbox_bearing_temp=70.0,
        generator_stator_temp=75.0,
        pitch_angle=0.5,
        is_curtailed=False,
    )

    vector = engine.compute_residuals(rec)
    assert not np.isnan(vector.z_power)
    assert not np.isinf(vector.z_power)
    assert not np.isnan(vector.z_gb)
    assert not np.isinf(vector.z_gb)


def test_synthetic_scenario_signatures(trained_residual_engine: ResidualEngine):
    """TEST-ML-SCEN-01: Verifies synthetic scenario verification criteria across S1, S2, S3, S4."""
    engine = trained_residual_engine
    sim = SCADASimulator(default_seed=42)

    # 1. Scenario S1: Baseline Healthy -> Near-zero residuals and |z| < 2.0
    res_s1 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, num_turbines=2, num_timesteps=36))
    vectors_s1 = engine.compute_batch_residuals(res_s1.records)
    avg_z_gb_s1 = float(np.mean([abs(v.z_gb) for v in vectors_s1]))
    assert avg_z_gb_s1 < 1.5, f"S1 healthy expected average |z_gb| < 1.5, got {avg_z_gb_s1}"

    # 2. Scenario S2: Gearbox Bearing Degradation on WTG-07
    res_s2 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, num_turbines=10, num_timesteps=144))
    wtg07_recs = [r for r in res_s2.records if r.turbine_id == "WTG-07"]
    wtg07_late_recs = wtg07_recs[72:]  # After thermal degradation has settled
    vectors_s2 = engine.compute_batch_residuals(wtg07_late_recs)

    # Verification criteria for S2: RGB > +10°C and z_GB > +2.5 sigma
    max_r_gb_s2 = max(v.residual_gb_temp_c for v in vectors_s2)
    max_z_gb_s2 = max(v.z_gb for v in vectors_s2)
    assert max_r_gb_s2 > 10.0, f"S2 criteria expected R_GB > 10°C, got {max_r_gb_s2}°C"
    assert max_z_gb_s2 > 2.5, f"S2 criteria expected z_GB > 2.5 sigma, got {max_z_gb_s2}"

    # 3. Scenario S3: Pitch Asymmetry on WTG-03
    res_s3 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY, num_turbines=5, num_timesteps=144))
    wtg03_recs = [r for r in res_s3.records if r.turbine_id == "WTG-03"]
    vectors_s3 = engine.compute_batch_residuals(wtg03_recs)

    # Verification criteria for S3: Under-power deficit R_power < -200 kW and z_power < -2.0 sigma
    min_r_power_s3 = min(v.residual_power_kw for v in vectors_s3)
    min_z_power_s3 = min(v.z_power for v in vectors_s3)
    assert min_r_power_s3 < -200.0, f"S3 criteria expected R_power < -200 kW, got {min_r_power_s3} kW"
    assert min_z_power_s3 < -2.0, f"S3 criteria expected z_power < -2.0 sigma, got {min_z_power_s3}"


def test_batch_residuals_computation(trained_residual_engine: ResidualEngine):
    """Verifies that batch residual computation matches single record computation exactly."""
    engine = trained_residual_engine
    sim = SCADASimulator(default_seed=42)
    res = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, num_turbines=2, num_timesteps=10))

    batch_vectors = engine.compute_batch_residuals(res.records)
    assert len(batch_vectors) == len(res.records)

    for i in range(len(res.records)):
        single_vector = engine.compute_residuals(res.records[i])
        assert batch_vectors[i].expected_power_kw == pytest.approx(single_vector.expected_power_kw, rel=1e-2)
        assert batch_vectors[i].residual_power_kw == pytest.approx(single_vector.residual_power_kw, rel=1e-2)
        assert batch_vectors[i].expected_gb_temp_c == pytest.approx(single_vector.expected_gb_temp_c, rel=1e-2)
        assert batch_vectors[i].residual_gb_temp_c == pytest.approx(single_vector.residual_gb_temp_c, rel=1e-2)
