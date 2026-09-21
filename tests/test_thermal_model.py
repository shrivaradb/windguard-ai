"""Unit and Benchmark Tests for ExpectedThermalModel (TEST-ML-THM-01).

Source: docs/09_technical_design.md §2.2, docs/11_ai_ml_design.md §2.2, §4, §6.1.
"""

import time
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.models.thermal_model import (
    CANONICAL_THERMAL_FEATURES,
    ExpectedThermalModel,
)
from backend.models.trainer import ModelTrainer


def test_expected_thermal_model_instantiation():
    """Verifies default parameters, canonical algorithm, and features."""
    model = ExpectedThermalModel(random_state=42)
    assert model.n_estimators == 100
    assert model.max_depth == 10
    assert model.random_state == 42
    assert model.feature_names == ["active_power", "ambient_temp", "rotor_speed"]
    assert model.target_variables == ["gearbox_bearing_temp", "generator_stator_temp"]
    assert model.is_fitted is False


def test_expected_thermal_model_training_and_metrics():
    """TEST-ML-THM-01: Verifies thermal model fitting and accuracy on holdout test set."""
    trainer = ModelTrainer(random_seed=42)
    results = trainer.train_and_evaluate(save_artifacts=False)

    gb_metrics = results["thermal_model_metrics"]["gearbox_bearing"]
    gen_metrics = results["thermal_model_metrics"]["generator_stator"]

    # Verify Gearbox Bearing metrics against documented targets
    assert gb_metrics["rmse_c"] <= settings.ML.TARGET_THERMAL_RMSE_C, f"Expected GB RMSE <= 2.5°C, got {gb_metrics['rmse_c']}"
    assert gb_metrics["r2_score"] >= settings.ML.TARGET_THERMAL_R2, f"Expected GB R² >= 0.96, got {gb_metrics['r2_score']}"

    # Verify Generator Stator metrics against documented targets
    assert gen_metrics["rmse_c"] <= settings.ML.TARGET_THERMAL_RMSE_C, f"Expected Gen RMSE <= 2.5°C, got {gen_metrics['rmse_c']}"
    assert gen_metrics["r2_score"] >= settings.ML.TARGET_THERMAL_R2, f"Expected Gen R² >= 0.96, got {gen_metrics['r2_score']}"


def test_expected_thermal_ambient_and_load_sensitivity():
    """Verifies that thermal predictions accurately reflect ambient shifts and electrical load changes."""
    trainer = ModelTrainer(random_seed=42)
    records = trainer.load_or_generate_training_data()
    train_recs, _, _ = trainer.chronological_split(records)

    X_train = np.array([[r.active_power, r.ambient_temp, r.rotor_speed] for r in train_recs])
    y_gb = np.array([r.gearbox_bearing_temp for r in train_recs])
    y_gen = np.array([r.generator_stator_temp for r in train_recs])

    model = ExpectedThermalModel(random_state=42)
    model.fit(X_train, y_gb, y_gen)

    # 1. Electrical Load Sensitivity: 500 kW vs 1800 kW at constant 25°C ambient
    gb_low, gen_low = model.predict([[500.0, 25.0, 10.0]])
    gb_high, gen_high = model.predict([[1800.0, 25.0, 14.0]])

    assert gb_high[0] > gb_low[0], "Higher active power must yield higher expected gearbox temp"
    assert gen_high[0] > gen_low[0], "Higher active power must yield higher expected generator temp"

    # 2. Ambient Temperature Sensitivity: 24°C vs 32°C at constant 1000 kW load (within trained diurnal support)
    gb_cool, gen_cool = model.predict([[1000.0, 24.0, 12.0]])
    gb_warm, gen_warm = model.predict([[1000.0, 32.0, 12.0]])

    temp_diff_gb = gb_warm[0] - gb_cool[0]
    temp_diff_gen = gen_warm[0] - gen_cool[0]

    # Steady-state thermal rise above ambient should preserve roughly positive delta
    assert 3.0 <= temp_diff_gb <= 12.0
    assert 3.0 <= temp_diff_gen <= 12.0


def test_expected_thermal_inference_latency():
    """Verifies single-record thermal inference latency is within target threshold."""
    model = ExpectedThermalModel(random_state=42)
    X = np.random.uniform(0.0, 2000.0, (100, 3))
    y_gb = X[:, 1] + 25.0 * (X[:, 0] / 2000.0)
    y_gen = X[:, 1] + 35.0 * (X[:, 0] / 2000.0)
    model.fit(X, y_gb, y_gen)

    sample = [[1400.0, 28.0, 14.0]]
    n_iters = 100
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = model.predict(sample)
    avg_latency_ms = ((time.perf_counter() - t0) / n_iters) * 1000.0

    assert avg_latency_ms < settings.ML.TARGET_LATENCY_MS, f"Expected latency < {settings.ML.TARGET_LATENCY_MS} ms, got {avg_latency_ms:.4f} ms"


def test_expected_thermal_predict_record():
    """Verifies predict_record interface returns valid tuple of floats."""
    trainer = ModelTrainer(random_seed=42)
    records = trainer.load_or_generate_training_data()
    train_recs, _, _ = trainer.chronological_split(records)

    X_train = np.array([[r.active_power, r.ambient_temp, r.rotor_speed] for r in train_recs])
    y_gb = np.array([r.gearbox_bearing_temp for r in train_recs])
    y_gen = np.array([r.generator_stator_temp for r in train_recs])

    model = ExpectedThermalModel(random_state=42)
    model.fit(X_train, y_gb, y_gen)

    rec = train_recs[0]
    t_gb_exp, t_gen_exp = model.predict_record(rec)

    assert isinstance(t_gb_exp, float)
    assert isinstance(t_gen_exp, float)
    assert t_gb_exp >= 0.0
    assert t_gen_exp >= 0.0


def test_expected_thermal_forbidden_features_leakage_rejection():
    """Verifies that passing target or metadata columns raises an explicit ValueError."""
    model = ExpectedThermalModel(random_state=42)
    leaked_df = pd.DataFrame({
        "active_power": [1000.0, 1200.0],
        "ambient_temp": [25.0, 26.0],
        "rotor_speed": [12.0, 13.0],
        "gearbox_bearing_temp": [60.0, 62.0],  # Target leaked as input!
    })
    with pytest.raises(ValueError, match="Data Leakage Violation"):
        model._validate_feature_inputs(leaked_df)
