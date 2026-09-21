---
document: PHASE_7_OWNER_DECISION_RESOLUTION
version: 1.0
status: READY FOR OWNER IMPLEMENTATION AUTHORIZATION
date: 2026-09-20
author: Project Owner & Lead System Architect
governance: Phase 7 Formal Owner Decision Resolution Record
depends_on:
  - docs/00_documentation_index.md
  - docs/06_prd.md
  - docs/07_srs.md
  - docs/08_system_architecture.md
  - docs/09_technical_design.md
  - docs/10_data_architecture.md
  - docs/11_ai_ml_design.md
  - docs/12_ui_ux_specification.md
  - docs/13_technology_stack.md
  - docs/14_implementation_plan.md
  - docs/PHASE_4_OWNER_SIGN_OFF.md
  - docs/PHASE_5_OWNER_SIGN_OFF.md
  - docs/PHASE_6_GOVERNANCE_RECONCILIATION.md
  - docs/PHASE_6_OWNER_SIGN_OFF.md
  - docs/PHASE_7_SCOPE_REVIEW.md
  - docs/PHASE_7_GOVERNANCE_RECONCILIATION.md
---

# Phase 7 Owner Decision Resolution Record
## Presentation, Operator Web Dashboard & Demonstration Layer

```
====================================================================================================
                     PHASE 7 OWNER DECISION RESOLUTION RECORD
====================================================================================================
Governance Phase                   : Phase 7 (Presentation & Operator Web Dashboard Layer)
Document Type                      : Formal Project Owner Decision Resolution Record
Upstream Frozen Baselines          : Phase 1 through Phase 6 FROZEN & IMMUTABLE
Decision Status Summary            : ALL 4 REMAINING OWNER DECISIONS FORMALLY RESOLVED
OD-P7-04 (Operator Identity)       : RESOLVED (Session Profile Selector + X-Operator-ID Attribution)
OD-P7-05 (Polling Strategy)        : RESOLVED (5s Fleet / 10s Cases with Pause-on-Blur Engine)
OD-P7-06 (Work-Order Export)       : RESOLVED (Presentation-Only @media print Browser Print Export)
OD-P7-11 (Performance Targets)     : RESOLVED (Approved Tier 3 UI Budgets within 2.5s Formal SLA)
Remaining Open Owner Decisions     : 0 (ZERO)
Remaining Specification Gaps       : 0 (ZERO)
Implementation Authorization       : NOT AUTHORIZED BY THIS TASK (Requires Separate Owner Order)
Final Phase 7 Classification       : READY FOR OWNER IMPLEMENTATION AUTHORIZATION
====================================================================================================
```

> [!IMPORTANT]
> **PHASE 7 IMPLEMENTATION IS NOT AUTHORIZED BY THIS DOCUMENT.**
> This document establishes the formal, binding resolution of all four open Owner Decisions governing Phase 7. It does not authorize the start of coding, UI construction, backend modifications, or testing. Implementation requires a separate, explicit Project Owner Implementation Authorization order.

---

## 1. Document Purpose

