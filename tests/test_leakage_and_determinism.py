"""Data Leakage Audit and Deterministic Training Tests (TEST-ML-LEAK-01, TEST-ML-DET-01).

Source: docs/08_system_architecture.md §1, docs/11_ai_ml_design.md §7, docs/PHASE_2_SCOPE_REVIEW.md §13, §18.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.models.expected_power import (
    CANONICAL_POWER_FEATURES,
    FORBIDDEN_PREDICTIVE_FEATURES,
    ExpectedPowerModel,
)
from backend.models.thermal_model import (
    CANONICAL_THERMAL_FEATURES,
    FORBIDDEN_THERMAL_PREDICTIVE_FEATURES,
    ExpectedThermalModel,
)
from backend.models.trainer import ModelTrainer


def test_leakage_audit_forbidden_features_rejected():
    """TEST-ML-LEAK-01: Verifies that passing any forbidden label or metadata feature triggers a hard error."""
    power_model = ExpectedPowerModel(random_state=42)
    thermal_model = ExpectedThermalModel(random_state=42)

    # All forbidden labels that must never contaminate model inputs
    forbidden_columns = [
        "is_fault",
        "fault_type",
        "affected_subsystem",
        "scenario_id",
        "scenario_name",
        "quality_flags",
        "is_curtailed",
    ]

    for col in forbidden_columns:
        # Check power model input validation
        df_power = pd.DataFrame({
            "wind_speed": [8.0, 9.0],
            "ambient_temp": [25.0, 26.0],
            "pitch_angle": [0.5, 0.5],
            col: [False, False] if "is" in col else ["None", "None"],
        })
        with pytest.raises(ValueError, match="Data Leakage Violation"):
            power_model.fit(df_power, np.array([1000.0, 1200.0]))

        # Check thermal model input validation
        df_therm = pd.DataFrame({
            "active_power": [1000.0, 1200.0],
            "ambient_temp": [25.0, 26.0],
            "rotor_speed": [12.0, 13.0],
            col: [False, False] if "is" in col else ["None", "None"],
        })
        with pytest.raises(ValueError, match="Data Leakage Violation"):
            thermal_model.fit(df_therm, np.array([60.0, 62.0]), np.array([65.0, 67.0]))


def test_leakage_audit_target_variables_not_in_inputs():
    """Verifies that active_power is not in power inputs and component temps are not in thermal inputs."""
    power_model = ExpectedPowerModel(random_state=42)
    assert "active_power" not in power_model.feature_names
    assert "active_power" in FORBIDDEN_PREDICTIVE_FEATURES

    thermal_model = ExpectedThermalModel(random_state=42)
    assert "gearbox_bearing_temp" not in thermal_model.feature_names
    assert "generator_stator_temp" not in thermal_model.feature_names
    assert "gearbox_bearing_temp" in FORBIDDEN_THERMAL_PREDICTIVE_FEATURES
    assert "generator_stator_temp" in FORBIDDEN_THERMAL_PREDICTIVE_FEATURES


def test_deterministic_reproducibility_with_fixed_seed(temp_dir: Path):
    """TEST-ML-DET-01: Verifies that training with fixed seed produces identical weights, predictions, and metrics."""
    dir_a = temp_dir / "run_a"
    dir_b = temp_dir / "run_b"

    trainer_a = ModelTrainer(output_dir=dir_a, random_seed=42)
    trainer_b = ModelTrainer(output_dir=dir_b, random_seed=42)

    res_a = trainer_a.train_and_evaluate(save_artifacts=True)
    res_b = trainer_b.train_and_evaluate(save_artifacts=True)

    # 1. Exact metric matching
    assert res_a["power_model_metrics"]["r2_score"] == res_b["power_model_metrics"]["r2_score"]
    assert res_a["power_model_metrics"]["rmse_kw"] == res_b["power_model_metrics"]["rmse_kw"]
    assert res_a["thermal_model_metrics"]["gearbox_bearing"]["rmse_c"] == res_b["thermal_model_metrics"]["gearbox_bearing"]["rmse_c"]

    # 2. Exact prediction matching on fresh test input
    model_a = ExpectedPowerModel.load(dir_a / "expected_power_gbr_v1.joblib")
    model_b = ExpectedPowerModel.load(dir_b / "expected_power_gbr_v1.joblib")

    test_inputs = np.array([[8.5, 25.0, 0.5], [12.0, 30.0, 1.2], [16.0, 20.0, 8.5]])
    preds_a = model_a.predict(test_inputs)
    preds_b = model_b.predict(test_inputs)

    np.testing.assert_array_almost_equal(preds_a, preds_b, decimal=8)
