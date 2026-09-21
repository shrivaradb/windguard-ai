---
document: 06_prd
version: 0.1
status: REVIEW
last_updated: 2026-09-20
author: WindGuard AI Product & Architecture Team
depends_on:
  - docs/01_problem_statement.md
  - docs/02_literature_review.md
  - docs/03_gap_analysis.md
  - docs/04_proposed_solution.md
  - docs/05_uniqueness_and_innovation.md
---

# 06. Product Requirements Document (PRD) — WindGuard AI

## 1. Product Overview

**WindGuard AI** is an explainable AI-powered health monitoring and maintenance decision-support platform designed for wind farm operations and maintenance (O&M) teams. The platform bridges the operational gap between **Detection**, **Understanding**, and **Action** by synthesizing SCADA operational analytics, physics-informed expected-behaviour baselines, context-aware false-alarm filtering, technical-document RAG, and constrained LLM advisory reasoning into a centralized, human-governed operator dashboard.

---

## 2. Product Vision

To become the industry-standard decision-support co-pilot for renewable energy operations, empowering wind farm engineers to eliminate catastrophic downtime, optimize clean energy generation (SDG 7), and make verifiable, evidence-grounded maintenance decisions with complete confidence.

---

## 3. Product Goals

1. **G-01 (Early & Accurate Anomaly Detection)**: Detect incipient mechanical, electrical, and aerodynamic performance degradations in 10-minute SCADA telemetry prior to catastrophic failure.
2. **G-02 (Operational False-Alarm Elimination)**: [TARGET] Suppress $\ge 95\%$ of nuisance false alarms caused by benign environmental transients, ambient heatwaves ($>38^\circ\text{C}$), and grid curtailment (`is_curtailed`).
3. **G-03 (Transparent Physical Explainability)**: Provide quantitative residual attribution ($\Delta P$, $\Delta T_{\text{GB}}$, $\Delta T_{\text{Gen}}$) and dominant signal contributions for every detected anomaly.
4. **G-04 (Technical Knowledge Grounding via RAG)**: Automatically retrieve relevant OEM maintenance manual sections, IEC alarm code playbooks, and inspection checklists for active anomalies.
5. **G-05 (Factually Bounded Maintenance Advisories)**: Generate structured, human-readable O&M advisory cases strictly constrained to explain verified analytical telemetry and authentic documentation without independent numerical generation.
6. **G-06 (Human-in-the-Loop Governance)**: Provide a streamlined decision center enabling engineers to review, investigate, escalate, or dismiss maintenance cases while strictly locking out unauthorized autonomous turbine actuation.

---

## 4. Non-Goals

1. **NG-01 (No Autonomous Turbine Actuation)**: The platform will not directly actuate pitch angles, yaw drives, generator torque, or trigger emergency turbine trips. All recommendations are advisory.
2. **NG-02 (No High-Frequency Raw Vibration Waveform FFT Processing)**: The platform will not process $50\,\text{kHz}$ raw accelerometer streams; vibration is evaluated via integrated SCADA statistical summary channels.
3. **NG-03 (No Full Blade Aeroelastic Finite-Element Simulation)**: Real-time 3D FEA stress/fatigue simulations are excluded from the MVP.
4. **NG-04 (No Day-Ahead Electricity Market Spot Bidding)**: Automated algorithmic trading and grid bidding are out of scope.

---

## 5. Target Users & User Personas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WINDGUARD AI USER PERSONAS                          │
└─────────────────────────────────────────────────────────────────────────────┘

  PERSONA 1: RAJESH SHARMA — LEAD O&M OPERATIONS ENGINEER (PRIMARY)
  ├── Location: Centralized Remote Operations Center (ROC).
  ├── Responsibilities: Monitoring 120 multi-OEM turbines across 3 wind farms.
  ├── Pain Points: Drowning in 300+ daily SCADA alarms; lacks time to manually
  │   cross-reference 500-page OEM manuals when power drops.
  └── Goal: Needs prioritized, context-filtered anomalies with instant technical guidance.

  PERSONA 2: ANIL PATEL — SENIOR FIELD MAINTENANCE TECHNICIAN (SECONDARY)
  ├── Location: On-site Wind Farm Substation & Nacelle.
  ├── Responsibilities: Physical turbine inspection, lubrication flushing, component replacement.
  ├── Pain Points: Climbing towers without knowing exact failure modes or required tools.
  └── Goal: Needs concise, step-by-step diagnostic checklists and OEM chapter citations.

  PERSONA 3: PRIYA MENON — RENEWABLE ASSET PORTFOLIO MANAGER (EXECUTIVE)
  ├── Location: Corporate Asset Management Headquarters.
  ├── Responsibilities: Asset availability, Capacity Utilization Factor (CUF), O&M OPEX.
  ├── Pain Points: Unplanned downtime eroding PPA revenues and increasing LCOE.
  └── Goal: Needs fleet health visibility, lost generation (kWh) metrics, and maintenance ROI.
