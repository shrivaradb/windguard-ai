"""Unit Tests for Curtailment Handling in Machine Learning Models (TEST-ML-CURT-01).

Source: docs/09_technical_design.md §2.1, docs/11_ai_ml_design.md §1, §3, docs/PHASE_2_SCOPE_REVIEW.md §8.
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
from backend.models.residual_engine import BaselineStats, ResidualEngine
from backend.models.thermal_model import ExpectedThermalModel
from backend.models.trainer import ModelTrainer


def test_curtailment_exclusion_from_training_dataset():
    """TEST-ML-CURT-01: Verifies that curtailed records are strictly excluded from the training dataset."""
    trainer = ModelTrainer(random_seed=42)
    # Generate mixed dataset containing curtailment
    sim = SCADASimulator(default_seed=42)
    res_s4 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE, num_turbines=10, num_timesteps=72))

    # Verify S4 contains curtailed records
    assert any(r.is_curtailed for r in res_s4.records)

    # Pass to trainer data loader filter
    clean_recs = trainer.load_or_generate_training_data(dataset_records=res_s4.records)

    # Verify zero curtailed records survived the training filter
    assert len(clean_recs) > 0
    assert all(not r.is_curtailed for r in clean_recs), "Curtailed records MUST NOT be present in training dataset"


def test_expected_power_estimates_physical_potential_during_curtailment(temp_dir: Path):
    """Verifies that during inference, curtailed records compute full physical capability and negative residual."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    _ = trainer.train_and_evaluate(save_artifacts=True)

    power_model = ExpectedPowerModel.load(temp_dir / "expected_power_gbr_v1.joblib")
    thermal_model = ExpectedThermalModel.load(temp_dir / "expected_thermal_rf_v1.joblib")
    baseline_stats = BaselineStats.load(temp_dir / "baseline_stats_v1.json")
    engine = ResidualEngine(power_model, thermal_model, baseline_stats)

    # Curtailed Telemetry: Wind is 10.5 m/s (rated potential ~1700 kW), but active power is capped at 1000 kW
    curtailed_record = TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-04",
        wind_speed=10.5,
        ambient_temp=30.0,
        active_power=1000.0,  # Grid capped
        rotor_speed=14.0,
        generator_speed=1430.0,
        gearbox_bearing_temp=62.0,
        generator_stator_temp=68.0,
        pitch_angle=15.0,  # Feathered to shed power
        is_curtailed=True,
        curtailment_limit_kw=1000.0,
    )

    vector = engine.compute_residuals(curtailed_record)

    # The expected power should reflect healthy aerodynamic potential
    # Power residual should be negative due to deliberate curtailment
    assert vector.residual_power_kw < 0.0, f"Expected negative residual due to power cap, got {vector.residual_power_kw}"
    assert vector.z_power < -1.5, f"Expected significant negative z-score during curtailment, got {vector.z_power}"
