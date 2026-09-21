"""Unit Tests for Eligible Energy & Financial Loss Engine (Layer 3).

Source of Truth:
- docs/07_srs.md §3.5
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.4 & §8 (TEST-LOSS-01)
"""

import pytest
from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.loss_calculator import (
    AggregatedLossSummary,
    LossCalculator,
    LossEligibility,
    RecordLossResult,
)
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.engine.tariff_registry import TariffProvenance, TariffRegistry
from backend.models.residual_engine import ResidualVector


@pytest.fixture
def loss_calculator() -> LossCalculator:
    return LossCalculator()


@pytest.fixture
def base_telemetry() -> TelemetryRecord:
    return TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-03",
        wind_speed=11.0,
        wind_direction=180.0,
        ambient_temp=25.0,
        active_power=1500.0,
        reactive_power=50.0,
        rotor_speed=15.0,
        generator_speed=1500.0,
        gearbox_bearing_temp=65.0,
        generator_stator_temp=70.0,
        nacelle_temp=30.0,
        pitch_angle=3.5,
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


def test_loss_eligibility_enum():
    """Verifies all canonical loss eligibility categories exist."""
    assert LossEligibility.ELIGIBLE_DEGRADATION == "ELIGIBLE_DEGRADATION"
    assert LossEligibility.CURTAILED_CAPACITY == "CURTAILED_CAPACITY"
    assert LossEligibility.LOW_WIND_IDLE == "LOW_WIND_IDLE"
    assert LossEligibility.EXCLUDED_SENSOR_ERROR == "EXCLUDED_SENSOR_ERROR"
    assert LossEligibility.NOMINAL_NO_DEFICIT == "NOMINAL_NO_DEFICIT"


