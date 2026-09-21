# Phase 2 Scope & Traceability Review

**Project**: WindGuard AI  
**Subsystem**: Phase 2 — Physics-Informed ML Baselines & Residual Engine (Layer 2)  
**Review Type**: Final Pre-Implementation Hardening & Traceability Gate Review  
**Date**: 2026-09-20  
**Status**: REVIEW COMPLETE (HARDENED)  
**Review Base**: `docs/00_documentation_index.md` through `docs/14_implementation_plan.md`, `docs/DOCUMENTATION_REVIEW.md`, `docs/PHASE_1_VERIFICATION.md`, and Phase 1 Codebase/Tests.

---

## 1. Phase 2 Objective

The primary objective of **Phase 2** is to build, train, validate, serialize, and test the **Layer 2 Deterministic Analytical ML & Residual Engine** for **WindGuard AI**.

Specifically, Phase 2 implements:
1. An empirical **Expected Power Regressor** ($\hat{P} = f(v_{\text{wind}}, T_{\text{ambient}}, \theta_{\text{pitch}})$) modeling the non-linear aerodynamic power curve under healthy operating regimes.
2. Component **Expected Thermal Equilibrium Baselines** ($\hat{T}_{\text{GB}} = g_{\text{GB}}(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}})$ and $\hat{T}_{\text{Gen}} = h_{\text{Gen}}(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}})$) capturing steady-state thermodynamic equilibrium for drivetrain gearbox bearings and generator stator windings.
3. A **Residual Engine** calculating raw physical residuals ($\Delta P, \Delta T_{\text{GB}}, \Delta T_{\text{Gen}}$) and standardized rolling statistical $z$-scores ($z_{\text{power}}, z_{\text{GB}}, z_{\text{Gen}}$) with persistence tracking calibrated against healthy baseline variance ($\mu, \sigma$).

Phase 2 establishes the quantitative analytical foundation upon which subsequent context filtering (Phase 3), technical document retrieval (Phase 4), and advisory synthesis (Phase 5) strictly depend.

---

## 2. Confirmed Phase 2 Components

Based on exhaustive inspection of `docs/14_implementation_plan.md` §3 (Phase 2), `docs/09_technical_design.md` §2.2, `docs/11_ai_ml_design.md` §1–§4, `docs/08_system_architecture.md` §3.2, and `docs/07_srs.md` §3.2 (`SRS-ML-01`), the following three components constitute the **exclusive and deterministic scope of Phase 2**:

