---
document: PHASE_3_SCOPE_REVIEW
version: 2.0
status: PROPOSED SCOPE REVIEW — NOT YET AUTHORIZED
date: 2026-09-20
author: Lead System Architect & Engineering Auditor
governance: Phase 3 Pre-Implementation Scope & Traceability Gate
depends_on:
  - docs/06_prd.md
  - docs/07_srs.md
  - docs/08_system_architecture.md
  - docs/09_technical_design.md
  - docs/10_data_architecture.md
  - docs/11_ai_ml_design.md
  - docs/14_implementation_plan.md
  - docs/PHASE_1_VERIFICATION.md
  - docs/PHASE_2_FINAL_SIGNOFF_REVIEW.md
---

# Phase 3 Scope & Traceability Review (Hardened)
## Layer 3: Operational Context Engine, Multi-Signal Reasoner, Tariff Registry & Loss Engine

---

## 1. Executive Summary & Phase Objectives

**Document Status**: **`PROPOSED SCOPE REVIEW — NOT YET AUTHORIZED`**  
**Precondition Status**: **`PHASE 2 — OWNER SIGNED OFF (IMPLEMENTATION FROZEN)`**

This document establishes the hardened pre-implementation specification, mathematical formulations, deterministic precedence hierarchies, loss eligibility boundaries, parameter classification taxonomies, data schemas, and traceability requirements for **Phase 3 (Layer 3 Context Engine, Multi-Signal Reasoner, Tariff Registry & Loss Engine)** of **WindGuard AI**.

### Core Objectives of Phase 3:
1. **Operational Context Filtering (FR-004)**: Decouple external environmental transients (ambient heat $\ge 38^\circ\text{C}$, low-wind idling $< 3.0\,\text{m/s}$) and grid dispatch commands (`is_curtailed == True`) from physical mechanical/aerodynamic equipment faults, achieving false-alarm suppression under benign conditions.
2. **Multi-Signal Residual Attribution (FR-005)**: Cross-correlate standardized residuals ($\Delta P, \Delta T_{\text{GB}}, \Delta T_{\text{Gen}}, \Delta\omega$) with operational context to deterministically isolate affected subsystems (`DRIVETRAIN_GEARBOX`, `GENERATOR_COOLING`, `AERODYNAMIC_PITCH`, `GRID_CURTAILMENT`, `SENSOR_ANOMALY`) using rule-based evidence scores.
3. **Multi-Mode Tariff Registry (FR-007)**: Implement a multi-mode tariff registry supporting Project PPA, Regulatory Benchmark, Configured Baseline Assumption (₹3.20/kWh baseline assumption), and Scenario Override with full provenance tracking and system constraint validation bounds ($₹0.01 - ₹20.00/\text{kWh}$).
4. **Eligible Energy & Financial Loss Calculation (FR-007)**: Deterministically compute lost energy ($E_{\text{lost}}\,\text{kWh}$) and financial impact ($\text{Loss}_{\text{INR}}$), with strict loss eligibility boundaries distinguishing degradation-attributable losses from commercial curtailment capacity and excluded sensor errors.
5. **Transparent Multi-Factor Prioritization (FR-006)**: Implement a normalized 5-factor scoring engine ($0-100$) based on initial baseline design parameters for severity ($S_{\text{sev}}$), persistence ($S_{\text{pers}}$), rule confidence ($S_{\text{conf}}$), component criticality ($S_{\text{crit}}$), and financial loss impact ($S_{\text{loss}}$).

---

## 2. Document Governance & Traceability Matrix

Every Phase 3 component traces directly to authoritative system requirements across the documentation suite:

