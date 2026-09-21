---
document: 01_problem_statement
version: 0.1
status: REVIEW
last_updated: 2026-09-20
author: WindGuard AI Research & Architecture Team
depends_on:
  - extracted_paper_1.md
---

# 01. Problem Statement — WindGuard AI

## 1. Executive Summary

Modern multi-megawatt wind turbines are complex cyber-physical machines operating in highly variable and hostile atmospheric environments. While modern wind energy installations produce vast streams of high-frequency supervisory control and data acquisition (SCADA) telemetry and condition monitoring records, wind farm operations and maintenance (O&M) teams face an acute operational bottleneck: the gap between **Detection**, **Understanding**, and **Action**.

Current monitoring systems rely predominantly on static threshold alarms or black-box machine learning anomaly detectors. These systems alert operators that an anomaly is present but fail to contextualize whether the anomaly is physically benign (e.g., transient wind shear, high ambient summer temperatures, or grid curtailment) or symptomatic of developing mechanical/electrical degradation. Furthermore, they do not explain *why* the condition was flagged, *what physical evidence* supports the assessment, *which technical manuals or alarm response protocols* apply, or *what precise inspection steps* a field engineer should execute.

**WindGuard AI** addresses this foundational gap by introducing an explainable, physics-grounded, and technical-knowledge-integrated decision-support architecture. By fusing physics-informed expected-behaviour baselines, context-aware operational filtering, multi-signal residual attribution, and Retrieval-Augmented Generation (RAG) over engineering documentation, WindGuard AI transforms raw SCADA anomalies into verifiable, evidence-grounded maintenance intelligence while strictly preserving human oversight.

---

## 2. Background

Wind energy has emerged as a cornerstone of the global transition toward clean, decarbonized electricity generation, directly supporting the United Nations Sustainable Development Goal 7 (SDG 7: Affordable and Clean Energy). Over the past three decades, commercial wind turbine designs have evolved from sub-megawatt, fixed-speed machines into flexible multi-megawatt systems characterized by rotor diameters exceeding 150 meters, hub heights surpassing 120 meters, and complex multi-stage drivetrains and power electronics.

As documented in the foundational research by Academic Literature (2026) [SOURCE-DERIVED CLAIM], modern turbines represent tightly coupled aeroelastic, structural, mechanical, electrical, and thermal systems:

$$\text{Wind Inflow} \xrightarrow{\text{Aerodynamics}} \text{Rotor/Blades} \xrightarrow{\text{Drivetrain/Torque}} \text{Gearbox/Bearings} \xrightarrow{\text{Electromechanics}} \text{Generator/Converter} \xrightarrow{\text{Grid Integration}} \text{Power Grid}$$

Operating in uncontrolled atmospheric boundaries, wind turbines experience severe cyclic fatigue loading, thermal gradients, pre-monsoon dust exposure, and fluctuating grid demands. To safeguard capital-intensive assets, turbines are equipped with SCADA networks sampling operational parameters (wind speed, active power, bearing temperatures, pitch angles, rotor speeds) typically recorded at 10-minute statistical intervals.

---

## 3. Problem Context

### 3.1 Industrial and Geographic Context (Indian & Global Wind Fleets)
The operational landscape of commercial wind energy—particularly within high-growth developing economies such as India—exhibits distinct operational vulnerabilities [SOURCE-DERIVED CLAIM]:
1. **High Ambient Thermal Stress**: Operating in ambient temperatures frequently exceeding $40^\circ\text{C}$ to $45^\circ\text{C}$ causes rapid thermal derating and strains lubrication cooling circuits.
2. **Monsoon and Seasonal Variability**: Extreme seasonal turbulence, gusting, and high humidity accelerate mechanical fatigue and aerodynamic blade degradation.
3. **Multi-OEM Fleet Fragmentation**: Wind farm operators manage mixed fleets encompassing multiple turbine generations, original equipment manufacturers (OEMs), and proprietary SCADA formats without standardized diagnostic interfaces.
4. **Grid Congestion and Dynamic Curtailment**: Grid infrastructure constraints force frequent dispatch curtailment (feathering blades and capping electrical output despite high available wind), creating operational profiles that traditional monitoring algorithms misclassify as severe hardware faults.

### 3.2 Economic and Sustainability Impact
Operation and maintenance (O&M) expenditures account for 20% to 30% of the lifetime levelized cost of energy (LCOE) for onshore wind farms and up to 40% for offshore installations [SOURCE-DERIVED CLAIM: Academic Literature, 2026]. Catastrophic failures of major components (e.g., high-speed gearbox bearings, planetary stages, generator stator insulation) require crane mobilizations, extended supply-chain lead times, and catastrophic downtime lasting from several weeks to months. Early, explainable detection can avert catastrophic failures through minor pre-emptive interventions (e.g., oil flushing, sensor recalibration, pitch bearing re-greasing), directly increasing clean energy yields and protecting asset value.