| Component Name | Authoritative Source | Section Reference | Primary Purpose | Inputs | Outputs | Canonical Algorithm (Phase 2) | Requirement Type | Documented Acceptance Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ExpectedPowerModel`** | `docs/09_technical_design.md`<br>`docs/11_ai_ml_design.md`<br>`docs/14_implementation_plan.md` | `docs/09` §2.2<br>`docs/11` §2.1 & §4<br>`docs/14` §3 | Predicts expected aerodynamic healthy power output $\hat{P}$ | $[v_{\text{wind}}, T_{\text{ambient}}, \theta_{\text{pitch}}]$ (m/s, °C, deg) | $\hat{P}$ (Expected Power in kW) | **`GradientBoostingRegressor`** (`scikit-learn`) | Explicitly Required (`FR-002`, `SRS-ML-01`) | `[TARGET: R² ≥ 0.95]`<br>`[TARGET: RMSE ≤ 45 kW]`<br>`[TARGET: MAE ≤ 30 kW]`<br>`[TARGET: Latency < 1 ms]` |
| **`ExpectedThermalModel`** | `docs/09_technical_design.md`<br>`docs/11_ai_ml_design.md`<br>`docs/14_implementation_plan.md` | `docs/09` §2.2<br>`docs/11` §2.2 & §4<br>`docs/14` §3 | Predicts expected component thermal baselines $\hat{T}_{\text{GB}}$ and $\hat{T}_{\text{Gen}}$ | $[P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}}]$ (kW, °C, RPM) | $\hat{T}_{\text{GB}}, \hat{T}_{\text{Gen}}$ (Expected temps in °C) | **`RandomForestRegressor`** (`scikit-learn`) | Explicitly Required (`FR-003`, `SRS-ML-01`) | `[TARGET: RMSE ≤ 2.5°C]`<br>`[TARGET: R² ≥ 0.96]`<br>`[TARGET: Latency < 1 ms]` |
| **`ResidualEngine`** | `docs/09_technical_design.md`<br>`docs/11_ai_ml_design.md`<br>`docs/14_implementation_plan.md` | `docs/09` §2.2<br>`docs/11` §2.3<br>`docs/14` §3 | Computes physical residuals ($\Delta P, \Delta T$), $z$-scores, and persistence | Live `TelemetryRecord`, trained models, and `BaselineStats` | `ResidualVector` ($\hat{P}, \Delta P, z_P, \hat{T}_{\text{GB}}, \Delta T_{\text{GB}}, z_{\text{GB}}, \hat{T}_{\text{Gen}}, \Delta T_{\text{Gen}}, z_{\text{Gen}}$) | Deterministic Analytical Mathematics | Explicitly Required (`SRS-ML-01`, `TEST-ML-01`) | Exact residual math;<br>Canonical $\theta_{\text{thresh}} = 2.5\sigma$;<br>`[TARGET: Compute < 50 ms]` |

> [!IMPORTANT]
> **Canonical Algorithm Lockout**:
> - `ExpectedPowerModel` is strictly locked to **`GradientBoostingRegressor`** (`scikit-learn`).
> - `ExpectedThermalModel` is strictly locked to **`RandomForestRegressor`** (`scikit-learn`).
> - Any alternative machine learning algorithms (e.g. LightGBM, XGBoost, Neural Networks, LSTMs, MultiOutputRegressor) are classified as future research experimentation and are **STRICTLY OUT OF SCOPE for Phase 2**.

---

## 3. ExpectedPowerModel Traceability

The technical specification of `ExpectedPowerModel` is traced directly to the documentation suite:

### 3.1 Target Variable
- **Variable**: Active Power $P_{\text{actual}}$
- **Unit**: Kilowatts ($\text{kW}$)
- **Valid Range**: $0.0\,\text{kW}$ to $2750.0\,\text{kW}$ (Rated: $2000.0\,\text{kW}$ for benchmark 2.X MW turbine).

### 3.2 Input Features
- **Operational Aerodynamic Vector** $\mathbf{x}_{\text{aero}}(t) = [v_{\text{wind}}(t), T_{\text{ambient}}(t), \theta_{\text{pitch}}(t)]^T \in \mathbb{R}^3$ (`docs/11` §2.1, `docs/09` §2.2):
  1. `wind_speed` ($v_{\text{wind}}$): 10-minute average wind speed in $\text{m/s}$ ($[0.0, 50.0]$).
  2. `ambient_temp` ($T_{\text{ambient}}$): 10-minute average ambient temperature in $^\circ\text{C}$ ($[-25.0, 60.0]$).
  3. `pitch_angle` ($\theta_{\text{pitch}}$): 10-minute average blade pitch angle in degrees ($[-5.0, 95.0]$).
- **Optional Derived Feature**: Air Density $\rho_{\text{air}} = \frac{101325}{287.05 \times (T_{\text{ambient}} + 273.15)}$ (`docs/11` §3) [CONFIGURABLE].
- **Feature Exclusions**: `is_curtailed` is **NOT** a predictive feature; it serves strictly as a data filtering and routing condition. Ground truth labels (`is_fault`, `fault_type`, `scenario_id`) and `quality_flags` are strictly excluded from the feature matrix.

### 3.3 Model Family & Justification
- **Canonical Algorithm**: **`GradientBoostingRegressor`** from `scikit-learn` (`docs/11` §4, `docs/08` ADR-004, `docs/14` §3).
- **Hyperparameter Baseline**: `n_estimators=100`, `max_depth=5`, `learning_rate=0.1`, `random_state=42`.
- **Justification**: Captures the non-linear cubic aerodynamic power rise in Region II and the flat saturation in Region III, trains in $<2.5\,\text{s}$, executes in $<0.1\,\text{ms}$, and provides deterministic feature attribution (`docs/08` ADR-004).

### 3.4 Training Methodology & Data Filtering
- **Training Corpus**: Certified normal, healthy operational data (Scenario S1 Baseline Healthy, uncurtailed, non-fault data).
- **Curtailment Exclusion**: Records with `is_curtailed == True` MUST BE EXCLUDED from training (`docs/11` §1, `docs/09` §2.1).
- **Sensor Quality Exclusion**: Records flagged with unphysical values, rate-of-change violations, or `SENSOR_DROPOUT` MUST BE EXCLUDED from training (`docs/10` §5, `docs/07` §3.1).
- **Fault Exclusion**: Data from fault scenarios (S2 bearing degradation, S3 pitch asymmetry, S4 curtailment/heatwave, S5 sensor dropout) MUST NEVER be present in training sets.

### 3.5 Evaluation Metrics & Documented Targets
- **Coefficient of Determination**: `[TARGET: R² ≥ 0.95]` (`docs/14` §3, `docs/06` FR-002, `docs/11` §6.1).
- **Root Mean Squared Error**: `[TARGET: RMSE ≤ 45 kW]` (`docs/11` §6.1).
- **Mean Absolute Error**: `[TARGET: MAE ≤ 30 kW]` (`docs/11` §6.1).
- **Inference Latency**: `[TARGET: < 1 ms]` per inference (`docs/14` §3, `docs/11` §4).

---

## 4. ExpectedThermalModel Traceability

The technical specification of `ExpectedThermalModel` is traced directly to the documentation suite:

### 4.1 Target Temperature Variables
- **Gearbox High-Speed Bearing Temperature**: $T_{\text{GB}}$ ($^\circ\text{C}$, range: $[-10.0, 130.0]^\circ\text{C}$).
- **Generator Stator Winding Temperature**: $T_{\text{Gen}}$ ($^\circ\text{C}$, range: $[0.0, 160.0]^\circ\text{C}$).

### 4.2 Canonical Algorithm
- **Canonical Algorithm**: **`RandomForestRegressor`** from `scikit-learn` (`docs/11` §4 "Selected for Thermal Baselines").
- **Hyperparameter Baseline**: `n_estimators=100`, `max_depth=10`, `random_state=42`.
- **Architecture**: Dual regressor estimators or multi-output random forest modeling steady-state thermal baselines:
  $$\hat{T}_{\text{GB}} = g_{\text{GB}}(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}}), \quad \hat{T}_{\text{Gen}} = h_{\text{Gen}}(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}})$$
- **Scope Restriction**: Any alternative thermal model algorithm (e.g. GradientBoosting, Neural Networks, Physics-only ODEs) is strictly out of scope for Phase 2.

### 4.3 Input Features
- **Operational Thermal Vector** $\mathbf{x}_{\text{therm}}(t) = [P_{\text{active}}(t), T_{\text{ambient}}(t), \omega_{\text{rotor}}(t)]^T \in \mathbb{R}^3$ (`docs/11` §2.2, `docs/09` §2.2):
  1. `active_power` ($P_{\text{active}}$): Active electrical power in $\text{kW}$.
  2. `ambient_temp` ($T_{\text{ambient}}$): Ambient temperature in $^\circ\text{C}$.
  3. `rotor_speed` ($\omega_{\text{rotor}}$): Rotor rotational speed in $\text{RPM}$ (and/or `generator_speed` $\omega_{\text{gen}}$ for generator baseline as documented in `docs/07` §3.2).
- **Optional Derived Features**: Load Ratio ($P / P_{\text{rated}}$) and Gearbox Slip Ratio ($\omega_{\text{gen}} / \omega_{\text{rotor}}$) (`docs/11` §3) [CONFIGURABLE].

### 4.4 Evaluation Metrics & Documented Targets
- **Root Mean Squared Error**: `[TARGET: RMSE ≤ 2.5°C]` (`docs/14` §3, `docs/06` FR-003).
- **Coefficient of Determination**: `[TARGET: R² ≥ 0.96]` (`docs/11` §4).
- **Inference Latency**: `[TARGET: < 1 ms]` per inference (`docs/14` §3, `docs/11` §4).

---

## 5. ResidualEngine Traceability

The `ResidualEngine` computes physical deviations and statistical standardized anomalies between observed telemetry and expected baselines:

### 5.1 Documented Mathematical Formulations (`docs/11` §2.1–§2.3, `docs/09` §2.2)

1. **Power Residual**:
   $$R_{\text{power}}(t) = P_{\text{actual}}(t) - \hat{P}(t) \quad [\text{kW}]$$

2. **Gearbox Bearing Thermal Residual**:
   $$R_{\text{GB}}(t) = T_{\text{GB\_actual}}(t) - \hat{T}_{\text{GB}}(t) \quad [^\circ\text{C}]$$

3. **Generator Stator Thermal Residual**:
   $$R_{\text{Gen}}(t) = T_{\text{Gen\_actual}}(t) - \hat{T}_{\text{Gen}}(t) \quad [^\circ\text{C}]$$

4. **Statistical Standardization ($z$-score)**:
   $$z_i(t) = \frac{R_i(t) - \mu_{R_i}}{\sigma_{R_i}}$$
   where $\mu_{R_i}, \sigma_{R_i}$ are empirical mean and standard deviation calibrated strictly on the healthy validation dataset.

5. **Canonical Temporal Persistence Formulation**:
   $$\text{Persistence}(t) = \frac{1}{W} \sum_{k=0}^{W-1} \mathbb{I}\left(|z_i(t-k)| \ge \theta_{\text{thresh}}\right) \ge 0.80$$
   - **Canonical Persistence Threshold**: $\mathbf{\theta_{\text{thresh}} = 2.5\sigma}$
   - **Sliding Window Length**: $W=6$ consecutive 10-minute intervals ($1\,\text{hour}$).
   - **Persistence Ratio**: $\ge 0.80$ (at least 5 out of 6 consecutive intervals exceeding $2.5\sigma$).

> [!IMPORTANT]
> **Canonical Threshold Unification**: The threshold $\mathbf{\theta_{\text{thresh}} = 2.5\sigma}$ is the single canonical statistical persistence threshold for Phase 2, eliminating previous document ambiguity between $2.0\sigma$ and $2.5\sigma$.

### 5.2 Output Schema (`docs/09` §2.2 `ResidualVector`)
```python
class ResidualVector(BaseModel):
    expected_power_kw: float
    residual_power_kw: float
    z_power: float
    expected_gb_temp_c: float
    residual_gb_temp_c: float
    z_gb: float
    expected_gen_temp_c: float
    residual_gen_temp_c: float
    z_gen: float
