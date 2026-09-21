"""Unit Tests for SCADA Simulation Engine and 5 Benchmark Scenarios."""

import pytest

from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, OperatingStatus, SimulationConfig, TurbineState


def test_aerodynamic_power_curve_regions(simulator: SCADASimulator):
    """Verifies that turbine aerodynamic power correctly models Regions I, II, III, and IV."""
    state = TurbineState(turbine_id="WTG-01", rated_power_kw=2000.0, cut_in_speed_mps=3.0, rated_speed_mps=12.0, cut_out_speed_mps=25.0)

    # Region I: Wind below cut-in (2.0 m/s) -> Power = 0 kW
    rec_r1 = simulator._update_turbine_physics(state, wind_speed=2.0, ambient_temp=25.0, wind_direction=180.0, timestamp_str="2026-09-20T12:00:00Z")
    assert rec_r1.active_power == 0.0

    # Region II: Partial load (7.5 m/s) -> Cubic power curve (0 < P < 2000)
    rec_r2 = simulator._update_turbine_physics(state, wind_speed=7.5, ambient_temp=25.0, wind_direction=180.0, timestamp_str="2026-09-20T12:10:00Z")
    assert 0.0 < rec_r2.active_power < 2000.0

    # Region III: Rated wind speed (13.0 m/s) -> Rated Power (2000 kW)
    rec_r3 = simulator._update_turbine_physics(state, wind_speed=13.0, ambient_temp=25.0, wind_direction=180.0, timestamp_str="2026-09-20T12:20:00Z")
    assert rec_r3.active_power == 2000.0

    # Region IV: Above cut-out (26.0 m/s) -> Cut-out shutdown (0 kW, pitch feathered 90°)
    rec_r4 = simulator._update_turbine_physics(state, wind_speed=26.0, ambient_temp=25.0, wind_direction=180.0, timestamp_str="2026-09-20T12:30:00Z")
    assert rec_r4.active_power == 0.0
    assert rec_r4.pitch_angle >= 85.0


def test_first_order_thermal_differential_lag(simulator: SCADASimulator):
    """Verifies thermal heating lag conforming to dT/dt = (T_target - T) / tau."""
    state = TurbineState(
        turbine_id="WTG-01",
        temp_gearbox_bearing=30.0,
        tau_thermal_gb=60.0  # 60 minutes
    )
    ambient = 25.0
    # Step at rated power (load_ratio = 1.0) -> Target temp = 25 + 25 = 50.0°C
    # For dt = 10 min: T(t+10) = 30 + (50 - 30) * (1 - exp(-10/60)) = 30 + 20 * (1 - 0.8465) = 30 + 3.07 = 33.07°C
    rec = simulator._update_turbine_physics(state, wind_speed=12.0, ambient_temp=ambient, wind_direction=180.0, timestamp_str="2026-09-20T12:00:00Z", dt_min=10.0)
    assert 32.5 <= rec.gearbox_bearing_temp <= 33.5


def test_scenario_s1_baseline_healthy(simulator: SCADASimulator):
    """Verifies Scenario S1 (Baseline Healthy Operation) produces valid normal telemetry."""
    cfg = SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, num_turbines=3, num_timesteps=24, random_seed=42)
    res = simulator.simulate(cfg)

    assert res.total_records == 3 * 24
    assert res.ground_truth.is_fault is False
    assert all(r.is_synthetic is True for r in res.records)
    assert all(r.is_curtailed is False for r in res.records)


def test_scenario_s2_gearbox_bearing_degradation(simulator: SCADASimulator):
    """Verifies Scenario S2 injects bearing friction thermal rise on WTG-07."""
    cfg = SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, num_turbines=10, num_timesteps=72, random_seed=42)
    res = simulator.simulate(cfg)

    assert res.ground_truth.is_fault is True
    assert res.ground_truth.affected_turbine_id == "WTG-07"
    assert res.ground_truth.fault_type == "GEARBOX_BEARING_OVERHEATING"

    # Compare WTG-07 bearing temp against healthy WTG-01 at the end of simulation
    wtg07_recs = [r for r in res.records if r.turbine_id == "WTG-07"]
    wtg01_recs = [r for r in res.records if r.turbine_id == "WTG-01"]

    # WTG-07 should exhibit elevated bearing temperature due to injected wear heat
    assert wtg07_recs[-1].gearbox_bearing_temp > wtg01_recs[-1].gearbox_bearing_temp + 10.0


def test_scenario_s3_pitch_asymmetry(simulator: SCADASimulator):
    """Verifies Scenario S3 injects aerodynamic derating on WTG-03."""
    cfg = SimulationConfig(scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY, num_turbines=5, num_timesteps=72, random_seed=42)
    res = simulator.simulate(cfg)

    assert res.ground_truth.is_fault is True
    assert res.ground_truth.affected_turbine_id == "WTG-03"
    assert res.ground_truth.fault_type == "PITCH_ASYMMETRY"

    wtg03_recs = [r for r in res.records if r.turbine_id == "WTG-03"]
    wtg01_recs = [r for r in res.records if r.turbine_id == "WTG-01"]

    # WTG-03 active power should be lower than healthy WTG-01
    assert wtg03_recs[-1].active_power < wtg01_recs[-1].active_power


def test_scenario_s4_grid_curtailment_heatwave(simulator: SCADASimulator):
    """Verifies Scenario S4 simulates grid curtailment and high ambient temperatures."""
    cfg = SimulationConfig(scenario=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE, num_turbines=5, num_timesteps=72, random_seed=42)
    res = simulator.simulate(cfg)

    assert res.ground_truth.is_fault is False
    assert res.ground_truth.fault_type == "GRID_CURTAILMENT"

    curtailed_recs = [r for r in res.records if r.is_curtailed]
    assert len(curtailed_recs) > 0
    # Power capped at 1000 kW and ambient temp high (heatwave)
    assert any(r.curtailment_limit_kw == 1000.0 for r in curtailed_recs)
    assert any(r.ambient_temp >= 35.0 for r in res.records)


def test_scenario_s5_sensor_dropout(simulator: SCADASimulator):
    """Verifies Scenario S5 injects thermocouple sensor dropout on WTG-09."""
    cfg = SimulationConfig(scenario=BenchmarkScenarioType.S5_SENSOR_DROPOUT, num_turbines=10, num_timesteps=72, random_seed=42)
    res = simulator.simulate(cfg)

    assert res.ground_truth.is_fault is True
    assert res.ground_truth.affected_turbine_id == "WTG-09"
    assert res.ground_truth.fault_type == "SENSOR_DROPOUT"

    dropout_recs = [r for r in res.records if r.turbine_id == "WTG-09" and r.operating_status == OperatingStatus.SENSOR_DROPOUT.value]
    assert len(dropout_recs) > 0
