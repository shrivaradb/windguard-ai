---
document: PRESENTATION_DECK_18_SLIDES
version: 1.0
status: PUBLISHED & VERIFIED
date: 2026-09-21
author: WindGuard AI Architecture & Presentation Group
governance: Master 18-Slide Capstone Technical Defense Deck Specification (Phase 9)
depends_on:
  - docs/00_documentation_index.md
  - docs/MASTER_TECHNICAL_REPORT.md
  - docs/MODEL_CARDS.md
  - docs/RAG_KNOWLEDGE_CATALOG.md
  - docs/RESPONSIBLE_AI_AND_SDG.md
  - docs/EVALUATION_REPORT.md
---

# WindGuard AI: Master 18-Slide Capstone Presentation Deck
## Technical Viva Defense & Industrial Demonstration Specification

```
====================================================================================================
                        MASTER 18-SLIDE TECHNICAL DEFENSE SPECIFICATION
====================================================================================================
Project Name                       : WindGuard AI
Presentation Title                 : Explainable Wind Turbine Predictive Health & Decision Support
Target Presentation Duration       : 20 Minutes (plus 10 Minutes Oral Viva Q&A)
Total Slide Count                  : Exactly 18 Technical Slides
Academic Literature Reference      : Bhagwatikar & Bhagwatikar (2026)
Architecture Coverage              : Full 6-Layer Hybrid Architecture & Empirical Verification
Safety Protocol                    : Non-Actuating Human-in-the-Loop Governance
====================================================================================================
```

---

## Slide 1: Title & Capstone Project Overview

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        WINDGUARD AI                                              │
│         Explainable Wind Turbine Predictive Health, Anomaly Attribution & Revenue Assurance     │
│                                                                                                  │
│   [ 6-Layer Hybrid Architecture ]      [ Physics-Informed ML ]      [ Deterministic Local RAG ]  │
│                                                                                                  │
│   Candidate: Lead Engineering Group                   Academic Year: 2026                        │
│   Department of Computer Science & Renewable Energy   Institution: Capstone Board Examination   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Core Focus**: Bridging the critical gap between stochastic wind turbine SCADA telemetry, physical drivetrain mechanics, and actionable financial decision support.
* **Academic Lineage**: Built upon the foundational research framework of **Bhagwatikar & Bhagwatikar (2026)**.
* **Key Innovation**: Integrating physical ODE simulation, machine learning baselines ($R^2=1.0$), context-aware false alarm suppression ($100\%$), local hybrid RAG (MRR = 1.0), and numerical guardrails into a sub-200ms decision-support tool.

### Speaker Notes (Timing: 1.0 min)
> *"Distinguished members of the examination committee, welcome to the presentation of WindGuard AI. WindGuard AI is an explainable, physics-informed condition monitoring and revenue assurance platform designed to eliminate the massive false alarm rates and financial blind spots that plague modern utility-scale wind energy operations. Over the next 20 minutes, I will walk you through the theoretical foundations, the 6-layer architecture, our empirical benchmark results, and our strict Responsible AI safety covenants."*

---

## Slide 2: Problem Statement & Industrial Wind O&M Crisis

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             THE UTILITY-SCALE WIND O&M CRISIS                                    │
│                                                                                                  │
│   [ 20%–30% of LCOE ]            [ >85% False Alarm Rate ]        [ Financial Blindness ]        │
│   Drivetrain O&M dominates       Conventional SCADA limits        SCADA alerts ignore tariffs    │
│   lifetime operating costs.      trigger severe alarm fatigue.    and unscheduled losses.        │
│                                                                                                  │
│   Catastrophic Bearing Failure: $150k–$350k replacement + 6–8 weeks complete field downtime.    │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **O&M Cost Burden**: Operating expenditures account for nearly a third of wind energy LCOE.
* **The SCADA Threshold Trap**: Static high/low alarms cannot account for environmental transients (summer heatwaves $>38^\circ\text{C}$ or aerodynamic turbulence), generating over 85% false alarms.
* **The High-Cost Consequence**: Operators experience alarm fatigue, causing incipient micro-pitting in high-speed gearbox bearings to go unnoticed until catastrophic shaft seizure occurs.