```

### 5.3 Clear Layer Boundaries (Phase 2 vs. Phase 3)

| Functional Responsibility | Layer & Phase Assignment | Component Owner |
| :--- | :--- | :--- |
| **Expected-value regression prediction** ($\hat{P}, \hat{T}_{\text{GB}}, \hat{T}_{\text{Gen}}$) | **Layer 2 (Phase 2)** | `ExpectedPowerModel`, `ExpectedThermalModel` |
| **Raw physical residual calculation** ($\Delta P, \Delta T_{\text{GB}}, \Delta T_{\text{Gen}}$) | **Layer 2 (Phase 2)** | `ResidualEngine` |
| **Standardized $z$-score calculation** ($z_P, z_{\text{GB}}, z_{\text{Gen}}$) | **Layer 2 (Phase 2)** | `ResidualEngine` |
| **Rolling statistical persistence calculation** ($W=6, \theta_{\text{thresh}}=2.5\sigma$) | **Layer 2 (Phase 2)** | `ResidualEngine` |
| **`ResidualVector` generation & schema validation** | **Layer 2 (Phase 2)** | `ResidualEngine` |
| **Contextual alarm suppression** (`is_curtailed`, ambient heat derating) | **Layer 3 (Phase 3)** | `ContextFilterEngine` (STRICTLY OUT OF SCOPE FOR PHASE 2) |
| **Fault & root-cause interpretation** (Subsystem isolation) | **Layer 3 (Phase 3)** | `MultiSignalReasoner` (STRICTLY OUT OF SCOPE FOR PHASE 2) |
| **Multi-signal correlation & prioritization scoring** | **Layer 3 (Phase 3)** | `PrioritizationEngine` (STRICTLY OUT OF SCOPE FOR PHASE 2) |
| **Deterministic financial loss & tariff provenance** | **Layer 3 (Phase 3)** | `LossCalculator`, `TariffRegistry` (STRICTLY OUT OF SCOPE FOR PHASE 2) |

---

## 6. Data Sources & Dataset Policy

### 6.1 Primary Training Dataset
Phase 2 ML models must be trained **EXCLUSIVELY on certified healthy normal operational data**:
- **Primary Training Dataset**: Synthetic Scenario S1 (Baseline Healthy Operation, $N = 1,440$ to $10,080$ records across multi-turbine fleet, seed 42) generated deterministically by `SCADASimulator` and watermarked with `is_synthetic=True`.

### 6.2 External / Benchmark SCADA Dataset Policy
- Real / public benchmark datasets (`data/benchmarks/sample_scada.csv`, Kelmarsh, Penmanshiel) must **NOT** automatically be mixed into Phase 2 training data.
- Benchmark data is classified strictly as **Optional External Validation Data** and requires explicit prior verification of:
  1. Schema compatibility (canonical column naming).
  2. Physical units (kW, m/s, °C, RPM).
  3. Turbine nameplate rating (scaling parameters).
  4. Sampling interval (10-minute average resolution).
  5. Sensor semantics (thermocouple locations).
  6. Verified healthy operating-period filtering.
- Public benchmark data is **not claimed** to be automatically representative of the WindGuard target fleet.

### 6.3 Treatment of Benchmark Scenarios

| Scenario | Title | Treatment in Phase 2 Training | Treatment in Phase 2 Testing / Verification |
| :--- | :--- | :--- | :--- |
| **S1** | Baseline Healthy Operation | **PRIMARY TRAINING & VALIDATION** (Certified healthy baseline) | Regression accuracy evaluation ($R^2$, RMSE, MAE, baseline $\mu \approx 0, \sigma$) |
| **S2** | Gearbox Bearing Degradation | **STRICTLY EXCLUDED** (Fault contamination) | **SYNTHETIC TEST ONLY**: Verify scenario verification criteria ($R_{\text{GB}} > +10^\circ\text{C}, z_{\text{GB}} > +2.5\sigma$) |
| **S3** | Pitch Asymmetry / Derate | **STRICTLY EXCLUDED** (Fault contamination) | **SYNTHETIC TEST ONLY**: Verify scenario verification criteria ($R_{\text{power}} < -200\,\text{kW}, z_P < -2.0\sigma$) |
| **S4** | Grid Curtailment & Heatwave | **STRICTLY EXCLUDED** (Operational constraint) | **SYNTHETIC TEST ONLY**: Verify power deficit and ambient tracking without mechanical alarm |
| **S5** | Sensor Dropout | **STRICTLY EXCLUDED** (Sensor failure) | **SYNTHETIC TEST ONLY**: Verify preprocessor dropout handling and model robustness |

---

## 7. Train/Validation/Test Strategy

To ensure zero temporal or cross-scenario contamination:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│             SCENARIO S1 BASELINE HEALTHY TELEMETRY (CHRONOLOGICAL)           │
└─────────────────────────────────────────────────────────────────────────────┘
  0%                                     70%             85%            100%
  ├───────────────────────────────────────┼───────────────┼───────────────┤
  │              TRAINING SET             │  VALIDATION   │   TEST SET    │
  │                 (70%)                 │     (15%)     │     (15%)     │
  └───────────────────────────────────────┴───────────────┴───────────────┘
```

