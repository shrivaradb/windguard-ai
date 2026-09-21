"""FastAPI Routes for Layer 2 ML Model Residual Inferences & Operational Status.

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.2
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §7 (GOV-TRAIN-01)

GOVERNANCE DIRECTIVE:
Model training (POST /api/models/train) is OUT OF SCOPE and NOT AUTHORIZED for runtime service execution.
Phase 2 analytical models remain frozen.
"""

from typing import List, Union
from fastapi import APIRouter, Depends

from backend.api.dependencies import get_residual_engine
from backend.api.schemas import ModelStatusResponse
from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.models.residual_engine import ResidualEngine, ResidualVector

router = APIRouter(prefix="/models", tags=["Layer 2: ML Models & Residuals"])


@router.post("/residuals", response_model=Union[ResidualVector, List[ResidualVector]])
def compute_residuals(
    payload: Union[TelemetryRecord, List[TelemetryRecord]],
    engine: ResidualEngine = Depends(get_residual_engine),
) -> Union[ResidualVector, List[ResidualVector]]:
    """Calculates physical residuals and standardized z-scores for single or batch TelemetryRecord."""
    if isinstance(payload, list):
        return engine.compute_batch_residuals(payload)
    return engine.compute_residuals(payload)


@router.get("/status", response_model=ModelStatusResponse)
def get_model_status(
    engine: ResidualEngine = Depends(get_residual_engine),
) -> ModelStatusResponse:
    """Returns the operational status and baseline configuration of Layer 2 ML baselines."""
    return ModelStatusResponse(
        is_trained=True,
        model_version="1.0.0",
        power_algorithm=settings.ML.POWER_ALGORITHM,
        thermal_algorithm=settings.ML.THERMAL_ALGORITHM,
        baseline_stats=engine.baseline_stats,
        persistence_threshold_sigma=engine.persistence_threshold,
        persistence_window_steps=engine.persistence_window,
    )
