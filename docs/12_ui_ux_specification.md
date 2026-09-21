---
document: 12_ui_ux_specification
version: 0.2
status: REVIEW
last_updated: 2026-09-20
author: WindGuard AI UX & Product Design Team
depends_on:
  - docs/06_prd.md
  - docs/07_srs.md
  - docs/08_system_architecture.md
  - docs/09_technical_design.md
  - docs/10_data_architecture.md
---

# 12. UI/UX Specification — WindGuard AI

## 1. UX Goals & Principles

The user interface of **WindGuard AI** is engineered for high-stakes, data-dense wind farm control room environments and executive operations review. The UX is guided by four primary principles:

1. **Zero Cognitive Clutter**: Present aggregated fleet health at a glance; surface complex multi-signal residuals only when investigating a specific anomaly.
2. **Context-Rich Visual Diagnostics**: Integrate live operational points directly onto theoretical power curves and thermal baseline charts with explicit `is_curtailed` indicator badges.
3. **Transparent Decision Auditability & Tariff Provenance**: Make AI evidence, RAG citations, tariff provenance, and human operator actions visible on a single unified case inspection screen.
4. **Accessible & High Contrast**: Clean modern dark/light industrial theme adhering to WCAG 2.1 AA contrast requirements with responsive layout support.

---

## 2. Information Architecture & Navigation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WINDGUARD AI INFORMATION ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────────────────────┘

  TOP NAVIGATION BAR
  ├── Brand Logo & System Status (Engine Active | Mode: Online / Offline Fallback)
  ├── Fleet Summary Badges (10 Turbines | 1 Active Case | ₹8,448 Est. Loss)
  └── Navigation Tabs:
      ├── [1] Fleet Overview & Cases (Summary, KPI cards, Cases Table via GET /api/cases)
      ├── [2] Turbine Deep Dive (Power Curves, Thermal Baselines, is_curtailed status)
      ├── [3] AI Diagnostic Studio (Evidence Table, RAG Citations, Tariff Provenance, HITL)
      ├── [4] Knowledge Assistant (Conversational RAG over OEM manuals & Alarm SOPs)
      ├── [5] Tariff & Settings (View / Edit Active Tariff Rate & Provenance Mode)
      └── [6] 10-Stage Guided Demo (Reproducible walk-through of benchmark scenarios)
