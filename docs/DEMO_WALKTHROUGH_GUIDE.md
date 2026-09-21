---
document: DEMO_WALKTHROUGH_GUIDE
version: 1.0
status: PUBLISHED & VERIFIED
date: 2026-09-21
author: WindGuard AI Quality Assurance & UI/UX Group
governance: 10-Stage Interactive Operator Studio Walkthrough & Examiner Guide (Phase 9)
depends_on:
  - docs/12_ui_ux_specification.md
  - docs/MASTER_TECHNICAL_REPORT.md
  - docs/PRESENTATION_DECK_18_SLIDES.md
---

# WindGuard AI: Interactive 10-Stage Demonstration Guide
## Step-by-Step Examiner Walkthrough & Technical Demonstration Playbook

```
====================================================================================================
                        10-STAGE DEMO WALKTHROUGH & EXAMINER PLAYBOOK
====================================================================================================
Application URL                    : http://127.0.0.1:8000/
Target Interface                   : WindGuard AI Operator Studio & Interactive 10-Stage Stepper
Underlying Backend Endpoint        : GET /api/demo/stage/{stage_id} (Stages 1 through 10)
Total Demonstration Stages         : Exactly 10 Sequential Operational Scenarios
Execution Mode                     : 100% Deterministic Local Offline Mode A
Safety Protocol                    : Non-Actuating Human-in-the-Loop Workflow
====================================================================================================
```

---

## 1. Demonstration Setup & Examiner Quickstart

1. Launch the application launcher:
   ```bash
   python run_demo.py
   ```
2. The browser automatically navigates to `http://127.0.0.1:8000/`.
3. Locate the **Interactive Demo Stepper** bar located prominently at the top of the Operator Studio.
4. Click through the stages sequentially (Stage 1 to Stage 10) or jump directly to any stage.

---

## 2. Detailed Stage-by-Stage Examiner Walkthrough

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               10-STAGE OPERATIONAL LIFECYCLE MATRIX                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Stage 1: Clean Fleet Baseline (Healthy Operation)
* **Objective**: Demonstrate normal aerodynamic and thermal tracking across the 10-turbine fleet under standard conditions.
* **Target Turbine**: `WTG-001` (Wind: $8.5\,\text{m/s}$, Ambient: $22.0^\circ\text{C}$).
* **API Invocation**: `GET /api/demo/stage/1`
* **Underlying Telemetry**: Scenario S1 (Normal Operation, zero mechanical faults, zero curtailment).
* **Observable UI Changes**:
  - All 10 turbine cards display green `NORMAL` status badges.
  - Power Curve Visualizer shows actual SCADA scatter points tightly aligned along the GBR expected power curve ($R^2=1.00$).
  - Residuals Panel shows power residual $\Delta P \approx 0\,\text{kW}$ and thermal residuals $< 1.5^\circ\text{C}$.
  - Priority Score: $S_{\text{priority}} = 0.0$ (No active case generated).
* **Examiner Talking Point**: *"Notice how the GBR model accurately predicts electrical output directly from wind speed, showing that our physics-informed baseline tracks healthy aerodynamic behavior without baseline drift."*

---

### Stage 2: Gearbox Overheating Inception (Incipient Thermal Fault)
* **Objective**: Demonstrate early detection of high-speed stage bearing degradation before static SCADA threshold tripping.
* **Target Turbine**: `WTG-003` (Wind: $11.0\,\text{m/s}$, Power: $1750\,\text{kW}$).
* **API Invocation**: `GET /api/demo/stage/2`
* **Underlying Telemetry**: Scenario S2 (Progressive bearing friction, $T_{\text{gb}} = 82.5^\circ\text{C}$ vs expected $68.0^\circ\text{C}$).
* **Observable UI Changes**:
  - `WTG-003` card transitions to amber `WARNING` with Priority Score $S_{\text{priority}} \approx 65.0$.
  - AI Diagnostic Studio highlights **Gearbox Sump Oil Thermal Residual** ($\Delta T_{\text{gb}} = +14.5^\circ\text{C}$, $z = +7.55\sigma$).
  - Retrieved RAG Panel displays: `derived/windguard_gearbox_guide.md#chunk-1` (*High-Speed Shaft Bearing Wear & Borescope SOP*).
  - Prospective Loss Estimate: $450.00\,\text{INR/hour}$ calculated under PPA Flat rate.
* **Examiner Talking Point**: *"Conventional SCADA triggers only when temperature exceeds 85°C. WindGuard AI flags this anomaly at 82.5°C because the expected model predicted only 68°C for this specific power load, granting the operator critical lead time."*

---

