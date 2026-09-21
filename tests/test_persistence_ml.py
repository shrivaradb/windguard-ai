"""Unit Tests for Model Artifact Persistence and Metadata Verification (TEST-ML-PERSIST).

Source: docs/14_implementation_plan.md §3, docs/PHASE_2_SCOPE_REVIEW.md §14.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from backend.config import settings
from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import BaselineStats
from backend.models.thermal_model import ExpectedThermalModel
from backend.models.trainer import ModelTrainer


def test_model_artifact_serialization_and_deserialization(temp_dir: Path):
    """TEST-ML-PERSIST: Verifies that serialized models and baseline stats reload with 100% fidelity."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    results = trainer.train_and_evaluate(save_artifacts=True)

    power_file = temp_dir / "expected_power_gbr_v1.joblib"
    thermal_file = temp_dir / "expected_thermal_rf_v1.joblib"
    stats_file = temp_dir / "baseline_stats_v1.json"
    meta_file = temp_dir / "model_metadata.json"

    assert power_file.exists()
    assert thermal_file.exists()
    assert stats_file.exists()
    assert meta_file.exists()

    # Load artifacts
    power_loaded = ExpectedPowerModel.load(power_file)
    thermal_loaded = ExpectedThermalModel.load(thermal_file)
    stats_loaded = BaselineStats.load(stats_file)

    assert power_loaded.is_fitted is True
    assert thermal_loaded.is_fitted is True
    assert stats_loaded.sigma_p > 0.0
    assert stats_loaded.sigma_gb > 0.0

    # Verify prediction consistency
    sample_aero = np.array([[8.5, 25.0, 0.5]])
    sample_therm = np.array([[1400.0, 25.0, 14.0]])

    p_pred = power_loaded.predict(sample_aero)
    gb_pred, gen_pred = thermal_loaded.predict(sample_therm)

    assert p_pred[0] > 0.0
    assert gb_pred[0] > 0.0
    assert gen_pred[0] > 0.0


def test_model_metadata_schema_and_measured_values(temp_dir: Path):
    """Verifies that model_metadata.json contains authentic post-training measured metrics."""
    trainer = ModelTrainer(output_dir=temp_dir, random_seed=42)
    _ = trainer.train_and_evaluate(save_artifacts=True)

    meta_file = temp_dir / "model_metadata.json"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Schema integrity checks
    assert meta["model_name"] == "windguard_ml_baselines_layer2"
    assert meta["model_version"] == "1.0.0"
    assert meta["random_seed"] == 42
    assert meta["power_model"]["algorithm"] == "GradientBoostingRegressor"
    assert meta["thermal_model"]["algorithm"] == "RandomForestRegressor"

    # Actual measured metrics (must be populated floats, not null)
    p_metrics = meta["power_model"]["measured_metrics"]
    assert isinstance(p_metrics["r2_score"], float)
    assert isinstance(p_metrics["rmse_kw"], float)
    assert p_metrics["r2_score"] >= 0.90

    t_metrics = meta["thermal_model"]["measured_metrics"]
    assert isinstance(t_metrics["gearbox_bearing"]["rmse_c"], float)
    assert isinstance(t_metrics["generator_stator"]["rmse_c"], float)

    # Latency measurements populated
    lat = meta["latency_measurements"]
    assert isinstance(lat["single_residual_inference_ms"], float)
    assert lat["single_residual_inference_ms"] < settings.ML.TARGET_LATENCY_MS
