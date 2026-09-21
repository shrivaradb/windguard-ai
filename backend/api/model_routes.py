"""FastAPI Routes for Phase 2 Machine Learning Baselines & Residual Engine.

Source: docs/09_technical_design.md §2.2, docs/PHASE_2_SCOPE_REVIEW.md §15.
"""

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import (
    BaselineStats,
    ResidualEngine,
    ResidualVector,
)
from backend.models.thermal_model import ExpectedThermalModel
from backend.models.trainer import ModelTrainer

router = APIRouter(prefix="/api/models", tags=["Layer 2: ML Models & Residuals"])

# Global singleton model instances for runtime inference
_power_model: Optional[ExpectedPowerModel] = None
_thermal_model: Optional[ExpectedThermalModel] = None
_baseline_stats: Optional[BaselineStats] = None
_residual_engine: Optional[ResidualEngine] = None


def get_residual_engine() -> ResidualEngine:
    """Lazy loader for persisted ML model artifacts."""
    global _power_model, _thermal_model, _baseline_stats, _residual_engine

    if _residual_engine is None:
        power_path = settings.PATHS.MODELS_DIR / "expected_power_gbr_v1.joblib"
        thermal_path = settings.PATHS.MODELS_DIR / "expected_thermal_rf_v1.joblib"
        stats_path = settings.PATHS.MODELS_DIR / "baseline_stats_v1.json"

        # If artifacts do not exist yet, train them automatically on S1 healthy baseline
        if not power_path.exists() or not thermal_path.exists() or not stats_path.exists():
            trainer = ModelTrainer(output_dir=settings.PATHS.MODELS_DIR)
            _ = trainer.train_and_evaluate(save_artifacts=True)

        _power_model = ExpectedPowerModel.load(power_path)
        _thermal_model = ExpectedThermalModel.load(thermal_path)
        _baseline_stats = BaselineStats.load(stats_path)
        _residual_engine = ResidualEngine(
            power_model=_power_model,
            thermal_model=_thermal_model,
            baseline_stats=_baseline_stats,
            persistence_threshold=settings.ML.PERSISTENCE_THRESHOLD_SIGMA,
            persistence_window=settings.ML.PERSISTENCE_WINDOW_STEPS,
            persistence_ratio=settings.ML.PERSISTENCE_RATIO_THRESHOLD,
        )

    return _residual_engine


class TrainResponse(BaseModel):
    status: str
    training_timestamp: str
    dataset_info: Dict[str, Any]
    power_model_metrics: Dict[str, Any]
    thermal_model_metrics: Dict[str, Any]
    calibrated_baseline_stats: Dict[str, Any]
    latency_measurements: Dict[str, Any]


class ModelStatusResponse(BaseModel):
    is_trained: bool
    model_version: str
    power_algorithm: str
    thermal_algorithm: str
    baseline_stats: BaselineStats
    persistence_threshold_sigma: float
    persistence_window_steps: int


@app_router_train := router.post("/train", response_model=TrainResponse)
def train_models() -> TrainResponse:
    """Triggers deterministic training and evaluation of ExpectedPowerModel and ExpectedThermalModel."""
    global _residual_engine
    trainer = ModelTrainer(output_dir=settings.PATHS.MODELS_DIR)
    results = trainer.train_and_evaluate(save_artifacts=True)
    # Invalidate cached runtime engine to force reload
    _residual_engine = None

    return TrainResponse(
        status="TRAINED_SUCCESS",
        training_timestamp=results["training_timestamp"],
        dataset_info=results["dataset_info"],
        power_model_metrics=results["power_model_metrics"],
        thermal_model_metrics=results["thermal_model_metrics"],
        calibrated_baseline_stats=results["calibrated_baseline_stats"],
        latency_measurements=results["latency_measurements"],
    )


@router.post("/residuals", response_model=Union[ResidualVector, List[ResidualVector]])
def compute_residuals(
    payload: Union[TelemetryRecord, List[TelemetryRecord]]
) -> Union[ResidualVector, List[ResidualVector]]:
    """Calculates physical residuals and standardized z-scores for single or batch TelemetryRecord."""
    engine = get_residual_engine()
    if isinstance(payload, list):
        return engine.compute_batch_residuals(payload)
    return engine.compute_residuals(payload)


@router.get("/status", response_model=ModelStatusResponse)
def get_model_status() -> ModelStatusResponse:
    """Returns the operational status and configuration of Layer 2 ML baselines."""
    engine = get_residual_engine()
    return ModelStatusResponse(
        is_trained=True,
        model_version="1.0.0",
        power_algorithm=settings.ML.POWER_ALGORITHM,
        thermal_algorithm=settings.ML.THERMAL_ALGORITHM,
        baseline_stats=engine.baseline_stats,
        persistence_threshold_sigma=engine.persistence_threshold,
        persistence_window_steps=engine.persistence_window,
    )
