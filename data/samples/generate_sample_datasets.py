"""Generates realistic open-access style benchmark SCADA CSV datasets for WindGuard AI."""

import os
from pathlib import Path
import numpy as np
import pandas as pd

def generate_samples():
    output_dir = Path("data/samples")
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(42)

    # =========================================================================
    # 1. Engie La Haute Borne Sample (France, MM82 2.05MW)
    # =========================================================================
    # 144 timesteps (24 hours @ 10-min interval)
    n_steps = 288 # 48 hours
    dates = pd.date_range("2024-03-15 00:00:00", periods=n_steps, freq="10min")

    # Realistic turbulent wind series
    wind = 4.0 + 5.5 * np.sin(np.linspace(0, 3 * np.pi, n_steps)) + rng.normal(0, 1.2, n_steps)
    wind = np.clip(wind, 1.0, 22.0)

    # Ambient temp: spring France 8°C - 18°C
    amb_temp = 12.0 + 4.0 * np.sin(np.linspace(0, 4 * np.pi, n_steps) - 1.5) + rng.normal(0, 0.4, n_steps)

    # Power curve for 2050 kW
    rated_kw = 2050.0
    power = np.zeros(n_steps)
    pitch = np.zeros(n_steps)
    rotor_spd = np.zeros(n_steps)
    gb_temp = np.zeros(n_steps)
    gen_temp = np.zeros(n_steps)

    for i, w in enumerate(wind):
        if w < 3.0 or w > 25.0:
            power[i] = 0.0
            pitch[i] = 85.0 if w > 25.0 else 0.0
            rotor_spd[i] = 2.0 + rng.uniform(0, 0.5)
        elif w < 12.0:
            ratio = (w - 3.0) / (12.0 - 3.0)
            power[i] = rated_kw * (ratio ** 3) + rng.normal(0, 15.0)
            pitch[i] = 0.5 + rng.normal(0, 0.1)
            rotor_spd[i] = 6.0 + 9.0 * (ratio ** 0.5) + rng.normal(0, 0.2)
        else:
            power[i] = rated_kw + rng.normal(0, 20.0)
            pitch[i] = 0.5 + 1.8 * (w - 12.0) + rng.normal(0, 0.2)
            rotor_spd[i] = 15.0 + rng.normal(0, 0.1)

        power[i] = max(0.0, min(rated_kw * 1.05, power[i]))
        load_ratio = power[i] / rated_kw
        gb_temp[i] = amb_temp[i] + 18.0 + (28.0 * load_ratio) + rng.normal(0, 0.5)
        gen_temp[i] = amb_temp[i] + 22.0 + (35.0 * load_ratio) + rng.normal(0, 0.6)

    # Injected subtle early bearing friction degradation in second half (steps 180-288)
    gb_temp[180:] += np.linspace(2.0, 14.5, n_steps - 180)

    df_engie = pd.DataFrame({
        "Date_and_time": [d.strftime("%Y-%m-%d %H:%M:%S") for d in dates],
        "Turbine_identifier": ["R80711 (WTG-01)"] * n_steps,
        "Wind_speed": np.round(wind, 2),
        "Active_power": np.round(power, 1),
        "Outdoor_temperature": np.round(amb_temp, 1),
        "Pitch_angle": np.round(pitch, 2),
        "Rotor_speed": np.round(rotor_spd, 2),
        "Gearbox_bearing_temperature": np.round(gb_temp, 1),
        "Generator_stator_temperature": np.round(gen_temp, 1),
    })
    df_engie.to_csv(output_dir / "real_lahauteborne_sample.csv", index=False)

    # =========================================================================
    # 2. Kelmarsh Wind Farm Sample (UK, Senvion MM92 2.05MW)
    # =========================================================================
    dates_k = pd.date_range("2024-05-10 00:00:00", periods=n_steps, freq="10min")
    wind_k = 7.0 + 4.0 * np.sin(np.linspace(0, 2.5 * np.pi, n_steps)) + rng.normal(0, 1.5, n_steps)
    wind_k = np.clip(wind_k, 2.0, 20.0)
    amb_k = 14.0 + 3.5 * np.sin(np.linspace(0, 4 * np.pi, n_steps) - 1.0) + rng.normal(0, 0.3, n_steps)

    power_k = np.zeros(n_steps)
    pitch_k = np.zeros(n_steps)
    curtailed_k = [False] * n_steps

    for i, w in enumerate(wind_k):
        if w < 3.0:
            power_k[i] = 0.0
            pitch_k[i] = 0.0
        elif w < 12.0:
            ratio = (w - 3.0) / 9.0
            power_k[i] = 2050.0 * (ratio ** 3) + rng.normal(0, 20.0)
            pitch_k[i] = 0.2 + rng.normal(0, 0.1)
        else:
            power_k[i] = 2050.0 + rng.normal(0, 25.0)
            pitch_k[i] = 0.5 + 1.8 * (w - 12.0)

        # Curtailment order during peak hours (steps 100 to 180)
        if 100 <= i <= 180:
            curtailed_k[i] = True
            power_k[i] = min(power_k[i], 800.0) # Derated to 800 kW by National Grid
            pitch_k[i] = max(pitch_k[i], 16.5 + rng.normal(0, 0.3))

        power_k[i] = max(0.0, power_k[i])

    df_kelmarsh = pd.DataFrame({
        "Timestamp": [d.strftime("%d/%m/%Y %H:%M") for d in dates_k],
        "Asset_ID": ["KLM-WTG03"] * n_steps,
        "Wspd_Avg": np.round(wind_k, 2),
        "P_Active_kW": np.round(power_k, 1),
        "Temp_Ambient_degC": np.round(amb_k, 1),
        "Blade_Pitch_Avg": np.round(pitch_k, 2),
        "Grid_Curtailment_Flag": [1 if c else 0 for c in curtailed_k],
    })
    df_kelmarsh.to_csv(output_dir / "real_kelmarsh_sample.csv", index=False)

    # =========================================================================
    # 3. Tamil Nadu High-Ambient Indian Wind Corridor (India, 2.1MW)
    # =========================================================================
    dates_ind = pd.date_range("2024-06-20 00:00:00", periods=n_steps, freq="10min")
    wind_ind = 9.0 + 3.0 * np.sin(np.linspace(0, 3 * np.pi, n_steps)) + rng.normal(0, 1.0, n_steps)
    wind_ind = np.clip(wind_ind, 3.0, 18.0)
    # Summer heatwave in corridor: 36°C - 44°C
    amb_ind = 38.0 + 4.5 * np.sin(np.linspace(0, 4 * np.pi, n_steps) - 1.2) + rng.normal(0, 0.4, n_steps)

    power_ind = np.zeros(n_steps)
    gb_ind = np.zeros(n_steps)
    gen_ind = np.zeros(n_steps)
    pitch_ind = np.zeros(n_steps)

    for i, w in enumerate(wind_ind):
        ratio = min(1.0, max(0.0, (w - 3.0) / 9.0))
        power_ind[i] = 2100.0 * (ratio ** 3) if w < 12.0 else 2100.0
        pitch_ind[i] = 0.5 if w < 12.0 else 1.8 * (w - 12.0)

        # Thermal rise under severe ambient heat
        load_r = power_ind[i] / 2100.0
        gb_ind[i] = amb_ind[i] + 20.0 + (25.0 * load_r) + rng.normal(0, 0.4)
        gen_ind[i] = amb_ind[i] + 24.0 + (32.0 * load_r) + rng.normal(0, 0.5)

    df_ind = pd.DataFrame({
        "time": [d.strftime("%Y-%m-%dT%H:%M:%SZ") for d in dates_ind],
        "turbine": ["T-IND-07"] * n_steps,
        "windspeed": np.round(wind_ind, 2),
        "power_kw": np.round(power_ind, 1),
        "ambient_temp": np.round(amb_ind, 1),
        "gearbox_temp": np.round(gb_ind, 1),
        "stator_temp": np.round(gen_ind, 1),
        "pitch": np.round(pitch_ind, 2),
    })
    df_ind.to_csv(output_dir / "real_indian_corridor_sample.csv", index=False)
    print("Generated 3 realistic benchmark datasets in data/samples/")

if __name__ == "__main__":
    generate_samples()