1. **Chronological Deterministic Split**:
   - **Training Set (70%)**: Chronologically earliest 70% of Scenario S1 healthy records.
   - **Validation Set (15%)**: Subsequent 15% of chronological time-series (used for tuning and calibrating baseline statistics $\mu, \sigma$).
   - **Test Set (15%)**: Final 15% of chronological time-series (used for holdout regression evaluation).
2. **Role of `random_state=42`**:
   - `random_state=42` applies **STRICTLY** to the internal stochastic algorithms of `GradientBoostingRegressor` and `RandomForestRegressor` during model fitting.
   - `random_state` does **NOT** control or randomize the dataset split; the split is purely chronological and deterministic based on time ordering.
3. **Isolated Fault Test Sets**: Scenarios S2, S3, S4, S5 are kept in strictly separate evaluation sets and evaluated only during inference verification.

---

## 8. Curtailment Handling

The relationship between `is_curtailed` and Phase 2 models is strictly defined:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 SCADA TELEMETRY RECORD                  │
                  └─────────────────────────────────────────────────────────┘
                                               │
                                       is_curtailed?
                                       /           \
                                      /             \
                                [ YES ]             [ NO ]
                                  │                   │
                                  ▼                   ▼
                     EXCLUDE FROM TRAINING     INCLUDE IN TRAINING
                     (Prevents distortion of   (Learns authentic physical
                      healthy power curve)      aerodynamic conversion)
                                  │                   │
                                  └─────────┬─────────┘
                                            │
                                            ▼
                               [ LIVE INFERENCE PHASE ]
                                            │
                                            ▼
                     ExpectedPowerModel computes expected healthy P_exp
                                            │
                                            ▼
                       ResidualEngine computes raw ΔP = P_act - P_exp
                                            │
                                            ▼
                      TelemetryRecord.is_curtailed passed to Layer 3
                   (Phase 3 ContextEngine suppresses spurious alarm)
