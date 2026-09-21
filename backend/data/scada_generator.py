"""Physics-Informed Deterministic Wind-Turbine SCADA Simulation Engine.

Implements aerodynamic power curves, first-order differential thermal heating dynamics,
diurnal climate variations, and the 5 documented benchmark operating scenarios.

Source:
- docs/09_technical_design.md §2.1
- docs/10_data_architecture.md §2
- docs/14_implementation_plan.md §3 (Phase 1)
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

from backend.config import settings
from backend.data.schema import (
    BenchmarkScenarioType,
    GroundTruthLabel,
    OperatingStatus,
    SimulationConfig,
    SimulationResult,
    TelemetryRecord,
    TurbineState,
)


class SCADASimulator:
    """Generates physics-informed, deterministic synthetic wind-turbine SCADA telemetry."""

    def __init__(self, default_seed: int = 42):
        self.default_seed = default_seed
        self.turb_cfg = settings.TURBINE
        self.sim_cfg = settings.SIMULATION

    def _generate_wind_and_weather_series(
        self,
        rng: np.random.RandomState,
        num_timesteps: int,
        dt_min: float = 10.0,
        is_heatwave: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generates realistic correlated wind speed, direction, and ambient temperature series."""
        # Baseline wind series via auto-regressive Markov / Ornstein-Uhlenbeck process
        mean_wind = 8.5
        v_wind = np.zeros(num_timesteps)
        v_wind[0] = mean_wind + rng.normal(0, 1.0)
        phi = 0.92  # persistence factor for 10-minute intervals

        for t in range(1, num_timesteps):
            # AR(1) process with bounded turbulence
            v_wind[t] = phi * v_wind[t - 1] + (1 - phi) * mean_wind + rng.normal(0, 0.45)
            # Occasional transient gust
            if rng.rand() < 0.03:
                v_wind[t] += rng.uniform(2.0, 4.5)
            v_wind[t] = float(np.clip(v_wind[t], 0.5, 24.5))

        # Wind direction series: slow drift with boundary wrap [0, 360)
        v_dir = np.zeros(num_timesteps)
        v_dir[0] = 220.0
        for t in range(1, num_timesteps):
            v_dir[t] = (v_dir[t - 1] + rng.normal(0, 2.5)) % 360.0

        # Ambient temperature diurnal cycle (24h sine wave + noise)
        # 144 steps = 24 hours (step corresponds to 10 min)
        base_ambient = 38.0 if is_heatwave else 28.0
        amplitude = 4.5 if is_heatwave else 6.0
        t_ambient = np.zeros(num_timesteps)
        for t in range(num_timesteps):
            hour_angle = (2.0 * math.pi * (t % 144)) / 144.0
            diurnal = -amplitude * math.cos(hour_angle)  # min at dawn, max in afternoon
            t_ambient[t] = float(np.clip(base_ambient + diurnal + rng.normal(0, 0.3), -20.0, 50.0))

        return v_wind, v_dir, t_ambient

    def _update_turbine_physics(
        self,
        state: TurbineState,
        wind_speed: float,
        ambient_temp: float,
        wind_direction: float,
        timestamp_str: str,
        dt_min: float = 10.0,
        rng: Optional[np.random.RandomState] = None
    ) -> TelemetryRecord:
        """Calculates aerodynamic power and updates first-order differential thermal equilibrium.

        Formulation defined in docs/09_technical_design.md §2.1.
        """
        noise = rng.normal(0, 1.0) if rng is not None else 0.0

        # 1. Aerodynamic Power Curve
        if wind_speed < state.cut_in_speed_mps or wind_speed > state.cut_out_speed_mps:
            p_aero = 0.0
            pitch_angle = 90.0 if wind_speed > state.cut_out_speed_mps else 0.0
        elif wind_speed < state.rated_speed_mps:
            # Region II cubic aerodynamic response
            speed_ratio = (wind_speed - state.cut_in_speed_mps) / (state.rated_speed_mps - state.cut_in_speed_mps)
            p_aero = state.rated_power_kw * (speed_ratio ** 3)
            pitch_angle = 0.5 + 0.1 * noise
        else:
            # Region III rated power
            p_aero = state.rated_power_kw
            # Pitch actively sheds power to regulate at rated
            excess_speed = wind_speed - state.rated_speed_mps
            pitch_angle = 0.5 + 1.8 * excess_speed + 0.1 * noise

        # Apply aerodynamic degradation (Scenario S3)
        p_actual = p_aero * (1.0 - state.aerodynamic_derate_factor)

        # Apply Grid Curtailment setpoint limit (Scenario S4)
        operating_status = OperatingStatus.RUNNING.value
        if state.is_curtailed:
            operating_status = OperatingStatus.CURTAILED.value
            if state.curtailment_limit_kw is not None:
                p_actual = min(p_actual, state.curtailment_limit_kw)
            pitch_angle = max(pitch_angle, 15.0 + 0.2 * noise)

        # Handle idling / low-power state
        if p_actual < 5.0 and wind_speed < state.cut_in_speed_mps:
            operating_status = OperatingStatus.IDLING.value
            rotor_speed = max(0.5, 2.5 + 0.2 * noise)
            gen_speed = rotor_speed * self.turb_cfg.GEARBOX_RATIO * 0.2
        else:
            load_fraction = max(0.0, min(1.1, p_actual / state.rated_power_kw))
            rotor_speed = self.turb_cfg.RATED_ROTOR_RPM * (load_fraction ** 0.5) + 0.1 * noise
            rotor_speed = float(np.clip(rotor_speed, 0.0, 30.0))
            gen_speed = rotor_speed * self.turb_cfg.GEARBOX_RATIO + 2.0 * noise
            gen_speed = float(np.clip(gen_speed, 0.0, 2000.0))

        # 2. First-Order Thermal Differential Heating: dT/dt = (T_target - T_current) / tau
        load_ratio = max(0.0, p_actual / state.rated_power_kw)

        # Gearbox Bearing Thermal Target & Integration
        t_target_gb = ambient_temp + (self.turb_cfg.GB_TEMP_RISE_COEFF * load_ratio) + state.bearing_wear_heat_c + 0.2 * noise
        alpha_gb = 1.0 - math.exp(-dt_min / state.tau_thermal_gb)
        state.temp_gearbox_bearing += (t_target_gb - state.temp_gearbox_bearing) * alpha_gb

        # Generator Stator Thermal Target & Integration
        t_target_gen = ambient_temp + (self.turb_cfg.GEN_TEMP_RISE_COEFF * load_ratio) + state.gen_cooling_loss_heat_c + 0.2 * noise
        alpha_gen = 1.0 - math.exp(-dt_min / state.tau_thermal_gen)
        state.temp_gen_stator += (t_target_gen - state.temp_gen_stator) * alpha_gen

        # Nacelle Temp
        nacelle_temp = ambient_temp + 5.0 + (8.0 * load_ratio) + 0.1 * noise

        # Reactive Power
        q_actual = 0.08 * p_actual + 5.0 * noise

        return TelemetryRecord(
            timestamp=timestamp_str,
            turbine_id=state.turbine_id,
            wind_speed=round(float(wind_speed), 2),
            wind_direction=round(float(wind_direction), 1),
            ambient_temp=round(float(ambient_temp), 2),
            active_power=round(float(p_actual), 2),
            reactive_power=round(float(q_actual), 2),
            rotor_speed=round(float(rotor_speed), 2),
            generator_speed=round(float(gen_speed), 2),
            gearbox_bearing_temp=round(float(state.temp_gearbox_bearing), 2),
            generator_stator_temp=round(float(state.temp_gen_stator), 2),
            nacelle_temp=round(float(nacelle_temp), 2),
            pitch_angle=round(float(pitch_angle), 2),
            is_curtailed=state.is_curtailed,
            curtailment_limit_kw=state.curtailment_limit_kw if state.is_curtailed else None,
            operating_status=operating_status,
            is_synthetic=True
        )

    def simulate(self, config: Optional[SimulationConfig] = None) -> SimulationResult:
        """Executes a full multi-turbine deterministic simulation conforming to the requested scenario."""
        cfg = config or SimulationConfig()
        rng = np.random.RandomState(cfg.random_seed)

        start_dt = datetime.fromisoformat(cfg.start_timestamp.replace("Z", "+00:00"))
        is_heatwave = (cfg.scenario == BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE)

        # Generate weather profile
        v_wind_base, v_dir_base, t_amb_base = self._generate_wind_and_weather_series(
            rng=rng,
            num_timesteps=cfg.num_timesteps,
            dt_min=cfg.sampling_interval_min,
            is_heatwave=is_heatwave
        )

        # Initialize Turbine States (WTG-01 to WTG-N)
        turbines: Dict[str, TurbineState] = {}
        for i in range(1, cfg.num_turbines + 1):
            t_id = f"{self.sim_cfg.TURBINE_ID_PREFIX}-{i:02d}"
            init_amb = t_amb_base[0]
            turbines[t_id] = TurbineState(
                turbine_id=t_id,
                rated_power_kw=self.turb_cfg.RATED_POWER_KW,
                cut_in_speed_mps=self.turb_cfg.CUT_IN_SPEED_MPS,
                rated_speed_mps=self.turb_cfg.RATED_SPEED_MPS,
                cut_out_speed_mps=self.turb_cfg.CUT_OUT_SPEED_MPS,
                temp_gearbox_bearing=init_amb + 15.0,
                temp_gen_stator=init_amb + 20.0,
                tau_thermal_gb=self.turb_cfg.TAU_THERMAL_GB_MIN,
                tau_thermal_gen=self.turb_cfg.TAU_THERMAL_GEN_MIN
            )

        # Ground truth metadata initialization
        ground_truth = self._build_ground_truth_label(cfg, start_dt)

        all_records: List[TelemetryRecord] = []

        # Fault onset parameters for benchmark scenarios
        fault_onset_step = 36  # 6 hours in
        dropout_onset_step = 48  # 8 hours in

        for t in range(cfg.num_timesteps):
            curr_dt = start_dt + timedelta(minutes=t * cfg.sampling_interval_min)
            timestamp_str = curr_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            for i in range(1, cfg.num_turbines + 1):
                t_id = f"{self.sim_cfg.TURBINE_ID_PREFIX}-{i:02d}"
                state = turbines[t_id]

                # Local micro-turbulence variance across farm layout
                local_wind = float(np.clip(v_wind_base[t] + rng.normal(0, 0.25), 0.0, 50.0))
                local_dir = float(v_dir_base[t] + rng.normal(0, 1.0)) % 360.0
                local_amb = float(t_amb_base[t] + rng.normal(0, 0.15))

                # Inject Scenario-Specific Dynamics
                if cfg.scenario == BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION:
                    # Injected on WTG-07
                    if t_id == "WTG-07" and t >= fault_onset_step:
                        progression = min(1.0, (t - fault_onset_step) / 36.0)
                        state.bearing_wear_heat_c = 16.5 * progression

                elif cfg.scenario == BenchmarkScenarioType.S3_PITCH_ASYMMETRY:
                    # Injected on WTG-03
                    if t_id == "WTG-03" and t >= fault_onset_step:
                        progression = min(1.0, (t - fault_onset_step) / 24.0)
                        state.aerodynamic_derate_factor = 0.18 * progression

                elif cfg.scenario == BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE:
                    # Grid curtailment active on WTG-01 through WTG-05
                    if t >= fault_onset_step and i <= 5:
                        state.is_curtailed = True
                        state.curtailment_limit_kw = 1000.0

                record = self._update_turbine_physics(
                    state=state,
                    wind_speed=local_wind,
                    ambient_temp=local_amb,
                    wind_direction=local_dir,
                    timestamp_str=timestamp_str,
                    dt_min=cfg.sampling_interval_min,
                    rng=rng
                )

                # Inject Scenario S5 Sensor Dropout (on WTG-09)
                if cfg.scenario == BenchmarkScenarioType.S5_SENSOR_DROPOUT and t_id == "WTG-09" and t >= dropout_onset_step:
                    # Disconnected thermocouple signal drops to impossible value (0.0 or disconnected below ambient)
                    record.gearbox_bearing_temp = local_amb - 15.0  # violates thermal plausibility
                    record.operating_status = OperatingStatus.SENSOR_DROPOUT.value
                    record.quality_flags = {"gearbox_bearing_temp": "SENSOR_DROPOUT"}

                all_records.append(record)

        return SimulationResult(
            config=cfg,
            ground_truth=ground_truth,
            total_records=len(all_records),
            records=all_records,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    def _build_ground_truth_label(self, cfg: SimulationConfig, start_dt: datetime) -> GroundTruthLabel:
        """Constructs explicit ground truth metadata for the simulation scenario."""
        if cfg.scenario == BenchmarkScenarioType.S1_BASELINE_HEALTHY:
            return GroundTruthLabel(
                scenario_id=cfg.scenario,
                scenario_name="Baseline Healthy Operation",
                is_fault=False,
                description="Healthy multi-turbine fleet operating under normal meteorological and thermal conditions."
            )
        elif cfg.scenario == BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION:
            start_time = (start_dt + timedelta(minutes=36 * cfg.sampling_interval_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return GroundTruthLabel(
                scenario_id=cfg.scenario,
                scenario_name="Gearbox High-Speed Bearing Degradation",
                is_fault=True,
                fault_type="GEARBOX_BEARING_OVERHEATING",
                affected_subsystem="DRIVETRAIN",
                affected_turbine_id="WTG-07",
                start_time=start_time,
                description="High-speed shaft bearing friction degradation causing thermal excursion (+16.5°C above baseline)."
            )
        elif cfg.scenario == BenchmarkScenarioType.S3_PITCH_ASYMMETRY:
            start_time = (start_dt + timedelta(minutes=36 * cfg.sampling_interval_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return GroundTruthLabel(
                scenario_id=cfg.scenario,
                scenario_name="Pitch Asymmetry / Aerodynamic Loss",
                is_fault=True,
                fault_type="PITCH_ASYMMETRY",
                affected_subsystem="AERODYNAMIC_ROTOR",
                affected_turbine_id="WTG-03",
                start_time=start_time,
                description="Blade pitch misalignment resulting in 18% aerodynamic power deficit with normal thermal baseline."
            )
        elif cfg.scenario == BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE:
            start_time = (start_dt + timedelta(minutes=36 * cfg.sampling_interval_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return GroundTruthLabel(
                scenario_id=cfg.scenario,
                scenario_name="Grid Curtailment & Ambient Summer Heatwave",
                is_fault=False,
                fault_type="GRID_CURTAILMENT",
                affected_subsystem="GRID_DISPATCH",
                affected_turbine_id="WTG-01 to WTG-05",
                start_time=start_time,
                description="Active grid dispatch power capping (1000 kW) during high ambient summer conditions (>=40°C). Not an equipment fault."
            )
        elif cfg.scenario == BenchmarkScenarioType.S5_SENSOR_DROPOUT:
            start_time = (start_dt + timedelta(minutes=48 * cfg.sampling_interval_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return GroundTruthLabel(
                scenario_id=cfg.scenario,
                scenario_name="Sensor Dropout & Thermocouple Disconnection",
                is_fault=True,
                fault_type="SENSOR_DROPOUT",
                affected_subsystem="SENSOR_AUXILIARY",
                affected_turbine_id="WTG-09",
                start_time=start_time,
                description="Thermocouple sensor electrical disconnection resulting in anomalous unphysical temperature readings."
            )
        else:
            return GroundTruthLabel(
                scenario_id=cfg.scenario,
                scenario_name="Custom Simulation",
                is_fault=False,
                description="Custom telemetry simulation run."
            )
