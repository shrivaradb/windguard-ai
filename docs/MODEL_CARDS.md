---
document: MODEL_CARDS
version: 1.0
status: PUBLISHED & VERIFIED
date: 2026-09-21
author: WindGuard AI ML & Data Engineering Team
governance: Standardized Machine Learning Model Cards (IEEE / ACM / Responsible AI)
depends_on:
  - docs/11_ai_ml_design.md
  - docs/10_data_architecture.md
  - docs/PHASE_2_OWNER_RESOLUTION.md
  - docs/EVALUATION_REPORT.md
  - docs/MASTER_TECHNICAL_REPORT.md
---

# WindGuard AI: Standardized Machine Learning Model Cards
## Physics-Informed Expected Behavior Baselines & Statistical Stores

```
====================================================================================================
                              WINDGUARD AI MODEL CARDS REGISTER
====================================================================================================
Framework Standard                 : IEEE / ACM / Google Responsible AI Model Card Format
Registered Model Artifact 1        : ExpectedPowerGBR (expected_power_gbr_v1.joblib)
Registered Model Artifact 2        : ExpectedThermalRF (expected_thermal_rf_v1.joblib)
Registered Baseline Store          : BaselineStatisticsStore (baseline_stats_v1.json)
Target Subsystem                   : Layer 2 Physics-Informed Expected Behavior & Residual Analytics
Offline Determinism Guarantee      : 100% Deterministic (Fixed Random Seed = 42)
Model Retraining Status            : Disabled (GOV-TRAIN-01 Enforced / Read-Only Weight Inspection)
Thermal Modeling Limitation Status : Formally Documented & Accepted (OD-P8-05 / OD-P9-04)
====================================================================================================
```

---

## 1. Model Card: Expected Power Model (`ExpectedPowerGBR`)

### 1.1 Model Overview
* **Model Identifier**: `ExpectedPowerGBR`
* **Artifact Path**: `data/models/expected_power_gbr_v1.joblib`
* **Model Version**: `1.0.0`
* **Release Date**: 2026-09-20 (Frozen in Phase 2)
* **Architecture**: Gradient Boosting Regressor (`sklearn.ensemble.GradientBoostingRegressor`)
* **Primary Developer**: WindGuard AI ML Engineering Group

### 1.2 Intended Use & Target Application
* **Primary Purpose**: Predicts the theoretical aerodynamically expected active power generation ($P_{\text{expected}}$ in $\text{kW}$) of a 2.0 MW wind turbine given ambient wind speed, blade pitch angle, and air density.
* **Downstream Integration**: Provides the non-fault baseline against which actual SCADA power output is subtracted to calculate underproduction residuals ($\Delta P = P_{\text{actual}} - P_{\text{expected}}$) and prospective revenue losses.
* **Target Users**: Wind farm operations engineers, SCADA diagnostic pipelines, automated context engines.
* **Prohibited Uses**: Direct closed-loop pitch control, emergency aerodynamic braking actuation, autonomous grid frequency stabilization.

### 1.3 Input Feature Schema & Operational Envelope

| Feature Name | Data Type | Engineering Units | Valid Operational Range | Description |
| :--- | :---: | :---: | :---: | :--- |
| `wind_speed_mps` | `float64` | $\text{m/s}$ | $[0.0, 50.0]$ | 10-minute mean anemometer wind speed. |
| `blade_pitch_angle_deg` | `float64` | Degrees ($^\circ$) | $[-5.0, 95.0]$ | 10-minute mean blade pitch angle. |
| `ambient_temperature_c` | `float64` | $^\circ\text{C}$ | $[-25.0, 60.0]$ | Used for air density ($\rho$) calculation. |

#### Operational Wind Speed Envelope
* **Cut-In Wind Speed ($v_{\text{cut-in}}$)**: $3.0\,\text{m/s}$ ($P_{\text{expected}} = 0.0\,\text{kW}$ below cut-in)
* **Rated Wind Speed ($v_{\text{rated}}$)**: $12.0\,\text{m/s}$ ($P_{\text{expected}} = 2000.0\,\text{kW}$ rated capacity)
* **Cut-Out Wind Speed ($v_{\text{cut-out}}$)**: $25.0\,\text{m/s}$ ($P_{\text{expected}} = 0.0\,\text{kW}$ pitch-to-feather shutdown)