### Speaker Notes (Timing: 1.0 min)
> *"The fundamental problem in utility-scale wind energy today is not a lack of data, but a lack of actionable, context-aware intelligence. SCADA systems produce millions of data points, yet operators are inundated with false alarms caused by benign ambient temperature spikes or grid curtailment orders. When real mechanical degradation begins in high-speed bearings or generator stators, it is easily lost in the noise, leading to catastrophic component failures that cost hundreds of thousands of dollars and weeks of lost generation."*

---

## Slide 3: Motivation & UN SDG 7 Clean Energy Assurance

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 MOTIVATION & UN SDG 7 ALIGNMENT                                  │
│                                                                                                  │
│   [ UN SDG 7: Target 7.2 ]                [ UN SDG 7: Target 7.a ]                               │
│   Accelerate Renewable Share              Advance Clean Energy Tech & LCOE Parity                │
│   • 15%–22% Unplanned O&M Reduction       • Real-time Indian Corridor Tariff Modeling            │
│   • Multi-week Catastrophic Lead Time     • PPA, ToD, FiT, and APPC Optimization                 │
│                                                                                                  │
│   Impact: Transforming passive telemetry into proactive financial revenue protection.            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **SDG 7 Alignment**: Directly advances Target 7.2 (expanding renewable generation) and Target 7.a (clean energy economic efficiency).
* **Financial Grounding**: Translates abstract engineering residuals into real-world monetary impact across 4 Indian tariff structures (PPA Flat, Time-of-Day, Feed-in Tariff, APPC).
* **Grid Resilience**: Improves asset availability and predictability for national transmission system operators.

### Speaker Notes (Timing: 1.0 min)
> *"Our core motivation is aligned with United Nations Sustainable Development Goal 7: Affordable and Clean Energy. To make wind energy truly competitive with fossil baseload, we must drive down O&M costs. WindGuard AI transforms raw sensor readings into explicit financial terms—calculating the exact prospective revenue loss per hour under specific state power purchase agreements—enabling asset owners to prioritize urgent mechanical repairs over cosmetic issues."*

---

## Slide 4: Literature Landscape & The 5 Intelligence Generations

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                   5 GENERATIONS OF WIND TURBINE INTELLIGENCE (Bhagwatikar 2026)                  │
│                                                                                                  │
│   Gen 1: Static Thresholds      ──> High False Alarms (>85% FAR)                                 │
│   Gen 2: Statistical SCADA      ──> Moving averages; misses nonlinear aerodynamics               │
│   Gen 3: Black-Box ML/Deep Nets ──> Uninterpretable; severe hallucination & trust deficit        │
│   Gen 4: Physics-Informed ML    ──> Good residuals; lacks operational context & financial link   │
│   Gen 5: WindGuard AI Hybrid    ──> Context-Aware + Physics Baselines + Guardrailed RAG + HITL   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Theoretical Framework**: Formally grounded in **Bhagwatikar & Bhagwatikar (2026)**.
* **Evolutionary Transition**: Traces the transition from primitive thresholding through black-box neural networks to explainable hybrid decision support.
* **Passive Digital Shadow**: Establishes a passive digital shadow that accurately models expected physical states without introducing unsafe closed-loop actuators.

### Speaker Notes (Timing: 1.0 min)
> *"In their 2026 survey, Bhagwatikar and Bhagwatikar categorized wind turbine condition monitoring into five evolutionary generations. While Generation 3 introduced deep neural networks, it created a severe trust deficit due to black-box uninterpretability. WindGuard AI realizes Generation 5: an explainable, physics-informed hybrid architecture that combines mathematical baselines with operational context filtering and guardrailed technical retrieval."*

---