def test_non_negative_power_deficit_clamping(loss_calculator, base_telemetry, normal_context):
    """Verifies that overperformance (actual > expected) is clamped to zero loss."""
    # Actual power = 1500 kW, Expected power = 1450 kW (overperformance)
    residuals = ResidualVector(
        expected_power_kw=1450.0,
        residual_power_kw=50.0,
        z_power=1.11,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    res = loss_calculator.calculate_record_loss(base_telemetry, residuals, normal_context)
    assert res.power_deficit_kw == 0.0
    assert res.energy_deficit_kwh == 0.0
    assert res.financial_loss_inr == 0.0
    assert res.eligibility == LossEligibility.NOMINAL_NO_DEFICIT


def test_s3_aerodynamic_pitch_degradation_loss(loss_calculator, base_telemetry, normal_context):
    """Verifies S3 Aerodynamic Pitch Degradation is included in maintenance financial loss."""
    # Expected power = 1850 kW, Actual power = 1500 kW -> Deficit = 350 kW
    residuals = ResidualVector(
        expected_power_kw=1850.0,
        residual_power_kw=-350.0,
        z_power=-7.78,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attribution = AttributionResult(
        subsystem=SubsystemLabel.AERODYNAMIC_PITCH,
        rule_confidence=0.88,
        is_persistent=True,
        excursion_count=6,
        window_size=6,
        matched_rule="RULE_AERODYNAMIC_PITCH_DEFICIT",
        explanation="Pitch asymmetry derate.",
    )

    # 350 kW * 10/60 h = 58.3333 kWh
    # Financial loss at ₹3.20/kWh = 58.3333 * 3.20 = ₹186.67
    res = loss_calculator.calculate_record_loss(base_telemetry, residuals, normal_context, attribution)
    assert res.eligibility == LossEligibility.ELIGIBLE_DEGRADATION
    assert res.power_deficit_kw == 350.0
    assert pytest.approx(res.eligible_degradation_energy_kwh, 0.01) == 58.33
    assert pytest.approx(res.financial_loss_inr, 0.01) == 186.67
    assert res.curtailed_capacity_kwh == 0.0


def test_s4_grid_curtailment_excluded_from_maintenance_loss(loss_calculator, base_telemetry):
    """Verifies S4 Grid Curtailment is tracked as curtailed capacity and EXCLUDED from maintenance loss."""
    tel = base_telemetry.model_copy(update={"is_curtailed": True, "curtailment_limit_kw": 1000.0, "active_power": 1000.0})
    curt_context = ContextResult(
        state=OperationalContextState.CURTAILED,
        is_suppressed=True,
        explanation="Grid curtailment dispatch.",
        precedence_level=2,
    )
    # Expected power = 2000 kW, Actual power = 1000 kW -> Deficit = 1000 kW
    residuals = ResidualVector(
        expected_power_kw=2000.0,
        residual_power_kw=-1000.0,
        z_power=-22.2,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr = AttributionResult(
        subsystem=SubsystemLabel.GRID_CURTAILMENT,
        rule_confidence=1.00,
        is_persistent=True,
        matched_rule="RULE_GRID_CURTAILMENT",
        explanation="Curtailment.",
    )

    res = loss_calculator.calculate_record_loss(tel, residuals, curt_context, attr)
    assert res.eligibility == LossEligibility.CURTAILED_CAPACITY
    assert pytest.approx(res.curtailed_capacity_kwh, 0.01) == 166.67  # 1000 kW * 10/60
    assert res.eligible_degradation_energy_kwh == 0.0
    assert res.financial_loss_inr == 0.0  # ZERO maintenance financial loss!


def test_low_wind_excluded_from_loss(loss_calculator, base_telemetry):
    """Verifies low-wind idling is excluded from loss calculations."""
    tel = base_telemetry.model_copy(update={"wind_speed": 2.2, "active_power": 0.0})
    low_wind_ctx = ContextResult(
        state=OperationalContextState.LOW_WIND_IDLE,
        is_suppressed=True,
        explanation="Low wind.",
        precedence_level=3,
    )
    residuals = ResidualVector(
        expected_power_kw=0.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=30.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=35.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    res = loss_calculator.calculate_record_loss(tel, residuals, low_wind_ctx)
    assert res.eligibility == LossEligibility.LOW_WIND_IDLE
    assert res.financial_loss_inr == 0.0
    assert res.eligible_degradation_energy_kwh == 0.0


def test_s5_sensor_dropout_excluded_from_loss(loss_calculator, base_telemetry):
    """Verifies S5 sensor dropout is tagged as excluded and incurs zero financial loss."""
    tel = base_telemetry.model_copy(update={"operating_status": OperatingStatus.SENSOR_DROPOUT.value})
    sensor_ctx = ContextResult(
        state=OperationalContextState.SENSOR_ANOMALY,
        is_suppressed=True,
        explanation="Sensor dropout.",
        precedence_level=1,
    )
    residuals = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=-500.0,
        z_power=-10.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=-40.0,
        z_gb=-15.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    res = loss_calculator.calculate_record_loss(tel, residuals, sensor_ctx)
    assert res.eligibility == LossEligibility.EXCLUDED_SENSOR_ERROR
    assert res.financial_loss_inr == 0.0
    assert res.eligible_degradation_energy_kwh == 0.0


def test_batch_losses_aggregation(loss_calculator, base_telemetry, normal_context):
    """Verifies multi-interval batch loss aggregation."""
    # 2 degradation records (58.33 kWh each) + 1 curtailment record (166.67 kWh)
    res_deg = ResidualVector(
        expected_power_kw=1850.0,
        residual_power_kw=-350.0,
        z_power=-7.78,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr_deg = AttributionResult(
        subsystem=SubsystemLabel.AERODYNAMIC_PITCH,
        rule_confidence=0.88,
        is_persistent=True,
        matched_rule="RULE_AERODYNAMIC_PITCH_DEFICIT",
        explanation="Pitch.",
    )

    res_curt = ResidualVector(
        expected_power_kw=2000.0,
        residual_power_kw=-1000.0,
        z_power=-22.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    ctx_curt = ContextResult(
        state=OperationalContextState.CURTAILED,
        is_suppressed=True,
        explanation="Curtailment.",
        precedence_level=2,
    )
    attr_curt = AttributionResult(
        subsystem=SubsystemLabel.GRID_CURTAILMENT,
        rule_confidence=1.00,
        is_persistent=True,
        matched_rule="RULE_GRID_CURTAILMENT",
        explanation="Curt.",
    )

    records = [base_telemetry, base_telemetry, base_telemetry.model_copy(update={"is_curtailed": True, "active_power": 1000.0})]
    res_list = [res_deg, res_deg, res_curt]
    ctx_list = [normal_context, normal_context, ctx_curt]
    attr_list = [attr_deg, attr_deg, attr_curt]

    summary = loss_calculator.calculate_batch_losses(records, res_list, ctx_list, attr_list)
    assert summary.total_records == 3
    assert pytest.approx(summary.eligible_degradation_energy_kwh, 0.1) == 116.67
    assert pytest.approx(summary.curtailed_capacity_kwh, 0.1) == 166.67
    assert pytest.approx(summary.maintenance_financial_loss_inr, 0.5) == 373.33
    assert summary.tariff_provenance.applied_rate_inr_per_kwh == 3.20
