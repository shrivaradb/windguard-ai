"""Unit Tests for Operational Context Engine (Layer 3).

Source of Truth:
- docs/07_srs.md §3.3
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.1 & §8 (TEST-CTX-01)
"""

import pytest
from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.engine.context_engine import (
    ContextFilterEngine,
    ContextResult,
    OperationalContextState,
)
from backend.models.residual_engine import ResidualVector


@pytest.fixture
def context_engine() -> ContextFilterEngine:
    return ContextFilterEngine()


@pytest.fixture
def base_telemetry() -> TelemetryRecord:
    return TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-01",
        wind_speed=8.5,
        wind_direction=180.0,
        ambient_temp=25.0,
        active_power=1400.0,
        reactive_power=50.0,
        rotor_speed=14.5,
        generator_speed=1450.0,
        gearbox_bearing_temp=65.0,
        generator_stator_temp=70.0,
        nacelle_temp=30.0,
        pitch_angle=1.0,
        is_curtailed=False,
        operating_status=OperatingStatus.RUNNING.value,
    )


@pytest.fixture
def base_residuals() -> ResidualVector:
    return ResidualVector(
        expected_power_kw=1410.0,
        residual_power_kw=-10.0,
        z_power=-0.22,
        expected_gb_temp_c=64.0,
        residual_gb_temp_c=1.0,
        z_gb=0.40,
        expected_gen_temp_c=69.0,
        residual_gen_temp_c=1.0,
        z_gen=0.33,
    )


def test_context_states_enum():
    """Verifies all canonical operational context states exist."""
    assert OperationalContextState.NORMAL == "NORMAL"
    assert OperationalContextState.CURTAILED == "CURTAILED"
    assert OperationalContextState.HIGH_AMBIENT_DERATE == "HIGH_AMBIENT_DERATE"
    assert OperationalContextState.LOW_WIND_IDLE == "LOW_WIND_IDLE"
    assert OperationalContextState.SENSOR_ANOMALY == "SENSOR_ANOMALY"


def test_precedence_1_sensor_dropout_status(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 1: Explicit sensor dropout operating status."""
    tel = base_telemetry.model_copy(update={"operating_status": OperatingStatus.SENSOR_DROPOUT.value})
    res = context_engine.evaluate_record(tel, base_residuals)
    assert res.state == OperationalContextState.SENSOR_ANOMALY
    assert res.is_suppressed is True
    assert res.precedence_level == 1
    assert "dropout" in res.explanation.lower()


def test_precedence_1_implausible_thermocouple(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 1: Thermocouple reading unphysically colder than ambient."""
    # S5 pattern: ambient is 30°C, but sensor reports 15°C (colder than ambient - 5°C)
    tel = base_telemetry.model_copy(update={"ambient_temp": 30.0, "gearbox_bearing_temp": 15.0})
    res = context_engine.evaluate_record(tel, base_residuals)
    assert res.state == OperationalContextState.SENSOR_ANOMALY
    assert res.is_suppressed is True
    assert res.precedence_level == 1


def test_precedence_2_grid_curtailment(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 2: Grid dispatch curtailment command."""
    tel = base_telemetry.model_copy(update={"is_curtailed": True, "curtailment_limit_kw": 1000.0})
    res = context_engine.evaluate_record(tel, base_residuals)
    assert res.state == OperationalContextState.CURTAILED
    assert res.is_suppressed is True
    assert res.precedence_level == 2
    assert res.metadata.get("curtailment_limit_kw") == 1000.0


def test_precedence_2_s4_curtailment_plus_heatwave(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 2: S4 co-occurring Grid Curtailment + Ambient Heatwave.

    Must resolve strictly to CURTAILED while retaining heatwave in metadata.
    """
    tel = base_telemetry.model_copy(
        update={
            "is_curtailed": True,
            "curtailment_limit_kw": 1000.0,
            "ambient_temp": 42.0,  # Extreme heatwave
        }
    )
    res = context_engine.evaluate_record(tel, base_residuals)
    assert res.state == OperationalContextState.CURTAILED
    assert res.is_suppressed is True
    assert res.precedence_level == 2
    # Check that secondary heatwave metadata is preserved
    assert res.metadata.get("co_occurring_heatwave") is True
    assert res.metadata.get("ambient_temp_c") == 42.0


def test_precedence_3_low_wind_idling(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 3: Wind speed below physical cut-in threshold (3.0 m/s)."""
    tel = base_telemetry.model_copy(update={"wind_speed": 2.1, "active_power": 0.0})
    res = context_engine.evaluate_record(tel, base_residuals)
    assert res.state == OperationalContextState.LOW_WIND_IDLE
    assert res.is_suppressed is True
    assert res.precedence_level == 3


def test_precedence_4_high_ambient_derate(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 4: High ambient temperature (>=38°C) within normal thermal rise."""
    tel = base_telemetry.model_copy(update={"ambient_temp": 39.5, "wind_speed": 9.0})
    res = context_engine.evaluate_record(tel, base_residuals)
    assert res.state == OperationalContextState.HIGH_AMBIENT_DERATE
    assert res.is_suppressed is True
    assert res.precedence_level == 4


def test_precedence_5_normal_operation(context_engine, base_telemetry, base_residuals):
    """Verifies Precedence 5: Standard nominal operating regime."""
    res = context_engine.evaluate_record(base_telemetry, base_residuals)
    assert res.state == OperationalContextState.NORMAL
    assert res.is_suppressed is False
    assert res.precedence_level == 5


def test_batch_evaluation_and_suppression_rate(context_engine, base_telemetry, base_residuals):
    """Verifies batch context evaluation and suppression rate computation."""
    records = [
        base_telemetry,                                                                     # Normal (not suppressed)
        base_telemetry.model_copy(update={"is_curtailed": True}),                           # Curtailment (suppressed)
        base_telemetry.model_copy(update={"wind_speed": 1.5}),                              # Low wind (suppressed)
        base_telemetry.model_copy(update={"ambient_temp": 40.0}),                           # Heatwave (suppressed)
        base_telemetry.model_copy(update={"operating_status": "Sensor Dropout"}),          # Dropout (suppressed)
    ]
    results = context_engine.evaluate_batch(records, [base_residuals] * 5)
    assert len(results) == 5
    assert results[0].state == OperationalContextState.NORMAL
    assert results[1].state == OperationalContextState.CURTAILED
    assert results[2].state == OperationalContextState.LOW_WIND_IDLE
    assert results[3].state == OperationalContextState.HIGH_AMBIENT_DERATE
    assert results[4].state == OperationalContextState.SENSOR_ANOMALY

    # 4 out of 5 suppressed
    overall_rate = context_engine.calculate_suppression_rate(results)
    assert overall_rate == 80.0

    # Subset of benign events (indices 1, 2, 3, 4) -> 100% suppression
    benign_rate = context_engine.calculate_suppression_rate(results, benign_indices=[1, 2, 3, 4])
    assert benign_rate == 100.0