## Slide 5: Research & Operational Gap Analysis (8 Key Gaps)

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    8 CORE RESEARCH & FIELD GAPS                                  │
│                                                                                                  │
│   [GAP-01] Curtailment Confounding         [GAP-05] Cloud LLM Hallucination Risk                 │
│   [GAP-02] Summer Heatwave Thermal Drift   [GAP-06] Unbounded Latency & SLA Violations           │
│   [GAP-03] Financial & Tariff Blindness    [GAP-07] Autonomous Actuation Vulnerabilities         │
│   [GAP-04] Diagnostic Actionability Void   [GAP-08] Regulatory Auditability Deficit              │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Identification of 8 Core Gaps**: Dissecting why existing commercial and academic tools fail in practical wind farm control rooms.
* **The False Curtailment Dilemma**: Grid-ordered curtailment causes power drop that naive models misdiagnose as mechanical pitch/blade failure.
* **The Thermal Drift Trap**: Normal ambient summer heatwaves cause bearing temperatures to exceed static limits without mechanical fault.

### Speaker Notes (Timing: 1.0 min)
> *"Our research identified eight critical gaps across existing systems. For instance, Gap 1: when the grid operator orders a curtailment, power drops while wind remains high; naive models immediately flag a major aerodynamic failure. Gap 2: during summer heatwaves, ambient temperatures exceed 40°C, causing generator bearings to run hot even though the cooling system is fully functional. WindGuard AI was designed specifically to solve all eight gaps."*

---

## Slide 6: Proposed Solution — WindGuard AI Hybrid Framework

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE WINDGUARD AI HYBRID SOLUTION                                 │
│                                                                                                  │
│   ┌───────────────────────────┐    ┌───────────────────────────┐    ┌─────────────────────────┐  │
│   │   PHYSICS-INFORMED ML     │    │    OPERATIONAL CONTEXT    │    │    LOCAL HYBRID RAG     │  │
│   │   GBR Expected Power      │───>│    5-Level Precedence     │───>│    7 Docs / 29 Chunks   │  │
│   │   RF Expected Thermal     │    │    100% Curtailment Fil.  │    │    TF-IDF + BM25 Fusion │  │
│   └───────────────────────────┘    └───────────────────────────┘    └─────────────────────────┘  │
│                                                                                                  │
│   Outcome: 100% Deterministic, Auditable, Sub-Second Maintenance Advisories with Zero Hallucination│
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Triple-Layer Synergy**: Seamless integration of regression physics, operational context logic, and offline retrieval.
* **Deterministic Mode A**: Replaces unpredictable cloud LLM generation with algorithmic template synthesis, ensuring 100% numerical fidelity.
* **Sub-Second Response**: Full diagnostic cycle executes in under $200\,\text{ms}$, far exceeding the $2500\,\text{ms}$ SLA requirement.

### Speaker Notes (Timing: 1.0 min)
> *"Our proposed solution brings together three core pillars: first, physics-informed regressors that compute expected aerodynamic and thermal baselines; second, an operational context engine that filters out non-fault transients like curtailment and heatwaves; and third, a local, deterministic RAG subsystem that retrieves verified engineering SOPs without touching the cloud. The result is a sub-second, fully auditable advisory platform."*

---

## Slide 7: Canonical 6-Layer Modular Architecture Overview

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  CANONICAL 6-LAYER ARCHITECTURE                                  │
│                                                                                                  │
│   [ Layer 1 ] Ingestion & ODE Simulation  ──> 10-min SCADA, 1st-Order ODEs, Scenarios S1–S5      │
│   [ Layer 2 ] Physics-Informed ML         ──> Expected Power GBR (R²=1.0), Thermal RF Baselines  │
│   [ Layer 3 ] Context & Loss Engine       ──> Curtailment Filter, 4-Tier Tariff Loss Hierarchy   │
│   [ Layer 4 ] Technical Local RAG         ──> Hybrid TF-IDF + BM25, 7 Docs / 29 Chunks (MRR=1.0) │
│   [ Layer 5 ] Advisory & Guardrails       ──> Deterministic Mode A, 100% Numerical Fidelity      │
│   [ Layer 6 ] API Backend & Operator UI   ──> 19 FastAPI Routes, Atomic File Store, 10-Stage UI  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Modular Decoupling**: Strict separation of concerns across 6 layers, allowing independent verification and zero circular dependencies.
* **Layer Immutability**: All six layers are fully implemented, verified, and sealed across Phases 1 through 8.
* **Complete Test Coverage**: Validated by 273+ automated regression tests and a dedicated empirical evaluation suite.