```

1. **Not a Predictive Feature**: `is_curtailed` is **NEVER** fed as an input feature into `ExpectedPowerModel` or `ExpectedThermalModel`.
2. **Training Exclusion Filter**: All records with `is_curtailed == True` are strictly filtered out before model fitting.
3. **Inference Routing**: During live inference, curtailed records pass through `ExpectedPowerModel` to calculate the physical power deficit ($\Delta P = P_{\text{curtailed}} - \hat{P}_{\text{healthy}}$), which is then passed to Layer 3 for contextual suppression.

---

## 9. Sensor Quality Handling

1. **Physical Range Violations**: Records failing physical minimum/maximum thresholds (e.g., $v_{\text{wind}} < 0$, $T_{\text{ambient}} > 60^\circ\text{C}$) are rejected by `SCADAPreprocessor` and never reach model training.
2. **Thermocouple Plausibility Rule**: Thermocouple disconnects ($T_{\text{GB}} < T_{\text{ambient}} - 5.0^\circ\text{C}$) are flagged as `ANOMALOUS_SENSOR` and excluded from thermal model training.
3. **Short Missing Gaps ($1-2$ steps)**: Linearly interpolated records with `quality_flags = {"feature": "INTERPOLATED_LINEAR"}` may be ingested for continuous inference.
4. **Prolonged Dropout ($>2$ steps)**: Records flagged as `SENSOR_DROPOUT` are excluded from training. In inference mode, the engine produces explicit sensor failure notices rather than false mechanical degradation scores.
5. **Quality Flag Isolation**: `quality_flags` dictionaries are metadata tags for routing and auditing; they are **NEVER** encoded as numerical features in regression models.

---

## 10. Feature Engineering Traceability

The complete, verified feature inventory for Phase 2:

| Feature Name | Source Field | Unit | Physical Purpose | Document Reference | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `wind_speed` | `TelemetryRecord.wind_speed` | $\text{m/s}$ | Primary aerodynamic kinetic energy input | `docs/11` §2.1, `docs/09` §2.2 | **EXPLICIT CORE** |
| `ambient_temp` | `TelemetryRecord.ambient_temp` | $^\circ\text{C}$ | Air density modifier & thermal boundary baseline | `docs/11` §2.1, `docs/09` §2.2 | **EXPLICIT CORE** |
| `pitch_angle` | `TelemetryRecord.pitch_angle` | $\text{deg}$ | Blade aerodynamic angle of attack & power regulation | `docs/11` §2.1, `docs/09` §2.2 | **EXPLICIT CORE** |
| `active_power` | `TelemetryRecord.active_power` | $\text{kW}$ | Thermal loading / electrical heat dissipation input | `docs/11` §2.2, `docs/09` §2.2 | **EXPLICIT CORE** |
| `rotor_speed` | `TelemetryRecord.rotor_speed` | $\text{RPM}$ | Drivetrain rotational velocity & mechanical friction | `docs/11` §2.2, `docs/09` §2.2 | **EXPLICIT CORE** |
| `generator_speed` | `TelemetryRecord.generator_speed` | $\text{RPM}$ | High-speed shaft speed & generator stator loading | `docs/07` §3.2 | **EXPLICIT CORE** |
| $\rho_{\text{air}}$ (Air Density) | Derived: $\frac{101325}{287.05 \cdot (T_{\text{amb}} + 273.15)}$ | $\text{kg/m}^3$ | Normalizes aerodynamic power for air density shifts | `docs/11` §3 | **CONFIGURABLE DERIVED** |
| $\text{Load Ratio}$ | Derived: $P_{\text{active}} / P_{\text{rated}}$ | $-$ | Normalized electrical loading factor | `docs/11` §3 | **CONFIGURABLE DERIVED** |
| $\text{Gearbox Ratio Slip}$ | Derived: $\frac{\omega_{\text{gen}}}{\omega_{\text{rotor}}} - \text{Ratio}_{\text{nom}}$ | $-$ | Drivetrain mechanical slippage / clutch degradation | `docs/11` §3 | **CONFIGURABLE DERIVED** |

### Verified Feature Exclusions
- **Fault Labels**: `is_fault`, `fault_type`, `affected_subsystem` $\implies$ **EXCLUDED**.
- **Scenario Metadata**: `scenario_id`, `scenario_name`, `BenchmarkScenarioType` $\implies$ **EXCLUDED**.
- **Data Quality Metadata**: `quality_flags` $\implies$ **EXCLUDED**.
- **Operational Dispatch**: `is_curtailed` $\implies$ **EXCLUDED** from feature matrix.

---

## 11. Training Pipeline

The Phase 2 training and serialization workflow is formulated as a 12-step deterministic pipeline:

```mermaid
flowchart TD
    S1[1. Load Scenario S1 SCADA Data] --> S2[2. Preprocessing & Quality Filtering]
    S2 --> S3[3. Filter is_curtailed == False & Status == Running]
    S3 --> S4[4. Chronological 70/15/15 Split]
    S4 --> S5[5. Feature Matrix & Target Extraction]
    S5 --> S6[6. Fit ExpectedPowerModel GBR random_state=42]
    S5 --> S7[7. Fit ExpectedThermalModel RF random_state=42]
    S6 --> S8[8. Evaluate Metrics on Validation & Test Sets]
    S7 --> S8
    S8 --> S9[9. Calibrate BaselineStats mu, sigma on Validation Residuals]
    S9 --> S10[10. Populate model_metadata.json with Measured Results]
    S10 --> S11[11. Save Serialized Artifacts via joblib]
    S11 --> S12[12. Execute Automated Verification Suite]