| Component / Subsystem | Target Module Path | Authoritative Requirement ID | PRD Reference | SRS Reference | Architecture Reference | Technical Design Reference |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| **Context Engine** | `backend/engine/context_engine.py` | **FR-004** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.3 | `docs/08` §3.3 | `docs/09_technical_design.md` §2.3 |
| **Multi-Signal Reasoner** | `backend/engine/reasoner.py` | **FR-005** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.4 | `docs/08` §3.4 | `docs/09_technical_design.md` §2.3 |
| **Tariff Registry** | `backend/engine/tariff_registry.py` | **FR-007** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.5 | `docs/08` §3.4 | `docs/09_technical_design.md` §2.3 |
| **Loss Calculator** | `backend/engine/loss_calculator.py` | **FR-007** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.5 | `docs/08` §3.4 | `docs/09_technical_design.md` §2.3 |
| **Prioritization Engine** | `backend/engine/prioritization.py` | **FR-006** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.4 | `docs/08` §3.4 | `docs/09_technical_design.md` §2.3 |

---

## 3. Systematic Parameter Classification & Traceability

To maintain engineering precision, every numeric parameter, threshold, constant, and formula weight in Phase 3 is explicitly classified according to the 6 authoritative governance categories:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             PARAMETER CLASSIFICATION TAXONOMY                                    │
├──────────────────────────────┬───────────────────────────────────────────────────────────────────┤
│ TARGET                       │ Performance goal to be verified by acceptance tests (not result)  │
│ SYSTEM CONSTRAINT            │ Hard physical or architectural boundary enforced by code/types   │
│ INITIAL DESIGN PARAMETER     │ Configurable heuristic/baseline subject to tuning/calibration    │
│ ASSUMPTION                   │ Contextual premise adopted for synthetic evaluation baseline      │
│ MEASURED RESULT              │ Empirical value obtained from verified test execution             │
│ SOURCE-DERIVED REQUIREMENT   │ Specification directly derived from OEM standard or regulation    │
└──────────────────────────────┴───────────────────────────────────────────────────────────────────┘
```

### Comprehensive Parameter Traceability Table:

| Parameter / Constant Name | Symbol / Field | Canonical Value | Classification | Technical Rationale & Scope |
| :--- | :---: | :---: | :---: | :--- |
| **Curtailment False-Alarm Suppression** | $\text{FAR}_{\text{curt}}$ | $\ge 90.0\%$ | **TARGET** | Target false-alarm reduction under grid dispatch / heatwaves. |
| **Subsystem Attribution Accuracy** | $\text{Acc}_{\text{attrib}}$ | $\ge 90.0\%$ | **TARGET** | Target ratio of correctly attributed to total eligible evaluation records over S1–S5 synthetic evaluation data. |
| **Tariff Rate Lower Bound** | $\text{Rate}_{\min}$ | $₹0.01/\text{kWh}$ | **SYSTEM CONSTRAINT** | Hard validation lower limit preventing negative or zero tariff. |
| **Tariff Rate Upper Bound** | $\text{Rate}_{\max}$ | $₹20.00/\text{kWh}$ | **SYSTEM CONSTRAINT** | Hard validation upper limit preventing unphysical tariff spikes. |
| **Priority Score Range** | $\text{Score}$ | $[0.0, 100.0]$ | **SYSTEM CONSTRAINT** | Hard bounded output of PrioritizationEngine. |
| **Energy Loss Non-Negativity** | $P_{\text{deficit}}$ | $\ge 0.0\,\text{kW}$ | **SYSTEM CONSTRAINT** | Overperformance ($P_{\text{act}} > \hat{P}$) clamped to zero loss. |
| **Baseline Tariff Rate Assumption** | $\text{Rate}_{\text{base}}$ | $₹3.20/\text{kWh}$ | **ASSUMPTION** | Configured baseline assumption for demonstration (NOT a universal Indian tariff). |
| **Ambient Heatwave Threshold** | $T_{\text{amb, hot}}$ | $\ge 38.0^\circ\text{C}$ | **INITIAL DESIGN PARAMETER** | Initial threshold for ambient derate context evaluation. |
| **Low-Wind Cut-In Threshold** | $v_{\text{cut-in}}$ | $3.0\,\text{m/s}$ | **SOURCE-DERIVED REQUIREMENT** | Turbine physical cut-in speed from `TurbineDefaultParams`. |
| **Severity Weight** | $w_{\text{sev}}$ | $0.25$ | **INITIAL DESIGN PARAMETER** | Initial weighting term for $S_{\text{sev}}$ in Priority Score. |
| **Persistence Weight** | $w_{\text{pers}}$ | $0.20$ | **INITIAL DESIGN PARAMETER** | Initial weighting term for $S_{\text{pers}}$ in Priority Score. |
| **Rule Confidence Weight** | $w_{\text{conf}}$ | $0.20$ | **INITIAL DESIGN PARAMETER** | Initial weighting term for $S_{\text{conf}}$ in Priority Score. |
| **Component Criticality Weight** | $w_{\text{crit}}$ | $0.15$ | **INITIAL DESIGN PARAMETER** | Initial weighting term for $S_{\text{crit}}$ in Priority Score. |
| **Financial Loss Weight** | $w_{\text{loss}}$ | $0.20$ | **INITIAL DESIGN PARAMETER** | Initial weighting term for $S_{\text{loss}}$ in Priority Score. |
| **Gearbox Criticality Score** | $C_{\text{GB}}$ | $1.0$ | **INITIAL DESIGN PARAMETER** | High-speed stage mechanical replacement lead time / cost baseline. |
| **Generator Criticality Score** | $C_{\text{Gen}}$ | $0.8$ | **INITIAL DESIGN PARAMETER** | Stator winding insulation failure severity baseline. |
| **Pitch/Aero Criticality Score** | $C_{\text{Pitch}}$ | $0.6$ | **INITIAL DESIGN PARAMETER** | Aerodynamic conversion loss / blade bearing wear baseline. |
| **Sensor Criticality Score** | $C_{\text{Sensor}}$ | $0.3$ | **INITIAL DESIGN PARAMETER** | Instrumentation dropout severity baseline. |
| **Loss Normalization Ceiling** | $L_{\text{norm}}$ | $₹50,000$ | **INITIAL DESIGN PARAMETER** | Reference financial loss ceiling for single-shift severe derate. |
| **Severity Level Thresholds** | — | $40.0 / 60.0 / 80.0$ | **INITIAL DESIGN PARAMETER** | Score boundaries for LOW, MEDIUM, HIGH, CRITICAL classification. |

---

## 4. Mathematical Formulations & Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             LAYER 3 ANALYTICAL REASONING PIPELINE                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

   TelemetryRecord (L1) + ResidualVector (L2)
                       │
                       ▼
         ┌───────────────────────────┐
         │       ContextEngine       │ ──► Operational Context State (Deterministic Precedence)
         └───────────────────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │    MultiSignalReasoner    │ ──► Subsystem Attribution + Rule Confidence Score
         └───────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
  ┌──────────────┐            ┌──────────────┐
  │TariffRegistry│            │LossCalculator│ ──► Eligible Loss (kWh) & Financial Impact (INR)
  └──────────────┘            └──────────────┘
         │                           │
         └─────────────┬─────────────┘
                       ▼
         ┌───────────────────────────┐
         │   PrioritizationEngine    │ ──► Priority Score (0-100), Severity [CRITICAL..LOW]
         └───────────────────────────┘
```