---

## 4. Core Problem

The central problem addressed by WindGuard AI is:

> **Wind turbine operational monitoring currently fails at the transition from anomaly detection to actionable engineering decision support.** 
> Existing monitoring tools generate alarms when sensor readings deviate from historical baselines, but they do not provide O&M engineers with the contextual justification, multi-signal physical evidence, grounded technical documentation, and structured investigation pathways necessary to make timely, confident, and risk-mitigating maintenance decisions.

The problem is explicitly **not** the inability to collect data or detect deviations. Rather, it is the inability to convert raw, non-stationary SCADA telemetry and fragmented engineering documentation into an explainable, verifiable, and advisory maintenance workflow.

---

## 5. Problem Decomposition

To formulate an engineering solution, the core problem is decomposed into six interdependent domain and technical sub-problems:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       WINDGUARD AI PROBLEM DECOMPOSITION                    │
└─────────────────────────────────────────────────────────────────────────────┘

  1. ENVIRONMENTAL NON-STATIONARITY & ALARM OVERLOAD
     ├── Problem: SCADA thresholds trigger hundreds of false alarms due to weather/curtailment.
     └── Requirement: Dynamic expected-behaviour baselines conditioned on ambient factors.

  2. DATA IMBALANCE & FAILURE DATA SCARCITY
     ├── Problem: Billions of normal operational records; extremely sparse labelled failure cases.
     └── Requirement: Unsupervised / semi-supervised residual modeling over normal operations.

  3. DETECTION IS NOT DIAGNOSIS (MULTI-SIGNAL AMBIGUITY)
     ├── Problem: A single sensor drop (e.g., low power) does not indicate the subsystem root cause.
     └── Requirement: Multi-signal cross-subsystem attribution (aerodynamic vs. mechanical vs. electrical).

  4. FRAGMENTATION OF ENGINEERING & OEM KNOWLEDGE
     ├── Problem: OEM manuals, IEC 61400 guidelines, and alarm matrix playbooks are siloed.
     └── Requirement: Grounded technical retrieval (RAG) linked directly to active sensor anomalies.

  5. BLACK-BOX MODEL OPACITY & NUMERICAL HALLUCINATION
     ├── Problem: Deep learning models output ungrounded alerts; generative models hallucinate values.
     └── Requirement: Strict deterministic ML-LLM separation with explicit uncertainty quantification.

  6. ABSENCE OF HUMAN-IN-THE-LOOP (HITL) GOVERNANCE
     ├── Problem: Operators cannot audit, acknowledge, escalate, or dismiss advisory alerts cleanly.
     └── Requirement: Structured decision interface preserving human engineering oversight.