```

---

## 3. Screen Inventory & Layout Specifications

### Screen 1: Fleet Health Overview & Cases
- **Purpose**: Real-time fleet-wide health monitoring, priority anomaly triage, and production loss tracking.
- **Key Visual Elements**:
  - **KPI Metric Cards**: Total Turbines (10), Healthy (8), Attention Required (1), Curtailed (1), Fleet Capacity Utilization ($84.2\%$), Daily Production Loss ($2,640\,\text{kWh}$ / ₹$8,448$).
  - **Fleet Turbine Grid**: 10 interactive turbine cards displaying ID, current wind speed, active power, status badge (`NORMAL`, `CURTAILED`, `HIGH_ANOMALY`), and quick-action "Investigate" button.
  - **Active Maintenance Cases Table**: Integrated case log fetched via `GET /api/cases`, with filtering by Turbine, Severity, and Status (*OPEN*, *ACKNOWLEDGED*, *INVESTIGATING*, *ESCALATED*, *DISMISSED*).
  - **Active Anomaly Alert Banner**: Prominently highlights the highest-priority active case with severity badge, time elapsed, and estimated revenue impact.

### Screen 2: Turbine Deep-Dive Studio
- **Purpose**: Detailed engineering analysis of a selected turbine's live telemetry, power curve, and thermal residuals.
- **Key Visual Elements**:
  - **Turbine Selector & Status Card**: Turbine ID (`WTG-07`), Model, Rated Capacity ($2.0\,\text{MW}$), Hub Height ($90\,\text{m}$), Curtailment Status (`is_curtailed: false`).
  - **Interactive Power Curve Chart (Chart.js)**: Plots $P_{\text{actual}}$ vs. $v_{\text{wind}}$ with overlay of theoretical OEM curve, empirical ML expected curve, and live operational point with highlighted residual $\Delta P$.
  - **Multi-Sensor Time-Series Charts**: Synchronized timeline of Wind Speed, Active Power, Gearbox Bearing Temp, and Generator Stator Temp.
  - **Residual Breakdown Gauge / Bar**: Displays exact numerical deviations ($\Delta P = -220\,\text{kW}$, $\Delta T_{\text{GB}} = +16.3^\circ\text{C}$, $z_{\text{GB}} = +3.2\sigma$).

### Screen 3: AI Diagnostic & Case Studio (HITL Center)
- **Purpose**: Structured root-cause investigation, RAG evidence review, financial loss audit, and human operator decision logging.
- **Layout Structure**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CASE ID: CASE-20260920-001 | WTG-07 | SEVERITY: HIGH | PRIORITY: 88/100    │
├─────────────────────────────────────────────────────────────────────────────┤
│  [1. EVENT SUMMARY & CONTEXT ASSESSMENT]                                    │
│  Power derating (-13.4%) with severe gearbox bearing overheating (+16.3°C)  │
│  under healthy wind (8.5 m/s). Grid curtailment: INACTIVE.                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  [2. EVIDENCE TABLE]                                                        │
│  Parameter            Observed    Expected    Deviation        Status       │
│  Active Power         1420 kW     1640 kW     -220 kW (-2.4σ)  ANOMALOUS    │
│  Gearbox Bearing Temp 78.4°C      62.1°C      +16.3°C (+3.2σ)  CRITICAL     │
│  Ambient Temp         32.1°C      32.1°C      0.0°C            NORMAL       │
├─────────────────────────────────────────────────────────────────────────────┤
│  [3. FINANCIAL & ENERGY LOSS ESTIMATE]                                      │
│  • Energy Loss: 2,640.0 kWh (over 12.0 hrs)                                  │
│  • Financial Loss: ₹8,448.00 INR                                            │
│  • Tariff Applied: ₹3.20/kWh [CONFIGURED BASELINE ASSUMPTION]               │
│  • Source: CERC Benchmark & Industry Baseline Configuration                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  [4. DIFFERENTIAL DIAGNOSTIC HYPOTHESES]                                    │
│  • Hypothesis A (82%): High-speed shaft bearing lubrication starvation      │
│  • Hypothesis B (18%): Early inner raceway fatigue spalling                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  [5. RETRIEVED TECHNICAL DOCUMENTATION (RAG CITATIONS)]                     │
│  📖 OEM 2.X MW Maintenance Manual — Sec 4.2 High-Speed Shaft Bearings (P.114)│
│  📖 SCADA Alarm Code Matrix — AL-104 Gearbox Bearing High Temp (P.18)       │
├─────────────────────────────────────────────────────────────────────────────┤
│  [6. RECOMMENDED TECHNICIAN CHECKLIST]                                      │
│  [ ] 1. Extract 100ml lubrication sample for ferrographic particle check.   │
│  [ ] 2. Measure high-speed shaft axial play using dial indicator.           │
│  [ ] 3. Check oil filter differential pressure indicator.                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  [7. HUMAN OPERATOR DECISION ACTIONS]                                       │
│  [ ACKNOWLEDGE ]   [ INVESTIGATE ]   [ ESCALATE WORK ORDER ]   [ DISMISS ]  │
│  Operator Notes: [ Dispatched site mechanical crew for bearing inspection ] │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 4: Technical Knowledge Assistant (RAG Q&A)
- **Purpose**: Conversational technical interface allowing operators to query wind turbine manuals and alarm codes.
- **Key Visual Elements**:
  - Interactive search bar with suggested quick queries (e.g., *"What tools are required for AL-104?"*, *"How does high ambient summer temperature affect gearbox cooling?"*).
  - Conversational message thread rendering formatted answers with clickable, highlighted document source badges.

### Screen 5: Tariff & Financial Settings
- **Purpose**: View, verify, and update the active tariff rate and provenance mode.
- **Key Visual Elements**:
  - Active Tariff Card: Displays Current Rate (₹3.20/kWh), Mode, Effective Date, and Source Citation.
  - Rate Configurator Form: Allows updating rate, selecting mode (*PROJECT_PPA*, *REGULATORY_BENCHMARK*, *CONFIGURED_BASELINE*, *SCENARIO_OVERRIDE*), and documenting source reference notes.

### Screen 6: 10-Stage Interactive Demo Walkthrough
- **Purpose**: Guided educational and assessment walkthrough demonstrating the 10 stages of the benchmark scenario.
- **Key Visual Elements**:
  - Top Stepper Progress Bar (Stages 1 to 10 with clickable active step pills).
  - Split-screen layout: Left pane displays the real-time telemetry and power curve; Right pane displays the AI diagnostic evolution and operator action.

---

## 4. UI States & Design System

### 4.1 System & Component States
- **Loading State**: Displays skeleton shimmer animations on metric cards and charts while fetching telemetry or running inference.
- **Empty State**: Clear placeholder messages when no open cases exist (*"All turbines operating within normal thermal and power envelopes"*).
- **Sensor Dropout Warning**: Amber warning banner rendered when a sensor violates physical plausibility limits.
- **Offline / Local Mode Badge**: Top badge indicator showing *"Local Deterministic Synthesis Active (Offline Mode)"* if external cloud endpoints are disconnected.

### 4.2 Theme & Styling Tokens
- **Color Palette (Industrial Clean Energy)**:
  - Background: Slate Dark (`#0f172a` / `#1e293b`) or Clean Light (`#f8fafc`).
  - Primary Accent (Clean Energy Cyan): `#06b6d4` / `#0891b2`.
  - Secondary Accent (Wind Blue): `#3b82f6` / `#2563eb`.
  - Severity Warning (Amber): `#f59e0b`.
  - Severity High / Critical (Rose/Red): `#ef4444`.
  - Normal / Healthy (Emerald Green): `#10b981`.
- **Typography**: Inter / System Sans-Serif font stack with monospace formatting for sensor values and code snippets.
- **Iconography**: Lucide SVG Icons (`Wind`, `Activity`, `AlertTriangle`, `BookOpen`, `CheckCircle`, `ShieldCheck`, `DollarSign`).