### Stage 3: Grid Curtailment Order (100% False Alarm Suppression)
* **Objective**: Prove that grid-imposed power curtailment does NOT trigger a false mechanical underproduction alarm.
* **Target Turbine**: `WTG-004` (Wind: $13.5\,\text{m/s}$, Potential: $2000\,\text{kW}$, Actual: $1000\,\text{kW}$, `is_curtailed = 1`).
* **API Invocation**: `GET /api/demo/stage/3`
* **Underlying Telemetry**: Scenario S4 (Grid curtailment order with blade pitch feathering to $\beta = 18.0^\circ$).
* **Observable UI Changes**:
  - `WTG-004` card displays blue `CURTAILED` badge (Zero false anomaly alert).
  - Context Engine Banner: `[Precedence Level 2: Grid Curtailment Active] Mechanical Fault Evaluation Suppressed`.
  - Power underproduction of $1000\,\text{kW}$ is categorized as `GRID_INDUCED` rather than mechanical failure.
  - Priority Score: $0.0$; Zero false work order generated.
* **Examiner Talking Point**: *"This demonstrates our solution to Gap 1. Naive ML models would flag a catastrophic 1000 kW loss as a mechanical blade failure. WindGuard AI's context engine evaluates the curtailment state and completely suppresses the false alarm."*

---

### Stage 4: Generator Stator Thermal Runaway (Critical Severity Escalation)
* **Objective**: Demonstrate rapid multi-factor priority escalation during severe cooling system failure.
* **Target Turbine**: `WTG-002` (Wind: $12.0\,\text{m/s}$, Power: $2000\,\text{kW}$, $T_{\text{gen}} = 98.0^\circ\text{C}$).
* **API Invocation**: `GET /api/demo/stage/4`
* **Underlying Telemetry**: Scenario S3 (Clogged heat exchanger, $T_{\text{gen}}$ rising at $+2.5^\circ\text{C/hr}$).
* **Observable UI Changes**:
  - `WTG-002` card flashes red `CRITICAL` at the top of the fleet list.
  - Priority Score escalates to $S_{\text{priority}} = 92.4 / 100.0$.
  - Thermal residual $\Delta T_{\text{gen}} = +28.5^\circ\text{C}$ exceeds $11.6\sigma$.
  - Retrieved RAG Panel displays: `derived/windguard_generator_guide.md#chunk-3` (*Air-to-Air Heat Exchanger Fouling & Emergency Derate SOP*).
* **Examiner Talking Point**: *"Notice how the 5-factor priority formula combines high residual severity (35%), financial exposure (25%), and component criticality (20%) to push WTG-002 to the very top of the fleet queue for immediate intervention."*

---

### Stage 5: Aerodynamic Blade Pitch Misalignment (Subtle Power Loss)
* **Objective**: Detect subtle aerodynamic underperformance without thermal anomalies.
* **Target Turbine**: `WTG-005` (Wind: $9.0\,\text{m/s}$, Pitch: $\beta_1 = 4.5^\circ, \beta_2 = 2.0^\circ, \beta_3 = 2.0^\circ$).
* **API Invocation**: `GET /api/demo/stage/5`
* **Observable UI Changes**:
  - `WTG-005` card displays amber `DEGRADED` status.
  - Power curve scatter point falls visibly below the expected curve ($\Delta P = -220.0\,\text{kW}$).
  - Thermal residuals remain completely normal ($z_{\text{thermal}} \approx 0.1\sigma$).
  - Attributed Subsystem: `AERODYNAMIC_PITCH`.
  - Retrieved RAG: `derived/windguard_pitch_guide.md#chunk-1` (*Pitch Angle Asymmetry & Valve Calibration*).
* **Examiner Talking Point**: *"Here, component temperatures are normal, but power is down 220 kW. The system isolates the fault specifically to the pitch subsystem by identifying the asymmetric blade pitch signature."*

---

### Stage 6: Ambient Heatwave Transients (Dynamic Thermal Derating)
* **Objective**: Demonstrate ambient temperature compensation preventing false summer heatwave alarms.
* **Target Turbine**: `WTG-006` (Wind: $10.0\,\text{m/s}$, Ambient: $43.5^\circ\text{C}$, $T_{\text{gen}} = 86.0^\circ\text{C}$).
* **API Invocation**: `GET /api/demo/stage/6`
* **Observable UI Changes**:
  - `WTG-006` card displays green `NORMAL (HEATWAVE COMPENSATED)`.
  - Context Engine Banner: `[Precedence Level 4: High Ambient Derating Active (43.5°C > 38.0°C)]`.
  - Absolute temperature of $86^\circ\text{C}$ is evaluated against ambient-compensated baseline ($T_{\text{expected}} = 84.5^\circ\text{C}$), resulting in non-anomalous residual $\Delta T = +1.5^\circ\text{C}$.