### 4.1 Context Filtering & Deterministic Precedence Hierarchy

The `ContextEngine` deterministically classifies the operating environment into one of four canonical states:

```python
class OperationalContextState(str, Enum):
    NORMAL = "NORMAL"
    CURTAILED = "CURTAILED"
    HIGH_AMBIENT_DERATE = "HIGH_AMBIENT_DERATE"
    LOW_WIND_IDLE = "LOW_WIND_IDLE"
```

#### Deterministic Precedence Rules:
When multiple operating conditions coincide (such as grid curtailment occurring during an ambient heatwave in Scenario S4), the state is resolved strictly according to the following deterministic hierarchy:

```
[ Precedence 1 (Highest) ] ──► SENSOR QUALITY / DROPOUT
                               If telemetry.is_dropout == True or thermocouple implausible:
                               Tag record as SENSOR_ANOMALY / DATA_QUALITY_EXCLUDED.
                                        │
                                        ▼ (If sensor data valid)
[ Precedence 2 ] ────────────► GRID CURTAILMENT (CURTAILED)
                               If telemetry.is_curtailed == True OR
                               (pitch > 10.0° AND wind > 6.0 m/s AND power < 0.8 * power_exp):
                               State = CURTAILED.
                               (Takes precedence over thermal conditions because grid dispatch
                               actively dictates generator setpoint. Ambient heat logged in context).
                                        │
                                        ▼ (If not curtailed)
[ Precedence 3 ] ────────────► LOW-WIND IDLING (LOW_WIND_IDLE)
                               If wind_speed < 3.0 m/s:
                               State = LOW_WIND_IDLE.
                               (Aerodynamic energy harvest is physically unavailable below cut-in).
                                        │
                                        ▼ (If wind >= 3.0 m/s)
[ Precedence 4 ] ────────────► AMBIENT HEATWAVE (HIGH_AMBIENT_DERATE)
                               If ambient_temp >= 38.0°C AND residual_gb < 6.0°C AND z_gb < 2.0:
                               State = HIGH_AMBIENT_DERATE.
                               (Elevated component temp is driven by environmental boundary).
                                        │
                                        ▼ (If no ambient heatwave condition)
[ Precedence 5 (Lowest) ] ───► NORMAL REGIME (NORMAL)
                               State = NORMAL.
                               (Standard operating regime for fault residual evaluation).
```

