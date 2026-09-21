"""WindGuard AI Configuration Module for Phase 1.

Defines environment variables, file paths, turbine baseline physical constants,
validation bounds, and simulation parameters.
Strictly contains NO tariff configurations or financial loss settings.
"""

from pathlib import Path
from pydantic import BaseModel, Field


class PathSettings(BaseModel):
    """Base filesystem paths for WindGuard AI."""
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    SYNTHETIC_DIR: Path = DATA_DIR / "synthetic"
    BENCHMARKS_DIR: Path = DATA_DIR / "benchmarks"
    STORAGE_DIR: Path = DATA_DIR / "storage"
    MODELS_DIR: Path = DATA_DIR / "models"
    ARTIFACTS_DIR: Path = BASE_DIR / "backend" / "models" / "artifacts"


class TurbineDefaultParams(BaseModel):
    """Documented baseline turbine engineering parameters (2.0 MW baseline).

    Source: docs/09_technical_design.md §2.1 and docs/10_data_architecture.md §3.
    """
    RATED_POWER_KW: float = Field(default=2000.0, description="Rated active power in kW")
    CUT_IN_SPEED_MPS: float = Field(default=3.0, description="Cut-in wind speed in m/s")
    RATED_SPEED_MPS: float = Field(default=12.0, description="Rated wind speed in m/s")
    CUT_OUT_SPEED_MPS: float = Field(default=25.0, description="Cut-out wind speed in m/s")
    RATED_ROTOR_RPM: float = Field(default=14.5, description="Nominal rotor speed at rated power")
    GEARBOX_RATIO: float = Field(default=102.4, description="Gearbox step-up transmission ratio")
    TAU_THERMAL_GB_MIN: float = Field(default=60.0, description="Gearbox thermal time constant in minutes")
    TAU_THERMAL_GEN_MIN: float = Field(default=45.0, description="Generator stator thermal time constant in minutes")
    GB_TEMP_RISE_COEFF: float = Field(default=25.0, description="Gearbox steady-state temp rise above ambient at 1.0 load (°C)")
    GEN_TEMP_RISE_COEFF: float = Field(default=35.0, description="Generator steady-state temp rise above ambient at 1.0 load (°C)")


class ValidationThresholds(BaseModel):
    """Documented physical ranges and rate-of-change validation rules.

    Source: docs/10_data_architecture.md §5 and docs/07_srs.md §3.1.
    """
    WIND_SPEED_MIN: float = 0.0
    WIND_SPEED_MAX: float = 50.0
    WIND_SPEED_MAX_DELTA_10MIN: float = 15.0

    WIND_DIRECTION_MIN: float = 0.0
    WIND_DIRECTION_MAX: float = 360.0

    AMBIENT_TEMP_MIN: float = -25.0
    AMBIENT_TEMP_MAX: float = 60.0
    AMBIENT_TEMP_MAX_DELTA_10MIN: float = 10.0

    ACTIVE_POWER_MIN: float = -50.0
    ACTIVE_POWER_MAX: float = 2750.0  # 1.15 * 2000 kW + margin or max sensor limit
    ACTIVE_POWER_OVERLOAD_FACTOR: float = 1.15

    REACTIVE_POWER_MIN: float = -1000.0
    REACTIVE_POWER_MAX: float = 1000.0

    ROTOR_SPEED_MIN: float = 0.0
    ROTOR_SPEED_MAX: float = 30.0

    GENERATOR_SPEED_MIN: float = 0.0
    GENERATOR_SPEED_MAX: float = 2000.0

    GEARBOX_BEARING_TEMP_MIN: float = -10.0
    GEARBOX_BEARING_TEMP_MAX: float = 130.0

    GENERATOR_STATOR_TEMP_MIN: float = 0.0
    GENERATOR_STATOR_TEMP_MAX: float = 160.0

    NACELLE_TEMP_MIN: float = 0.0
    NACELLE_TEMP_MAX: float = 80.0

    PITCH_ANGLE_MIN: float = -5.0
    PITCH_ANGLE_MAX: float = 95.0

    # Thermocouple plausibility check: component temp must not be lower than ambient - 5°C
    THERMAL_PLAUSIBILITY_DELTA: float = -5.0

    # Missing interval threshold for linear interpolation
    MAX_CONSECUTIVE_MISSING_FOR_INTERPOLATION: int = 2


