"""WindGuard AI Layer 2 Machine Learning Models & Residual Engine.

Exports:
- ExpectedPowerModel (GradientBoostingRegressor)
- ExpectedThermalModel (RandomForestRegressor)
- ResidualEngine
- BaselineStats
- ResidualVector
- ModelTrainer
"""

from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import (
    BaselineStats,
    ResidualEngine,
    ResidualVector,
)
from backend.models.thermal_model import ExpectedThermalModel
from backend.models.trainer import ModelTrainer

__all__ = [
    "ExpectedPowerModel",
    "ExpectedThermalModel",
    "ResidualEngine",
    "BaselineStats",
    "ResidualVector",
    "ModelTrainer",
]