The purpose of this document is to formally resolve the four open Owner Decisions identified during the **Phase 7 Scope Review** ([`docs/PHASE_7_SCOPE_REVIEW.md`](file:///c:/Users/shriv/OneDrive/Desktop/WindGuardAI/docs/PHASE_7_SCOPE_REVIEW.md)) and reconciled in the **Phase 7 Technical Governance Reconciliation** ([`docs/PHASE_7_GOVERNANCE_RECONCILIATION.md`](file:///c:/Users/shriv/OneDrive/Desktop/WindGuardAI/docs/PHASE_7_GOVERNANCE_RECONCILIATION.md)).

By formally deciding each item, this record establishes the definitive engineering baseline for Phase 7 implementation while preserving the strict immutability of the frozen Phase 1–6 backend contracts.

---

## 2. Decision Status Summary

| Decision ID | Decision Area | Governance Status | Owner-Approved Resolution Summary | Resulting Implementation Implication |
| :---: | :--- | :---: | :--- | :--- |
| **OD-P7-04** | Operator Identity Presentation | **RESOLVED** | **Client Session Profile Selector with `X-Operator-ID` Header & Payload Attribution.** | Top navbar persona selector; persists active ID to `sessionStorage`; attaches header/payload to all mutating requests; zero auth/JWT backend changes. |
| **OD-P7-05** | UI Polling Strategy | **RESOLVED** | **Configurable Polling Engine: 5s Fleet / 10s Cases with Automatic Pause-on-Blur.** | 5s poll for Fleet/Telemetry, 10s for Cases; pauses immediately when tab inactive (`visibilityState`); manual refresh toggle; in-flight request lock. |
| **OD-P7-06** | Work-Order / PDF Export | **RESOLVED** | **Presentation-Only Client-Side Print Stylesheet (`@media print`) and Browser PDF Export.** | Formatted print CSS layout rendering draft work order with evidence, checklist, citations, and non-actuating disclaimer; zero backend/external execution. |
| **OD-P7-11** | UI Performance Targets | **RESOLVED** | **Formal Adoption of Tier 3 Client Performance Budgets within the $\le 2.5\,\text{s}$ System Ceiling.** | Load $<500\,\text{ms}$, Fleet $<250\,\text{ms}$, Tab $<50\,\text{ms}$, Charts $<150\,\text{ms}$, Diagnosis UI $<1.5\,\text{s}$; validated against Chromium/Firefox. |

---

## 3. Pre-Existing Frozen Governance Constraints

The Project Owner re-attests the following immutable constraints across all decisions:

1. **Phase 1–6 Immutability**: No backend code, schemas, routes, models, storage mechanisms, RAG indices, or tests in Phases 1–6 may be modified to accommodate Phase 7.
2. **Permanent Prohibition of Actuation**: WindGuard AI is strictly an advisory decision-support system. The UI must never contain, render, or imply turbine start/stop controls, pitch overrides, yaw slewing commands, breaker trips, alarm resets, remote actuation toggles, or autonomous control workflows.
3. **Attribution vs. Authentication**: Operator identity represents audit trail *attribution*, not authentication or authorization. No JWT, OAuth, session cookies, or user databases shall be introduced.
4. **Offline Local Self-Containment**: The UI operates 100% locally from the static server without external CDN dependencies or public cloud LLM connections.
5. **Immutable Case Store**: Cases are strictly append-only. Zero case deletion or modification capabilities exist.

---

## 4. Formal Resolution: `OD-P7-04` — Operator Identity Presentation

```
====================================================================================================
                                FORMAL OWNER DECISION: OD-P7-04
====================================================================================================
Decision Topic                     : Operator Identity Presentation & Audit Attribution
Selected Architectural Option      : Client Session Profile Selector + HTTP Header/Payload Propagation
Owner Decision Status              : FORMALLY RESOLVED (OWNER-APPROVED)
====================================================================================================
```

### 4.1 Context & Alternative Evaluation
- **Option A (Formal Authentication / Login Modal)**: Requires creating a login barrier, mock password store, JWT tokens, and session expiration handlers.
  - *Evaluation*: Rejected. Unnecessarily complicates an offline control room (ROC) workstation where physical/network access is already secured; introduces fake security credentials not backed by Phase 6.
- **Option B (Lightweight Client Session Profile Selector)**: A top navbar Operator Profile Switcher that persists the active operator persona in browser session storage and propagates attribution to Phase 6 APIs.
  - *Evaluation*: **APPROVED**. Fulfills 100% of audit logging, case tracking, and persona demonstration requirements while maintaining 100% compatibility with frozen Phase 6 endpoints.

### 4.2 Exact Approved UI & Technical Behavior:
1. **Top Navigation Bar Display**:
   - The top navigation bar renders an Operator Badge showing the active persona icon, name, and role (e.g., `Rajesh Sharma (ROC Lead)`).
   - Clicking the badge opens a lightweight dropdown allowing the user to select from canonical personas derived from [`docs/06_prd.md`](file:///c:/Users/shriv/OneDrive/Desktop/WindGuardAI/docs/06_prd.md) §5:
     1. `Rajesh Sharma — Lead O&M Operations Engineer` (ID: `OPERATOR_RAJESH`)
     2. `Anil Patel — Senior Field Maintenance Technician` (ID: `TECHNICIAN_ANIL`)
     3. `Priya Menon — Renewable Asset Portfolio Manager` (ID: `EXECUTIVE_PRIYA`)
     4. `Default Local ROC Operator` (ID: `OPERATOR_LOCAL`)
     5. `Custom Operator` (Write-in input field for evaluator/operator badge ID).
2. **Persistence**:
   - The selected operator identity is stored in `sessionStorage.getItem("windguard_operator_id")` and `sessionStorage.getItem("windguard_operator_name")`. It persists across page refreshes within the browser session.
   - If unset, it defaults deterministically to `"OPERATOR_LOCAL"`.
3. **API Propagation**:
   - Every outgoing `fetch()` request automatically attaches the `X-Operator-ID` HTTP request header.
   - For mutating payloads requiring an `operator_id` field (`OperatorDecisionRequest`, `TariffUpdateRequest`, `DiagnoseRequest`), the client populates `operator_id` with the active ID.
4. **Validation**:
   - Operator ID must be a sanitized string ($1 \le \text{length} \le 64$ characters, alphanumeric plus underscores/hyphens).
5. **Explicit Non-Goals**:
   - No passwords, no login gate, no access control lists (RBAC), no route locking, and zero changes to `backend/api/dependencies.py`.

---

## 5. Formal Resolution: `OD-P7-05` — Polling & Refresh Strategy

```
====================================================================================================
                                FORMAL OWNER DECISION: OD-P7-05
====================================================================================================
Decision Topic                     : UI Polling Strategy & Telemetry Refresh Engine
Selected Architectural Option      : Tiered Client Polling with Automatic Pause-on-Blur Engine
Owner Decision Status              : FORMALLY RESOLVED (OWNER-APPROVED)
====================================================================================================
```

### 5.1 Approved Polling Cadence by View:

| UI View / Subsystem | Target REST Endpoint | Approved Refresh Mode | Polling Interval | Rationale |
| :--- | :--- | :---: | :---: | :--- |
| **Screen 1: Fleet Overview** | `GET /api/fleet/status` + Telemetry | Periodic Polling | **5.0 seconds** | Keeps aggregated fleet metrics, power, wind, and active anomaly cards fresh. |
| **Screen 1 & 3: Cases Table** | `GET /api/cases` | Periodic Polling | **10.0 seconds** | Updates open/investigating/escalated case registry without high request frequency. |
| **Screen 2: Turbine Deep Dive**| `GET /api/turbines/{id}/telemetry`| Periodic Polling | **5.0 seconds** | Keeps 10-minute time-series charts and live operational points synchronized. |
| **Screen 3: Diagnostic Studio** | `POST /turbines/{id}/diagnose` | **On-Demand Only** | *None (Manual)* | Executed only on operator click, case selection, or explicit triage trigger. |
| **Screen 4: Knowledge Assistant**| `POST /api/rag/query` | **On-Demand Only** | *None (Manual)* | Executed strictly upon operator natural-language search query submission. |
| **Screen 5: Tariff Settings** | `GET /api/tariffs` | **On-Demand / Entry** | *None (On Load)*| Fetched upon viewing the settings tab or following a tariff update. |
| **Screen 6: 10-Stage Demo UI** | `GET /api/demo/stage/{id}` | **On-Demand Stepper** | *None (Manual)* | Zero background polling during demo mode to ensure 100% deterministic progression. |

### 5.2 Approved Visibility & Network Management Rules:
1. **Automatic Pause-on-Blur (`document.visibilityState`)**:
   - When the user switches tabs, minimizes the browser, or blurs the window (`visibilitychange` event), all polling timers are paused immediately.
   - When the tab returns to visible focus, an immediate refresh tick is triggered for the active view, and regular timers resume.
2. **In-Flight Request Concurrency Lock**:
   - If an API request is still pending when the next poll tick fires, the client skips that tick to prevent overlapping requests or thundering herd conditions.
3. **Manual Refresh Controls**:
   - The top navigation bar includes a prominent "Refresh Now" icon button and a "Live Updates [ON / PAUSED]" toggle switch, allowing operators to freeze live telemetry during detailed root-cause investigations.
4. **Exponential Backoff on Failure**:
   - Upon encountering consecutive network errors ($5\text{xx}$ or connection drop), polling automatically backs off ($5\text{s} \to 10\text{s} \to 20\text{s} \to 30\text{s}$ max) and renders a non-blocking reconnection indicator. Upon a successful response, polling returns immediately to standard $5\text{s}$ cadence.

---

## 6. Formal Resolution: `OD-P7-06` — Work Order / PDF Export

```
====================================================================================================
                                FORMAL OWNER DECISION: OD-P7-06
====================================================================================================
Decision Topic                     : Work Order / PDF Export Presentation & Architecture
Selected Architectural Option      : Option A — Client-Side Print Stylesheet (@media print) Export
Owner Decision Status              : FORMALLY RESOLVED (OWNER-APPROVED)
====================================================================================================
```

### 6.1 Architectural Justification
- **Option B (Server-Side PDF Binary via WeasyPrint / ReportLab / Puppeteer)**:
  - *Evaluation*: Rejected. Would violate Phase 6 freeze by introducing heavy new system dependencies (C-libraries, headless Chromium, font packages), new backend routes, and new file storage overhead.
- **Option A (Client-Side Print-Optimized Stylesheet `@media print`)**:
  - *Evaluation*: **APPROVED**. Introduces zero backend changes, zero server dependencies, operates 100% offline, and utilizes the browser's native, high-quality PDF rendering engine (`window.print()`).

### 6.2 Approved Work Order Document Specification:
1. **Trigger**: An "Export Work Order (Print / PDF)" button on Screen 3 (AI Diagnostic Studio) and Case Detail Inspector.
2. **Formatted Print Layout**: When `window.print()` is called, `@media print` CSS rules transform the diagnostic case into an executive, high-contrast, multi-page maintenance dossier:
   - **Header Section**: WindGuard AI Logo, Wind Farm Name, Target Turbine ID (`WTG-07`), Unique Case ID, Date/Timestamp, Attributed Operator, Severity Badge, Priority Score (0–100).
   - **Executive Summary & Context**: Plain-language anomaly event summary, ambient temperature, grid curtailment status (`is_curtailed: false`), and operational state.
   - **Grounding Evidence Table**: Clean tabular layout of observed vs. expected sensor values, deviations, and standardized $z$-scores.
   - **Differential Diagnostic Hypotheses**: Ranked hypotheses with qualitative `PlausibilityRating` badges (`HIGH`, `MODERATE`, `LOW`) and supporting evidence references.
   - **Technical RAG Citations**: Complete document title, chapter, section heading, source locator, page number (if present), and cryptographic SHA-256 hash.
   - **Technician Inspection Checklist**: Actionable physical inspection steps with printed checkboxes (`[ ]`) for field sign-off.
   - **Commercial Loss & Tariff Provenance**: Eligible energy loss (kWh), financial loss (₹ INR), applied tariff rate (₹3.20/kWh), and provenance mode.
   - **Human Action & Decision History**: Complete audit trail of operator decisions, timestamps, and entered engineering notes.
3. **Safety Disclaimer & Watermark**:
   - Fixed header/footer watermark: *"DRAFT WORK ORDER — FOR HUMAN ON-SITE PHYSICAL VERIFICATION ONLY — ADVISORY / NON-ACTUATING"*.
4. **Strict Scope Enforcement**:
   - Zero external API dispatching, zero automated ticketing, zero CMMS integrations, zero SCADA actuation.

---

## 7. Formal Resolution: `OD-P7-11` — Phase 7 UI Performance Targets

```
====================================================================================================
                                FORMAL OWNER DECISION: OD-P7-11
====================================================================================================
Decision Topic                     : Phase 7 UI Performance Targets & Acceptance Thresholds
Selected Architectural Option      : Formal Adoption of Tier 3 Client Budgets within 2.5s Hard SLA
Owner Decision Status              : FORMALLY RESOLVED (OWNER-APPROVED)
====================================================================================================
```

### 7.1 Formal Three-Tier Performance Hierarchy:
1. **Tier 1 (Binding System SLA Ceiling)**: **$\le 2.5\,\text{seconds}$** (`SRS-NFR-01` / Phase 6 frozen ceiling). Binding hard constraint.
2. **Tier 2 (Measured Phase 6 Backend Baseline)**: Mean $122.2\,\text{ms}$, P50 $110.9\,\text{ms}$, P95 $212.9\,\text{ms}$, Max $305.7\,\text{ms}$ on Windows 11 / Python 3.13.
3. **Tier 3 (Owner-Approved Phase 7 Client UI Acceptance Criteria)**: Approved client-side thresholds defined below.

### 7.2 Approved Phase 7 UI Acceptance Thresholds:

| Performance Metric | Approved Threshold | Measurement Method | Verification Environment | Acceptance Gate |
| :--- | :---: | :--- | :--- | :---: |
| **Initial Web App Cold Load** | **$\le 500\,\text{ms}$** | `performance.timing` / Navigation Timing API | Desktop Chrome / Firefox (Localhost) | `GATE-01`, `GATE-20` |
| **Fleet Dashboard Full Render** | **$\le 250\,\text{ms}$** | DOM Render Benchmark (10 turbine cards + KPI summary) | Desktop $1920\times1080$ | `GATE-03`, `GATE-20` |
| **Turbine Deep Dive Render** | **$\le 200\,\text{ms}$** | View transition to complete telemetry display | Desktop $1920\times1080$ | `GATE-04`, `GATE-20` |
| **Screen / Tab Switching** | **$\le 50\,\text{ms}$** | Client-side routing hash change to DOM display | Desktop $1920\times1080$ | `GATE-01`, `GATE-20` |
| **Chart.js Power Curve & Trends** | **$\le 150\,\text{ms}$** | Canvas drawing duration for 144 telemetry data points | Desktop $1920\times1080$ | `GATE-05`, `GATE-06` |
| **Cases Registry Table Render** | **$\le 100\,\text{ms}$** | DOM rendering of 50 paginated case rows | Desktop $1920\times1080$ | `GATE-13`, `GATE-20` |
| **On-Demand Diagnosis UI Response**| **$\le 1.5\,\text{s}$** | User click to complete diagnostic studio render | Localhost (Full 6-layer pipeline) | `GATE-10`, `GATE-20` |
| **Knowledge Assistant RAG Render** | **$\le 300\,\text{ms}$** | Query submission to citation cards DOM display | Localhost hybrid RAG | `GATE-14`, `GATE-20` |
| **HITL Decision State Transition** | **$\le 100\,\text{ms}$** | Modal submit to updated status badge & log render | Localhost atomic store | `GATE-12`, `GATE-20` |
| **Demo Stepper Step Transition** | **$\le 250\,\text{ms}$** | Stepper click to telemetry & diagnosis render | Localhost demo router | `GATE-16`, `GATE-20` |

---

## 8. Cross-Decision Consistency & Safety Verification

An end-to-end consistency audit was conducted to verify that all four resolved decisions harmonize seamlessly with the frozen Phase 1–6 baseline:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                         CROSS-DECISION CONSISTENCY AUDIT MATRIX                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Verification Check | Target Baseline | Consistency Verdict | Audit Findings & Rationale |
| :--- | :--- | :---: | :--- |
| **Phase 1–6 Code Freeze** | `backend/`, `data/`, `tests/` | **VERIFIED** | All 4 decisions operate 100% in the presentation layer. Zero backend code or tests modified. |
| **Phase 6 API Contracts** | 19 REST Endpoints | **VERIFIED** | All endpoints consumed strictly according to frozen schemas and parameter models. |
| **HITL Action Semantics** | `ACK`, `INV`, `ESC`, `DIS` | **VERIFIED** | `OD-P7-04` attaches operator identity to standard `OperatorDecisionRequest` without changing enums. |
| **RAG Provenance Rules** | `CitationItem` & Hash | **VERIFIED** | `OD-P7-06` renders exact source metadata and hashes; optional page numbers handled truthfully. |
| **Hypothesis Uncertainty** | Qualitative `Plausibility` | **VERIFIED** | `OD-P7-06` formats qualitative ratings (`HIGH`, `MOD`, `LOW`) without artificial percentages. |
| **No-Actuation Safety** | Permanent Prohibition | **VERIFIED** | Zero actuator controls in UI; work orders explicitly labeled as non-actuating draft artifacts. |
| **Offline Self-Containment**| Local Static Assets | **VERIFIED** | Zero external CDNs; zero cloud LLMs; zero remote dependencies. |
| **Immutable Case History** | Append-Only Store | **VERIFIED** | Zero case deletion endpoints exposed; audit trail displayed faithfully. |

---

## 9. Updated Phase 7 Governance Status

```
====================================================================================================
                        PHASE 7 GOVERNANCE READINESS AUDIT
====================================================================================================
Scope Review Documentation         : COMPLETE (docs/PHASE_7_SCOPE_REVIEW.md)
Technical Governance Reconciliation: COMPLETE (docs/PHASE_7_GOVERNANCE_RECONCILIATION.md)
Owner Decision Resolutions         : COMPLETE (docs/PHASE_7_OWNER_DECISION_RESOLUTION.md)
Total Owner Decisions Resolved     : 4 of 4 (100.0% Resolved)
Remaining Open Owner Decisions     : 0 (ZERO)
Remaining Specification Gaps       : 0 (ZERO)
Architecture Boundary Violations   : 0 (ZERO)
Safety & Non-Actuation Invariants  : VERIFIED & CONFIRMED
Phase 7 Implementation Status      : NOT AUTHORIZED (Awaiting Owner Implementation Order)
====================================================================================================
```

---

## 10. Remaining Open Decisions & Specification Gaps

**There are ZERO remaining open Owner Decisions and ZERO specification gaps.**

All architectural, operational, performance, safety, and integration dimensions of Phase 7 are fully specified, formally reconciled, and approved by the Project Owner.

---

## 11. Explicit Implementation Authorization Status

```
====================================================================================================
                      IMPLEMENTATION AUTHORIZATION ATTESTATION
====================================================================================================
Phase Evaluated                    : Phase 7 (Presentation & Operator Web Dashboard Layer)
Governance Gate                    : Phase 7 Owner Decision Resolution Gate
Implementation Authorization       : NOT AUTHORIZED BY THIS DOCUMENT
Current Status                     : READY FOR OWNER IMPLEMENTATION AUTHORIZATION
====================================================================================================
```

> [!CAUTION]
> **HARD STOP: DO NOT BEGIN IMPLEMENTATION.**
> While all governance prerequisites are complete and the phase is classified as `READY FOR OWNER IMPLEMENTATION AUTHORIZATION`, actual implementation (creating frontend files, writing UI code, installing dependencies, or running implementation test suites) requires a formal, separate **Phase 7 Implementation Authorization Order** from the Project Owner.

---

## 12. Final Classification

The Project Owner formally classifies Phase 7 as:

### **READY FOR OWNER IMPLEMENTATION AUTHORIZATION**

---

## 13. Document Control & Signatures

```
====================================================================================================
                                DOCUMENT CONTROL ATTESTATION
====================================================================================================
Document Title                     : docs/PHASE_7_OWNER_DECISION_RESOLUTION.md
Active Governance Phase            : Phase 7 (Presentation & Operator Web Dashboard Layer)
Review Date                        : 2026-09-20
Attesting Authority                : Project Owner & Lead System Architect
Classification Decision           : READY FOR OWNER IMPLEMENTATION AUTHORIZATION
Next Step                          : Issue Formal Project Owner Phase 7 Implementation Authorization
====================================================================================================
```