### Speaker Notes (Timing: 1.0 min)
> *"Here we see the canonical 6-layer architecture of WindGuard AI. Telemetry flows upward from Layer 1 through physical feature extraction in Layer 2, operational context filtering in Layer 3, technical knowledge retrieval in Layer 4, and guardrailed advisory synthesis in Layer 5, finally terminating at Layer 6 in our FastAPI REST backend and operator studio. Each layer is strictly decoupled and governed by formal acceptance gates."*

---

## Slide 8: Layer 1 — High-Fidelity SCADA Ingestion & ODE Physical Simulation

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 1: SCADA INGESTION & ODE PHYSICAL SIMULATION                         │
│                                                                                                  │
│   SCADA Ingestion: 10-minute average intervals conforming to IEC 61400-25 schema (12 channels).  │
│                                                                                                  │
│   Thermal ODE Formulation:                                                                       │
│   dT_comp/dt = (1/tau) * [ (T_amb + deltaT_max * (P / P_rated)^2) - T_comp(t) ]                  │
│   (tau_gearbox = 60 min, tau_generator = 45 min, deltaT_max = 25°C / 35°C)                      │
│                                                                                                  │
│   Benchmark Scenarios: S1 (Normal), S2 (Gearbox), S3 (Generator), S4 (Curtailment), S5 (Sensor)  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **IEC 61400-25 Compliance**: Canonical 12-channel telemetry schema including power, wind speed, pitch, shaft speeds, component temperatures, and curtailment flag.
* **First-Order Thermal ODE**: Models physical thermal inertia with realistic component time constants ($\tau_{\text{gb}} = 60\,\text{min}, \tau_{\text{gen}} = 45\,\text{min}$).
* **Deterministic Benchmarks**: Standardized 24-hour (144-step) datasets S1 through S5 for reproducible cross-validation.

### Speaker Notes (Timing: 1.0 min)
> *"Layer 1 handles telemetry ingestion and physical ODE simulation. Following the IEC 61400-25 standard, we ingest 10-minute averaged records. To validate our models under known ground truth, we implemented a first-order thermal differential equation that models the thermal inertia of multi-ton gearboxes and generators. We synthesized five canonical 24-hour benchmark scenarios covering normal operation, gearbox overheating, generator cooling failure, grid curtailment, and sensor dropouts."*

---

## Slide 9: Layer 2 — Physics-Informed ML Baselines & Residual Analytics

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 2: PHYSICS-INFORMED ML & RESIDUAL ANALYTICS                          │
│                                                                                                  │
│   [ Expected Power GBR ]                  [ Expected Thermal RF ]                                │
│   • R² = 1.0000, RMSE = 1.31 kW           • Multi-output Random Forest (100 trees)               │
│   • Latency: 0.26 ms                      • Holdout RMSE: 4.92°C (GB) / 6.06°C (Gen)             │
│   • Input: Wind speed, Pitch, Air density • Transparent Thermal Lag Limitation (OD-P8-05)        │
│                                                                                                  │
│   Residual Tracking: Standardized z = (Residual - mu) / sigma. Canonical 2.5-sigma Persistence. │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Aerodynamic GBR Precision**: Near-perfect power curve fit ($R^2=1.0000, \text{RMSE}=1.31\,\text{kW}$) executing in $0.26\,\text{ms}$.
* **Multi-Output Thermal RF**: Simultaneously predicts gearbox sump oil and generator bearing temperatures.
* **Transparent Limitation Framing**: Formally documents the $4.92^\circ\text{C} / 6.06^\circ\text{C}$ RMSE resulting from static 10-minute snapshot features under dynamic thermal inertia ($\tau \approx 60\,\text{min}$).
* **2.5σ Persistence Filter**: Requires $|z| \ge 2.5$ across $5/6$ consecutive timesteps ($60\,\text{min}$) to suppress transient noise.

