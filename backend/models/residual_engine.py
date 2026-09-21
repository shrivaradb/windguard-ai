"""Deterministic Residual Calculation and Standardized Anomaly Engine for WindGuard AI.

Source of Truth:
- docs/09_technical_design.md §2.2
- docs/11_ai_ml_design.md §2.1–§2.3
- docs/PHASE_2_SCOPE_REVIEW.md §5

Calculates raw physical residuals, standardized z-scores, and canonical 2.5-sigma
statistical persistence over a 6-step sliding window (1 hour).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
from pydantic import BaseModel, Field

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.models.expected_power import ExpectedPowerModel
from backend.models.thermal_model import ExpectedThermalModel


class BaselineStats(BaseModel):
    """Calibrated empirical baseline mean and standard deviation from healthy validation data."""

    mu_p: float = Field(default=0.0, description="Active power residual mean (kW)")
    sigma_p: float = Field(default=45.0, description="Active power residual standard deviation (kW)")
    mu_gb: float = Field(default=0.0, description="Gearbox bearing temp residual mean (°C)")
    sigma_gb: float = Field(default=2.5, description="Gearbox bearing temp residual standard deviation (°C)")
    mu_gen: float = Field(default=0.0, description="Generator stator temp residual mean (°C)")
    sigma_gen: float = Field(default=3.0, description="Generator stator temp residual standard deviation (°C)")

    def save(self, filepath: Union[str, Path]) -> None:
        """Serializes baseline statistics to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "BaselineStats":
        """Loads baseline statistics from JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"BaselineStats file not found at: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


class ResidualVector(BaseModel):
    """Canonical Residual Output Vector schema documented in docs/09_technical_design.md §2.2."""

    expected_power_kw: float = Field(..., description="Expected healthy active power (kW)")
    residual_power_kw: float = Field(..., description="Raw power residual: P_act - P_exp (kW)")
    z_power: float = Field(..., description="Standardized active power z-score")

    expected_gb_temp_c: float = Field(..., description="Expected gearbox bearing temp (°C)")
    residual_gb_temp_c: float = Field(..., description="Raw gearbox thermal residual: T_act - T_exp (°C)")
    z_gb: float = Field(..., description="Standardized gearbox bearing thermal z-score")

    expected_gen_temp_c: float = Field(..., description="Expected generator stator temp (°C)")
    residual_gen_temp_c: float = Field(..., description="Raw generator thermal residual: T_act - T_exp (°C)")
    z_gen: float = Field(..., description="Standardized generator stator thermal z-score")


class ResidualEngine:
    """Computes physics-informed residuals, standardized z-scores, and canonical persistence."""

    def __init__(
        self,
        power_model: ExpectedPowerModel,
        thermal_model: ExpectedThermalModel,
        baseline_stats: Optional[BaselineStats] = None,
        persistence_threshold: float = 2.5,
        persistence_window: int = 6,
        persistence_ratio: float = 0.80,
    ):
        self.power_model = power_model
        self.thermal_model = thermal_model
        self.baseline_stats = baseline_stats or BaselineStats()
        self.persistence_threshold = persistence_threshold
        self.persistence_window = persistence_window
        self.persistence_ratio = persistence_ratio

    def compute_residuals(self, telemetry: TelemetryRecord) -> ResidualVector:
        """Computes expected baselines, physical residuals, and standardized z-scores for a single record.

        Args:
            telemetry: Canonical TelemetryRecord.

        Returns:
            ResidualVector containing all analytical residuals and normalized z-scores.
        """
        # 1. Expected baselines
        p_exp = self.power_model.predict_record(telemetry)
        t_gb_exp, t_gen_exp = self.thermal_model.predict_record(telemetry)

        # 2. Raw physical residuals
        r_p = round(telemetry.active_power - p_exp, 2)
        r_gb = round(telemetry.gearbox_bearing_temp - t_gb_exp, 2)
        r_gen = round(telemetry.generator_stator_temp - t_gen_exp, 2)

        # 3. Standardized z-scores with deterministic zero-division protection
        sigma_p = max(self.baseline_stats.sigma_p, 1e-6)
        sigma_gb = max(self.baseline_stats.sigma_gb, 1e-6)
        sigma_gen = max(self.baseline_stats.sigma_gen, 1e-6)

        z_p = round((r_p - self.baseline_stats.mu_p) / sigma_p, 2)
        z_gb = round((r_gb - self.baseline_stats.mu_gb) / sigma_gb, 2)
        z_gen = round((r_gen - self.baseline_stats.mu_gen) / sigma_gen, 2)

        return ResidualVector(
            expected_power_kw=round(p_exp, 2),
            residual_power_kw=r_p,
            z_power=z_p,
            expected_gb_temp_c=round(t_gb_exp, 2),
            residual_gb_temp_c=r_gb,
            z_gb=z_gb,
            expected_gen_temp_c=round(t_gen_exp, 2),
            residual_gen_temp_c=r_gen,
            z_gen=z_gen,
        )

    def compute_batch_residuals(
        self, records: List[TelemetryRecord]
    ) -> List[ResidualVector]:
        """Vectorized batch computation of residuals for a collection of telemetry records.

        Args:
            records: List of TelemetryRecord objects.

        Returns:
            List of ResidualVector objects.
        """
        if not records:
            return []

        # Vectorized feature matrix extraction
        aero_features = np.array(
            [[r.wind_speed, r.ambient_temp, r.pitch_angle] for r in records],
            dtype=np.float64,
        )
        therm_features = np.array(
            [[r.active_power, r.ambient_temp, r.rotor_speed] for r in records],
            dtype=np.float64,
        )

        p_exp_arr = self.power_model.predict(aero_features)
        t_gb_exp_arr, t_gen_exp_arr = self.thermal_model.predict(therm_features)

        sigma_p = max(self.baseline_stats.sigma_p, 1e-6)
        sigma_gb = max(self.baseline_stats.sigma_gb, 1e-6)
        sigma_gen = max(self.baseline_stats.sigma_gen, 1e-6)

        results: List[ResidualVector] = []
        for i, rec in enumerate(records):
            p_exp = float(p_exp_arr[i])
            t_gb_exp = float(t_gb_exp_arr[i])
            t_gen_exp = float(t_gen_exp_arr[i])

            r_p = rec.active_power - p_exp
            r_gb = rec.gearbox_bearing_temp - t_gb_exp
            r_gen = rec.generator_stator_temp - t_gen_exp

            z_p = (r_p - self.baseline_stats.mu_p) / sigma_p
            z_gb = (r_gb - self.baseline_stats.mu_gb) / sigma_gb
            z_gen = (r_gen - self.baseline_stats.mu_gen) / sigma_gen

            results.append(
                ResidualVector(
                    expected_power_kw=round(p_exp, 2),
                    residual_power_kw=round(r_p, 2),
                    z_power=round(z_p, 2),
                    expected_gb_temp_c=round(t_gb_exp, 2),
                    residual_gb_temp_c=round(r_gb, 2),
                    z_gb=round(z_gb, 2),
                    expected_gen_temp_c=round(t_gen_exp, 2),
                    residual_gen_temp_c=round(r_gen, 2),
                    z_gen=round(z_gen, 2),
                )
            )

        return results

    def check_persistence(
        self,
        z_series: List[float],
        window: Optional[int] = None,
        threshold: Optional[float] = None,
        ratio_threshold: Optional[float] = None,
    ) -> bool:
        """Evaluates canonical 2.5-sigma temporal persistence over a sliding window.

        Formulation (docs/11 §2.3, docs/PHASE_2_SCOPE_REVIEW.md §5.1):
            Persistence(t) = (1/W) * sum( I(|z_i(t-k)| >= 2.5) ) >= 0.80
            (At least 5 of the last 6 intervals exceeding 2.5 sigma).

        Args:
            z_series: List of recent z-scores in chronological order.
            window: Number of consecutive intervals (default: 6 = 1 hour).
            threshold: Standardized sigma threshold (canonical default: 2.5).
            ratio_threshold: Minimum ratio of exceeding intervals (default: 0.80).

        Returns:
            True if anomaly is persistent, False otherwise.
        """
        w = window or self.persistence_window
        th = threshold or self.persistence_threshold
        ratio = ratio_threshold or self.persistence_ratio

        if len(z_series) < w:
            return False

        recent_window = z_series[-w:]
        exceed_count = sum(1 for z in recent_window if abs(z) >= th)
        exceed_ratio = exceed_count / float(w)

        return exceed_ratio >= ratio
