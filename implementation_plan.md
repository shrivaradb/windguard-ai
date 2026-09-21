# Implementation Plan: WindGuard AI

**Explainable AI for Wind-Turbine Health Monitoring and Maintenance Decision Support**
*Developed for the 1M1B AI for Sustainability Virtual Internship in collaboration with IBM SkillsBuild & AICTE*

---

## 1. Executive Summary & Research Grounding

WindGuard AI is an integrated, explainable decision-support platform designed to bridge the critical operational gap between **Detection**, **Understanding**, and **Action** in wind energy operations.

### Grounding in Reference Literature
The project builds directly upon the conceptual frameworks articulated in the reference research paper:
> *“Artificial Intelligence in Wind Turbines: Current Trends, Emerging Architectures and Future Developments Toward Autonomous Wind Energy Systems”* (Academic Research Survey (2026), 2026) [Established].

Key insights incorporated from the paper:
1. **The Evolution of Turbine Intelligence**: Moving from purely reactive threshold SCADA monitoring $\to$ Machine Learning prediction $\to$ Hybrid Physics-Data-Knowledge systems $\to$ Supervised Decision Support (Sections II, XXVIII).
2. **The Failure of Purely Data-Driven Black Boxes**: High environmental non-stationarity, extreme class imbalance (rare failures vs. abundant normal data), and domain shift mean black-box classifiers fail to provide actionable maintenance confidence (Sections I, XXIV, XXV).
3. **The Imperative for Explainability & Uncertainty**: Maintenance engineers cannot act on a binary "Anomaly Detected" flag. They require quantified residuals, dominant signal attributions, confidence bounds, and engineering context (Sections XXV, XXVI).
4. **Human-in-the-Loop (HITL) Architecture**: AI must remain strictly advisory for safety-critical assets. Emergency shutdown, pitch/yaw actuation, and physical maintenance work orders require human review and escalation (Section XXVII).
5. **Indian Wind Energy Realities**: Addressing high ambient temperatures ($>40^\circ\text{C}$), pre-monsoon dust/turbulence, aging multi-OEM fleets, and grid curtailment derating (`is_curtailed`) (Section XXXIV).

### Primary Sustainability Alignment: SDG 7 (Affordable and Clean Energy)
- **Causal Impact Logic**: Early anomaly detection $\to$ Contextual filtering (eliminating false alarms) $\to$ Evidence-grounded root-cause reasoning $\to$ Targeted, pre-emptive maintenance $\to$ Reduction of catastrophic component failures (gearbox, generator, pitch) $\to$ Minimization of unplanned downtime $\to$ Higher turbine availability and Capacity Utilization Factor (CUF) $\to$ Lower Levelized Cost of Electricity (LCOE) $\to$ Accelerated renewable energy penetration.
- **Secondary Alignment**: SDG 9 (Industry, Innovation & Infrastructure) & SDG 13 (Climate Action).

---

## 2. Research Landscape & Novelty Definition

| Monitoring Paradigm | Typical Approach | Major Practical Limitation | WindGuard AI Advancement |
| :--- | :--- | :--- | :--- |
| **SCADA Thresholds** | Fixed sensor limit alarms (e.g. $T > 85^\circ\text{C}$) | Severe alarm fatigue; triggers false alarms under high ambient summer conditions; fails during early gradual degradation. | Context-aware dynamic baselines that adjust expected thresholds according to wind speed, ambient temperature, and power loading. |
| **Pure ML Anomaly Detection** | Isolation Forests / Autoencoders on SCADA | Flags "something is unusual" without explaining the physical root cause, subsystem attribution, or urgency. | Multi-signal residual attribution that isolates drivetrain vs. electrical vs. aerodynamic subsystems with statistical confidence. |
| **Traditional Vibration CMS** | High-frequency FFT spectrum analysis | Expensive sensor retrofits; siloed from operational SCADA and maintenance records; requires dedicated vibration experts. | Fuses SCADA operational dynamics with technical maintenance documentation to provide holistic condition assessments. |
| **Generic LLM Chatbots** | Standard conversational RAG | Prone to numerical hallucination; invents sensor metrics and fabricated repair procedures without physical grounding. | **Strict Hybrid Separation**: Numerical ML determines exact anomalies; Context Engine validates physics; RAG retrieves validated OEM manuals; LLM synthesizes facts strictly from bounded evidence. |

### Defensible Novelty Claim
> **Contribution**: A prototype hybrid decision-support architecture that connects context-aware SCADA anomaly analysis with engineering-document retrieval (RAG) and evidence-grounded LLM maintenance reasoning, while enforcing deterministic safety boundaries and human oversight.

---

## 3. Canonical 6-Layer System Architecture