```

1. **Data Loading**: Load Scenario S1 SCADA records via `SCADADataLoader`.
2. **Quality Filtering**: Drop invalid sensor records using `SCADAPreprocessor`.
3. **Curtailment Filtering**: Filter out `is_curtailed == True` records.
4. **Chronological Splitting**: Deterministically partition into 70% Train, 15% Validation, 15% Test.
5. **Feature/Target Extraction**: Construct $\mathbf{X}_{\text{aero}} \to y_{\text{power}}$ and $\mathbf{X}_{\text{therm}} \to (y_{\text{GB}}, y_{\text{Gen}})$.
6. **Power Model Fitting**: Train `GradientBoostingRegressor(random_state=42, n_estimators=100, max_depth=5)`.
7. **Thermal Model Fitting**: Train `RandomForestRegressor(random_state=42, n_estimators=100, max_depth=10)`.
8. **Validation Evaluation**: Calculate $R^2$, RMSE, MAE on validation and test sets.
9. **Baseline Calibration**: Compute residual sample statistics ($\mu_P, \sigma_P, \mu_{\text{GB}}, \sigma_{\text{GB}}, \mu_{\text{Gen}}, \sigma_{\text{Gen}}$) on validation split.
10. **Metadata Manifest Generation**: Populate `model_metadata.json` with actual post-training measured metrics.
11. **Artifact Serialization**: Persist model binaries via `joblib` into `backend/models/artifacts/` or `data/models/`.
12. **Gate Validation**: Run automated regression, persistence, and latency benchmark tests.

---

## 12. Evaluation Metrics & Targets

All quantitative metrics and verification criteria are classified strictly into three distinct categories:

### Category A: Engineering Design TARGETS
Design goals specified in the engineering requirements:

| Metric Identifier | Metric Name | Formulation | Classification | Documented Target | Source Reference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **METRIC-PWR-R2** | Power Curve $R^2$ Score | $1 - \frac{\sum (P_i - \hat{P}_i)^2}{\sum (P_i - \bar{P})^2}$ | **TARGET** | $R^2 \ge 0.95$ | `docs/14` §3, `docs/06` FR-002, `docs/11` §6.1 |
| **METRIC-PWR-RMSE** | Power Curve RMSE | $\sqrt{\frac{1}{N}\sum (P_i - \hat{P}_i)^2}$ | **TARGET** | $\text{RMSE} \le 45.0\,\text{kW}$ | `docs/11` §6.1 |
| **METRIC-PWR-MAE** | Power Curve MAE | $\frac{1}{N}\sum |P_i - \hat{P}_i|$ | **TARGET** | $\text{MAE} \le 30.0\,\text{kW}$ | `docs/11` §6.1 |
| **METRIC-THM-RMSE** | Thermal Baseline RMSE | $\sqrt{\frac{1}{N}\sum (T_i - \hat{T}_i)^2}$ | **TARGET** | $\text{RMSE} \le 2.5^\circ\text{C}$ | `docs/14` §3, `docs/06` FR-003 |
| **METRIC-THM-R2** | Thermal Baseline $R^2$ | $1 - \frac{\sum (T_i - \hat{T}_i)^2}{\sum (T_i - \bar{T})^2}$ | **TARGET** | $R^2 \ge 0.96$ | `docs/11` §4 |
| **METRIC-LAT-INF** | Single Inference Latency | Elapsed time per `predict()` | **TARGET** | $< 1.0\,\text{ms}$ per record | `docs/14` §3, `docs/11` §4 |
| **METRIC-LAT-RES** | Residual Vector Latency | Elapsed time for `compute_residuals()` | **TARGET** | $< 50.0\,\text{ms}$ batch / $< 1.0\,\text{ms}$ single | `docs/06` FR-002 |

### Category B: Measured Phase 2 RESULTS
- **Current Status**: **NONE YET**. Actual measured values will be computed and recorded strictly post-implementation upon test suite execution.

### Category C: Synthetic Scenario Verification Criteria
Scenario-specific verification thresholds derived from the Phase 1 synthetic ground truth / simulation physics:

| Scenario | Verification Parameter | Scenario-Specific Threshold | Significance | Source Reference |
| :--- | :--- | :--- | :--- | :--- |
| **S2** (Bearing Degradation) | Gearbox Thermal Residual | $R_{\text{GB}} > +10.0^\circ\text{C}$, $z_{\text{GB}} > +2.5\sigma$ | Confirms model detects $+16.5^\circ\text{C}$ injected bearing degradation | `docs/10` §2, `docs/09` §2.1 |
| **S3** (Pitch Asymmetry) | Power Residual | $R_{\text{power}} < -200.0\,\text{kW}$, $z_P < -2.0\sigma$ | Confirms model detects $18\%$ aerodynamic derate | `docs/10` §2, `docs/09` §2.1 |
| **S4** (Curtailment/Heatwave) | Power Deficit & Thermal Rise | $R_{\text{power}} < 0$, $R_{\text{GB}} < +6.0^\circ\text{C}$ | Confirms power deficit without anomalous thermal rise | `docs/09` §2.3 |

> [!WARNING]
> **Not General Real-World Thresholds**: The thresholds in Category C are scenario-specific synthetic verification criteria designed to validate the simulator's injected failure signatures. They are **NOT** universal real-world wind turbine diagnostic thresholds.

---

## 13. Leakage Prevention

A rigorous leakage prevention audit confirms:

1. **Ground-Truth Label Isolation**:
   - `GroundTruthLabel.is_fault`, `GroundTruthLabel.fault_type`, `GroundTruthLabel.affected_subsystem`, and `GroundTruthLabel.scenario_id` are strictly excluded from feature matrices.
2. **Scenario ID Isolation**:
   - Models have zero access to `scenario_name` or `scenario_id`.
3. **Target Isolation**:
   - $P_{\text{actual}}$ is the target $y$ for `ExpectedPowerModel` and never an input feature.
   - $T_{\text{GB}}$ and $T_{\text{Gen}}$ are targets for `ExpectedThermalModel` and never input features.
4. **Chronological Split Isolation**:
   - Training sets and testing sets are strictly disjoint in time.
   - Baseline statistics ($\mu, \sigma$) are computed exclusively on validation data, never on the holdout test set.
5. **Quality Flag Isolation**:
   - `quality_flags` (e.g. `INTERPOLATED_LINEAR`) are metadata fields, never converted to numerical predictor columns.

---

## 14. Model Persistence & Versioning

### 14.1 Persistence Mechanism
- **Serialization Framework**: Standard `joblib` serialization.
- **Directory Location**: `data/models/` or `backend/models/artifacts/`.
- **File Naming Convention**:
  - `expected_power_gbr_v1.joblib`
  - `expected_thermal_rf_v1.joblib`
  - `baseline_stats_v1.json`
  - `model_metadata.json`

### 14.2 Model Metadata Manifest Schema (`model_metadata.json`)
Every serialized model artifact is paired with an immutable metadata manifest. **All metric fields remain null/placeholder until populated by actual post-training evaluation**:

```json
{
  "model_name": "expected_power_gbr",
  "model_version": "1.0.0",
  "algorithm": "GradientBoostingRegressor",
  "framework": "scikit-learn",
  "feature_names": ["wind_speed", "ambient_temp", "pitch_angle"],
  "target_variable": "active_power",
  "training_dataset": "synthetic_s1_baseline_healthy_seed42",
  "is_synthetic_training_data": true,
  "training_timestamp": null,
  "random_seed": 42,
  "hyperparameters": {
    "n_estimators": 100,
    "learning_rate": 0.1,
    "max_depth": 5,
    "random_state": 42
  },
  "metrics": {
    "r2_score": null,
    "rmse_kw": null,
    "mae_kw": null
  }
}
```

---

## 15. API / Service Boundary

### 15.1 Internal Service Interfaces
Phase 2 primarily exposes clean, typed Python interfaces:
```python
class ExpectedPowerModel:
    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> "ExpectedPowerModel": ...
    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray: ...
    def save(self, filepath: Path) -> None: ...
    @classmethod
    def load(cls, filepath: Path) -> "ExpectedPowerModel": ...