class SimulationSettings(BaseModel):
    """Simulation engine configuration defaults."""
    DEFAULT_RANDOM_SEED: int = 42
    SAMPLING_INTERVAL_MINUTES: float = 10.0
    DEFAULT_NUM_TURBINES: int = 10
    TURBINE_ID_PREFIX: str = "WTG"
    DEFAULT_NUM_TIMESTEPS: int = 144  # 24 hours at 10-minute resolution
    SLIDING_WINDOW_CACHE_SIZE: int = 144  # 24h per turbine buffer


class MLSettings(BaseModel):
    """Phase 2 Deterministic Machine Learning Baselines & Residual Engine Settings."""
    POWER_ALGORITHM: str = "GradientBoostingRegressor"
    THERMAL_ALGORITHM: str = "RandomForestRegressor"
    RANDOM_SEED: int = 42

    # Chronological dataset splitting ratios (strictly non-random)
    CHRONOLOGICAL_TRAIN_RATIO: float = 0.70
    CHRONOLOGICAL_VAL_RATIO: float = 0.15
    CHRONOLOGICAL_TEST_RATIO: float = 0.15

    # Power curve baseline hyperparameters (LOCKED for Phase 2)
    POWER_GBR_N_ESTIMATORS: int = 100
    POWER_GBR_MAX_DEPTH: int = 5
    POWER_GBR_LEARNING_RATE: float = 0.1

    # Thermal baseline hyperparameters (LOCKED for Phase 2)
    THERMAL_RF_N_ESTIMATORS: int = 100
    THERMAL_RF_MAX_DEPTH: int = 10

    # Canonical statistical persistence threshold and window
    PERSISTENCE_THRESHOLD_SIGMA: float = 2.5
    PERSISTENCE_WINDOW_STEPS: int = 6  # 6 * 10 min = 1 hour
    PERSISTENCE_RATIO_THRESHOLD: float = 0.80  # >= 5 of 6 steps

    # Engineering Design Targets (docs/PHASE_2_SCOPE_REVIEW.md §12, docs/11_ai_ml_design.md §4, §6.1)
    TARGET_POWER_R2: float = 0.95
    TARGET_POWER_RMSE_KW: float = 45.0
    TARGET_POWER_MAE_KW: float = 30.0
    TARGET_THERMAL_RMSE_C: float = 2.5
    TARGET_THERMAL_R2: float = 0.96
    TARGET_LATENCY_MS: float = 1.0


class LLMSettings(BaseModel):
    """Phase 5 Advisory & Guardrail Initial Design Parameters (Temporary Defaults)."""
    DEFAULT_PROVIDER_MODE: str = "MODE_A"  # MODE_A: Deterministic Local Template Synthesizer (100% Offline CPU)
    LLM_TIMEOUT_SECONDS: float = 5.0  # Temporary default for OD-P5-05
    CRITICAL_REVIEW_LOSS_CEILING_INR: float = 25000.0  # Temporary default for OD-P5-04
    RELEVANCE_SCORE_FLOOR: float = 0.15  # Minimum hybrid score for technical chunk grounding
    NUMERICAL_TOLERANCE_EPSILON: float = 0.01  # Tolerance for numerical drift assertion
    DEFAULT_GUARDRAIL_POLICY: str = "STANDARD"  # OD-P5-03 configurable policy


class Settings(BaseModel):
    """Master application settings."""
    PATHS: PathSettings = PathSettings()
    TURBINE: TurbineDefaultParams = TurbineDefaultParams()
    VALIDATION: ValidationThresholds = ValidationThresholds()
    SIMULATION: SimulationSettings = SimulationSettings()
    ML: MLSettings = MLSettings()
    LLM: LLMSettings = LLMSettings()


# Instantiate global settings singleton
settings = Settings()

# Ensure directories exist
settings.PATHS.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.PATHS.SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
settings.PATHS.BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
settings.PATHS.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.PATHS.MODELS_DIR.mkdir(parents=True, exist_ok=True)
settings.PATHS.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
