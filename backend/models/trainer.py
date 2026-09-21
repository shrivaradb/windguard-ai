"""Deterministic Training and Evaluation Pipeline for WindGuard AI Layer 2 ML Baselines.

Source of Truth:
- docs/11_ai_ml_design.md §6
- docs/14_implementation_plan.md §3 (Phase 2)
- docs/PHASE_2_SCOPE_REVIEW.md §6, §7, §11, §14

Enforces:
1. Primary training source: Scenario S1 Baseline Healthy Operation.
2. Strict chronological splitting (70% Train, 15% Val, 15% Test).
3. Baseline stats calibration strictly from Validation residuals.
4. Final evaluation metrics strictly from holdout Test set.
5. Generation of truthful model_metadata.json with actual measured results.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.config import settings
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import (
    BenchmarkScenarioType,
    OperatingStatus,
    SimulationConfig,
    TelemetryRecord,
)
from backend.models.expected_power import (
    CANONICAL_POWER_FEATURES,
    ExpectedPowerModel,
)
from backend.models.residual_engine import BaselineStats, ResidualEngine, ResidualVector
from backend.models.thermal_model import (
    CANONICAL_THERMAL_FEATURES,
    ExpectedThermalModel,
)


class ModelTrainer:
    """Orchestrates deterministic model training, chronological splitting, validation, and serialization."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        random_seed: int = 42,
    ):
        self.output_dir = output_dir or settings.PATHS.MODELS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.random_seed = random_seed
        self.simulator = SCADASimulator(default_seed=random_seed)

    def load_or_generate_training_data(
        self,
        dataset_records: Optional[List[TelemetryRecord]] = None,
        num_turbines: int = 10,
        num_timesteps: int = 288,
    ) -> List[TelemetryRecord]:
        """Generates or loads certified Scenario S1 Baseline Healthy telemetry.

        Filters out curtailed records and non-running states.
        """
        if dataset_records is None:
            config = SimulationConfig(
                scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY,
                num_turbines=num_turbines,
                num_timesteps=num_timesteps,
                random_seed=self.random_seed,
            )
            sim_result = self.simulator.simulate(config)
            raw_records = sim_result.records
        else:
            raw_records = dataset_records

        # Filter strictly for healthy, running, uncurtailed data
        clean_records = [
            r
            for r in raw_records
            if not r.is_curtailed
            and r.operating_status == OperatingStatus.RUNNING.value
            and r.wind_speed >= settings.VALIDATION.WIND_SPEED_MIN
            and r.active_power >= 0.0
        ]
        return clean_records

    def chronological_split(
        self,
        records: List[TelemetryRecord],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> Tuple[List[TelemetryRecord], List[TelemetryRecord], List[TelemetryRecord]]:
        """Splits records into Train (70%), Validation (15%), and Test (15%) strictly chronologically.

        DOES NOT randomly shuffle. random_state is NOT used for splitting.
        """
        total = len(records)
        if total < 20:
            raise ValueError(f"Insufficient dataset size for reliable splitting: {total} records.")

        n_train = int(total * train_ratio)
        n_val = int(total * val_ratio)

        train_set = records[:n_train]
        val_set = records[n_train : n_train + n_val]
        test_set = records[n_train + n_val :]

        return train_set, val_set, test_set

    def train_and_evaluate(
        self,
        dataset_records: Optional[List[TelemetryRecord]] = None,
        save_artifacts: bool = True,
    ) -> Dict[str, Any]:
        """Executes the full training, validation, baseline calibration, and testing pipeline.

        Returns comprehensive evaluation dictionary with actual measured metrics.
        """
        # 1. Load clean healthy data
        records = self.load_or_generate_training_data(dataset_records)
        train_recs, val_recs, test_recs = self.chronological_split(
            records,
            train_ratio=settings.ML.CHRONOLOGICAL_TRAIN_RATIO,
            val_ratio=settings.ML.CHRONOLOGICAL_VAL_RATIO,
            test_ratio=settings.ML.CHRONOLOGICAL_TEST_RATIO,
        )

        # 2. Extract feature matrices and targets
        X_train_p = np.array(
            [[r.wind_speed, r.ambient_temp, r.pitch_angle] for r in train_recs],
            dtype=np.float64,
        )
        y_train_p = np.array([r.active_power for r in train_recs], dtype=np.float64)

        X_train_t = np.array(
            [[r.active_power, r.ambient_temp, r.rotor_speed] for r in train_recs],
            dtype=np.float64,
        )
        y_train_gb = np.array(
            [r.gearbox_bearing_temp for r in train_recs], dtype=np.float64
        )
        y_train_gen = np.array(
            [r.generator_stator_temp for r in train_recs], dtype=np.float64
        )

        # 3. Fit ExpectedPowerModel (GBR) and ExpectedThermalModel (RF)
        power_model = ExpectedPowerModel(
            n_estimators=settings.ML.POWER_GBR_N_ESTIMATORS,
            max_depth=settings.ML.POWER_GBR_MAX_DEPTH,
            learning_rate=settings.ML.POWER_GBR_LEARNING_RATE,
            random_state=self.random_seed,
        )
        power_model.fit(X_train_p, y_train_p)

        thermal_model = ExpectedThermalModel(
            n_estimators=settings.ML.THERMAL_RF_N_ESTIMATORS,
            max_depth=settings.ML.THERMAL_RF_MAX_DEPTH,
            random_state=self.random_seed,
        )
        thermal_model.fit(X_train_t, y_train_gb, y_train_gen)

        # 4. Calibrate Baseline Statistics strictly on Validation set
        X_val_p = np.array(
            [[r.wind_speed, r.ambient_temp, r.pitch_angle] for r in val_recs],
            dtype=np.float64,
        )
        y_val_p = np.array([r.active_power for r in val_recs], dtype=np.float64)
        val_pred_p = power_model.predict(X_val_p)
        res_val_p = y_val_p - val_pred_p

        X_val_t = np.array(
            [[r.active_power, r.ambient_temp, r.rotor_speed] for r in val_recs],
            dtype=np.float64,
        )
        y_val_gb = np.array(
            [r.gearbox_bearing_temp for r in val_recs], dtype=np.float64
        )
        y_val_gen = np.array(
            [r.generator_stator_temp for r in val_recs], dtype=np.float64
        )
        val_pred_gb, val_pred_gen = thermal_model.predict(X_val_t)
        res_val_gb = y_val_gb - val_pred_gb
        res_val_gen = y_val_gen - val_pred_gen

        baseline_stats = BaselineStats(
            mu_p=float(round(np.mean(res_val_p), 3)),
            sigma_p=float(round(np.std(res_val_p), 3)),
            mu_gb=float(round(np.mean(res_val_gb), 3)),
            sigma_gb=float(round(np.std(res_val_gb), 3)),
            mu_gen=float(round(np.mean(res_val_gen), 3)),
            sigma_gen=float(round(np.std(res_val_gen), 3)),
        )

        # 5. Evaluate on Holdout Test Set (Unseen during training & calibration)
        X_test_p = np.array(
            [[r.wind_speed, r.ambient_temp, r.pitch_angle] for r in test_recs],
            dtype=np.float64,
        )
        y_test_p = np.array([r.active_power for r in test_recs], dtype=np.float64)
        test_pred_p = power_model.predict(X_test_p)

        p_r2 = float(r2_score(y_test_p, test_pred_p))
        p_rmse = float(np.sqrt(mean_squared_error(y_test_p, test_pred_p)))
        p_mae = float(mean_absolute_error(y_test_p, test_pred_p))

        X_test_t = np.array(
            [[r.active_power, r.ambient_temp, r.rotor_speed] for r in test_recs],
            dtype=np.float64,
        )
        y_test_gb = np.array(
            [r.gearbox_bearing_temp for r in test_recs], dtype=np.float64
        )
        y_test_gen = np.array(
            [r.generator_stator_temp for r in test_recs], dtype=np.float64
        )
        test_pred_gb, test_pred_gen = thermal_model.predict(X_test_t)

        gb_r2 = float(r2_score(y_test_gb, test_pred_gb))
        gb_rmse = float(np.sqrt(mean_squared_error(y_test_gb, test_pred_gb)))
        gb_mae = float(mean_absolute_error(y_test_gb, test_pred_gb))

        gen_r2 = float(r2_score(y_test_gen, test_pred_gen))
        gen_rmse = float(np.sqrt(mean_squared_error(y_test_gen, test_pred_gen)))
        gen_mae = float(mean_absolute_error(y_test_gen, test_pred_gen))

        # 6. Benchmark Latency Measurements
        residual_engine = ResidualEngine(
            power_model=power_model,
            thermal_model=thermal_model,
            baseline_stats=baseline_stats,
            persistence_threshold=settings.ML.PERSISTENCE_THRESHOLD_SIGMA,
            persistence_window=settings.ML.PERSISTENCE_WINDOW_STEPS,
            persistence_ratio=settings.ML.PERSISTENCE_RATIO_THRESHOLD,
        )

        # Single record latency
        single_sample = test_recs[0]
        n_lat_iters = 200
        t0 = time.perf_counter()
        for _ in range(n_lat_iters):
            _ = residual_engine.compute_residuals(single_sample)
        t_single_ms = ((time.perf_counter() - t0) / n_lat_iters) * 1000.0

        # Batch latency over entire test set
        t0_batch = time.perf_counter()
        batch_residuals = residual_engine.compute_batch_residuals(test_recs)
        t_batch_ms = (time.perf_counter() - t0_batch) * 1000.0

        # Compile actual measured evaluation results
        results = {
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "random_seed": self.random_seed,
            "dataset_info": {
                "total_clean_records": len(records),
                "train_samples": len(train_recs),
                "val_samples": len(val_recs),
                "test_samples": len(test_recs),
                "is_synthetic": True,
                "scenario": BenchmarkScenarioType.S1_BASELINE_HEALTHY.value,
            },
            "power_model_metrics": {
                "r2_score": round(p_r2, 4),
                "rmse_kw": round(p_rmse, 2),
                "mae_kw": round(p_mae, 2),
                "target_r2_status": "PASS" if p_r2 >= settings.ML.TARGET_POWER_R2 else "FAIL",
                "target_rmse_status": "PASS" if p_rmse <= settings.ML.TARGET_POWER_RMSE_KW else "FAIL",
                "target_mae_status": "PASS" if p_mae <= settings.ML.TARGET_POWER_MAE_KW else "FAIL",
            },
            "thermal_model_metrics": {
                "gearbox_bearing": {
                    "r2_score": round(gb_r2, 4),
                    "rmse_c": round(gb_rmse, 2),
                    "mae_c": round(gb_mae, 2),
                    "target_rmse_status": "PASS" if gb_rmse <= settings.ML.TARGET_THERMAL_RMSE_C else "FAIL",
                },
                "generator_stator": {
                    "r2_score": round(gen_r2, 4),
                    "rmse_c": round(gen_rmse, 2),
                    "mae_c": round(gen_mae, 2),
                    "target_rmse_status": "PASS" if gen_rmse <= settings.ML.TARGET_THERMAL_RMSE_C else "FAIL",
                },
            },
            "calibrated_baseline_stats": baseline_stats.model_dump(),
            "latency_measurements": {
                "single_residual_inference_ms": round(t_single_ms, 4),
                "batch_residual_computation_ms": round(t_batch_ms, 2),
                "batch_records_count": len(test_recs),
                "target_latency_status": "PASS" if t_single_ms < settings.ML.TARGET_LATENCY_MS else "FAIL",
            },
        }

        # 7. Persist Artifacts and Metadata
        if save_artifacts:
            power_artifact = self.output_dir / "expected_power_gbr_v1.joblib"
            thermal_artifact = self.output_dir / "expected_thermal_rf_v1.joblib"
            stats_artifact = self.output_dir / "baseline_stats_v1.json"
            metadata_artifact = self.output_dir / "model_metadata.json"

            power_model.save(power_artifact)
            thermal_model.save(thermal_artifact)
            baseline_stats.save(stats_artifact)

            # Build metadata manifest with actual measured results
            metadata = {
                "model_name": "windguard_ml_baselines_layer2",
                "model_version": "1.0.0",
                "power_model": {
                    "algorithm": "GradientBoostingRegressor",
                    "framework": "scikit-learn",
                    "feature_names": list(CANONICAL_POWER_FEATURES),
                    "target_variable": "active_power",
                    "hyperparameters": {
                        "n_estimators": settings.ML.POWER_GBR_N_ESTIMATORS,
                        "max_depth": settings.ML.POWER_GBR_MAX_DEPTH,
                        "learning_rate": settings.ML.POWER_GBR_LEARNING_RATE,
                        "random_state": self.random_seed,
                    },
                    "measured_metrics": results["power_model_metrics"],
                },
                "thermal_model": {
                    "algorithm": "RandomForestRegressor",
                    "framework": "scikit-learn",
                    "feature_names": list(CANONICAL_THERMAL_FEATURES),
                    "target_variables": ["gearbox_bearing_temp", "generator_stator_temp"],
                    "hyperparameters": {
                        "n_estimators": settings.ML.THERMAL_RF_N_ESTIMATORS,
                        "max_depth": settings.ML.THERMAL_RF_MAX_DEPTH,
                        "random_state": self.random_seed,
                    },
                    "measured_metrics": results["thermal_model_metrics"],
                },
                "dataset_info": results["dataset_info"],
                "calibrated_baseline_stats": results["calibrated_baseline_stats"],
                "latency_measurements": results["latency_measurements"],
                "training_timestamp": results["training_timestamp"],
                "random_seed": self.random_seed,
            }

            with open(metadata_artifact, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

        return results