### Speaker Notes (Timing: 1.0 min)
> *"In Layer 2, we train machine learning regressors on healthy baseline operations. Our Gradient Boosting power model achieves an R-squared of 1.0 with an RMSE of only 1.31 kW. For thermal modeling, our Random Forest captures steady-state temperatures. As transparently documented in Model Cards, predicting dynamic temperatures from static 10-minute snapshots without autoregression incurs a known thermal lag of 4.92°C to 6.06°C. We mitigate this downstream using a 60-minute rolling persistence filter."*

---

## Slide 10: Layer 3 — Operational Context Precedence & Financial Tariff Loss Engine

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 3: OPERATIONAL CONTEXT & TARIFF LOSS ENGINE                          │
│                                                                                                  │
│   5-Level Context Precedence Hierarchy:                                                          │
│   Level 1: Sensor Plausibility ──> Level 2: Grid Curtailment (is_curtailed == 1) ──>             │
│   Level 3: Low Wind Idling     ──> Level 4: Heatwave Derating (Tamb > 38°C)     ──>              │
│   Level 5: Normal Mechanical Attribution & Fault Scoring                                         │
│                                                                                                  │
│   100% Curtailment Suppression (540/540)  │  4-Tier Tariff Hierarchy (PPA, ToD, FiT, APPC)       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Deterministic Precedence**: Strict hierarchical filtering ensures grid curtailments and ambient heatwaves are evaluated before mechanical fault attribution.
* **100% Curtailment Suppression**: Exactly $540/540$ test timesteps in Scenario S4 correctly suppressed from false alarm generation.
* **5-Factor Priority Formula**: Combines anomaly severity ($35\%$), monetary loss ($25\%$), component criticality ($20\%$), model confidence ($10\%$), and persistence ($10\%$).

### Speaker Notes (Timing: 1.0 min)
> *"Layer 3 is the intelligence filter of WindGuard AI. It enforces a strict 5-level precedence hierarchy: before flagging any mechanical fault, it verifies sensor plausibility, checks for grid curtailment commands, confirms wind is above cut-in, and compensates for high ambient heatwaves. In benchmark testing, it achieved 100% false alarm suppression during curtailment events. It then calculates real-time revenue loss across four Indian tariff structures and generates a normalized 0-to-100 priority score."*

---

## Slide 11: Layer 4 — Technical Knowledge Base & Local Hybrid RAG Subsystem

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 4: TECHNICAL LOCAL HYBRID RAG SUBSYSTEM                              │
│                                                                                                  │
│   Corpus Inventory: Exactly 7 Governed Technical Documents / 29 Indexed Chunks                   │
│   Provenance Integrity: 29/29 Cryptographically SHA-256 Hashed (0 Unverified Chunks)             │
│                                                                                                  │
│   Score_hybrid(q, d) = 0.5 * BM25_score(q, d) + 0.5 * TF-IDF_cosine(q, d)                       │
│                                                                                                  │
│   Mean Reciprocal Rank (MRR): 1.0000 (15/15)  │  Operational Recall@3: 96.67% (29/30)            │
│   Retrieval Latency: 1.14 ms (Target < 50 ms) │  Zero Cloud / 100% Offline Local Execution       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Governed 7-Document Corpus**: Covers gearbox SOPs, generator diagnostics, pitch calibration, Indian corridor O&M, and IEC 61400-25 standards.
* **Deterministic Hybrid Fusion**: Fuses exact lexical BM25 matching with global TF-IDF cosine similarity ($\alpha=0.5$).
* **Empirical Retrieval Power**: MRR $= 1.0000$, Recall@3 $= 96.67\%$, executing in just $1.14\,\text{ms}$ with zero network connectivity.

### Speaker Notes (Timing: 1.0 min)
> *"Layer 4 bridges anomaly detection and operational actionability through our local RAG subsystem. We index exactly seven governed technical documents split into 29 cryptographically hashed chunks. Using a deterministic hybrid fusion of Okapi BM25 and TF-IDF cosine similarity, our retriever achieves a perfect Mean Reciprocal Rank of 1.0 and 96.67% Recall@3 in just 1.14 milliseconds, completely offline in local memory."*

