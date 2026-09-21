"""Expected Component Thermal Baselines Regression Model for WindGuard AI.

Source of Truth:
- docs/09_technical_design.md §2.2
- docs/11_ai_ml_design.md §2.2, §4
- docs/PHASE_2_SCOPE_REVIEW.md §4

Canonical Algorithm:
- sklearn.ensemble.RandomForestRegressor(
      n_estimators=100,
      max_depth=10,
      random_state=42
  )

Predicts healthy steady-state thermal baselines for gearbox high-speed bearings
and generator stator windings:
    T_GB_hat  = g(active_power, ambient_temp, rotor_speed)
    T_Gen_hat = h(active_power, ambient_temp, rotor_speed)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from backend.config import settings
from backend.data.schema import TelemetryRecord


# Canonical thermal feature set strictly locked for Phase 2
CANONICAL_THERMAL_FEATURES: List[str] = [
    "active_power",
    "ambient_temp",
    "rotor_speed",
]

# Forbidden features that must never be used as inputs
FORBIDDEN_THERMAL_PREDICTIVE_FEATURES: List[str] = [
    "gearbox_bearing_temp",
    "generator_stator_temp",
    "is_curtailed",
    "is_fault",
    "fault_type",
    "affected_subsystem",
    "scenario_id",
    "scenario_name",
    "quality_flags",
]


class ExpectedThermalModel:
    """Multi-output thermal baseline regressor predicting healthy component temperatures."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 10,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self.feature_names = list(CANONICAL_THERMAL_FEATURES)
        self.target_variables = ["gearbox_bearing_temp", "generator_stator_temp"]

        # Canonical multi-output RandomForest estimator
        self.model: RandomForestRegressor = RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=self.random_state,
        )
        self.is_fitted: bool = False

    def _validate_feature_inputs(self, df: pd.DataFrame) -> None:
        """Validates that all canonical features exist and no forbidden features leak into inputs."""
        for forbidden in FORBIDDEN_THERMAL_PREDICTIVE_FEATURES:
            if forbidden in df.columns:
                raise ValueError(
                    f"Data Leakage Violation: Forbidden column '{forbidden}' detected in feature matrix."
                )

        missing_features = [f for f in self.feature_names if f not in df.columns]
        if missing_features:
            raise ValueError(
                f"Missing canonical thermal features: {missing_features}. Required: {self.feature_names}"
            )

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray, List[List[float]]],
        y_gb: Union[pd.Series, np.ndarray, List[float]],
        y_gen: Union[pd.Series, np.ndarray, List[float]],
    ) -> "ExpectedThermalModel":
        """Fits the RandomForest thermal baselines on healthy operational training data.

        Args:
            X: Input feature matrix matching CANONICAL_THERMAL_FEATURES.
            y_gb: Target gearbox bearing temperatures in °C.
            y_gen: Target generator stator temperatures in °C.
        """
        if isinstance(X, pd.DataFrame):
            self._validate_feature_inputs(X)
            X_mat = X[self.feature_names].values
        else:
            X_mat = np.asarray(X, dtype=np.float64)
            if X_mat.ndim != 2 or X_mat.shape[1] != len(self.feature_names):
                raise ValueError(
                    f"Expected input array with shape (N, {len(self.feature_names)}), got {X_mat.shape}"
                )

        y_gb_vec = np.asarray(y_gb, dtype=np.float64).ravel()
        y_gen_vec = np.asarray(y_gen, dtype=np.float64).ravel()

        if len(X_mat) != len(y_gb_vec) or len(X_mat) != len(y_gen_vec):
            raise ValueError(
                f"Length mismatch: X has {len(X_mat)} samples, y_gb has {len(y_gb_vec)}, y_gen has {len(y_gen_vec)}."
            )

        y_mat = np.column_stack([y_gb_vec, y_gen_vec])
        self.model.fit(X_mat, y_mat)
        self.is_fitted = True
        return self

    def predict(
        self, X: Union[pd.DataFrame, np.ndarray, List[List[float]]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predicts expected component temperatures in °C.

        Args:
            X: Input feature matrix.

        Returns:
            Tuple of (expected_gb_temp, expected_gen_temp) numpy arrays in °C.
        """
        if not self.is_fitted:
            raise RuntimeError("ExpectedThermalModel must be fitted before calling predict().")

        if isinstance(X, pd.DataFrame):
            self._validate_feature_inputs(X)
            X_mat = X[self.feature_names].values
        else:
            X_mat = np.asarray(X, dtype=np.float64)
            if X_mat.ndim == 1:
                X_mat = X_mat.reshape(1, -1)
            if X_mat.shape[1] != len(self.feature_names):
                raise ValueError(
                    f"Expected input array with shape (N, {len(self.feature_names)}), got {X_mat.shape}"
                )

        preds = self.model.predict(X_mat)
        pred_gb = preds[:, 0]
        pred_gen = preds[:, 1]

        # Physical clamping within plausible thermocouple bounds
        pred_gb_clamped = np.clip(
            pred_gb,
            settings.VALIDATION.GEARBOX_BEARING_TEMP_MIN,
            settings.VALIDATION.GEARBOX_BEARING_TEMP_MAX,
        )
        pred_gen_clamped = np.clip(
            pred_gen,
            settings.VALIDATION.GENERATOR_STATOR_TEMP_MIN,
            settings.VALIDATION.GENERATOR_STATOR_TEMP_MAX,
        )

        return pred_gb_clamped, pred_gen_clamped

    def predict_record(self, record: TelemetryRecord) -> Tuple[float, float]:
        """Convenience method to predict expected component temperatures for a single record.

        Args:
            record: Canonical TelemetryRecord.

        Returns:
            Tuple of (expected_gb_temp_c, expected_gen_temp_c) rounded to 2 decimal places.
        """
        features = [[record.active_power, record.ambient_temp, record.rotor_speed]]
        pred_gb, pred_gen = self.predict(features)
        return float(round(pred_gb[0], 2)), float(round(pred_gen[0], 2))

    def save(self, filepath: Union[str, Path]) -> None:
        """Serializes trained thermal model artifact to disk via joblib."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted ExpectedThermalModel.")
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "feature_names": self.feature_names,
                "target_variables": self.target_variables,
                "hyperparameters": {
                    "n_estimators": self.n_estimators,
                    "max_depth": self.max_depth,
                    "random_state": self.random_state,
                },
                "is_fitted": self.is_fitted,
            },
            path,
        )

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "ExpectedThermalModel":
        """Loads serialized model artifact from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {path}")

        data = joblib.load(path)
        instance = cls(
            n_estimators=data["hyperparameters"]["n_estimators"],
            max_depth=data["hyperparameters"]["max_depth"],
            random_state=data["hyperparameters"]["random_state"],
        )
        instance.model = data["model"]
        instance.feature_names = data["feature_names"]
        instance.target_variables = data["target_variables"]
        instance.is_fitted = data["is_fitted"]
        return instance