---

### 4.2 Multi-Signal Subsystem Attribution & Rule-Based Confidence

The `MultiSignalReasoner` evaluates multi-channel residuals to isolate the faulty subsystem. 

> [!IMPORTANT]
> **Rule Confidence Semantics**:
> Confidence values produced in Phase 3 represent **deterministic heuristic rule-evidence scores** ($0.0 \le \text{rule\_confidence} \le 1.0$), **NOT empirically calibrated posterior probabilities** $P(\text{Fault} \mid \mathbf{z})$.

| Subsystem Affected | Residual Condition | Context Precedence | Rule Evidence Score (`rule_confidence`) |
| :--- | :--- | :--- | :---: |
| **`DRIVETRAIN_GEARBOX`** | $R_{\text{GB}} > +10.0^\circ\text{C} \land z_{\text{GB}} \ge 2.5\sigma$ (persistent $\ge 5/6$) | Context $==$ `NORMAL` | $0.90$ (High rule match) |
| **`GENERATOR_COOLING`** | $R_{\text{Gen}} > +12.0^\circ\text{C} \land z_{\text{Gen}} \ge 2.5\sigma$ (persistent $\ge 5/6$) | Context $==$ `NORMAL` | $0.85$ (High rule match) |
| **`AERODYNAMIC_PITCH`** | $R_P \le -200.0\,\text{kW} \land z_P \le -2.0\sigma$ (persistent $\ge 5/6$) | Context $==$ `NORMAL` | $0.88$ (High rule match) |
| **`GRID_CURTAILMENT`** | $R_P < 0 \land \text{is\_curtailed} == \text{True}$ | Context $==$ `CURTAILED` | $1.00$ (Deterministic dispatch) |
| **`SENSOR_ANOMALY`** | `is_dropout == True` $\lor$ $T_{\text{sensor}} < T_{\text{amb}} - 5.0^\circ\text{C}$ | Precedence 1 | $1.00$ (Physical plausibility failure) |
| **`NORMAL_OPERATION`** | All residuals within $[-2.0\sigma, +2.0\sigma]$ | Context $==$ `NORMAL` | $1.00$ (Nominal baseline) |

