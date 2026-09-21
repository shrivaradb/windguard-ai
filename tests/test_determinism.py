"""Unit Tests for SCADA Simulation Determinism and Reproducibility."""

from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig


def test_simulation_exact_determinism_with_same_seed():
    """Verifies that two simulation executions with identical seed yield byte-for-byte identical records."""
    sim1 = SCADASimulator(default_seed=42)
    sim2 = SCADASimulator(default_seed=42)

    cfg = SimulationConfig(
        scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
        num_turbines=5,
        num_timesteps=36,
        random_seed=100
    )

    res1 = sim1.simulate(cfg)
    res2 = sim2.simulate(cfg)

    assert res1.total_records == res2.total_records
    assert len(res1.records) == len(res2.records)

    for i in range(len(res1.records)):
        r1 = res1.records[i]
        r2 = res2.records[i]
        assert r1.timestamp == r2.timestamp
        assert r1.turbine_id == r2.turbine_id
        assert r1.wind_speed == r2.wind_speed
        assert r1.ambient_temp == r2.ambient_temp
        assert r1.active_power == r2.active_power
        assert r1.gearbox_bearing_temp == r2.gearbox_bearing_temp
        assert r1.generator_stator_temp == r2.generator_stator_temp
        assert r1.pitch_angle == r2.pitch_angle
        assert r1.is_curtailed == r2.is_curtailed


def test_simulation_stochastic_variation_with_different_seeds():
    """Verifies that different seeds yield distinct random trajectories."""
    sim = SCADASimulator()

    cfg1 = SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, num_turbines=2, num_timesteps=20, random_seed=42)
    cfg2 = SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, num_turbines=2, num_timesteps=20, random_seed=999)

    res1 = sim.simulate(cfg1)
    res2 = sim.simulate(cfg2)

    # The random trajectories should not be identical
    powers1 = [r.active_power for r in res1.records]
    powers2 = [r.active_power for r in res2.records]

    assert powers1 != powers2
