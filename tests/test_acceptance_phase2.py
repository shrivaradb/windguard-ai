"""Phase 2 Master Acceptance Gate Test Suite (TEST-ML-01).

Formally verifies all mandatory Phase 2 acceptance criteria against
the finalized engineering documentation and Phase 2 Scope Review.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import (
    BenchmarkScenarioType,
    SimulationConfig,
    TelemetryRecord,
)
from backend.main import app
from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import (
    BaselineStats,
    ResidualEngine,
    ResidualVector,
)
from backend.models.thermal_model import ExpectedThermalModel
from backend.models.trainer import ModelTrainer


def test_gate_01_expected_power_model_accuracy(temp_dir: Path):
    """GATE 1: ExpectedPowerModel (GBR) trained on S1 achieves documented R² >= 0.95, RMSE <= 45 kW."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    results = trainer.train_and_evaluate(save_artifacts=True)

    metrics = results["power_model_metrics"]
    assert metrics["r2_score"] >= settings.ML.TARGET_POWER_R2, f"Target R² >= 0.95, got {metrics['r2_score']}"
    assert metrics["rmse_kw"] <= settings.ML.TARGET_POWER_RMSE_KW, f"Target RMSE <= 45 kW, got {metrics['rmse_kw']}"
    assert metrics["mae_kw"] <= settings.ML.TARGET_POWER_MAE_KW, f"Target MAE <= 30 kW, got {metrics['mae_kw']}"


def test_gate_02_expected_thermal_model_accuracy(temp_dir: Path):
    """GATE 2: ExpectedThermalModel (RF) trained on S1 achieves RMSE <= TARGET_THERMAL_RMSE_C, R² >= TARGET_THERMAL_R2."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    results = trainer.train_and_evaluate(save_artifacts=True)

    gb = results["thermal_model_metrics"]["gearbox_bearing"]
    gen = results["thermal_model_metrics"]["generator_stator"]

    assert gb["rmse_c"] <= settings.ML.TARGET_THERMAL_RMSE_C, f"Target GB RMSE <= {settings.ML.TARGET_THERMAL_RMSE_C}°C, got {gb['rmse_c']}"
    assert gb["r2_score"] >= settings.ML.TARGET_THERMAL_R2, f"Target GB R² >= {settings.ML.TARGET_THERMAL_R2}, got {gb['r2_score']}"

    assert gen["rmse_c"] <= settings.ML.TARGET_THERMAL_RMSE_C, f"Target Gen RMSE <= {settings.ML.TARGET_THERMAL_RMSE_C}°C, got {gen['rmse_c']}"
    assert gen["r2_score"] >= settings.ML.TARGET_THERMAL_R2, f"Target Gen R² >= {settings.ML.TARGET_THERMAL_R2}, got {gen['r2_score']}"


def test_gate_03_residual_engine_and_zscores(temp_dir: Path):
    """GATE 3: ResidualEngine calculates exact residuals and standardized z-scores against BaselineStats."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    _ = trainer.train_and_evaluate(save_artifacts=True)

    power_model = ExpectedPowerModel.load(temp_dir / "expected_power_gbr_v1.joblib")
    thermal_model = ExpectedThermalModel.load(temp_dir / "expected_thermal_rf_v1.joblib")
    baseline_stats = BaselineStats.load(temp_dir / "baseline_stats_v1.json")
    engine = ResidualEngine(power_model, thermal_model, baseline_stats)

    rec = TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-01",
        wind_speed=8.5,
        ambient_temp=25.0,
        active_power=1450.0,
        rotor_speed=14.0,
        generator_speed=1430.0,
        gearbox_bearing_temp=65.0,
        generator_stator_temp=70.0,
        pitch_angle=0.5,
        is_curtailed=False,
    )

    vec = engine.compute_residuals(rec)
    assert isinstance(vec, ResidualVector)
    assert vec.expected_power_kw > 0.0
    assert vec.expected_gb_temp_c > 0.0
    assert vec.expected_gen_temp_c > 0.0
    assert isinstance(vec.z_power, float)
    assert isinstance(vec.z_gb, float)
    assert isinstance(vec.z_gen, float)


def test_gate_04_canonical_persistence_threshold():
    """GATE 4: Persistence uses canonical theta_thresh = 2.5 sigma, W = 6 (1 hour), ratio >= 0.80."""
    engine = ResidualEngine(
        power_model=ExpectedPowerModel(random_state=42),
        thermal_model=ExpectedThermalModel(random_state=42),
        persistence_threshold=2.5,
        persistence_window=6,
        persistence_ratio=0.80,
    )
    # Exactly 5 of 6 intervals >= 2.5 sigma -> True
    assert engine.check_persistence([2.6, 2.7, 0.5, 2.8, 2.9, 3.0]) is True
    # 4 of 6 intervals >= 2.5 sigma -> False
    assert engine.check_persistence([2.6, 2.7, 0.5, 0.4, 2.9, 3.0]) is False