class ExpectedThermalModel:
    def fit(self, X: pd.DataFrame | np.ndarray, y_gb: np.ndarray, y_gen: np.ndarray) -> "ExpectedThermalModel": ...
    def predict(self, X: pd.DataFrame | np.ndarray) -> Tuple[np.ndarray, np.ndarray]: ...
    def save(self, filepath: Path) -> None: ...
    @classmethod
    def load(cls, filepath: Path) -> "ExpectedThermalModel": ...

class ResidualEngine:
    def __init__(self, power_model: ExpectedPowerModel, thermal_model: ExpectedThermalModel, baseline_stats: BaselineStats): ...
    def compute_residuals(self, telemetry: TelemetryRecord) -> ResidualVector: ...
    def compute_batch_residuals(self, records: List[TelemetryRecord]) -> List[ResidualVector]: ...
```

### 15.2 REST Endpoints (Phase 2 Analytical Boundary)
- `POST /api/models/train` (Development / Test Pipeline Utility): Triggers training and validation pipeline on healthy baseline data.
- `POST /api/models/residuals` (Analytical Endpoint): Computes `ResidualVector` for a given `TelemetryRecord`.
- `GET /api/turbines/{turbine_id}/telemetry` (Phase 1 endpoint): Remains functional.

*Phase 3+ endpoints (`/api/cases`, `/api/tariffs`, `/api/rag/query`, `/api/demo/*`) are strictly excluded.*

---

## 16. Phase 2 Test Strategy

The Phase 2 automated test suite maps directly to documented requirements:

| Test Case ID | Test File | Target Requirement | Verification Objective | Acceptance / Verification Criterion |
| :--- | :--- | :--- | :--- | :--- |
| `TEST-ML-PWR-01` | `test_expected_power.py` | `SRS-ML-01`, `FR-002` | Power curve model fitting on chronological S1 train/test split | **TARGET**: $R^2 \ge 0.95$, $\text{RMSE} \le 45\,\text{kW}$ on healthy test set |
| `TEST-ML-PWR-02` | `test_expected_power.py` | `docs/08` ADR-004 | Power model single-record inference latency on CPU | **TARGET**: Latency $< 1.0\,\text{ms}$ |
| `TEST-ML-THM-01` | `test_thermal_model.py` | `SRS-ML-01`, `FR-003` | Gearbox and generator thermal model fitting (`RandomForestRegressor`) | **TARGET**: $\text{RMSE} \le 2.5^\circ\text{C}$, $R^2 \ge 0.96$ on healthy test set |
| `TEST-ML-RES-01` | `test_residual_engine.py`| `docs/09` §2.2 | Exact physical residual math ($\Delta P, \Delta T_{\text{GB}}, \Delta T_{\text{Gen}}$) and $z$-scores | Residuals match exact difference; $z = (R - \mu) / \sigma$ |
| `TEST-ML-PERS-01`| `test_residual_engine.py`| `docs/11` §2.3 | Persistence filter with canonical $\theta_{\text{thresh}} = 2.5\sigma$ over $W=6$ steps | Flags persistence when $\ge 5/6$ intervals exceed $2.5\sigma$ |
| `TEST-ML-CURT-01`| `test_expected_power.py` | `docs/11` §1, `docs/09` §2.1 | Verifies `is_curtailed == True` records are excluded from training | Model power curve unaffected by curtailed setpoints |
| `TEST-ML-LEAK-01`| `test_leakage_and_determinism.py`| Governance | Verifies models do not consume `is_fault`, `fault_type`, `scenario_id` | Feature columns strictly match aerodynamic and thermal vectors |
| `TEST-ML-DET-01` | `test_leakage_and_determinism.py`| Governance | Verifies training with `random_state=42` is 100% reproducible | Identical model weights and predictions across runs |
| `TEST-ML-SCEN-01`| `test_residual_engine.py`| `docs/10` §2 | Evaluates synthetic scenario verification signatures | **SYNTHETIC CRITERIA**: S2 $z_{\text{GB}} > +2.5\sigma$; S3 $z_P < -2.0\sigma$; S1 $z \approx 0$ |
| `TEST-ML-PERSIST`| `test_persistence_ml.py` | `docs/14` §3 | Verifies model saving, loading, and metadata manifest generation | Reloaded models produce identical predictions |
| `TEST-ML-ACCEPT` | `test_acceptance_phase2.py`| Master Phase 2 Gate | Complete Phase 2 Acceptance Gate Verification (`TEST-ML-01`) | All Phase 2 tests pass; all 49 Phase 1 tests remain green |

---

## 17. Strict Phase Boundaries

To prevent architectural scope creep, Phase 2 **STRICTLY EXCLUDES** the following components:

- **NO `ContextEngine` / `ContextFilterEngine`** (Layer 3 — Deferred to Phase 3).
- **NO `MultiSignalReasoner`** (Layer 3 — Deferred to Phase 3).
- **NO `PrioritizationEngine`** (Layer 3 — Deferred to Phase 3).
- **NO `TariffRegistry` & `LossCalculator`** (Layer 3 — Deferred to Phase 3).
- **NO Technical RAG Knowledge Base / Vector Stores** (Layer 4 — Deferred to Phase 4).
- **NO LLM Advisory Synthesis / Prompts / Guardrails** (Layer 5 — Deferred to Phase 5).
- **NO Case Store / HITL Decision Logging** (Layer 6 — Deferred to Phase 6).
- **NO Frontend UI / Dashboard / Chart.js** (Layer 6 — Deferred to Phase 7).
- **NO Direct Actuation / Turbine Control Endpoints** (PERMANENT ARCHITECTURAL LOCKOUT).

---

## 18. Phase 1 Integration Requirements

Phase 2 builds directly upon Phase 1 without modifying Phase 1 behaviors or contracts:

1. **Telemetry Schema Invariance**: Phase 2 consumes `TelemetryRecord` directly from `backend.data.schema`. No breaking changes to `TelemetryRecord` are permitted.
2. **Canonical `is_curtailed` Field**: Phase 2 uses `is_curtailed` for filtering training data. The legacy `curtailment_flag` ingestion alias remains encapsulated in Layer 1.
3. **Data Quality & Simulator Integration**: Phase 2 uses `SCADADataLoader` to load benchmark SCADA data and `SCADASimulator` to generate healthy baseline S1 data.
4. **Phase 1 Test Suite Protection**: All 49 existing Phase 1 automated tests in `tests/` must continue to pass without modification.

---

## 19. Assumptions Introduced

The following hardened engineering assumptions govern Phase 2:

1. **Canonical Algorithms [Approved Requirement]**:
   - `ExpectedPowerModel`: `GradientBoostingRegressor` (`scikit-learn`).
   - `ExpectedThermalModel`: `RandomForestRegressor` (`scikit-learn`).
2. **Deterministic Random Seed [Approved Requirement]**: A fixed seed (`random_state=42`) is used across stochastic model fitting to guarantee 100% reproducible weights across platforms.
3. **Chronological Splitting [Approved Requirement]**: Data splitting is purely chronological (70% Train, 15% Validation, 15% Test) and is independent of `random_state`.
4. **Canonical Persistence Threshold [Approved Requirement]**: The statistical anomaly persistence threshold is fixed at $\theta_{\text{thresh}} = 2.5\sigma$ over a 6-step sliding window ($W=6$ consecutive 10-minute intervals = 1 hour).
5. **Baseline Statistics Calibration [Approved Requirement]**: Baseline mean and standard deviation ($\mu, \sigma$) for residuals are estimated on the validation partition of Scenario S1 healthy data.

---

## 20. TBDs Requiring Clarification

During this hardening review, all previous ambiguities were formally resolved:
- **Thermal Model Algorithm**: Locked to `RandomForestRegressor`.
- **Persistence Threshold**: Locked to $\theta_{\text{thresh}} = 2.5\sigma$.
- **Model Metadata**: Pre-filled metrics removed; set to `null` placeholders until training.
- **Dataset Splitting**: Disentangled chronological split from `random_state=42`.
- **Dataset Policy**: Clarified Scenario S1 as primary; external benchmarks quarantined as optional validation.
- **Scenario Criteria**: Explicitly demarcated synthetic verification criteria from general engineering targets.

**Zero blocking architectural ambiguities remain.**

---

## 21. Documentation Traceability Matrix

| Requirement / Component | PRD (`docs/06`) | SRS (`docs/07`) | System Architecture (`docs/08`) | Technical Design (`docs/09`) | Data Architecture (`docs/10`) | AI/ML Design (`docs/11`) | Technology Stack (`docs/13`) | Implementation Plan (`docs/14`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`ExpectedPowerModel`** | `FR-002` | `SRS-ML-01` | §3.2, ADR-004 | §2.2 | §2, §4.1 | §2.1, §4, §6.1 | §3.2 | §3 (Phase 2) |
| **`ExpectedThermalModel`** | `FR-003` | `SRS-ML-01` | §3.2 | §2.2 | §2, §4.1 | §2.2, §4, §6.1 | §3.2 | §3 (Phase 2) |
| **`ResidualEngine`** | `FR-002`, `FR-003` | `SRS-ML-01` | §2 (Layer 2) | §2.2 | §3, §4.3 | §2.1–§2.3 | §3.2 | §3 (Phase 2) |
| **Curtailment Handling** | `FR-001`, `FR-004` | `SRS-DATA-01`, `SRS-CTX-01` | §2 (Layer 1/3) | §2.1, §2.3 | §4.1, §5 | §1, §3 | §3.1, §3.2 | §3 (Phase 1/2/3) |
| **Leakage Isolation** | `G-01`, `G-03` | §2, §3.2 | ADR-001 | §2.2 | §2, §4.1 | §1, §2, §7 | §3.2 | §3 (Phase 2) |
| **Model Persistence** | `NFR-006` | §2 | ADR-006 | §2.2 | §6 | §4 | §3.5 | §3 (Phase 2) |
| **`TEST-ML-01` Gate** | `FR-002`, `FR-003` | `SRS-ML-01` | §3.2 | §2.2 | §2 | §6 | §3.2 | §3 (Phase 2) |

---

## 22. Final Recommendation

All ambiguities have been rigorously resolved. The algorithms, data policies, split strategies, threshold constants, metadata formats, and test classifications for Phase 2 are **completely specified, hardened, and traceable**.

# FINAL RECOMMENDATION: READY TO IMPLEMENT