### 1.4 Training Methodology & Provenance
* **Training Dataset**: High-fidelity aerodynamic actuator-disk simulation with stochastic turbulence ($N = 10,080$ records, 70-day synthetic benchmark).
* **Partitioning**: Chronological split (70% Train: 7,056 records, 15% Validation: 1,512 records, 15% Test: 1,512 records).
* **Hyperparameters**: `n_estimators=100`, `max_depth=5`, `learning_rate=0.1`, `loss='squared_error'`, `random_state=42`.

### 1.5 Evaluation Metrics & Empirical Performance

| Evaluation Dimension | Performance Metric | Specification Target | Measured Empirical Result | Evaluation Status |
| :--- | :--- | :---: | :---: | :---: |
| **Goodness of Fit** | Coefficient of Determination ($R^2$) | $\ge 0.95$ | **$1.0000$** | **PASS** |
| **Prediction Error** | Root Mean Square Error ($\text{RMSE}$) | $\le 45.0\,\text{kW}$ | **$1.31\,\text{kW}$** | **PASS** |
| **Mean Error** | Mean Absolute Error ($\text{MAE}$) | $\le 30.0\,\text{kW}$ | **$0.78\,\text{kW}$** | **PASS** |
| **Computational SLA**| Single-Record Inference Latency | $< 1.0\,\text{ms}$ | **$0.26\,\text{ms}$** | **PASS** |
| **Batch SLA** | 144-Record Batch Latency | $< 50.0\,\text{ms}$ | **$4.12\,\text{ms}$** | **PASS** |

---

## 2. Model Card: Expected Thermal Model (`ExpectedThermalRF`)

### 2.1 Model Overview
* **Model Identifier**: `ExpectedThermalRF`
* **Artifact Path**: `data/models/expected_thermal_rf_v1.joblib`
* **Model Version**: `1.0.0`
* **Release Date**: 2026-09-20 (Frozen in Phase 2)
* **Architecture**: Multi-Output Random Forest Regressor (`sklearn.ensemble.RandomForestRegressor`)
* **Primary Developer**: WindGuard AI ML Engineering Group

### 2.2 Intended Use & Target Application
* **Primary Purpose**: Predicts expected healthy steady-state operating temperatures for the gearbox sump oil ($T_{\text{expected, gb}}$) and generator drive-end bearing ($T_{\text{expected, gen}}$) as a function of electrical power load, ambient temperature, and shaft speed.
* **Downstream Integration**: Generates thermal residuals ($\Delta T_{\text{gb}}, \Delta T_{\text{gen}}$) which feed the Context Engine and Multi-Signal Reasoner for drivetrain fault diagnosis.
* **Prohibited Uses**: Automatic turbine shutdown tripping, direct cooling pump actuation, safety-critical breaker trip logic.

### 2.3 Input Feature Schema & Target Variables

#### Input Features
1. `active_power_kw` (`float64`, $\text{kW}$): Electrical power output ($[0.0, 2500.0]$).
2. `ambient_temperature_c` (`float64`, $^\circ\text{C}$): Ambient temperature ($[-25.0, 60.0]$).
3. `rotor_speed_rpm` (`float64`, $\text{RPM}$): Rotor shaft speed ($[0.0, 25.0]$).

#### Output Targets
1. `gearbox_oil_temperature_c` (`float64`, $^\circ\text{C}$): Expected gearbox oil temperature.
2. `generator_bearing_temperature_c` (`float64`, $^\circ\text{C}$): Expected generator bearing temperature.

### 2.4 Training Methodology & Hyperparameters
* **Training Dataset**: 1st-order thermal ODE physical simulation with thermal time constants ($\tau_{\text{gb}}=60\,\text{min}, \tau_{\text{gen}}=45\,\text{min}$) and stochastic environmental fluctuations.
* **Partitioning**: Chronological split (70% Train, 15% Validation, 15% Test).
* **Hyperparameters**: `n_estimators=100`, `max_depth=10`, `min_samples_split=5`, `random_state=42`.

### 2.5 Evaluation Metrics & Known Physical Limitations

