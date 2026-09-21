---
document: 07_srs
version: 0.1
status: REVIEW
last_updated: 2026-09-20
author: WindGuard AI Engineering & Architecture Team
depends_on:
  - docs/01_problem_statement.md
  - docs/02_literature_review.md
  - docs/03_gap_analysis.md
  - docs/04_proposed_solution.md
  - docs/05_uniqueness_and_innovation.md
  - docs/06_prd.md
---

# 07. Software Requirements Specification (SRS) — WindGuard AI

## 1. System Overview

This Software Requirements Specification (SRS) translates the Product Requirements Document ([`docs/06_prd.md`](file:///c:/Users/shriv/OneDrive/Desktop/WindGuardAI/docs/06_prd.md)) into rigorous, verifiable software engineering specifications for the **WindGuard AI** platform. It defines the exact technical behaviors, mathematical input/output transformations, data schemas, API interfaces, security constraints, and traceability links governing the system implementation.

---

## 2. Technical System Scope

WindGuard AI is implemented as a client-server architecture within the canonical 6-layer architecture:
1. **Python FastAPI High-Performance Backend Engine**: Encapsulating data ingestion, physics-informed regression models, context evaluation logic, vector-based RAG retrieval, and constrained LLM advisory synthesis.
2. **Modern Operator Web Interface (SPA)**: Delivering responsive interactive telemetry visualization, real-time power curve diagnostics, conversational knowledge retrieval, tariff display, and human-in-the-loop decision management.
3. **Local JSON File / SQLite Store**: Storing turbine configurations, time-series telemetry caches, technical document vector indexes, tariff configurations, and operator decision audit trails with thread-safe file locking.

---

## 3. Detailed Functional Specifications

### 3.1 Data Ingestion & Preprocessing Subsystem (SRS-DATA-01)
- **Traceability**: Derived from PRD `FR-001`.
- **Inputs**: 10-minute SCADA records containing:
  - `timestamp` (ISO-8601 string)
  - `turbine_id` (String, e.g., `"WTG-07"`)
  - `wind_speed` (Float, $0.0 - 50.0\,\text{m/s}$)
  - `wind_direction` (Float, $0.0 - 360.0^\circ$)
  - `ambient_temp` (Float, $-20.0 - 60.0^\circ\text{C}$)
  - `active_power` (Float, $0.0 - 2500.0\,\text{kW}$)
  - `reactive_power` (Float, $-1000.0 - 1000.0\,\text{kVAR}$)
  - `rotor_speed` (Float, $0.0 - 30.0\,\text{RPM}$)
  - `generator_speed` (Float, $0.0 - 2000.0\,\text{RPM}$)
  - `gearbox_bearing_temp` (Float, $0.0 - 130.0^\circ\text{C}$)
  - `generator_stator_temp` (Float, $0.0 - 160.0^\circ\text{C}$)
  - `nacelle_temp` (Float, $0.0 - 80.0^\circ\text{C}$)
  - `pitch_angle` (Float, $-5.0 - 95.0^\circ$)
  - `is_curtailed` (Boolean, `true`/`false` — Canonical field; `curtailment_flag` accepted as backward-compatible alias)
  - `operating_status` (String, e.g., `"Running"`, `"Curtailed"`, `"Maintenance"`)
- **Technical Behavior**:
  - Implements range-checking validation filters (flags impossible physics, e.g., negative wind speed).
  - Implements forward-fill / linear interpolation for missing sensor values up to 2 consecutive intervals; flags records with $>2$ missing intervals as sensor dropout.

---

### 3.2 Expected Power & Thermal Baseline Regressors (SRS-ML-01)
- **Traceability**: Derived from PRD `FR-002`, `FR-003`.
- **Mathematical Specification**:
  - **Expected Power**: $\hat{P} = f_{\text{GBR}}(v_{\text{wind}}, T_{\text{ambient}}, \theta_{\text{pitch}})$ trained using Gradient Boosted Decision Trees / Random Forests on validated healthy operational datasets.
  - **Expected Gearbox Temperature**: $\hat{T}_{\text{GB}} = g_{\text{thermal}}(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{rotor}})$.
  - **Expected Generator Temperature**: $\hat{T}_{\text{Gen}} = h_{\text{thermal}}(P_{\text{active}}, T_{\text{ambient}}, \omega_{\text{gen}})$.
- **Residual Computation**:
  - $R_{\text{power}} = P_{\text{actual}} - \hat{P}$
  - $R_{\text{GB}} = T_{\text{GB\_actual}} - \hat{T}_{\text{GB}}$
  - $R_{\text{Gen}} = T_{\text{Gen\_actual}} - \hat{T}_{\text{Gen}}$
  - Normalized $z$-score: $z_i = \frac{R_i - \mu_i}{\sigma_i}$.

---

### 3.3 Operational Context Engine (SRS-CTX-01)
- **Traceability**: Derived from PRD `FR-004`.
- **Logical Rules**:
  1. *Curtailment Rule*: If `is_curtailed == true` OR (`pitch_angle > 15°` AND `active_power < 0.6 * P_exp`):
     - `context_classification = "Operational Curtailment"`
     - Suppress high-priority anomaly; tag telemetry as intentional grid derating.
  2. *Ambient Thermal Rise Rule*: If `ambient_temp > 38.0°C` AND `(T_GB_actual - ambient_temp) <= Normal_Rise_Threshold`:
     - `context_classification = "High Ambient Seasonal Derating"`
     - Mark thermal elevation as environmental; suppress false mechanical alarm.
  3. *Low-Wind Cut-In Rule*: If `wind_speed < 3.0 m/s`:
     - `context_classification = "Below Cut-In / Idling"`
     - Suppress low power anomaly.

---

### 3.4 Multi-Signal Reasoner & Prioritization Engine (SRS-REAS-01)
- **Traceability**: Derived from PRD `FR-005`, `FR-006`, `FR-007`.
- **Subsystem Isolation Matrix**:
  - If $R_{\text{power}} < -2.0\sigma$ AND $R_{\text{GB}} > +2.5\sigma$ AND $\Delta\omega_{\text{slip}} > 1.5\sigma$ $\implies$ **Drivetrain / Gearbox Bearing Subsystem**.
  - If $R_{\text{power}} < -2.0\sigma$ AND $R_{\text{Gen}} > +2.5\sigma$ $\implies$ **Generator / Electrical Subsystem**.
  - If $R_{\text{power}} < -2.5\sigma$ AND $R_{\text{GB}} \approx 0$ AND $\Delta\theta_{\text{pitch}} > 2^\circ$ $\implies$ **Aerodynamic / Pitch Actuator Subsystem**.
- **Priority Formula**:
  $$\text{Priority Score} = 0.25 \cdot S_{\text{residual}} + 0.25 \cdot S_{\text{persistence}} + 0.20 \cdot S_{\text{confidence}} + 0.15 \cdot S_{\text{criticality}} + 0.15 \cdot S_{\text{loss}}$$
- **Energy & Financial Loss Formulation**:
  $$\text{Loss } (\text{kWh}) = \sum_{k=1}^{W} \max(0, \hat{P}_k - P_{\text{actual}, k}) \times \frac{10}{60}$$
  $$\text{Estimated Financial Loss } (₹) = \text{Loss } (\text{kWh}) \times \text{Applicable Tariff } (₹/\text{kWh})$$
  *(Note: Applicable Tariff is resolved from Tariff Hierarchy: Project-Specific Verified PPA $\to$ Official Regulatory Reference $\to$ Configured Default Baseline [₹3.20/kWh] $\to$ User Scenario Tariff).*

---

### 3.5 Technical Document RAG Knowledge Subsystem (SRS-RAG-01)
- **Traceability**: Derived from PRD `FR-008`, `FR-010`.
- **Corpus Structure**:
  - `oem_maintenance_manual.md`: Chapter 4 Drivetrain & Bearings, Chapter 5 Pitch & Yaw Systems, Chapter 6 Generator & Converters.
  - `scada_alarm_matrix.md`: Alarm codes AL-101 to AL-405, threshold limits, severity classes, initial diagnostic checks.
  - `india_wind_farm_sop.md`: High ambient heat derating, pre-monsoon oil flushing, dust filter replacement schedules.
- **Search Engine**:
  - Hybrid dense embedding search (cosine similarity) + lexical BM25 fallback.
  - Returns top-$k$ ($k=3$) text chunks with rich citation metadata (`document_name`, `chapter`, `section`, `page_number`).

---

### 3.6 Constrained Advisory Synthesis Subsystem (SRS-LLM-01)
- **Traceability**: Derived from PRD `FR-009`.
- **Output JSON Schema Specification**:
  ```json
  {
    "case_id": "CASE-WTG07-20260920-001",
    "turbine_id": "WTG-07",
    "timestamp": "2026-09-20T10:30:00Z",
    "severity": "HIGH",
    "priority_score": 84.5,
    "confidence_rating": "HIGH (88%)",
    "event_summary": "Persistent power derating (-18.2%) with elevated gearbox bearing temperature (+7.2°C) under healthy wind conditions (8.5 m/s).",
    "evidence_table": [
      {"parameter": "Active Power", "observed": "1420 kW", "expected": "1735 kW", "residual": "-315 kW (-18.2%)", "status": "ANOMALOUS"},
      {"parameter": "Gearbox Bearing Temp", "observed": "78.4°C", "expected": "71.2°C", "residual": "+7.2°C (+10.1%)", "status": "ANOMALOUS"},
      {"parameter": "Ambient Temp", "observed": "32.0°C", "expected": "32.0°C", "residual": "0.0°C", "status": "NORMAL"}
    ],
    "context_assessment": "Ambient temperature (32°C) and is_curtailed=false confirm deviation is physical, not environmental.",
    "differential_hypotheses": [
      {"hypothesis": "High-speed shaft bearing lubrication starvation or early surface spalling", "probability": "75%", "evidence": "High thermal residual + power loss"},
      {"hypothesis": "Gearbox oil cooling pump bypass valve sticking", "probability": "20%", "evidence": "Thermal elevation without severe rotor vibration"}
    ],
    "tariff_provenance": {
      "applied_rate": 3.20,
      "currency": "INR",
      "unit": "INR/kWh",
      "tariff_type": "Configurable Baseline PPA",
      "source": "CERC Wind Benchmark / Asset Default",
      "effective_period": "2025-2026",
      "verification_date": "2026-09-20"
    },
    "rag_citations": [
      {"document": "OEM 2.X MW Maintenance Manual", "section": "Sec 4.2 High-Speed Shaft Bearings", "page": 114},
      {"document": "SCADA Alarm Code Matrix", "section": "AL-104 Gearbox High Temp Response", "page": 18}
    ],
    "recommended_investigation_checklist": [
      "1. Perform offline grease/oil sample inspection for metallic particle contamination.",
      "2. Verify high-speed shaft mechanical alignment using dial indicators.",
      "3. Inspect gearbox oil radiator fan and filter differential pressure gauge."
    ],
    "human_action_options": ["Acknowledge", "Investigate", "Escalate", "Dismiss"]
  }
  ```

---

### 3.7 Operator Dashboard & Human-in-the-Loop Management (SRS-UI-01)
- **Traceability**: Derived from PRD `FR-011`, `FR-012`, `FR-013`.
- **Components**:
  - Fleet Status Banner: Real-time turbine health cards with color-coded severity badges.
  - Interactive Power Curve Chart: Plots active power vs. wind speed overlaying theoretical power curve, expected model curve, and live operational points.
  - Multi-Sensor Telemetry & Residual Trends: Synchronized time-series charts of power, temperatures, and speeds.
  - AI Diagnostic Case Inspector: Renders the structured advisory case with interactive action buttons (*Acknowledge*, *Investigate*, *Escalate*, *Dismiss*).
  - Tariff Provenance Card: Displays currently applied tariff value, tariff type, source, and calculated financial loss.
  - Conversational Knowledge Assistant: Search box supporting natural-language RAG queries with cited sources.
  - 10-Stage Reproducible Demo Stepper: UI navigation bar stepping through the 10 stages of the benchmark maintenance scenario.

---

## 4. External Interfaces

### 4.1 REST API Specification
- `GET /api/fleet/status` $\implies$ Returns summary array of all turbines, active anomaly counts, total fleet energy loss, and financial loss.
- `GET /api/turbines/{id}/telemetry` $\implies$ Returns time-series telemetry array with observed values and computed expected baselines.
- `POST /api/turbines/{id}/diagnose` $\implies$ Executes ML + Context + RAG + Advisory pipeline and returns the full structured JSON case.
- `GET /api/cases` $\implies$ Returns list of all generated maintenance advisory cases.
- `GET /api/cases/{id}` $\implies$ Returns a specific maintenance case by ID with evidence and tariff provenance.
- `POST /api/cases/{id}/decision` $\implies$ Ingests `{"action": "Escalate", "notes": "Dispatched site crew"}` and persists to audit log.
- `GET /api/tariffs` $\implies$ Returns active tariff configuration, official regulatory references, and scenario tariffs.
- `POST /api/tariffs` $\implies$ Sets or updates project-specific or scenario tariff configuration.
- `POST /api/rag/query` $\implies$ Ingests `{"query": "..."}` and returns answer with document citation metadata.
- `GET /api/demo/stage/{stage_id}` $\implies$ Returns mock telemetry and state representing the requested demo stage ($1-10$).

---

## 5. Requirement Traceability Matrix

| Requirement | PRD ID | Architecture Layer | Technical Component | Implementation Phase | Test Case ID |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **SRS-DATA-01** (SCADA Ingestion) | `FR-001` (P0) | Layer 1: Data Ingestion | Data Ingestion Engine | Phase 1 | `TEST-DATA-01` |
| **SRS-ML-01** (Power & Thermal ML) | `FR-002`, `FR-003` (P0) | Layer 2: Analytical Engine | Expected Behaviour Engine | Phase 2 | `TEST-ML-01` |
| **SRS-CTX-01** (Context Engine) | `FR-004` (P0) | Layer 3: Context Engine | Operational Context Engine | Phase 3 | `TEST-CTX-01` |
| **SRS-REAS-01** (Multi-Signal & Loss) | `FR-005`, `FR-006`, `FR-007` (P0) | Layer 3: Context Engine | Multi-Signal Reasoner & Tariffs | Phase 3 | `TEST-REAS-01` |
| **SRS-RAG-01** (Technical RAG) | `FR-008`, `FR-010` (P0/P1) | Layer 4: Technical Knowledge | Vector Knowledge Base | Phase 4 | `TEST-RAG-01` |
| **SRS-LLM-01** (Advisory Synthesis) | `FR-009` (P0) | Layer 5: Evidence Synthesis | Advisory Synthesis Engine | Phase 5 | `TEST-LLM-01` |
| **SRS-UI-01** (Operator UI & HITL) | `FR-011`, `FR-012`, `FR-013` (P0) | Layer 6: Presentation & HITL | Operator Dashboard & API | Phase 7 | `TEST-UI-01` |
| **SRS-NFR-01** (Inference Latency) | `NFR-001` | Layer 6: Presentation & API | Backend API Layer | Phase 6 | `TEST-PERF-01` |
| **SRS-NFR-02** (Factual Grounding) | `NFR-004` | Layer 5: Evidence Synthesis | Guardrail Audit Subsystem | Phase 5 | `TEST-AUDIT-01` |
