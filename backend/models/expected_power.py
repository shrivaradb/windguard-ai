"""Expected Power Curve Regression Model for WindGuard AI.

Source of Truth:
- docs/09_technical_design.md §2.2
- docs/11_ai_ml_design.md §2.1, §4
- docs/PHASE_2_SCOPE_REVIEW.md §3

Canonical Algorithm:
- sklearn.ensemble.GradientBoostingRegressor(
      n_estimators=100,
      max_depth=5,
      learning_rate=0.1,
      random_state=42
  )

Predicts healthy aerodynamic expected active power:
    P_hat = f(wind_speed, ambient_temp, pitch_angle)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from backend.config import settings
from backend.data.schema import TelemetryRecord


# Canonical feature set strictly locked for Phase 2
CANONICAL_POWER_FEATURES: List[str] = [
    "wind_speed",
    "ambient_temp",
    "pitch_angle",
]

# Forbidden features that must never be used for prediction
FORBIDDEN_PREDICTIVE_FEATURES: List[str] = [
    "active_power",
    "is_curtailed",
    "is_fault",
    "fault_type",
    "affected_subsystem",
    "scenario_id",
    "scenario_name",
    "quality_flags",
]


class ExpectedPowerModel:
    """Non-linear empirical power curve regressor predicting healthy expected active power."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.1,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.feature_names = list(CANONICAL_POWER_FEATURES)
        self.target_variable = "active_power"

        self.model: GradientBoostingRegressor = GradientBoostingRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
        )
        self.is_fitted: bool = False

    def _validate_feature_inputs(self, df: pd.DataFrame) -> None:
        """Validates that all canonical features exist and no forbidden features leak into inputs."""
        for forbidden in FORBIDDEN_PREDICTIVE_FEATURES:
            if forbidden in df.columns:
                raise ValueError(
                    f"Data Leakage Violation: Forbidden column '{forbidden}' detected in feature matrix."
                )

        missing_features = [f for f in self.feature_names if f not in df.columns]
        if missing_features:
            raise ValueError(
                f"Missing canonical power features: {missing_features}. Required: {self.feature_names}"
            )

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray, List[List[float]]],
        y: Union[pd.Series, np.ndarray, List[float]],
    ) -> "ExpectedPowerModel":
        """Fits the GradientBoostingRegressor on healthy aerodynamic training data.

        Args:
            X: Input feature matrix (DataFrame or array matching CANONICAL_POWER_FEATURES).
            y: Target active power values in kW.
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

        y_vec = np.asarray(y, dtype=np.float64).ravel()
        if len(X_mat) != len(y_vec):
            raise ValueError(
                f"Length mismatch: X has {len(X_mat)} samples, y has {len(y_vec)} samples."
            )

        self.model.fit(X_mat, y_vec)
        self.is_fitted = True
        return self

    def predict(
        self, X: Union[pd.DataFrame, np.ndarray, List[List[float]]]
    ) -> np.ndarray:
        """Predicts expected active power in kW.

        Args:
            X: Input feature matrix.

        Returns:
            np.ndarray of predicted expected power in kW (clamped to physical bounds [0, 2750]).
        """
        if not self.is_fitted:
            raise RuntimeError("ExpectedPowerModel must be fitted before calling predict().")

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
        # Physical boundary clamp: aerodynamic power is non-negative and capped by maximum turbine rating
        return np.clip(preds, 0.0, settings.VALIDATION.ACTIVE_POWER_MAX)

    def predict_record(self, record: TelemetryRecord) -> float:
        """Convenience method to predict expected power for a single canonical TelemetryRecord.

        Args:
            record: Canonical TelemetryRecord.

        Returns:
            Expected power in kW as a float.
        """
        features = [[record.wind_speed, record.ambient_temp, record.pitch_angle]]
        pred = self.predict(features)[0]
        return float(round(pred, 2))

    def save(self, filepath: Union[str, Path]) -> None:
        """Serializes trained model artifact to disk via joblib."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted ExpectedPowerModel.")
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "feature_names": self.feature_names,
                "target_variable": self.target_variable,
                "hyperparameters": {
                    "n_estimators": self.n_estimators,
                    "max_depth": self.max_depth,
                    "learning_rate": self.learning_rate,
                    "random_state": self.random_state,
                },
                "is_fitted": self.is_fitted,
            },
            path,
        )

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "ExpectedPowerModel":
        """Loads serialized model artifact from disk."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {path}")

        data = joblib.load(path)
        instance = cls(
            n_estimators=data["hyperparameters"]["n_estimators"],
            max_depth=data["hyperparameters"]["max_depth"],
            learning_rate=data["hyperparameters"]["learning_rate"],
            random_state=data["hyperparameters"]["random_state"],
        )
        instance.model = data["model"]
        instance.feature_names = data["feature_names"]
        instance.target_variable = data["target_variable"]
        instance.is_fitted = data["is_fitted"]
        return instance