#### Attribution Accuracy Formulation:
$$\text{Attribution Accuracy} = \frac{\text{correctly attributed eligible evaluation records}}{\text{total eligible evaluation records}} \times 100\%$$
- **Evaluation Population**: S1–S5 synthetic evaluation records evaluated against Phase 1 ground-truth fault injection labels.
- **Reporting Deliverables in Verification**: Overall accuracy, per-scenario accuracy, multi-class confusion matrix, total eligible records, correct classifications, and incorrect classifications.

---

### 4.3 Multi-Mode Tariff Architecture & Provenance Tracking

```python
class TariffMode(str, Enum):
    PROJECT_PPA = "PROJECT_PPA"                   # Long-term negotiated utility PPA rate
    REGULATORY_BENCHMARK = "REGULATORY_BENCHMARK" # State/Central regulatory benchmark (e.g., CERC/SERC)
    CONFIGURED_BASELINE = "CONFIGURED_BASELINE"   # Configured baseline assumption for demo (₹3.20/kWh)
    SCENARIO_OVERRIDE = "SCENARIO_OVERRIDE"       # Operator simulation / what-if test override
```

#### Tariff Baseline Clarification:
- **₹3.20/kWh** is strictly a **CONFIGURED BASELINE ASSUMPTION** for synthetic evaluation and local testing.
- It is **NOT** a universal Indian wind tariff or regulatory default.
- Acceptance tests must verify tariff configuration mechanics, registry mutability, rate boundary validation ($₹0.01 - ₹20.00/\text{kWh}$), and provenance tracking, **NOT** that ₹3.20/kWh is inherently correct.

```python
class TariffProvenance(BaseModel):
    applied_rate_inr_per_kwh: float = Field(ge=0.01, le=20.0, description="Tariff rate in INR per kWh")
    mode: TariffMode
    source_reference: str
    effective_date: str
    currency: str = "INR"
    is_baseline_assumption: bool
```

---

### 4.4 Strict Loss Eligibility Boundaries & Calculation