* **Examiner Talking Point**: *"In legacy SCADA, 86°C triggers a fixed alarm. WindGuard AI factors in the 43.5°C ambient heatwave, recognizing that the temperature rise is purely atmospheric and not a mechanical defect."*

---

### Stage 7: Sensor Dropout & Communication Loss (Plausibility Filter)
* **Objective**: Isolate electrical sensor dropouts from genuine physical component temperature drops.
* **Target Turbine**: `WTG-007` (Wind: $8.0\,\text{m/s}$, $T_{\text{gb}} = 0.0^\circ\text{C}$ / `NaN`).
* **API Invocation**: `GET /api/demo/stage/7`
* **Underlying Telemetry**: Scenario S5 (Thermocouple cable disconnection).
* **Observable UI Changes**:
  - `WTG-007` card displays gray `SENSOR FAULT` badge.
  - Context Engine: `[Precedence Level 1: Sensor Plausibility Violation] Stuck/Zero Reading Detected`.
  - Prevents erroneous financial loss calculation or mechanical gearbox replacement recommendations.
  - Retrieved RAG: `synthetic/windguard_synthetic_playbooks.md#chunk-4` (*Sensor Dropout & Loop Check SOP*).
* **Examiner Talking Point**: *"A sudden reading of 0°C during full operation is physically impossible. Layer 1's plausibility filter catches this immediately, preventing the system from falsely assuming the gearbox has magically frozen."*

---

### Stage 8: Complex Cascading Mechanical Fault (Multi-Signal Diagnosis)
* **Objective**: Diagnose compound multi-subsystem anomalies (gearbox wear causing generator vibration and aerodynamic drag).
* **Target Turbine**: `WTG-008` (Wind: $11.5\,\text{m/s}$, Power down $150\,\text{kW}$, $T_{\text{gb}} = +18^\circ\text{C}$, $T_{\text{gen}} = +12^\circ\text{C}$).
* **API Invocation**: `GET /api/demo/stage/8`
* **Observable UI Changes**:
  - Multi-signal residual matrix shows simultaneous anomalies across power, gearbox, and generator channels.
  - Reasoner outputs primary attribution: `GEARBOX_MECHANICAL` with secondary `GENERATOR_THERMAL_COUPLING`.
  - Priority Score: $S_{\text{priority}} = 96.8 / 100.0$.
* **Examiner Talking Point**: *"When multiple components degrade simultaneously, our multi-signal reasoner disaggregates the root cause from secondary thermal coupling."*

---

### Stage 9: Prospective Revenue Loss Calculation (Tariff Sensitivity)
* **Objective**: Demonstrate dynamic financial loss estimation across different regulatory tariff schemes.
* **Target Turbine**: `WTG-009` (Underproducing by $400\,\text{kW}$).
* **API Invocation**: `GET /api/demo/stage/9` & Interactive Tariff Switcher.
* **Observable UI Changes**:
  - Switching from **PPA Flat (3.50 INR/kWh)** $\rightarrow$ **Time-of-Day Peak (4.20 INR/kWh)** instantly recalculates hourly loss from $1,400.00\,\text{INR/hr}$ to $1,680.00\,\text{INR/hr}$.
  - Switching to **APPC (2.80 INR/kWh)** recalculates loss to $1,120.00\,\text{INR/hr}$.
  - Mathematical precision error verified at $0.0000\,\text{INR}$.
* **Examiner Talking Point**: *"This empowers the asset manager to schedule maintenance during off-peak tariff hours, saving thousands of rupees in lost generation revenue."*

---

### Stage 10: Human-in-the-Loop Advisory & Work Order Generation
* **Objective**: Demonstrate the complete human-mediated case management and printable work order workflow.
* **Target Turbine**: `WTG-002` (High-priority case from Stage 4).
* **API Invocation**: `POST /api/cases/CASE-WTG-002-001/decision`
* **UI Interactions**:
  1. Operator clicks `ESCALATE`.
  2. Enters notes: *"Dispatched local field team for immediate generator cooling fan inspection."*
  3. Clicks `Authorize & Print Work Order`.
* **Observable UI Changes**:
  - Decision is permanently appended to `audit_log.jsonl` with operator timestamp.
  - Formatted printable work order modal opens with retrieved RAG SOPs, component serial numbers, and physical signature lines.
* **Examiner Talking Point**: *"This completes the Responsible AI loop. The system never executes closed-loop control; it provides all verified evidence to a human engineer who authorizes the formal work order."*

---
*WindGuard AI 10-Stage Demonstration Guide — Phase 9 Verified.*
