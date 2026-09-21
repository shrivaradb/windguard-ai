"""Unit Tests for SCADA Data Preprocessor and Validation Engine."""

import numpy as np
import pandas as pd
import pytest

from backend.data.preprocessor import SCADAPreprocessor
from backend.data.schema import OperatingStatus


def test_physical_range_validation(preprocessor: SCADAPreprocessor, valid_telemetry_dict):
    """Verifies that out-of-physical-bound records are rejected."""
    # Negative wind speed
    bad_data = valid_telemetry_dict.copy()
    bad_data["wind_speed"] = -5.0
    rec, issues = preprocessor.validate_and_clean_record(bad_data)
    assert rec is None
    assert any(i.field_name == "wind_speed" and i.action_taken == "REJECTED" for i in issues)

    # Extreme active power exceeding physical limit
    bad_data2 = valid_telemetry_dict.copy()
    bad_data2["active_power"] = 5000.0
    rec2, issues2 = preprocessor.validate_and_clean_record(bad_data2)
    assert rec2 is None
    assert any(i.field_name == "active_power" and i.action_taken == "REJECTED" for i in issues2)

    # Impossible pitch angle
    bad_data3 = valid_telemetry_dict.copy()
    bad_data3["pitch_angle"] = 120.0
    rec3, issues3 = preprocessor.validate_and_clean_record(bad_data3)
    assert rec3 is None
    assert any(i.field_name == "pitch_angle" and i.action_taken == "REJECTED" for i in issues3)


def test_thermocouple_plausibility_rule(preprocessor: SCADAPreprocessor, valid_telemetry_dict):
    """Verifies that bearing temp lower than ambient - 5°C is flagged as SENSOR_DROPOUT."""
    data = valid_telemetry_dict.copy()
    data["ambient_temp"] = 35.0
    data["gearbox_bearing_temp"] = 20.0  # Impossible: 15°C below ambient
    rec, issues = preprocessor.validate_and_clean_record(data)

    assert rec is not None
    assert rec.operating_status == OperatingStatus.SENSOR_DROPOUT.value
    assert rec.quality_flags.get("gearbox_bearing_temp") == "SENSOR_DROPOUT"
    assert any(i.issue_type == "PLAUSIBILITY" and i.action_taken == "FLAGGED_SENSOR_DROPOUT" for i in issues)


def test_rate_of_change_validation(preprocessor: SCADAPreprocessor, valid_telemetry_dict):
    """Verifies that sudden impossible jumps in wind speed or temperature are rejected."""
    rec1, _ = preprocessor.validate_and_clean_record(valid_telemetry_dict)
    assert rec1 is not None

    # Step 2: Wind speed jumps from 8.5 to 30.0 m/s in 10 minutes (Delta = 21.5 m/s > 15.0)
    data2 = valid_telemetry_dict.copy()
    data2["timestamp"] = "2026-09-20T12:10:00Z"
    data2["wind_speed"] = 30.0
    rec2, issues = preprocessor.validate_and_clean_record(data2, row_idx=1, prev_record=rec1)

    assert rec2 is None
    assert any(i.issue_type == "RATE_OF_CHANGE" and i.field_name == "wind_speed" for i in issues)


def test_linear_interpolation_for_short_gaps(preprocessor: SCADAPreprocessor):
    """Verifies that 1-2 consecutive missing values are linearly interpolated with provenance quality flags."""
    df = pd.DataFrame([
        {
            "timestamp": "2026-09-20T10:00:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": 8.0,
            "ambient_temp": 30.0,
            "active_power": 1200.0,
            "rotor_speed": 13.0,
            "generator_speed": 1330.0,
            "gearbox_bearing_temp": 60.0,
            "generator_stator_temp": 68.0,
            "pitch_angle": 0.5,
            "is_curtailed": False
        },
        {
            "timestamp": "2026-09-20T10:10:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": np.nan,  # 1 missing interval
            "ambient_temp": 30.2,
            "active_power": 1300.0,
            "rotor_speed": 13.5,
            "generator_speed": 1380.0,
            "gearbox_bearing_temp": 61.0,
            "generator_stator_temp": 69.0,
            "pitch_angle": 0.5,
            "is_curtailed": False
        },
        {
            "timestamp": "2026-09-20T10:20:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": 10.0,
            "ambient_temp": 30.4,
            "active_power": 1400.0,
            "rotor_speed": 14.0,
            "generator_speed": 1430.0,
            "gearbox_bearing_temp": 62.0,
            "generator_stator_temp": 70.0,
            "pitch_angle": 0.5,
            "is_curtailed": False
        }
    ])

    records, summary = preprocessor.process_dataframe(df)
    assert len(records) == 3
    assert summary.interpolated_values_count == 1
    # Interpolated wind_speed should be average of 8.0 and 10.0 = 9.0
    assert records[1].wind_speed == 9.0
    assert records[1].quality_flags is not None
    assert records[1].quality_flags.get("wind_speed") == "INTERPOLATED_LINEAR"


def test_dropout_flagging_for_prolonged_gaps(preprocessor: SCADAPreprocessor):
    """Verifies that >2 consecutive missing values are flagged as SENSOR_DROPOUT without fake fabrication."""
    df = pd.DataFrame([
        {
            "timestamp": f"2026-09-20T10:{i*10:02d}:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": 8.0 if i == 0 else np.nan,  # 4 consecutive NaNs
            "ambient_temp": 30.0,
            "active_power": 1200.0,
            "rotor_speed": 13.0,
            "generator_speed": 1330.0,
            "gearbox_bearing_temp": 60.0,
            "generator_stator_temp": 68.0,
            "pitch_angle": 0.5,
            "is_curtailed": False
        }
        for i in range(5)
    ])

    records, summary = preprocessor.process_dataframe(df)
    # The first 2 NaNs get interpolated (short gap), step 3 and 4 (>2 gaps) get marked as SENSOR_DROPOUT
    assert summary.dropout_records_count >= 1
    assert any(r.operating_status == OperatingStatus.SENSOR_DROPOUT.value for r in records)