---

## Slide 12: Layer 5 — Constrained Advisory Synthesis & Numerical Guardrails

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                   LAYER 5: CONSTRAINED ADVISORY SYNTHESIS & GUARDRAILS                           │
│                                                                                                  │
│   Deterministic Mode A Template Engine:                                                          │
│   • Ingests verified telemetry, residuals, priority score, and RAG chunk references.             │
│   • Formats structured Pydantic JSON advisory output in sub-millisecond time.                    │
│                                                                                                  │
│   Numerical & Safety Guardrails:                                                                 │
│   • Exact mathematical cross-validation (|Text Loss - Calc Loss| < 0.01 INR).                   │
│   • Mandatory non-actuating safety disclaimer validation.                                        │
│   • 100.0% Numerical Fidelity (60/60) │ 100.0% Negative Catch (5/5)                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Zero-Hallucination Architecture**: Deterministic Mode A replaces unconstrained generative text with strict Pydantic JSON schemas.
* **Mathematical Guardrails**: Intercepts every output to verify that reported financial losses and residual figures match analytical computations down to $0.01\,\text{INR}$.
* **Negative Catch Testing**: Successfully caught and rejected $100\%$ ($5/5$) of synthetic malformed, ungrounded, or non-disclaimed candidate outputs.

### Speaker Notes (Timing: 1.0 min)
> *"Layer 5 generates the final advisory output. To eliminate the hallucination risks inherent in cloud LLMs, we utilize Deterministic Mode A synthesis. Our post-synthesis validation guardrails verify that every number stated in the advisory matches the underlying mathematical calculations to within one paisa, while enforcing our mandatory non-actuation disclaimer. In formal evaluation, it achieved 100% numerical fidelity across all 60 test cases."*

---

## Slide 13: Layer 6 — FastAPI REST Backend & Concurrency Storage Architecture

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 6: FASTAPI REST BACKEND & ATOMIC STORAGE                             │
│                                                                                                  │
│   Production REST API: Exactly 19 Endpoint Operations across 18 Unique Paths                     │
│   (System, Fleet, SCADA Ingest/Simulate, Models, Diagnostic Studio, Cases, Tariffs, RAG, Demo)  │
│                                                                                                  │
│   Retraining Lockout: POST /api/models/train is ABSENT and disabled (GOV-TRAIN-01).              │
│   SCADA Actuation Routes: Exactly 0 Control / Actuation Endpoints.                               │
│   Storage Architecture: Atomic file locking (portalocker) for cases.json & audit_log.jsonl.      │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **19 REST Operations**: Clean, RESTful FastAPI interface with complete OpenAPI/Swagger documentation.
* **Retraining Lockout (`GOV-TRAIN-01`)**: `/api/models/train` is permanently disabled in production to prevent model poisoning.
* **Thread-Safe Storage**: Atomic write-rename patterns and advisory file locking (`portalocker`) guarantee zero file corruption under concurrent case updates.

### Speaker Notes (Timing: 1.0 min)
> *"Layer 6 provides our application backend and persistence tier. The production API exposes exactly 19 endpoint operations across 18 paths. In strict accordance with governance rule GOV-TRAIN-01, model retraining routes are absent, and actuation routes are permanently zero. Concurrency is handled using cross-platform atomic file locking with portalocker, ensuring complete data integrity for active cases and append-only audit logs."*

---

## Slide 14: Operator Web Dashboard & 10-Stage Interactive Studio

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       OPERATOR WEB DASHBOARD & 10-STAGE STUDIO                                   │
│                                                                                                  │
│   [ Fleet Overview Cards ] ──> Live health status & priority rankings for WTG-001 to WTG-010     │
│   [ Power Curve Visualizer ] ──> Real-time SCADA scatter points vs GBR Expected Power curve      │
│   [ AI Diagnostic Studio ] ──> Component residuals, thermal time-series & retrieved RAG SOPs     │
│   [ Tariff Registry Editor ] ──> Interactive switching between PPA Flat, ToD, FiT, and APPC      │
│   [ Printable Work Orders ] ──> Client-side @media print layout requiring engineer sign-off      │
│   [ 10-Stage Demo Stepper ] ──> Sequential end-to-end operational walkthrough for examiners     │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Responsive Control Room UI**: Pure Vanilla JS and Tailwind CSS for rapid rendering without heavy framework overhead.
* **Interactive 10-Stage Stepper**: Built-in examiner demo stepping through clean baseline, thermal faults, curtailments, heatwaves, dropouts, cascading failures, tariff calculations, and human work orders.
* **Printable Field Work Orders**: Generates formatted maintenance draft tickets ready for human engineering review and physical site dispatch.

