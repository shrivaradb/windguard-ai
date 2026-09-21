"""Unit Tests for SCADA Data Schemas and Canonical Telemetry Definition."""

import pytest
from pydantic import ValidationError

from backend.data.schema import (
    BenchmarkScenarioType,
    GroundTruthLabel,
    OperatingStatus,
    SimulationConfig,
    TelemetryRecord,
)


def test_valid_telemetry_record_instantiation(valid_telemetry_dict):
    """Verifies that a valid SCADA record dictionary passes schema validation."""
    record = TelemetryRecord.model_validate(valid_telemetry_dict)
    assert record.turbine_id == "WTG-01"
    assert record.wind_speed == 8.5
    assert record.active_power == 1400.0
    assert record.is_curtailed is False
    assert record.operating_status == "Running"
    assert record.is_synthetic is False


def test_canonical_is_curtailed_flag():
    """Verifies that is_curtailed is the canonical boolean field."""
    record = TelemetryRecord(
        timestamp="2026-09-20T10:00:00Z",
        turbine_id="WTG-05",
        wind_speed=9.0,
        ambient_temp=32.0,
        active_power=1000.0,
        rotor_speed=12.0,
        generator_speed=1220.0,
        gearbox_bearing_temp=68.0,
        generator_stator_temp=74.0,
        pitch_angle=15.0,
        is_curtailed=True,
        curtailment_limit_kw=1000.0
    )
    assert record.is_curtailed is True
    assert record.curtailment_limit_kw == 1000.0


def test_curtailment_flag_backward_compatible_alias(valid_telemetry_dict):
    """Verifies that legacy curtailment_flag is mapped to canonical is_curtailed."""
    # Test integer 1
    data1 = valid_telemetry_dict.copy()
    data1.pop("is_curtailed", None)
    data1["curtailment_flag"] = 1
    rec1 = TelemetryRecord.model_validate(data1)
    assert rec1.is_curtailed is True

    # Test integer 0
    data2 = valid_telemetry_dict.copy()
    data2.pop("is_curtailed", None)
    data2["curtailment_flag"] = 0
    rec2 = TelemetryRecord.model_validate(data2)
    assert rec2.is_curtailed is False

    # Test string 'true' / 'false'
    data3 = valid_telemetry_dict.copy()
    data3.pop("is_curtailed", None)
    data3["curtailment_flag"] = "true"
    rec3 = TelemetryRecord.model_validate(data3)
    assert rec3.is_curtailed is True


def test_column_alias_mappings(valid_telemetry_dict):
    """Verifies that common legacy column variations map to canonical fields."""
    data = {
        "timestamp": "2026-09-20T12:00:00Z",
        "turbine_id": "WTG-03",
        "windspeed": 10.2,
        "power": 1850.0,
        "temp_ambient": 25.0,
        "temp_gearbox_bearing": 64.0,
        "temp_gen_stator": 71.0,
        "rotor_speed": 14.5,
        "generator_speed": 1480.0,
        "pitch_angle": 0.8,
        "curtailment_flag": False
    }
    rec = TelemetryRecord.model_validate(data)
    assert rec.wind_speed == 10.2
    assert rec.active_power == 1850.0
    assert rec.ambient_temp == 25.0
    assert rec.gearbox_bearing_temp == 64.0
    assert rec.generator_stator_temp == 71.0
    assert rec.is_curtailed is False


def test_invalid_timestamp_rejected(valid_telemetry_dict):
    """Verifies that invalid or malformed timestamp strings are rejected."""
    data = valid_telemetry_dict.copy()
    data["timestamp"] = "invalid-date-time-2026"
    with pytest.raises(ValidationError):
        TelemetryRecord.model_validate(data)


def test_missing_required_fields_rejected(valid_telemetry_dict):
    """Verifies that omitting a required field fails validation."""
    data = valid_telemetry_dict.copy()
    data.pop("wind_speed")
    with pytest.raises(ValidationError):
        TelemetryRecord.model_validate(data)


def test_simulation_config_validation():
    """Verifies that SimulationConfig enforces bounds on turbines and timesteps."""
    cfg = SimulationConfig(
        scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
        num_turbines=5,
        num_timesteps=72,
        random_seed=123
    )
    assert cfg.num_turbines == 5
    assert cfg.num_timesteps == 72
    assert cfg.random_seed == 123

    # Out of range turbines
    with pytest.raises(ValidationError):
        SimulationConfig(num_turbines=0)


def test_ground_truth_label_model():
    """Verifies GroundTruthLabel structure."""
    gt = GroundTruthLabel(
        scenario_id=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
        scenario_name="Gearbox High-Speed Bearing Degradation",
        is_fault=True,
        fault_type="GEARBOX_BEARING_OVERHEATING",
        affected_subsystem="DRIVETRAIN",
        affected_turbine_id="WTG-07",
        description="High bearing temp test"
    )
    assert gt.is_fault is True
    assert gt.affected_turbine_id == "WTG-07"