```

---

## 6. Stakeholders

| Stakeholder Group | Primary Interest | Pain Point with Current Systems | Expected Value from WindGuard AI |
| :--- | :--- | :--- | :--- |
| **Control Room SCADA Operators** | Real-time fleet health monitoring and rapid alert screening. | Alarm fatigue from hundreds of benign nuisance alarms daily. | Context-filtered alarms prioritized by physical severity and persistence. |
| **Wind Farm O&M Engineers / Site Technicians** | Performing targeted physical inspection and corrective maintenance. | Lack of actionable diagnosis; unknown root causes before climbing towers. | Evidence-grounded inspection checklists linked to specific manual sections. |
| **Independent Power Producers (IPPs) / Asset Managers** | Maximizing annual energy production (AEP), availability, and asset life. | Unplanned catastrophic downtime and high emergency repair CAPEX. | Reduced avoidable downtime, lower LCOE, and estimated energy loss metrics. |
| **Wind Turbine OEMs** | Fleet reliability, warranty claim validation, design feedback. | Disconnected field maintenance logs and lack of standardized SCADA analytics. | Transparent audit trails connecting operational telemetry to OEM guidelines. |
| **Sustainability & Grid Compliance Bodies** | Stable renewable energy delivery, grid stability, SDG 7 metrics. | Unscheduled turbine trips causing local grid frequency destabilization. | Higher turbine availability and reliable clean energy dispatch. |

---

## 7. Target Users

1. **Lead Operations Engineer (Primary User)**:
   - *Profile*: Degreed mechanical/electrical engineer operating from a centralized operations center.
   - *Needs*: Comprehensive fleet overview, dynamic power-curve tracking, statistical residual validation, automated technical documentation lookup, and formal maintenance case escalation.
2. **Field Maintenance Technician (Secondary User)**:
   - *Profile*: Site technician executing physical maintenance at the wind farm substation and nacelle.
   - *Needs*: Concise, step-by-step diagnostic checklists, physical component location guides, alarm code definitions, and lubrication/alignment inspection procedures.
3. **Renewable Asset Portfolio Manager (Executive User)**:
   - *Profile*: Asset manager monitoring fleet capacity utilization factor (CUF), lost production (kWh), and maintenance ROI.
   - *Needs*: Aggregated fleet health indexes, cumulative production impact tracking, and empirical maintenance priority distributions.

---

## 8. Existing Situation

Current commercial wind farm monitoring relies on a fragmented patchwork of legacy technologies:

1. **SCADA Supervisory Systems (OEM & Third-Party)**:
   - Utilize fixed static thresholds (e.g., generate High Alarm if $T_{\text{gearbox\_bearing}} > 80^\circ\text{C}$, or Low Alarm if $P_{\text{active}} < 0.85 P_{\text{rated}}$).
   - SCADA dashboards present raw time-series charts without physical residual subtraction or cross-signal correlation.
2. **Dedicated Vibration Condition Monitoring Systems (CMS)**:
   - Accelerometers placed on main bearings, planetary stages, and high-speed generator shafts sampling at $10\,\text{kHz} - 50\,\text{kHz}$.
   - Requires specialized vibration analysts to interpret FFT spectra, envelope demodulation, and order tracking.
   - High capital expenditure ($10,000 - $25,000 per turbine retrofit) means CMS is often omitted on older or sub-2MW fleets.
3. **Ad-Hoc Engineering Knowledge Management**:
   - Technical maintenance manuals (PDFs of 500+ pages), OEM service bulletins, and alarm matrix spreadsheets remain static files on local drives or intranet shares, disconnected from live telemetry.

---

## 9. Limitations of Existing Approaches

| Limitation Dimension | Existing Approach | Technical Root Cause | Practical Failure Mode |
| :--- | :--- | :--- | :--- |
| **Contextual Awareness** | Static threshold alarm triggering. | Fixed limit values do not account for ambient temperature, wind speed, or grid curtailment. | False alarms triggered during hot summer afternoons; true slow degradation missed in winter. |
| **Explainability** | Black-box deep learning or raw threshold flags. | Neural networks lack transparent attribution; SCADA flags state *what* triggered without *why*. | Operators ignore alarms ("cry wolf" syndrome) or cannot explain alerts to management. |
| **Subsystem Attribution** | Single-channel thresholding. | Lack of multi-signal joint residual reasoning across aerodynamic, mechanical, and electrical variables. | Misdiagnosing an electrical converter derating as a mechanical gearbox bearing failure. |
| **Knowledge Integration** | Manual search of PDF documentation. | Complete dissociation between time-series analytical models and unstructured text manuals. | Technicians spend hours locating relevant OEM service procedures; delays in repair execution. |
| **Safety Governance** | Either purely passive monitoring or risky unconstrained automation. | Lack of structured human-in-the-loop escalation workflows with deterministic guardrails. | Critical maintenance cases slip through untracked, or automated systems risk unauthorized actuation. |

---

## 10. Consequences of the Problem

1. **Avoidable Catastrophic Failures**: Unidentified minor bearing surface spalling or lubricant starvation progresses into full planetary gear failure, resulting in $\$150,000 - \$350,000$ in replacement costs and 4 to 12 weeks of downtime [Established].
2. **Alarm Fatigue and Human Error**: Control room operators handling 50 to 200 turbines receive thousands of daily nuisance alerts, leading to genuine pre-failure indicators being acknowledged without investigation.
3. **Lost Clean Energy Generation (AEP Reduction)**: Unplanned downtime directly reduces turbine availability from potential $>97\%$ down to $90\% - 93\%$, wasting renewable energy potential and increasing reliance on fossil backup generation.
4. **Maintenance Inefficiency & Increased LCOE**: Unprepared field crews climb towers without the required replacement seals, lubrication batches, or diagnostic tooling, necessitating repeat tower climbs and escalating O&M labor expenses.

---

## 11. Project Objectives

### 11.1 Primary Objectives
- **OBJ-01 (Physics-Informed Expected Behaviour)**: Formulate and implement non-linear baseline regression models to accurately predict expected turbine active power ($P_{\text{exp}}$) and subsystem thermal equilibrium states ($T_{\text{exp}}$) under variable ambient and aerodynamic conditions.
- **OBJ-02 (Context-Aware Anomaly Detection)**: Implement an operational context engine that filters out benign environmental transients, high-ambient summer heating, low-wind idling, and grid curtailment events before raising high-priority alerts.
- **OBJ-03 (Multi-Signal Residual Attribution)**: Develop a multi-signal reasoning engine that correlates power residuals, drivetrain thermal residuals, generator thermal residuals, and rotor speed slips to isolate likely affected subsystems.
- **OBJ-04 (Grounded Technical Retrieval - RAG)**: Build a local, verified technical knowledge base comprising OEM maintenance manuals, SCADA alarm matrices (IEC 61400), and troubleshooting playbooks, enabling deterministic document retrieval linked to active anomalies.
- **OBJ-05 (Evidence-Grounded AI Advisory)**: Implement a constrained reasoning engine that synthesizes computed physical residuals and retrieved OEM procedures into structured, factually bounded maintenance advisory cases without ungrounded numerical hallucinations.
- **OBJ-06 (Human-in-the-Loop Decision Interface)**: Deliver an interactive, professional operator dashboard enabling real-time fleet health tracking, deep-dive telemetry analysis, conversational technical Q&A, and structured operator decision logging (Acknowledge, Investigate, Escalate, Dismiss).
- **OBJ-07 (Production & Financial Loss Quantification)**: Quantify estimated energy loss ($\text{kWh}$) and estimated financial loss based on transparent, auditable tariff provenance (supporting Project-Specific PPA, Official Reference, and Configurable Baseline tariffs).

### 11.2 Secondary Objectives
- **OBJ-08 (Indian Wind Fleet Operating Considerations)**: Model and validate operational behaviors characteristic of Indian wind regimes (ambient temps $>40^\circ\text{C}$, monsoon variability, grid curtailment).
- **OBJ-09 (SDG 7 Impact Mapping)**: Provide transparent, defensible impact logic demonstrating how early explainable decision support improves turbine availability and clean energy generation.

---

## 12. Scope

### 12.1 In Scope
1. **SCADA Telemetry Processing**: Standard 10-minute multi-turbine operational data streams covering wind speed, active power, reactive power, pitch angle, rotor speed, generator speed, ambient temperature, gearbox bearing temperature, generator stator temperature, and nacelle temperature. Canonical curtailment indicator: `is_curtailed` (with `curtailment_flag` supported as a backward-compatible alias).
2. **Analytical & Machine Learning Models**:
   - Physics-inspired empirical power curve modeling ($P_{\text{actual}}$ vs. $P_{\text{exp}}$).
   - Component thermal equilibrium modeling ($T_{\text{actual}}$ vs. $T_{\text{exp}}$).
   - Robust statistical residual quantification ($z$-score, sliding window persistence).
3. **Context Filtering Engine**: Environmental threshold checking, thermal rise ($\Delta T$) analysis, and operational state/curtailment validation.
4. **Transparent Prioritization Scoring**: Multi-factor priority index based on residual severity, persistence duration, model confidence, component criticality, and energy loss impact.
5. **Technical RAG System**: Chunked, metadata-indexed technical corpus covering OEM manuals, alarm code dictionaries, and India-specific O&M protocols.
6. **Constrained Advisory Generation**: Structured JSON advisory generation with verifiable sensor evidence, differential diagnostic hypotheses, and technician checklists.
7. **Web Operator Dashboard & Studio**: Complete UI with Fleet Overview, Turbine Deep Dive, AI Diagnostic Studio, Knowledge Assistant, Tariff Display, and Case Management.
8. **Reproducible 10-Stage Demo Scenario**: End-to-end simulated lifecycle demonstrating normal operation $\to$ incipient deviation $\to$ persistence $\to$ context check $\to$ case generation $\to$ RAG lookup $\to$ AI explanation $\to$ human escalation.
9. **Empirical Evaluation Framework**: Quantitative evaluation scripts measuring regression accuracy ($R^2$, RMSE, MAE), anomaly detection metrics (Precision, Recall, F1, FAR), and RAG retrieval relevance.

### 12.2 Out of Scope
1. **Direct Turbine Actuation / Autonomous Control**: WindGuard AI will **never** directly issue control signals (pitch angle commands, yaw actuation, generator torque modulation, or emergency shutdown). All decisions remain strictly advisory [SOURCE-DERIVED SAFETY BOUNDARY: Academic Literature, 2026].
2. **Raw High-Frequency Vibration CMS (FFT Demodulation)**: Processing $50\,\text{kHz}$ raw accelerometer waveforms is out of scope for the SCADA-based MVP. Vibration indicators are treated as integrated statistical SCADA features (e.g., RMS/peak acceleration).
3. **Full Multi-Body Aeroelastic Digital Twin Simulation**: A complete numerical finite-element / FAST / aeroelastic simulation of physical blade deformation is designated as future scope.
4. **Fleet-Wide Electricity Market Trading Optimization**: Automated bidding into day-ahead spot electricity markets is excluded.
5. **Drone Computer Vision Blade Surface Processing**: High-resolution drone imagery processing for surface blade cracks is designated as an independent future module.

---

## 13. Constraints

1. **Safety & Regulatory Constraints**: The system must adhere to IEC 61400 wind turbine safety standards. AI outputs must never bypass human engineering sign-off for safety-critical maintenance.
2. **Computational & Hardware Constraints**: The MVP must execute locally or in lightweight containerized environments without requiring specialized multi-GPU supercomputing clusters.
3. **Data Availability & Privacy Constraints**: Real industrial SCADA datasets often contain proprietary commercial information. The system must operate on open benchmark datasets and verified semi-synthetic telemetry pipelines with clear provenance labeling.
4. **Factual Grounding & Deterministic Separation**: The advisory layer must not independently fabricate sensor numbers, physical thresholds, or maintenance procedures. All numerical values must originate directly from verified analytical data layers.

---

## 14. Assumptions & Claim Classifications

1. **Sampling Frequency [ASSUMPTION]**: Standard SCADA telemetry is available at 10-minute average intervals (mean, min, max, standard deviation).
2. **Sensor Integrity [ASSUMPTION]**: SCADA sensors undergo periodic calibration; physical sensor failure modes (e.g., stuck readings, flatlines) can be identified via basic pre-processing data quality checks.
3. **Thermal Inertia [SOURCE-DERIVED CLAIM]**: Component temperatures (gearbox oil, bearings, generator coils) exhibit physical thermal inertia governed by first-order thermal differential equations with time constants between 15 minutes and 2 hours.
4. **Economic Baseline Tariff [ASSUMPTION / CONFIGURABLE BASELINE]**: Electricity valuation for lost production estimation is modeled at an indicative configurable baseline tariff of INR ₹3.20/kWh. This value is an assumption/configurable baseline and NOT a universal Indian wind tariff; the system architecture supports project-specific PPAs, official CERC/SERC regulatory reference tariffs, and user scenario tariffs.

---

## 15. Success Criteria (Performance Targets)

| Criterion ID | Success Dimension | Target Metric / Evaluation Standard | Classification | Verification Method |
| :--- | :--- | :--- | :---: | :--- |
| **SC-01** | Expected Power Model Accuracy | TARGET: $R^2 \ge 0.95$, $\text{RMSE} \le 6.0\%$ of rated capacity on normal test sets. | **TARGET** | Automated regression evaluation on held-out test data. |
| **SC-02** | Thermal Baseline Accuracy | TARGET: $\text{RMSE} \le 2.5^\circ\text{C}$, $\text{MAE} \le 1.8^\circ\text{C}$ across variable ambient loads. | **TARGET** | Cross-validated thermal residual evaluation. |
| **SC-03** | Anomaly Detection Performance | TARGET: Precision $\ge 88\%$, Recall $\ge 90\%$, $\text{F1} \ge 89\%$ on benchmark fault injection sets. | **TARGET** | Confusion matrix evaluation on benchmark scenarios. |
| **SC-04** | False Alarm Suppression | TARGET: $\ge 95\%$ suppression of false alarms during grid curtailment & ambient heat transients. | **TARGET** | Context engine evaluation against benign operational edge cases. |
| **SC-05** | Groundedness & Numerical Fidelity | TARGET: $100\%$ of numerical metrics and $\ge 95\%$ of technical citations verifiably grounded in source data/RAG. | **TARGET** | Automated factual consistency & citation audit. |
| **SC-06** | End-to-End Workflow Latency | TARGET: Complete inference cycle (ML + Context + RAG + Advisory) $\le 2.5\,\text{seconds}$ per turbine case. | **TARGET** | API benchmark timing tests. |
| **SC-07** | Reproducible Demonstration | Flawless 10-stage end-to-end interactive walkthrough demonstrating detection $\to$ action. | **TARGET** | Step-by-step UI verification script. |

---

## 16. Problem Statement — Final Form

> **"How can an explainable, physics-grounded, and technical-knowledge-integrated AI architecture transform multi-stream wind turbine SCADA telemetry into early, context-validated, and evidence-grounded maintenance decision support, thereby reducing avoidable downtime, preventing catastrophic drivetrain failures, and advancing SDG 7 clean energy availability while maintaining strict human engineering oversight?"**
