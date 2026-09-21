"""Canonical SCADA Data Schemas for WindGuard AI.

Source of Truth:
- docs/10_data_architecture.md §4.1
- docs/07_srs.md §3.1
- docs/09_technical_design.md §2.1

Preserves canonical `is_curtailed` as primary field with `curtailment_flag`
supported strictly as a backward-compatible ingestion alias.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OperatingStatus(str, Enum):
    """Standard turbine operating states."""
    RUNNING = "Running"
    CURTAILED = "Curtailed"
    IDLING = "Idling"
    MAINTENANCE = "Maintenance"
    FAULT = "Fault"
    SENSOR_DROPOUT = "Sensor Dropout"


class BenchmarkScenarioType(str, Enum):
    """The five documented benchmark operational scenarios.

    Source: docs/10_data_architecture.md §2 and docs/14_implementation_plan.md §3.
    """
    S1_BASELINE_HEALTHY = "S1_BASELINE_HEALTHY"
    S2_GEARBOX_BEARING_DEGRADATION = "S2_GEARBOX_BEARING_DEGRADATION"
    S3_PITCH_ASYMMETRY = "S3_PITCH_ASYMMETRY"
    S4_GRID_CURTAILMENT_HEATWAVE = "S4_GRID_CURTAILMENT_HEATWAVE"
    S5_SENSOR_DROPOUT = "S5_SENSOR_DROPOUT"


class TelemetryRecord(BaseModel):
    """Canonical 10-Minute SCADA Telemetry Record Schema.

    Documented in docs/10_data_architecture.md §4.1.
    """
    timestamp: str = Field(
        ...,
        description="ISO-8601 UTC timestamp string (e.g. 2026-09-20T12:00:00Z)"
    )
    turbine_id: str = Field(
        ...,
        description="Standard turbine identifier (e.g. WTG-01 to WTG-10)"
    )
    wind_speed: float = Field(
        ...,
        description="10-minute average wind speed in m/s (0.0 to 50.0 m/s)"
    )
    wind_direction: float = Field(
        default=180.0,
        description="10-minute average wind direction in degrees (0.0 to 360.0°)"
    )
    ambient_temp: float = Field(
        ...,
        description="10-minute average ambient temperature in °C (-25.0 to 60.0°C)"
    )
    active_power: float = Field(
        ...,
        description="10-minute average active power in kW (-50.0 to 2750.0 kW)"
    )
    reactive_power: float = Field(
        default=0.0,
        description="10-minute average reactive power in kVAR (-1000.0 to 1000.0 kVAR)"
    )
    rotor_speed: float = Field(
        ...,
        description="10-minute average rotor rotational speed in RPM (0.0 to 30.0 RPM)"
    )
    generator_speed: float = Field(
        ...,
        description="10-minute average generator rotational speed in RPM (0.0 to 2000.0 RPM)"
    )
    gearbox_bearing_temp: float = Field(
        ...,
        description="10-minute average gearbox high-speed bearing temp in °C (-10.0 to 130.0°C)"
    )
    generator_stator_temp: float = Field(
        ...,
        description="10-minute average generator stator winding temp in °C (0.0 to 160.0°C)"
    )
    nacelle_temp: float = Field(
        default=30.0,
        description="10-minute average internal nacelle temp in °C (0.0 to 80.0°C)"
    )
    pitch_angle: float = Field(
        ...,
        description="10-minute average blade pitch angle in degrees (-5.0 to 95.0°)"
    )
    is_curtailed: bool = Field(
        default=False,
        description="Canonical grid curtailment indicator (True if power output is restricted by grid dispatch)"
    )
    curtailment_limit_kw: Optional[float] = Field(
        default=None,
        description="Active grid dispatch setpoint limit in kW if is_curtailed=True"
    )
    operating_status: str = Field(
        default=OperatingStatus.RUNNING.value,
        description="High-level operating status label"
    )
    quality_flags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Provenance metadata for imputed/interpolated fields or sensor errors"
    )
    is_synthetic: bool = Field(
        default=False,
        description="Watermark flag distinguishing synthetic/simulated data from field measurements"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )

    @model_validator(mode="before")
    @classmethod
    def map_legacy_aliases_and_types(cls, data: Any) -> Any:
        """Pre-validation alias mapper for backward compatibility with external datasets.

        Maps legacy `curtailment_flag` to canonical `is_curtailed`.
        """
        if isinstance(data, dict):
            # Map legacy curtailment_flag to canonical is_curtailed
            if "is_curtailed" not in data and "curtailment_flag" in data:
                flag = data["curtailment_flag"]
                if isinstance(flag, str):
                    data["is_curtailed"] = flag.strip().lower() in ("true", "1", "t", "yes")
                elif isinstance(flag, (int, float)):
                    data["is_curtailed"] = bool(flag)
                elif isinstance(flag, bool):
                    data["is_curtailed"] = flag
                else:
                    data["is_curtailed"] = False

            # Convert boolean integer representations if passed as 0/1 for is_curtailed
            if "is_curtailed" in data and isinstance(data["is_curtailed"], (int, float)):
                data["is_curtailed"] = bool(data["is_curtailed"])
            elif "is_curtailed" in data and isinstance(data["is_curtailed"], str):
                data["is_curtailed"] = data["is_curtailed"].strip().lower() in ("true", "1", "t", "yes")

            # Map alternative common column names if present
            if "power" in data and "active_power" not in data:
                data["active_power"] = data["power"]
            if "windspeed" in data and "wind_speed" not in data:
                data["wind_speed"] = data["windspeed"]
            if "temp_ambient" in data and "ambient_temp" not in data:
                data["ambient_temp"] = data["temp_ambient"]
            if "temp_gearbox_bearing" in data and "gearbox_bearing_temp" not in data:
                data["gearbox_bearing_temp"] = data["temp_gearbox_bearing"]
            if "temp_gen_stator" in data and "generator_stator_temp" not in data:
                data["generator_stator_temp"] = data["temp_gen_stator"]

        return data

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_format(cls, v: str) -> str:
        """Validates that timestamp string conforms to ISO-8601 standard."""
        try:
            # Replace 'Z' with '+00:00' for standard ISO parsing if needed
            ts = v.replace("Z", "+00:00")
            datetime.fromisoformat(ts)
            return v
        except Exception as err:
            raise ValueError(f"Timestamp '{v}' is not a valid ISO-8601 string: {err}")


class TurbineState(BaseModel):
    """Internal dynamic physical state of a simulated wind turbine."""
    turbine_id: str
    rated_power_kw: float = 2000.0
    cut_in_speed_mps: float = 3.0
    rated_speed_mps: float = 12.0
    cut_out_speed_mps: float = 25.0
    aerodynamic_derate_factor: float = 0.0
    is_curtailed: bool = False
    curtailment_limit_kw: Optional[float] = None
    temp_gearbox_bearing: float = 45.0
    temp_gen_stator: float = 55.0
    bearing_wear_heat_c: float = 0.0
    gen_cooling_loss_heat_c: float = 0.0
    tau_thermal_gb: float = 60.0
    tau_thermal_gen: float = 45.0


class GroundTruthLabel(BaseModel):
    """Explicit ground-truth metadata describing simulated operational conditions."""
    scenario_id: BenchmarkScenarioType
    scenario_name: str
    is_fault: bool
    fault_type: Optional[str] = None
    affected_subsystem: Optional[str] = None
    affected_turbine_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: str


class SimulationConfig(BaseModel):
    """Parameters for running the deterministic SCADA simulation engine."""
    scenario: BenchmarkScenarioType = BenchmarkScenarioType.S1_BASELINE_HEALTHY
    num_turbines: int = Field(default=10, ge=1, le=50, description="Number of turbines to simulate")
    num_timesteps: int = Field(default=144, ge=1, le=1008, description="Number of 10-minute intervals (144 = 24h)")
    random_seed: int = Field(default=42, description="Random seed for deterministic reproducibility")
    start_timestamp: str = Field(default="2026-09-20T00:00:00Z", description="Start ISO-8601 timestamp")
    sampling_interval_min: float = Field(default=10.0, ge=1.0, le=60.0, description="Interval in minutes")


class ValidationIssue(BaseModel):
    """Record of a specific data quality violation."""
    row_index: int
    turbine_id: Optional[str] = None
    field_name: str
    issue_type: str  # "RANGE_VIOLATION" | "RATE_OF_CHANGE" | "PLAUSIBILITY" | "MISSING_VALUE" | "MALFORMED"
    observed_value: Any
    expected_rule: str
    action_taken: str  # "REJECTED" | "INTERPOLATED" | "FLAGGED_SENSOR_DROPOUT"


class ValidationSummary(BaseModel):
    """Aggregated results of data validation and ingestion processing."""
    total_records: int
    accepted_records: int
    rejected_records: int
    interpolated_values_count: int
    dropout_records_count: int
    is_valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)


class SimulationResult(BaseModel):
    """Complete output package from a simulation execution."""
    config: SimulationConfig
    ground_truth: GroundTruthLabel
    total_records: int
    records: List[TelemetryRecord]
    generated_at: str