The `LossCalculator` must **NOT** blindly convert every raw expected-vs-actual power deficit into maintenance financial loss. Lost energy is strictly partitioned into 5 eligibility categories:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               LOSS ELIGIBILITY BOUNDARY TAXONOMY                                 │
├──────────────────────────────┬──────────────────────────────┬────────────────────────────────────┤
│ Loss Category                │ Operating Condition          │ Financial Loss Calculation Rule    │
├──────────────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ 1. Raw Power Deficit         │ max(0, P_exp - P_act)        │ Intermediate analytical quantity   │
│ 2. Degradation Lost Energy   │ Context == NORMAL and        │ INCLUDED: E_deg * Tariff_applied   │
│    (E_deg)                   │ Subsystem == AERO_PITCH and  │ (Attributable to equipment wear)   │
│                              │ Persistence Verified (>=5/6) │                                    │
│ 3. Curtailed Lost Capacity   │ Context == CURTAILED         │ EXCLUDED from Maintenance Loss     │
│    (E_curt)                  │                              │ (Tracked as Deemed Generation)     │
│ 4. Low-Wind / Idling         │ Context == LOW_WIND_IDLE     │ EXCLUDED: E_lost = 0.0 kWh         │
│                              │                              │ (No harvestable energy available)  │
│ 5. Sensor Quality Error      │ Context == SENSOR_ANOMALY or │ EXCLUDED: loss_eligibility =       │
│                              │ is_dropout == True           │ EXCLUDED_SENSOR_ERROR, Loss = 0.0  │
└──────────────────────────────┴──────────────────────────────┴────────────────────────────────────┘
```

#### Mathematical Formulations:
1. **Raw Power Deficit**:
   $$P_{\text{deficit}}(t_k) = \max\left(0.0, \, \hat{P}(t_k) - P_{\text{actual}}(t_k)\right) \quad [\text{kW}]$$
2. **Eligible Degradation Energy Loss**:
   $$E_{\text{deg, total}} = \sum_{k \in \text{Eligible}} P_{\text{deficit}}(t_k) \times \frac{\Delta t}{60} \quad [\text{kWh}], \quad \text{where } \Delta t = 10\,\text{min}$$
3. **Eligible Maintenance Financial Loss**:
   $$\text{Financial Loss}_{\text{maint}} = E_{\text{deg, total}} \times \text{Tariff}_{\text{applied}} \quad [\text{INR}]$$
4. **Deemed Curtailed Lost Generation**:
   $$E_{\text{curt, total}} = \sum_{k \in \text{Curtailed}} P_{\text{deficit}}(t_k) \times \frac{\Delta t}{60} \quad [\text{kWh}]$$

---

### 4.5 Transparent 5-Factor Prioritization Scoring

The `PrioritizationEngine` combines 5 normalized sub-scores ($0.0 \le S_i \le 1.0$) using initial design baseline weights ($\sum w_i = 1.0$):

$$\text{Priority Score} = 100 \times \left( w_1 S_{\text{sev}} + w_2 S_{\text{pers}} + w_3 S_{\text{conf}} + w_4 S_{\text{crit}} + w_5 S_{\text{loss}} \right)$$

#### Sub-Score Formulations (Initial Design Parameters):
1. **$S_{\text{sev}}$ — Anomaly Severity ($w_1 = 0.25$)**:
   $$S_{\text{sev}} = \min\left(1.0, \, \frac{\max(|z_P|/2.0, \, |z_{\text{GB}}|/2.5, \, |z_{\text{Gen}}|/2.5)}{4.0}\right)$$
2. **$S_{\text{pers}}$ — Statistical Persistence ($w_2 = 0.20$)**:
   $$S_{\text{pers}} = \frac{N_{\text{excursions}}}{W}, \quad \text{where } W=6 \text{ steps}$$
3. **$S_{\text{conf}}$ — Rule Confidence ($w_3 = 0.20$)**:
   $$S_{\text{conf}} = \text{rule\_confidence} \in [0.0, 1.0]$$
4. **$S_{\text{crit}}$ — Component Criticality ($w_4 = 0.15$)**:
   - `DRIVETRAIN_GEARBOX`: $1.0$
   - `GENERATOR_COOLING`: $0.8$
   - `AERODYNAMIC_PITCH`: $0.6$
   - `SENSOR_ANOMALY`: $0.3$
   - `NORMAL_OPERATION`: $0.0$
5. **$S_{\text{loss}}$ — Financial Loss Impact ($w_5 = 0.20$)**:
   $$S_{\text{loss}} = \min\left(1.0, \, \frac{\text{Financial Loss}_{\text{maint}}}{L_{\text{norm}}}\right), \quad \text{where } L_{\text{norm}} = ₹50,000$$

#### Severity Classification (Initial Baseline Thresholds):
- **`CRITICAL`**: $\text{Priority Score} \ge 80.0$
- **`HIGH`**: $60.0 \le \text{Priority Score} < 80.0$
- **`MEDIUM`**: $40.0 \le \text{Priority Score} < 60.0$
- **`LOW`**: $\text{Priority Score} < 40.0$

---

## 5. Phase 3 Deliverables & Directory Structure Plan

```
backend/
├── engine/
│   ├── __init__.py                # Package exports for Layer 3 modules
│   ├── context_engine.py          # ContextFilterEngine & OperationalContextState (FR-004)
│   ├── reasoner.py                # MultiSignalReasoner & SubsystemAttribution (FR-005)
│   ├── tariff_registry.py         # TariffRegistry, TariffProvenance & TariffMode (FR-007)
│   ├── loss_calculator.py         # LossCalculator & LossEligibility (FR-007)
│   └── prioritization.py          # PrioritizationEngine & PriorityScoreResult (FR-006)