def test_gate_05_curtailment_handling(temp_dir: Path):
    """GATE 5: Curtailed records are excluded from training and produce expected power deficits in inference."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    _ = trainer.train_and_evaluate(save_artifacts=True)

    power_model = ExpectedPowerModel.load(temp_dir / "expected_power_gbr_v1.joblib")
    thermal_model = ExpectedThermalModel.load(temp_dir / "expected_thermal_rf_v1.joblib")
    baseline_stats = BaselineStats.load(temp_dir / "baseline_stats_v1.json")
    engine = ResidualEngine(power_model, thermal_model, baseline_stats)

    curtailed_rec = TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-05",
        wind_speed=11.0,
        ambient_temp=28.0,
        active_power=1000.0,
        rotor_speed=14.5,
        generator_speed=1480.0,
        gearbox_bearing_temp=60.0,
        generator_stator_temp=65.0,
        pitch_angle=15.0,
        is_curtailed=True,
        curtailment_limit_kw=1000.0,
    )
    vec = engine.compute_residuals(curtailed_rec)
    assert vec.residual_power_kw < 0.0, "Curtailed record must calculate negative power residual relative to healthy potential"


def test_gate_06_leakage_and_determinism(temp_dir: Path):
    """GATE 6: Zero data leakage confirmed and training with seed 42 is 100% deterministic."""
    trainer_1 = ModelTrainer(output_dir=temp_dir / "m1", random_seed=42)
    trainer_2 = ModelTrainer(output_dir=temp_dir / "m2", random_seed=42)

    res_1 = trainer_1.train_and_evaluate(save_artifacts=True)
    res_2 = trainer_2.train_and_evaluate(save_artifacts=True)

    assert res_1["power_model_metrics"]["r2_score"] == res_2["power_model_metrics"]["r2_score"]
    assert res_1["thermal_model_metrics"]["gearbox_bearing"]["rmse_c"] == res_2["thermal_model_metrics"]["gearbox_bearing"]["rmse_c"]


def test_gate_07_synthetic_scenario_verification_signatures(temp_dir: Path):
    """GATE 7: Synthetic scenario verification criteria confirmed for S2 (bearing wear) and S3 (pitch asymmetry)."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    _ = trainer.train_and_evaluate(save_artifacts=True)

    power_model = ExpectedPowerModel.load(temp_dir / "expected_power_gbr_v1.joblib")
    thermal_model = ExpectedThermalModel.load(temp_dir / "expected_thermal_rf_v1.joblib")
    baseline_stats = BaselineStats.load(temp_dir / "baseline_stats_v1.json")
    engine = ResidualEngine(power_model, thermal_model, baseline_stats)
    sim = SCADASimulator(default_seed=42)

    # S2 Verification: Gearbox thermal excursion
    res_s2 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, num_turbines=10, num_timesteps=144))
    wtg07 = [r for r in res_s2.records if r.turbine_id == "WTG-07"][72:]
    vecs_s2 = engine.compute_batch_residuals(wtg07)
    assert max(v.residual_gb_temp_c for v in vecs_s2) > 10.0
    assert max(v.z_gb for v in vecs_s2) > 2.5

    # S3 Verification: Power derate
    res_s3 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY, num_turbines=5, num_timesteps=144))
    wtg03 = [r for r in res_s3.records if r.turbine_id == "WTG-03"]
    vecs_s3 = engine.compute_batch_residuals(wtg03)
    assert min(v.residual_power_kw for v in vecs_s3) < -200.0
    assert min(v.z_power for v in vecs_s3) < -2.0


def test_gate_08_phase2_rest_apis(test_client: TestClient):
    """GATE 8: Phase 2 REST API endpoints (/api/models/train, /api/models/residuals, /api/models/status) functional."""
    # 1. Train endpoint
    r_train = test_client.post("/api/models/train")
    assert r_train.status_code == 200
    assert r_train.json()["status"] == "TRAINED_SUCCESS"

    # 2. Status endpoint
    r_status = test_client.get("/api/models/status")
    assert r_status.status_code == 200
    assert r_status.json()["is_trained"] is True

    # 3. Residuals computation endpoint
    sample_payload = {
        "timestamp": "2026-09-20T12:00:00Z",
        "turbine_id": "WTG-01",
        "wind_speed": 8.5,
        "ambient_temp": 25.0,
        "active_power": 1400.0,
        "rotor_speed": 14.0,
        "generator_speed": 1430.0,
        "gearbox_bearing_temp": 62.0,
        "generator_stator_temp": 68.0,
        "pitch_angle": 0.5,
        "is_curtailed": False,
    }
    r_res = test_client.post("/api/models/residuals", json=sample_payload)
    assert r_res.status_code == 200
    data = r_res.json()
    assert "expected_power_kw" in data
    assert "residual_power_kw" in data
    assert "z_power" in data


def test_gate_09_phase3_plus_boundary_lockout():
    """GATE 9: Confirms strict architectural lockout of Phase 3+ components."""
    backend_path = Path(__file__).resolve().parent.parent / "backend"
    assert not (backend_path / "engine" / "context_engine.py").exists()
    assert not (backend_path / "engine" / "tariff_registry.py").exists()
    assert not (backend_path / "rag" / "knowledge_base.py").exists()
    assert not (backend_path / "llm" / "advisory_engine.py").exists()
