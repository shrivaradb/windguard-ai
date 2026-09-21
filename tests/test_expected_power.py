"""Unit and Benchmark Tests for ExpectedPowerModel (TEST-ML-PWR-01, TEST-ML-PWR-02).

Source: docs/09_technical_design.md §2.2, docs/11_ai_ml_design.md §2.1, §4, §6.1.
"""

import time
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.models.expected_power import (
    CANONICAL_POWER_FEATURES,
    ExpectedPowerModel,
)
from backend.models.trainer import ModelTrainer


def test_expected_power_model_instantiation():
    """Verifies default parameters, canonical algorithm, and features."""
    model = ExpectedPowerModel(random_state=42)
    assert model.n_estimators == 100
    assert model.max_depth == 5
    assert model.learning_rate == 0.1
    assert model.random_state == 42
    assert model.feature_names == ["wind_speed", "ambient_temp", "pitch_angle"]
    assert model.is_fitted is False


def test_expected_power_model_training_and_regression_metrics():
    """TEST-ML-PWR-01: Verifies power model fitting and regression accuracy on holdout test set."""
    trainer = ModelTrainer(random_seed=42)
    results = trainer.train_and_evaluate(save_artifacts=False)

    metrics = results["power_model_metrics"]
    # Verify against documented Engineering Targets
    assert metrics["r2_score"] >= settings.ML.TARGET_POWER_R2, f"Expected R² >= 0.95, got {metrics['r2_score']}"
    assert metrics["rmse_kw"] <= settings.ML.TARGET_POWER_RMSE_KW, f"Expected RMSE <= 45 kW, got {metrics['rmse_kw']}"
    assert metrics["mae_kw"] <= settings.ML.TARGET_POWER_MAE_KW, f"Expected MAE <= 30 kW, got {metrics['mae_kw']}"


def test_expected_power_curve_regions_behavior():
    """Verifies expected aerodynamic power predictions across operational wind regions."""
    trainer = ModelTrainer(random_seed=42)
    records = trainer.load_or_generate_training_data()
    train_recs, _, _ = trainer.chronological_split(records)

    X_train = np.array([[r.wind_speed, r.ambient_temp, r.pitch_angle] for r in train_recs])
    y_train = np.array([r.active_power for r in train_recs])

    model = ExpectedPowerModel(random_state=42)
    model.fit(X_train, y_train)

    # Region I: Below Cut-in (2.0 m/s) -> Lower power than partial load
    pred_r1 = model.predict([[2.0, 25.0, 0.0]])[0]
    pred_8ms = model.predict([[8.0, 25.0, 0.5]])[0]
    pred_10ms = model.predict([[10.0, 25.0, 0.5]])[0]
    assert pred_r1 < pred_8ms

    # Region II: Partial Load (8.0 m/s vs 10.0 m/s) -> Cubic scaling monotonicity
    assert pred_10ms > pred_8ms > 0.0

    # Region III: Rated Wind (14.0 m/s, pitch regulated) -> Rated power (~2000 kW)
    pred_14ms = model.predict([[14.0, 25.0, 4.1]])[0]
    assert 1850.0 <= pred_14ms <= 2050.0


def test_expected_power_inference_latency():
    """TEST-ML-PWR-02: Verifies single-record inference latency on CPU is under 1.0 ms."""
    model = ExpectedPowerModel(random_state=42)
    # Fit on synthetic minimal data
    X = np.random.uniform(3.0, 20.0, (100, 3))
    y = np.clip(2000.0 * ((X[:, 0] - 3.0) / 9.0) ** 3, 0.0, 2000.0)
    model.fit(X, y)

    sample = [[8.5, 28.0, 0.5]]
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = model.predict(sample)
    avg_latency_ms = ((time.perf_counter() - t0) / n_iters) * 1000.0

    assert avg_latency_ms < settings.ML.TARGET_LATENCY_MS, f"Expected latency < 1.0 ms, got {avg_latency_ms:.4f} ms"


def test_expected_power_predict_record():
    """Verifies predict_record interface using canonical TelemetryRecord."""
    trainer = ModelTrainer(random_seed=42)
    records = trainer.load_or_generate_training_data()
    train_recs, _, _ = trainer.chronological_split(records)

    X_train = np.array([[r.wind_speed, r.ambient_temp, r.pitch_angle] for r in train_recs])
    y_train = np.array([r.active_power for r in train_recs])

    model = ExpectedPowerModel(random_state=42)
    model.fit(X_train, y_train)

    rec = train_recs[0]
    p_exp = model.predict_record(rec)
    assert isinstance(p_exp, float)
    assert p_exp >= 0.0


def test_expected_power_forbidden_features_leakage_rejection():
    """Verifies that passing forbidden features raises an explicit ValueError."""
    model = ExpectedPowerModel(random_state=42)
    leaked_df = pd.DataFrame({
        "wind_speed": [8.0, 9.0],
        "ambient_temp": [25.0, 26.0],
        "pitch_angle": [0.5, 0.5],
        "is_fault": [False, False],  # Forbidden feature
    })
    with pytest.raises(ValueError, match="Data Leakage Violation"):
        model._validate_feature_inputs(leaked_df)