tests/
├── test_context_engine.py         # Unit tests for context states, precedence & false-alarm suppression
├── test_reasoner.py               # Unit tests for multi-signal subsystem attribution & rule scores
├── test_tariff_registry.py        # Unit tests for multi-mode tariffs, bounds & provenance
├── test_loss_calculator.py        # Unit tests for eligible energy & financial loss integration
├── test_prioritization.py         # Unit tests for 5-factor priority score & severity classification
└── test_acceptance_phase3.py      # End-to-end acceptance tests for Layer 3 pipeline
```

---

## 6. Strict Phase Boundaries & Lockout Confirmation

To preserve modular architectural isolation, the following subsystems remain **100% LOCKED OUT**:

| Subsystem / Capability | Phase 3 Status | Scheduled Phase |
| :--- | :---: | :---: |
| **Context Engine & False Alarm Suppression** | **IN SCOPE** | **Phase 3** |
| **Multi-Signal Subsystem Attribution** | **IN SCOPE** | **Phase 3** |
| **Tariff Registry & Provenance Tracking** | **IN SCOPE** | **Phase 3** |
| **Eligible Loss Calculator** | **IN SCOPE** | **Phase 3** |
| **5-Factor Anomaly Prioritization** | **IN SCOPE** | **Phase 3** |
| **Technical RAG & Document Embeddings (`backend/rag/*`)** | **STRICTLY LOCKED OUT** | Phase 4 |
| **LLM Synthesis & Maintenance Cases (`backend/llm/*`)** | **STRICTLY LOCKED OUT** | Phase 5 |
| **Web UI / Operator Dashboard (`frontend/*`)** | **STRICTLY LOCKED OUT** | Phase 6 |
| **Fleet REST API Endpoints (`/api/cases`, `/api/fleet/*`)** | **STRICTLY LOCKED OUT** | Phase 6 |
| **SCADA Actuation / Control Commands** | **PERMANENTLY LOCKED OUT** | Never |

---

## 7. Synthetic Scenario Verification Scope

> [!NOTE]
> **SYNTHETIC SCENARIO VERIFICATION ONLY**:
> All scenario evaluations (S1–S5) in Phase 3 are conducted against the numerical simulation engine and represent synthetic scenario verification, **NOT** operational validation on physical utility-scale wind turbine fleets.

| Scenario ID | Tested Operational Condition | Expected Context State | Expected Subsystem Attribution | Loss Eligibility Type |
| :--- | :--- | :--- | :--- | :--- |
| **S1** | Baseline Healthy ($N=2880$) | `NORMAL` | `NORMAL_OPERATION` | No Loss ($E_{\text{lost}} = 0$) |
| **S2** | Gearbox Bearing Degradation ($+16.5^\circ\text{C}$) | `NORMAL` | `DRIVETRAIN_GEARBOX` | Thermal Alarm (No direct aerodynamic lost kWh) |
| **S3** | Pitch Asymmetry ($18\%$ Aerodynamic Derate) | `NORMAL` | `AERODYNAMIC_PITCH` | **Eligible Maintenance Loss** ($E_{\text{deg}} \times \text{Tariff}$) |
| **S4** | Grid Curtailment ($1000\,\text{kW}$) + Heatwave ($\ge 40^\circ\text{C}$) | `CURTAILED` (Precedence 2) | `GRID_CURTAILMENT` | **Deemed Curtailed Capacity** (Excluded from Maint Loss) |
| **S5** | Sensor Dropout ($T_{\text{sensor}} = T_{\text{amb}} - 15^\circ\text{C}$) | `SENSOR_ANOMALY` (Precedence 1) | `SENSOR_ANOMALY` | **Excluded Sensor Error** (Loss = 0) |

---

## 8. Phase 3 Test Plan & Acceptance Criteria

### Automated Acceptance Tests (Layer 3 Gate):

1. **`TEST-CTX-01` (Context Precedence & False-Alarm Suppression)**:
   - Evaluates deterministic precedence: S4 combination of Curtailment + Heatwave evaluates strictly to `CURTAILED`.
   - *Target*: $\ge 90\%$ false-alarm suppression on curtailed and heatwave records.
2. **`TEST-REAS-01` (Subsystem Attribution Accuracy)**:
   - **Evaluation Population**: S1–S5 synthetic evaluation records evaluated against Phase 1 ground-truth fault injection labels.
   - **Measurement Formulation**:
     $$\text{Attribution Accuracy} = \frac{\text{correctly attributed eligible evaluation records}}{\text{total eligible evaluation records}} \times 100\%$$
   - **Target Classification**: $\ge 90.0\%$ Subsystem Attribution Accuracy classified strictly as **`TARGET`** (performance design goal, not a measured result).
   - **Phase 3 Verification Report Deliverables**:
     The Phase 3 verification report (`docs/PHASE_3_VERIFICATION.md`) must explicitly report:
     - Overall attribution accuracy ($\%$)
     - Per-scenario attribution accuracy ($\%$) across S1, S2, S3, S4, and S5
     - Multi-class diagnostic confusion matrix (True Subsystem vs. Predicted Subsystem)
     - Total eligible record count ($N_{\text{eligible}}$)
     - Correct classification count ($N_{\text{correct}}$)
     - Incorrect classification count ($N_{\text{incorrect}}$)
   - **Rule Confidence Validation**:
     - Verifies deterministic rule confidence scores ($0.0 \le \text{rule\_confidence} \le 1.0$) across all evaluated records.
3. **`TEST-TRF-01` (Tariff Registry & Validation Bounds)**:
   - Verifies default rate $₹3.20/\text{kWh}$ under `CONFIGURED_BASELINE` as a configurable assumption.
   - Enforces system constraint validation bounds: accepts rates in $[₹0.01, ₹20.00]/\text{kWh}$, raises `ValueError` for negative or out-of-bounds rates.
   - Verifies immutable provenance object generation.
4. **`TEST-LOSS-01` (Eligible Energy & Financial Loss Integration)**:
   - Verifies non-negativity clamping ($P_{\text{deficit}} \ge 0.0$).
   - Verifies that curtailed records (S4), low-wind records, and sensor dropouts (S5) are excluded from maintenance financial loss.
   - Verifies exact integration of degradation lost energy on S3 ($E_{\text{deg}} = \int \Delta P \, dt$) and product with active tariff.
5. **`TEST-PRIO-01` (5-Factor Prioritization Scoring)**:
   - Enforces system constraint bounds: $0.0 \le \text{Priority Score} \le 100.0$.
   - Verifies monotonicity with severity and loss impact.
   - Verifies severity classification (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
6. **`TEST-REGRESS-P1-P2` (Phase 1 & Phase 2 Regression Protection)**:
   - Verifies all 49 Phase 1 tests pass (**49/49 GREEN**).
   - Verifies all 78 passing Phase 2 tests pass (0 regressions against frozen baseline).
7. **`TEST-LOCKOUT-P3` (Boundary Lockout)**:
   - Asserts zero existence of `backend/rag/`, `backend/llm/`, `frontend/`, or actuation endpoints.

---

## 9. Current Governance Status & Next Gate

```
====================================================================================================
                             PHASE 3 PRE-IMPLEMENTATION GOVERNANCE GATE
====================================================================================================
Phase 1 Status                      : VERIFIED & FROZEN (49/49 PASS)
Phase 2 Status                      : OWNER SIGNED OFF & FROZEN (78/82 PASS, 4 TARGETS NOT MET RECORDED)
Phase 3 Scope Status                : READY FOR OWNER AUTHORIZATION
Phase 3 Implementation Code         : ZERO CODE WRITTEN (FROZEN)
====================================================================================================
```

### Next Gate:
Awaiting explicit Project Owner authorization of `docs/PHASE_3_SCOPE_REVIEW.md` (v2.0) before starting Phase 3 implementation.
