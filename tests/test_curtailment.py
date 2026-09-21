"""Unit Tests for SCADA Curtailment Representation and Dynamics."""

from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, OperatingStatus, SimulationConfig, TurbineState


def test_curtailment_explicit_state_representation(simulator: SCADASimulator):
    """Verifies that curtailment is represented explicitly via is_curtailed rather than inferred."""
    state = TurbineState(
        turbine_id="WTG-01",
        is_curtailed=True,
        curtailment_limit_kw=800.0
    )

    # Under strong wind (10.0 m/s), uncurtailed power would be ~1400 kW, but curtailed should be capped at 800 kW
    rec = simulator._update_turbine_physics(
        state=state,
        wind_speed=10.0,
        ambient_temp=25.0,
        wind_direction=180.0,
        timestamp_str="2026-09-20T12:00:00Z"
    )

    assert rec.is_curtailed is True
    assert rec.active_power == 800.0
    assert rec.pitch_angle >= 15.0
    assert rec.operating_status == OperatingStatus.CURTAILED.value


def test_curtailment_vs_low_wind_distinction(simulator: SCADASimulator):
    """Verifies that low power from curtailment is explicitly distinct from low power due to low wind."""
    # Turbine A: Low wind idling (2.0 m/s, is_curtailed=False)
    state_idle = TurbineState(turbine_id="WTG-01", is_curtailed=False)
    rec_idle = simulator._update_turbine_physics(state_idle, wind_speed=2.0, ambient_temp=25.0, wind_direction=180.0, timestamp_str="2026-09-20T12:00:00Z")

    # Turbine B: Curtailment under high wind (12.0 m/s, is_curtailed=True, limit=500 kW)
    state_curt = TurbineState(turbine_id="WTG-02", is_curtailed=True, curtailment_limit_kw=500.0)
    rec_curt = simulator._update_turbine_physics(state_curt, wind_speed=12.0, ambient_temp=25.0, wind_direction=180.0, timestamp_str="2026-09-20T12:00:00Z")

    assert rec_idle.is_curtailed is False
    assert rec_idle.operating_status == OperatingStatus.IDLING.value
    assert rec_idle.wind_speed < 3.0

    assert rec_curt.is_curtailed is True
    assert rec_curt.operating_status == OperatingStatus.CURTAILED.value
    assert rec_curt.wind_speed >= 12.0
    assert rec_curt.active_power == 500.0