```

---

## 6. User Journeys

### User Journey: Morning Fleet Triage & Anomaly Escalation (Lead O&M Engineer)

```
[ Log into Dashboard ] 
        │
        ▼
[ Review Fleet Health Banner ] ──► Observes Turbine 07 flagged as "High Priority Anomaly"
        │
        ▼
[ Open Turbine 07 Deep Dive ] ──► Inspects Power Curve: Actual power is 18% below expected curve
        │
        ▼
[ View AI Diagnostic Case ] ────► Checks Multi-Signal Evidence:
                                  - Gearbox Bearing Temp: +7.2°C residual
                                  - Context Check: Ambient 32°C, is_curtailed = false (Valid Anomaly)
                                  - Tariff Provenance: PPA Rate ₹3.20/kWh [Configurable Baseline]
                                  - RAG Sources: OEM Manual Sec 4.2 & Alarm AL-104
        │
        ▼
[ Ask Knowledge Assistant ] ────► Queries: "What are the required tools for AL-104 inspection?"
                                  System returns: Oil sampling kit, dial indicator, torque wrench
        │
        ▼
[ Execute Action ] ──────────────► Clicks "Escalate Case", adds notes, and exports Work Order PDF
```

---

## 7. Functional Requirements

| Requirement ID | Requirement Name | Description & Preconditions | Priority | Target User | Acceptance Criteria |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **FR-001** | Multi-Turbine SCADA Ingestion | Ingests 10-minute SCADA data streams (wind speed, power, pitch, RPM, component temps, ambient temp, `is_curtailed`). | **P0 (Must Have)** | System / All | Ingests and validates tabular SCADA streams; canonical field `is_curtailed` (with `curtailment_flag` as backward-compatible alias); flags missing/out-of-range sensor readings. |
| **FR-002** | Expected Power Curve Modeling | Computes expected power $\hat{P} = f(v_{\text{wind}}, T_{\text{amb}}, \theta)$ and residual $\Delta P = P_{\text{act}} - \hat{P}$. | **P0 (Must Have)** | Operations Engineer | TARGET: Regression $R^2 \ge 0.95$ on normal test data; computes residuals in $<50\,\text{ms}$. |
| **FR-003** | Thermal Equilibrium Modeling | Computes expected gearbox bearing and generator stator temperatures and their residuals ($\Delta T$). | **P0 (Must Have)** | Operations Engineer | TARGET: Baseline $\text{RMSE} \le 2.5^\circ\text{C}$; isolates internal thermal rise from ambient baseline. |
| **FR-004** | Operational Context Filtering | Evaluates external ambient heat ($>38^\circ\text{C}$), low-wind idling, and grid curtailment (`is_curtailed`). | **P0 (Must Have)** | Operations Engineer | TARGET: Suppresses $\ge 95\%$ of false alarms caused by grid curtailment and benign ambient transients. |
| **FR-005** | Multi-Signal Residual Attribution | Jointly evaluates power, thermal, and rotor speed residuals to classify affected subsystem. | **P0 (Must Have)** | Operations Engineer | Correctly isolates Drivetrain, Generator, or Aerodynamic/Pitch subsystem in benchmark scenarios. |
| **FR-006** | Transparent Anomaly Prioritization | Computes a normalized Priority Score ($0-100$) based on severity, persistence, confidence, and energy loss. | **P0 (Must Have)** | Operations Engineer | Ranks active fleet anomalies with explicit breakdown of all five weighting terms. |
| **FR-007** | Energy & Financial Loss Estimation | Calculates estimated lost generation ($\text{kWh}$) and financial loss based on Applicable Tariff provenance. *(Reasoning: Essential core capability for O&M asset managers and anomaly prioritization $S_{\text{loss}}$, directly mapping to SDG 7 clean energy metrics).* | **P0 (Must Have)** | Asset Manager | Computes accumulated kWh loss over anomaly duration and displays financial impact with complete tariff provenance (supports Project-Specific, Official Regulatory, and Baseline tariffs). |
| **FR-008** | Technical Document RAG Retrieval | Performs vector/hybrid search over chunked OEM manuals, alarm tables (IEC 61400), and O&M SOPs. | **P0 (Must Have)** | Technician / Engineer | Returns top-$k$ relevant chunks with document name, section title, and page metadata. |
| **FR-009** | Evidence-Grounded Advisory Synthesis | Synthesizes pre-computed residuals + context + RAG chunks into structured JSON maintenance cases. | **P0 (Must Have)** | Operations Engineer | $100\%$ numerical values match telemetry; technical citations grounded in RAG; structured JSON format. |
| **FR-010** | Conversational Knowledge Assistant | Interactive natural-language interface allowing users to query wind turbine manuals and alarm codes. | **P1 (Should Have)** | Technician / Engineer | Responds to engineering queries with grounded answers and clickable document source citations. |
| **FR-011** | Human-in-the-Loop Decision Logging | Provides interactive actions: *Acknowledge*, *Investigate*, *Escalate*, *Dismiss/Monitor* with operator notes. | **P0 (Must Have)** | Operations Engineer | Records operator action, timestamp, and notes in persistent audit log; updates turbine status. |
| **FR-012** | Deterministic Safety Lockout | Enforces architectural lockout preventing AI from issuing direct control or actuation commands. | **P0 (Must Have)** | System / Safety | Complete absence of write-access actuation endpoints; outputs strictly advisory. |
| **FR-013** | Interactive 10-Stage Demo Mode | Provides a reproducible step-by-step 10-stage simulation demonstrating the full detection $\to$ action cycle. | **P0 (Must Have)** | Evaluator / All | Stepper walkthrough progresses through 10 discrete stages with verified telemetry and advisory states. |

---

## 8. Non-Functional Requirements

| Requirement ID | Category | Specification / Standard | Target Metric |
| :--- | :--- | :--- | :--- |
| **NFR-001** | Performance & Latency | Total end-to-end diagnosis latency (ML + Context + RAG + Advisory synthesis). | TARGET: $\le 2.5\,\text{seconds}$ per turbine diagnosis. |
| **NFR-002** | Computational Efficiency | Lightweight inference execution without mandatory GPU supercomputing hardware. | TARGET: Executes on standard dual-core CPU with $\le 2\,\text{GB}$ RAM. |
| **NFR-003** | Reliability & Availability | Continuous operational uptime during simulated telemetry streaming. | TARGET: $99.9\%$ uptime during demonstration and evaluation runs. |
| **NFR-004** | Security & Privacy | No transmission of proprietary operational data to untrusted public cloud endpoints. | Localized vector store and offline fallback capability. |
| **NFR-005** | Usability & Ergonomics | Modern, responsive web interface adhering to WCAG 2.1 AA accessibility standards. | Clean contrast, intuitive hierarchy, responsive on desktop and tablet ($>1024\text{px}$). |
| **NFR-006** | Maintainability & Modularity | Modular decoupled Python codebase with type annotations and separation of concerns. | Clean directory separation (data, models, context, RAG, LLM, API, frontend). |
| **NFR-007** | Observability & Auditability | Structured JSON logging of all analytical residuals, RAG queries, and operator decisions. | Complete timestamped audit trail stored locally for every generated maintenance case. |

---

## 9. Product Constraints & Dependencies

1. **SCADA 10-Minute Resolution [Constraint]**: System is designed for 10-minute SCADA intervals. High-speed transient electrical waveforms are not processed.
2. **Deterministic Safety Boundary [Constraint]**: Direct control loops (pitch, yaw, emergency trips) are strictly out of bounds.
3. **Python & Modern Web Ecosystem [Dependency]**: Backend implemented in Python (FastAPI, Scikit-Learn, Pandas, NumPy); Frontend in modern HTML5/Tailwind/Chart.js SPA.

---

## 10. MVP Scope vs. Future Enhancements

### MVP Scope (Current Release)
- Multi-turbine SCADA simulator and real benchmark dataset loader supporting canonical `is_curtailed`.
- Gradient Boosted Expected Power Curve and Thermal Equilibrium models.
- Operational Context Engine (Curtailment & Ambient Heat Filters).
- Multi-Signal Subsystem Reasoner and 5-factor Prioritization Engine with auditable Tariff Provenance.
- Local RAG Knowledge Base with OEM manuals, IEC alarm codes, and India O&M SOPs.
- Grounded Advisory Engine with deterministic analytical separation, guardrails, and JSON schema.
- Interactive Operator Web Dashboard (Fleet Overview, Deep Dive, Case Studio, RAG Q&A, 10-Stage Demo).
- Complete automated evaluation suite and comprehensive documentation.

### Future Enhancements (Post-MVP Roadmap)
- Real-time OPC-UA / Modbus live industrial field connectors.
- Computer Vision integration for automated drone blade surface crack inspection.
- Multi-agent collaborative fleet wake steering optimization.
- Full aeroelastic Digital Twin integration using OpenFAST / aeroelastic models.