### Speaker Notes (Timing: 1.0 min)
> *"Here we see our operator web dashboard. It features a live 10-turbine fleet overview, an interactive power curve visualizer comparing real-time SCADA points to the GBR baseline, an AI diagnostic studio, and an interactive tariff editor. Crucially, we built a 10-stage demo stepper into the interface, allowing examiners to walk through every operational scenario from normal operation to complex cascading faults with a single click."*

---

## Slide 15: Empirical Benchmark Evaluation & SLA Latency Results

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               MASTER EMPIRICAL BENCHMARK MATRIX                                  │
│                                                                                                  │
│   Metric Dimension             Target Threshold       Empirical Measured Result       Status     │
│   Power Curve Fit (R²)         >= 0.95                1.0000                          PASS       │
│   Power Curve RMSE             <= 45.0 kW             1.31 kW                         PASS       │
│   Curtailment Suppression      >= 90.0%               100.0% (540/540)                PASS       │
│   False Alarm Rate (FAR)       <= 5.0%                3.64%                           PASS       │
│   RAG Mean Reciprocal Rank     >= 0.80                1.0000 (15/15)                  PASS       │
│   Advisory Numerical Fidelity  = 100.0%               100.0% (60/60)                  PASS       │
│   Full Pipeline SLA Latency    <= 2500.0 ms           185.57 ms                       PASS       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Exceeding All SLA Targets**: End-to-end pipeline executes in $185.57\,\text{ms}$, over $13\times$ faster than the $2500\,\text{ms}$ ceiling.
* **Low False Alarm Rate**: Achieved a False Alarm Rate of just $3.64\%$, drastically lower than legacy SCADA thresholds ($>85\%$).
* **Full Multi-Layer Verification**: Verified across automated regression tests (273+ passing) and the comprehensive benchmark runner.

### Speaker Notes (Timing: 1.0 min)
> *"This table summarizes our empirical evaluation results. Every primary performance target has been met or exceeded. Our end-to-end diagnostic pipeline responds in 185.57 milliseconds against a 2500 millisecond ceiling. We achieved a False Alarm Rate of only 3.64%, 100% curtailment suppression, perfect RAG Mean Reciprocal Rank of 1.0, and 100% numerical fidelity across all synthesized advisories."*

---

## Slide 16: Safety Boundaries, Non-Actuation Protocol & Responsible AI

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               SAFETY & RESPONSIBLE AI COVENANT                                   │
│                                                                                                  │
│   [ Zero SCADA Actuation ]      [ Mandatory HITL ]            [ 100% Local Privacy ]             │
│   0 control/trip routes.        All case decisions require    Zero SCADA data or prompts         │
│   Cannot alter turbine states.  human engineer sign-off.      transmitted to cloud vendors.      │
│                                                                                                  │
│   4 Operator Decisions: ACKNOWLEDGE │ INVESTIGATE │ ESCALATE │ DISMISS                           │
│   Immutable Audit Trail: Every operator action recorded in append-only audit_log.jsonl.          │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Permanent Non-Actuation Guarantee**: Zero turbine start, stop, pitch, yaw, or breaker commands exist in the codebase.
* **Human-in-the-Loop Governance**: The system strictly advises; certified human engineers must authorize work orders.
* **Immutable Audit Trail**: Append-only logging (`audit_log.jsonl`) guarantees complete regulatory compliance and traceability.

