"""Unit Tests for Multi-Signal Residual Attribution Reasoner (Layer 3).

Source of Truth:
- docs/07_srs.md §3.4
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.2 & §8 (TEST-REAS-01)
"""

import pytest
from backend.data.schema import TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.reasoner import (
    AttributionResult,
    MultiSignalReasoner,
    SubsystemLabel,
)
from backend.models.residual_engine import ResidualVector


@pytest.fixture
def reasoner() -> MultiSignalReasoner:
    return MultiSignalReasoner()


@pytest.fixture
def base_telemetry() -> TelemetryRecord:
    return TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-01",
        wind_speed=9.0,
        wind_direction=180.0,
        ambient_temp=25.0,
        active_power=1500.0,
        reactive_power=50.0,
        rotor_speed=14.5,
        generator_speed=1450.0,
        gearbox_bearing_temp=65.0,
        generator_stator_temp=70.0,
        nacelle_temp=30.0,
        pitch_angle=1.0,
        is_curtailed=False,
    )


@pytest.fixture
def normal_context() -> ContextResult:
    return ContextResult(
        state=OperationalContextState.NORMAL,
        is_suppressed=False,
        explanation="Normal operating regime.",
        precedence_level=5,
    )


def test_subsystem_labels_enum():
    """Verifies all 6 canonical subsystem attribution labels."""
    assert SubsystemLabel.DRIVETRAIN_GEARBOX == "DRIVETRAIN_GEARBOX"
    assert SubsystemLabel.GENERATOR_COOLING == "GENERATOR_COOLING"
    assert SubsystemLabel.AERODYNAMIC_PITCH == "AERODYNAMIC_PITCH"
    assert SubsystemLabel.GRID_CURTAILMENT == "GRID_CURTAILMENT"
    assert SubsystemLabel.SENSOR_ANOMALY == "SENSOR_ANOMALY"
    assert SubsystemLabel.NORMAL_OPERATION == "NORMAL_OPERATION"


def test_attribution_gearbox_thermal(reasoner, base_telemetry, normal_context):
    """Verifies attribution of Drivetrain Gearbox bearing degradation (S2)."""
    residuals = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=16.5,  # > 10.0°C
        z_gb=5.50,               # >= 2.5 sigma
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=2.0,
        z_gen=0.67,
    )
    attr = reasoner.evaluate_record(base_telemetry, residuals, normal_context)
    assert attr.subsystem == SubsystemLabel.DRIVETRAIN_GEARBOX
    assert attr.rule_confidence == 0.90
    assert 0.0 <= attr.rule_confidence <= 1.0
    assert "GEARBOX" in attr.matched_rule


def test_attribution_generator_cooling(reasoner, base_telemetry, normal_context):
    """Verifies attribution of Generator Stator Cooling fault."""
    residuals = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=2.0,
        z_gb=0.80,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=15.0,  # > 12.0°C
        z_gen=4.50,                # >= 2.5 sigma
    )
    attr = reasoner.evaluate_record(base_telemetry, residuals, normal_context)
    assert attr.subsystem == SubsystemLabel.GENERATOR_COOLING
    assert attr.rule_confidence == 0.85
    assert "GENERATOR" in attr.matched_rule


def test_attribution_aerodynamic_pitch(reasoner, base_telemetry, normal_context):
    """Verifies attribution of Aerodynamic Pitch asymmetry power derate (S3)."""
    residuals = ResidualVector(
        expected_power_kw=1850.0,
        residual_power_kw=-350.0,  # <= -200 kW
        z_power=-6.50,             # <= -2.0 sigma
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.5,
        z_gb=0.20,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.5,
        z_gen=0.17,
    )
    attr = reasoner.evaluate_record(base_telemetry, residuals, normal_context)
    assert attr.subsystem == SubsystemLabel.AERODYNAMIC_PITCH
    assert attr.rule_confidence == 0.88
    assert "PITCH" in attr.matched_rule


def test_attribution_grid_curtailment(reasoner, base_telemetry):
    """Verifies attribution of Grid Curtailment context (S4)."""
    curt_context = ContextResult(
        state=OperationalContextState.CURTAILED,
        is_suppressed=True,
        explanation="Grid curtailment active.",
        precedence_level=2,
    )
    residuals = ResidualVector(
        expected_power_kw=2000.0,
        residual_power_kw=-1000.0,
        z_power=-18.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr = reasoner.evaluate_record(base_telemetry, residuals, curt_context)
    assert attr.subsystem == SubsystemLabel.GRID_CURTAILMENT
    assert attr.rule_confidence == 1.00
    assert attr.is_persistent is True


def test_attribution_sensor_dropout(reasoner, base_telemetry):
    """Verifies attribution of Sensor Dropout (S5)."""
    sensor_context = ContextResult(
        state=OperationalContextState.SENSOR_ANOMALY,
        is_suppressed=True,
        explanation="Thermocouple sensor disconnected.",
        precedence_level=1,
    )
    residuals = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=-45.0,
        z_gb=-15.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr = reasoner.evaluate_record(base_telemetry, residuals, sensor_context)
    assert attr.subsystem == SubsystemLabel.SENSOR_ANOMALY
    assert attr.rule_confidence == 1.00


def test_attribution_normal_operation(reasoner, base_telemetry, normal_context):
    """Verifies attribution of Nominal Baseline Operation (S1)."""
    residuals = ResidualVector(
        expected_power_kw=1505.0,
        residual_power_kw=-5.0,
        z_power=-0.11,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.5,
        z_gb=0.20,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.5,
        z_gen=0.17,
    )
    attr = reasoner.evaluate_record(base_telemetry, residuals, normal_context)
    assert attr.subsystem == SubsystemLabel.NORMAL_OPERATION
    assert attr.rule_confidence == 1.00


def test_attribution_accuracy_metrics_calculation():
    """Verifies calculation of attribution accuracy, per-scenario metrics, and confusion matrix."""
    preds = [
        SubsystemLabel.NORMAL_OPERATION,
        SubsystemLabel.DRIVETRAIN_GEARBOX,
        SubsystemLabel.AERODYNAMIC_PITCH,
        SubsystemLabel.GRID_CURTAILMENT,
        SubsystemLabel.SENSOR_ANOMALY,
    ]
    gt = [
        SubsystemLabel.NORMAL_OPERATION,
        SubsystemLabel.DRIVETRAIN_GEARBOX,
        SubsystemLabel.AERODYNAMIC_PITCH,
        SubsystemLabel.GRID_CURTAILMENT,
        SubsystemLabel.SENSOR_ANOMALY,
    ]
    scenarios = ["S1", "S2", "S3", "S4", "S5"]

    metrics = MultiSignalReasoner.compute_attribution_metrics(preds, gt, scenarios)
    assert metrics["overall_accuracy_pct"] == 100.0
    assert metrics["total_eligible_records"] == 5
    assert metrics["correct_classifications"] == 5
    assert metrics["incorrect_classifications"] == 0
    assert metrics["per_scenario_accuracy"]["S1"]["accuracy_pct"] == 100.0
    assert metrics["confusion_matrix"]["DRIVETRAIN_GEARBOX"]["DRIVETRAIN_GEARBOX"] == 1