WindGuard AI is organized strictly into a **6-layer modular architecture** conforming to [`docs/08_system_architecture.md`](file:///c:/Users/shriv/OneDrive/Desktop/WindGuardAI/docs/08_system_architecture.md):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WINDGUARD AI CANONICAL 6-LAYER ARCHITECTURE              │
└─────────────────────────────────────────────────────────────────────────────┘

  [ LAYER 1: DATA INGESTION & SCADA SIMULATOR ]
  ├── 10-minute SCADA data streams (Wind speed, Power, Temperatures, Speeds)
  ├── Ingests canonical telemetry schema (is_curtailed, ambient temp, pitch)
  └── Multi-source data engine (Kelmarsh/Penmanshiel benchmarks + Physics simulator)
                                │
                                ▼
  [ LAYER 2: DETERMINISTIC ANALYTICAL ML & RESIDUAL ENGINE ]
  ├── Non-linear Empirical Power Curve Model: P_expected = f(v_wind, T_ambient, pitch)
  ├── Thermal Equilibrium Baselines: T_gearbox_exp = f(P_active, T_amb, RPM), T_gen_exp
  └── Multi-variable Residual Calculator & z-scores: R_i = X_observed - X_expected
                                │
                                ▼
  [ LAYER 3: OPERATIONAL CONTEXT FILTER, REASONER & LOSS ENGINE ]
  ├── Context Filter: Suppresses false alarms during curtailment, heatwaves, low-wind
  ├── Multi-Signal Reasoner: Isolates Drivetrain, Generator, Rotor, Sensor failure modes
  ├── Tariff Registry: Multi-mode tariff provenance (PPA, Regulatory, ₹3.20/kWh Baseline)
  └── Loss Calculator (FR-007 P0): Deterministic Energy Loss (kWh) & Financial Loss (INR)
                                │
                                ▼
  [ LAYER 4: TECHNICAL KNOWLEDGE RETRIEVAL (RAG) ENGINE ]
  ├── IEC 61400 / OEM Technical Maintenance Manuals & Fault Matrices
  ├── SCADA Alarm Code Reference Catalog (AL-104, AL-208, AL-312, etc.)
  └── Local Hybrid Dense & TF-IDF/BM25 Vector Search with Source Citation Metadata
                                │
                                ▼
  [ LAYER 5: EVIDENCE SYNTHESIS, GUARDRAIL & GENERATION LAYER ]
  ├── Strict Deterministic Schema Bounding (prevents generative numerical modification)
  ├── Input: Analytical residuals + Context status + Calculated Loss + RAG chunks
  └── Output: Structured Maintenance Case (Hypotheses, Evidence Table, OEM Citations)
                                │
                                ▼
  [ LAYER 6: PRESENTATION, REST API & HITL GOVERNANCE LAYER ]
  ├── FastAPI Asynchronous REST Backend (/api/fleet, /api/turbines, /api/cases, /api/tariffs)
  ├── Operator Web Dashboard (Fleet Overview, Cases Log, Power Curves, RAG Assistant)
  ├── Atomic File Persistence (case_store.py with portalocker file locking)
  └── Human-in-the-Loop Governance: Acknowledge | Investigate | Escalate | Dismiss
```

---

## 4. Detailed Component Implementation Plan

### Component A: Data Pipeline & Realistic SCADA Simulation Engine (Layer 1)
- **Files**: `backend/data/scada_generator.py`, `backend/data/dataset_loader.py`
- **Functionality**:
  - Ingests public benchmark wind turbine SCADA data (e.g., Kelmarsh / Penmanshiel / La Haute Borne standard formats) and generates realistic multi-turbine telemetry streams with 10-minute resolution.
  - Implements canonical telemetry schema using `is_curtailed` (with backward-compatible `curtailment_flag` ingestion mapping).
  - Realistic physics relationships:
    - Aerodynamic power curve with cut-in ($3\,\text{m/s}$), rated ($12\,\text{m/s}$), and cut-out ($25\,\text{m/s}$).
    - Gearbox & generator heating dynamics modeled via first-order thermal differential equations responding to mechanical torque, electrical load, and ambient temperature.
  - Indian context simulation: High ambient summer peaks ($42^\circ\text{C}$), pre-monsoon turbulence, active grid curtailment events.
  - 5 Benchmarked Failure Scenarios for testing:
    1. *Scenario 1: Normal Operation & Weather Transients* (Baseline).
    2. *Scenario 2: Gearbox High-Speed Bearing Degradation* (Rising thermal residual + normal wind + rotor speed slip).
    3. *Scenario 3: Pitch Asymmetry / Aerodynamic Loss* (Under-power residual + normal temperatures + pitch angle imbalance).
    4. *Scenario 4: Grid Curtailment & Ambient Heat Wave* (Power capped by operator + high ambient temp $\to$ Context engine correctly suppresses false alarm).
    5. *Scenario 5: Sensor Dropout & Calibration Drift* (Thermocouple failure flagged as sensor error).

### Component B: Machine Learning & Residual Quantification Engine (Layer 2)
- **Files**: `backend/models/expected_power.py`, `backend/models/thermal_model.py`, `backend/models/residual_engine.py`
- **Functionality**:
  - **Expected Power Model**: Gradient Boosted Regressor / Random Forest trained on normal operational data to predict expected power:
    $$\hat{P} = f(v_{\text{wind}}, T_{\text{ambient}}, \theta_{\text{pitch}})$$
  - **Expected Component Temperature Models**:
    $$\hat{T}_{\text{gearbox}} = g(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}})$$
    $$\hat{T}_{\text{generator}} = h(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}})$$
  - **Residual Quantification & Anomaly Scoring**:
    - Residuals: $R_P = P_{\text{actual}} - \hat{P}$, $R_{\text{GB}} = T_{\text{GB}} - \hat{T}_{\text{GB}}$, $R_{\text{Gen}} = T_{\text{Gen}} - \hat{T}_{\text{Gen}}$.
    - Standardized z-score and robust rolling quantile thresholds over a 6-step sliding window ($1\,\text{hour}$ persistence).

### Component C: Context Engine, Reasoner & Tariff Loss Engine (Layer 3 — FR-007 P0)
- **Files**: `backend/engine/context_engine.py`, `backend/engine/prioritization.py`, `backend/engine/tariff_registry.py`, `backend/engine/loss_calculator.py`
- **Functionality**:
  - Context validation filters:
    - *Curtailment Check*: Is active power reduced due to grid dispatch commands (`is_curtailed == True`) or feathered pitch? (Classification: Operational Constraint, Not Equipment Fault).
    - *Environmental Heat Check*: Is temperature elevation purely caused by ambient heat ($>38^\circ\text{C}$) with normal thermal rise $\Delta T$? (Classification: Ambient Derating).
    - *Low-Wind / Cut-In Transition*: Suppress noise during low-wind rotor idling.
  - Multi-Signal Synthesis: Cross-correlates power drop + thermal surge + speed deviations to categorize subsystem likelihood (Drivetrain, Generator/Converter, Rotor/Aerodynamic, Sensor/Auxiliary).
  - Prioritization Metric:
    $$S_{\text{priority}} = 0.25 \times S_{\text{severity}} + 0.25 \times S_{\text{persistence}} + 0.20 \times S_{\text{conf}} + 0.15 \times S_{\text{crit}} + 0.15 \times S_{\text{loss}}$$
  - **Tariff Architecture & Loss Calculator**:
    - Multi-mode tariff registry (`PROJECT_PPA`, `REGULATORY_BENCHMARK`, `CONFIGURED_BASELINE` [default: ₹3.20/kWh], `SCENARIO_OVERRIDE`).
    - Deterministic energy loss: $\text{Energy Loss (kWh)} = \sum \max(0, \hat{P}_t - P_t) \times \frac{10}{60}$.
    - Deterministic financial loss: $\text{Financial Loss (INR)} = \text{Energy Loss} \times \text{Tariff Rate}$.
    - Full provenance metadata tracking on every generated advisory.

### Component D: RAG Technical Knowledge Base & Document Retrieval (Layer 4)
- **Files**: `backend/rag/knowledge_base.py`, `backend/rag/vector_store.py`, `backend/rag/documents/*`
- **Corpus Content**:
  - `oem_maintenance_manual.md`: Detailed inspection procedures for 2.X MW double-fed induction generator (DFIG) wind turbines.
  - `scada_alarm_matrix.md`: Alarm codes, descriptions, trigger thresholds, and recommended first-line investigations.
  - `root_cause_troubleshooting_guide.md`: Drivetrain vibration, bearing lubrication failure modes, pitch actuator calibration, generator stator insulation degradation.
  - `india_wind_farm_sop.md`: High-ambient temperature management, pre-monsoon gearbox oil flushing, dust filter maintenance, and grid compliance protocols.
- **Retrieval Mechanism**:
  - Local hybrid dense and TF-IDF/BM25 search engine with chunk-level metadata tracking, guaranteeing 100% offline functionality without external database services.

### Component E: Evidence-Grounded Synthesis & Guardrails (Layer 5)
- **Files**: `backend/llm/advisory_engine.py`, `backend/llm/prompts.py`, `backend/llm/guardrails.py`
- **Functionality**:
  - Multi-provider support: High-Fidelity Local Deterministic Fallback Engine (default offline) + Pluggable IBM Granite / Cloud LLMs.
  - Strict schema bounding: Prevents generative layer from modifying numerical outputs or inventing unverified facts.
  - Structured output payload matching Pydantic specification (`case_id`, `turbine_id`, `evidence_table`, `loss_estimate`, `tariff_provenance`, `differential_hypotheses`, `oem_citations`, `recommended_action`, `status`).

### Component F: FastAPI Backend & Presentation Studio (Layer 6)
- **Files**: `backend/main.py`, `backend/api/routes.py`, `backend/storage/case_store.py`, `frontend/*`
- **REST Endpoints**:
  - `GET /api/fleet/status`: Current health, active anomalies, fleet metrics.
  - `GET /api/turbines/{id}/telemetry`: Time-series sensor data and expected baselines.
  - `POST /api/turbines/{id}/diagnose`: Runs real-time diagnostic pipeline.
  - `GET /api/cases`: Paginated list of generated maintenance cases.
  - `GET /api/cases/{case_id}`: Detailed case view with evidence and citations.
  - `POST /api/cases/{id}/decision`: Records operator decision (Acknowledge/Inspect/Escalate/Dismiss) into atomic audit log.
  - `GET /api/tariffs`: Retrieves active tariff rate, mode, and provenance.
  - `POST /api/tariffs`: Updates or overrides active tariff rate.
  - `POST /api/rag/query`: Natural language knowledge assistant query with document citations.
  - `GET /api/demo/stage/{stage_id}`: Step-by-step 10-stage demo simulation state.
- **Operator Web Dashboard**:
  - Fleet health overview, cases table, power curves, thermal timelines, case inspector with Tariff Provenance block, RAG Q&A, and 10-stage stepper.

---

## 5. 10-Stage Reproducible Demo Scenario

1. **Stage 1 (Normal Operation)**: Turbine 07 runs smoothly; observed power matches expected curve (`[TARGET: R² > 0.98]`).
2. **Stage 2 (Incipient Power Deviation)**: Power drops $8\%$ below expected curve while wind speed remains steady ($8.5\,\text{m/s}$).
3. **Stage 3 (Thermal Residual Emergence)**: Gearbox high-speed bearing temperature rises $+6.5^\circ\text{C}$ above empirical baseline.
4. **Stage 4 (Persistent Multi-Signal Anomaly)**: Residuals persist for $>60$ minutes; statistical z-score exceeds $3.0\sigma$.
5. **Stage 5 (Context Engine Validation)**: System evaluates environmental factors; verifies `is_curtailed == False` and ambient temp ($32^\circ\text{C}$) do NOT explain deviation. Flags genuine anomaly.
6. **Stage 6 (Maintenance Case Generation & Loss)**: Reasoner assigns High Priority (Score: 88/100) and calculates $2,640\,\text{kWh}$ (₹$8,448$) loss with ₹3.20/kWh baseline tariff provenance.
7. **Stage 7 (RAG Technical Document Retrieval)**: Retrieves Section 4.2 of OEM Maintenance Manual & Alarm Code AL-104 (Bearing Lubrication Failure Modes).
8. **Stage 8 (Evidence-Grounded AI Reasoning)**: LLM synthesizes structured explanation citing exact sensor deltas and technical manual references.
9. **Stage 9 (Actionable Investigation Checklist)**: System provides ordered inspection steps (lubrication oil debris check, high-speed shaft alignment, oil filter differential pressure).
10. **Stage 10 (Human Operator Decision)**: O&M Engineer logs decision to *Escalate to Site Inspection Crew* and exports maintenance work order.

---

## 6. Verification Plan

### Automated Testing
- `python backend/evaluation/evaluate_models.py`: Runs ML model evaluation (`[TARGET: Power Curve R² ≥ 0.95]`, `[TARGET: Thermal RMSE ≤ 2.5°C]`).
- `python backend/evaluation/benchmark_scenarios.py`: Runs all 5 benchmark scenarios; validates Precision, Recall, F1, and False Alarm Suppression.
- `python -m pytest tests/`: Verifies API endpoints, RAG retrieval accuracy, tariff updates, and case decision logging with atomic persistence.

### Manual & Interactive Verification
- Launch FastAPI backend and web dashboard.
- Verify real-time telemetry streaming and charts for 10 simulated wind turbines.
- Step through the interactive 10-Stage Demo Walkthrough.
- Query the Knowledge Assistant with sample natural-language queries.
- Execute operator actions (Acknowledge, Inspect, Escalate) and verify case persistence.
- Inspect and verify all generated documentation artifacts.