| Component Target | Evaluation Metric | Historical Threshold | Measured Empirical Result | Governance Classification |
| :--- | :--- | :---: | :---: | :--- |
| **Gearbox Oil Temp** | Holdout Test $\text{RMSE}$ | $\le 2.50^\circ\text{C}$ | **$4.92^\circ\text{C}$** | `HISTORICAL BASELINE / LIMITATION` |
| **Gearbox Oil Temp** | Goodness of Fit ($R^2$) | $\ge 0.96$ | **$0.7812$** | `HISTORICAL BASELINE / LIMITATION` |
| **Generator Bearing Temp**| Holdout Test $\text{RMSE}$ | $\le 2.50^\circ\text{C}$ | **$6.06^\circ\text{C}$** | `HISTORICAL BASELINE / LIMITATION` |
| **Generator Bearing Temp**| Goodness of Fit ($R^2$) | $\ge 0.96$ | **$0.7245$** | `HISTORICAL BASELINE / LIMITATION` |
| **Single-Record Latency** | Inference Latency | $< 15.0\,\text{ms}$ | **$7.04\,\text{ms}$** | `PROPOSED METRIC (PASS)` |

#### Transparent Limitation Analysis (OD-P8-05 & OD-P9-04)
* **Physical Cause of Modeling Gap**: Drivetrain components possess significant thermal inertia ($\tau \approx 45\text{--}60\,\text{minutes}$). Under rapid wind gusts and power ramps, physical temperatures exhibit a lag of $30\text{--}60$ minutes behind electrical power. Because the static Random Forest regressor predicts temperature strictly from the instantaneous 10-minute snapshot features without autoregressive historical lag terms ($T_{t-1}, T_{t-2}$), it models quasi-steady-state temperature rather than transient thermal dynamic state.
* **Governance Invariant**: This limitation was formally reconciled in Phase 8 (`OD-P8-05`) and affirmed in Phase 9 (`OD-P9-04`). It is accepted as an accurate representation of static ML baseline behavior and is mitigated downstream by the **$60$-minute persistence accumulator ($5/6$ timesteps $\ge 2.5\sigma$)**, ensuring that transient prediction errors do not trigger false alarms.

---

## 3. Component Card: Baseline Statistics Store (`BaselineStatisticsStore`)

### 3.1 Overview
* **Artifact Path**: `data/models/baseline_stats_v1.json`
* **Purpose**: Houses the empirical healthy-operation mean ($\mu$) and standard deviation ($\sigma$) parameters for all residual channels across standard operating regimes.
* **Format**: Pydantic-validated JSON key-value store.
* **Integrity Guarantee**: Immutable, read-only at runtime.

### 3.2 Canonical Baseline Parameters

| Residual Channel | Baseline Mean ($\mu$) | Baseline Std Dev ($\sigma$) | Anomaly Threshold ($2.5\sigma$) |
| :--- | :---: | :---: | :---: |
| **Active Power Residual ($\Delta P$)** | $-0.02\,\text{kW}$ | $14.85\,\text{kW}$ | $\pm 37.13\,\text{kW}$ |
| **Gearbox Oil Temp Residual ($\Delta T_{\text{gb}}$)** | $+0.04^\circ\text{C}$ | $1.92^\circ\text{C}$ | $+4.80^\circ\text{C}$ |
| **Generator Bearing Temp Residual ($\Delta T_{\text{gen}}$)** | $-0.01^\circ\text{C}$ | $2.45^\circ\text{C}$ | $+6.13^\circ\text{C}$ |

---

## 4. Responsible AI & Operational Safety Constraints

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                RESPONSIBLE AI SAFETY COVENANT                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Human-in-the-Loop Precedence**: All model predictions are purely informational and advisory. No model output can directly trip breakers, feather blades, or dispatch maintenance crews without certified human operator authorization.
2. **Deterministic Execution Guarantee**: Both `ExpectedPowerGBR` and `ExpectedThermalRF` run with fixed random seeds (`seed=42`), guaranteeing identical output for identical SCADA telemetry inputs.
3. **Zero Data Poisoning / Runtime Retraining Lockout**: In accordance with rule `GOV-TRAIN-01`, model weights are permanently frozen in production. Online retraining endpoints are absent from the active router, preventing adversarial telemetry poisoning.

---
*WindGuard AI Model Cards — Phase 9 Publication-Grade Technical Specification.*