### Speaker Notes (Timing: 1.0 min)
> *"Safety and Responsible AI are foundational to WindGuard AI. The system is architecturally barred from autonomous actuation—there are exactly zero SCADA control routes. All recommendations require certified human review through four canonical actions: Acknowledge, Investigate, Escalate, or Dismiss. Every decision, note, and timestamp is permanently recorded in an immutable append-only audit log, ensuring complete regulatory auditability."*

---

## Slide 17: Transparent Engineering Limitations & Physical Thermal Inertia

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       TRANSPARENT ENGINEERING LIMITATIONS & PHYSICAL BOUNDS                      │
│                                                                                                  │
│   1. Static Thermal Inertia Lag (OD-P8-05 / OD-P9-04):                                           │
│      • Physical component thermal time constant: tau ≈ 45–60 min.                                │
│      • Static 10-minute snapshot features model quasi-steady-state rather than dynamic inertia.   │
│      • Measured holdout RMSE: 4.92°C (Gearbox) / 6.06°C (Generator).                             │
│      • Mitigated downstream by 60-minute rolling persistence accumulator (5/6 timesteps >= 2.5σ).│
│                                                                                                  │
│   2. Synthetic Benchmark Scope:                                                                  │
│      • Evaluated on high-fidelity ODE benchmark scenarios S1–S5. Multi-year field telemetry next.│
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Scientific Honesty & Transparency**: Proactively documents known physical limitations rather than concealing them.
* **Physical Cause of Thermal Lag**: Large mechanical masses (gearbox and generator) heat up and cool down slowly ($\tau \approx 60\,\text{min}$). Static 10-minute snapshot models experience a phase lag during sudden power transitions.
* **Architectural Mitigation**: Handled gracefully by the 60-minute rolling persistence accumulator, preventing transient thermal lag from triggering false alarms.

### Speaker Notes (Timing: 1.0 min)
> *"In the spirit of rigorous engineering transparency, we explicitly document our physical modeling boundaries. Because multi-ton gearboxes have thermal time constants of approximately 60 minutes, instantaneous 10-minute snapshot features cannot capture dynamic transient heating without autoregression. This results in a measured thermal RMSE of 4.92°C to 6.06°C. Rather than misrepresenting this metric, we accept it as an inherent property of static ML baselines and mitigate it using our 60-minute persistence accumulator."*

---

## Slide 18: Summary of Contributions, Academic Novelty & Future Scope

### Visual Layout & Wireframe
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        SUMMARY OF CONTRIBUTIONS & FUTURE RESEARCH ROADMAP                        │
│                                                                                                  │
│   4 Key Contributions:                                                                           │
│   1. Physics-Informed ML Baselines with near-perfect aerodynamic power tracking (R²=1.00).       │
│   2. Context-Aware Precedence Hierarchy delivering 100% false curtailment suppression.           │
│   3. Deterministic Local Hybrid RAG achieving MRR=1.0 and 1.14 ms retrieval without cloud LLMs.  │
│   4. Complete 6-Layer Decision-Support Platform with sub-200ms end-to-end SLA compliance.        │
│                                                                                                  │
│   Future Roadmap: Neural ODE dynamic thermal modeling, 10kHz vibration spectrum ingestion.       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Technical Talking Points
* **Synthesis of 4 Core Contributions**: Physics ML, Context Engine, Deterministic Local RAG, and End-to-End Decision Support.
* **Submission Readiness**: 100% of Phase 1 through 8 implementation complete, verified, and sealed.
* **Future Research**: Neural ODE autoregression for transient thermal lag, high-frequency vibration signal integration.

### Speaker Notes (Timing: 1.0 min)
> *"In summary, WindGuard AI delivers an end-to-end, physics-informed, context-aware decision support platform that solves the dual failure modes of legacy SCADA alarms and ungrounded cloud LLMs. With 100% curtailment suppression, sub-200ms latency, and full human-in-the-loop governance, it proves that explainable AI can drive down renewable O&M costs while maintaining absolute safety. Thank you for your time, and I look forward to your questions in the viva defense."*

---
*WindGuard AI Master 18-Slide Capstone Presentation Deck — Phase 9 Verified.*
