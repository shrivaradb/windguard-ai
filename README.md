# WindGuard AI: Explainable Wind Turbine Predictive Health & Decision-Support System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Governance Status](https://img.shields.io/badge/Governance-Phase%209%20Submission%20Ready-brightgreen.svg)](docs/00_documentation_index.md)
[![Safety Protocol](https://img.shields.io/badge/SCADA%20Actuation-Permanently%20Prohibited-red.svg)](docs/RESPONSIBLE_AI_AND_SDG.md)

> **WindGuard AI** is an explainable, physics-informed, evidence-grounded wind turbine predictive health and decision-support prototype evaluated primarily on synthetic benchmark scenarios. It combines first-order physical ODE simulation, machine learning expected-behavior baselines, multi-signal contextual anomaly attribution, offline deterministic hybrid RAG knowledge retrieval, and numerical guardrails into a human-in-the-loop decision-support system. Zero cloud LLM API connectivity or autonomous SCADA actuation routes are utilized.

---

## 1. Executive Summary & Problem Context

In modern utility-scale wind energy operations, operations and maintenance (O&M) costs account for **20% to 30% of the total Levelized Cost of Energy (LCOE)**. Traditional SCADA alarm systems generate massive false alarm volumes, often exceeding 85%, caused by benign environmental transients, grid curtailment orders, or high ambient heatwaves. Conversely, black-box machine learning approaches lack physical grounding, provide no auditability, and risk catastrophic hallucination when diagnosing mechanical faults.

WindGuard AI resolves this dual failure mode by introducing a **context-aware, physics-informed hybrid decision support architecture**:
1. **Physics-Informed ML Baselines**: Distinguishes true subsystem mechanical degradation from normal aerodynamic power curve tracking and ambient thermal rise.
2. **Operational Context Engine**: Eliminates false positive alarms by evaluating operational state hierarchy (grid curtailment, heatwaves, low-wind idling).
3. **Prospective Tariff Loss Engine**: Computes actual monetary exposure (INR / USD) based on Indian wind corridor tariff structures (PPA flat, time-of-day, Feed-in Tariff, component replacement cost).
4. **Local Hybrid RAG Subsystem**: Retrieves governed maintenance procedures from 7 technical documents (29 chunks) using hybrid TF-IDF + Okapi BM25 ranking (MRR = 1.0) with zero external network connectivity.
5. **Constrained Advisory Synthesis & Guardrails**: Generates deterministic, fully audited maintenance advisories verified against mathematical bounds with 100% numerical fidelity.
6. **Strict Non-Actuation Protocol**: Enforces human-in-the-loop governance where the system strictly advises and never executes autonomous SCADA control commands.

---

## 2. Academic Lineage & Research Foundation

WindGuard AI is academically anchored in the research framework established by **Bhagwatikar & Bhagwatikar (2026)** (*Explainable Artificial Intelligence for Wind Turbine Condition Monitoring*):
* **Evolution of Intelligence**: Contextualizes condition monitoring across the 5 generations of wind turbine intelligence (Threshold Alarms $\rightarrow$ Statistical SCADA $\rightarrow$ Black-Box ML $\rightarrow$ Physics-Informed ML $\rightarrow$ Explainable Generative Decision Support).
* **Digital Shadow Paradigm**: Implements passive digital shadows that model expected physical behavior without attempting ungrounded bi-directional closed-loop actuation.
* **Contextual Attribution**: Addresses the core open challenge of distinguishing sensor dropouts, grid-imposed curtailments, and ambient thermal saturation from genuine drivetrain component failures.

---

## 3. Canonical 6-Layer Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   WINDGUARD AI ARCHITECTURE                                      │
├───────────────────────────────────┬──────────────────────────────────────────────────────────────┤
│ Layer 1: Ingestion & Simulation   │ 10-Min SCADA Telemetry, 1st-Order ODEs, Benchmark S1–S5      │
├───────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Layer 2: Physics-Informed ML      │ Expected Power GBR (R²=1.0), Thermal RF, Baseline Residuals  │
├───────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Layer 3: Context & Loss Engine    │ Curtailment (100% S4), Heatwave Derate, Tariff Hierarchy     │
├───────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Layer 4: Technical Local RAG      │ Hybrid TF-IDF + Okapi BM25, 7 Documents / 29 Chunks (MRR=1.0)│
├───────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Layer 5: Advisory & Guardrails    │ Deterministic Mode A Synthesis, 100% Numerical Fidelity      │
├───────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Layer 6: API, UI & Case Store     │ 19 FastAPI Routes, Atomic File Locking, 10-Stage Studio UI   │
└───────────────────────────────────┴──────────────────────────────────────────────────────────────┘
```

---

## 4. Quickstart Guide (Native Python)

### 4.1 Prerequisites
* **Python**: `3.10`, `3.11`, `3.12`, or `3.13`
* **Operating System**: Windows, Linux, or macOS
* **Hardware**: Standard x86_64 or ARM64 CPU (Zero GPU required; offline CPU inference)

### 4.2 Installation

```bash
# 1. Clone the repository
git clone https://github.com/shrivaradb/windguard-ai.git
cd windguard-ai

# 2. Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 3. Install pinned dependencies
pip install -r requirements.txt
```

### 4.3 Launch Interactive Demo & Dashboard

Run the one-command launcher to start the backend and open the Operator Studio:

```bash
python run_demo.py
```

* **Operator Web UI**: `http://127.0.0.1:8000/`
* **API Documentation**: `http://127.0.0.1:8000/docs`
* **System Health Check**: `http://127.0.0.1:8000/api/health`

---

## 5. Verification & Testing Commands

### 5.1 Automated Regression Test Suite
Execute the full test suite (273+ passing unit and integration tests):

```bash
pytest -v
```

### 5.2 Automated Benchmark Evaluation Suite
Execute the multi-layer empirical evaluation harness and generate fresh benchmark reports:

```bash
python -m backend.evaluation.run_all_evaluations
```

Generated reports and metric JSONs are written directly to:
* `docs/EVALUATION_REPORT.md`
* `evaluation_results/*.json`

---

## 6. Key Empirical Results & Verified Metrics

| Dimension / Metric | Target Threshold | Measured Empirical Result | Status |
| :--- | :---: | :---: | :---: |
| **Power Curve Fit ($R^2$)** | $\ge 0.95$ | **$1.0000$** | **PASS** |
| **Power Curve RMSE** | $\le 45.0\,\text{kW}$ | **$1.31\,\text{kW}$** | **PASS** |
| **Power Inference Latency** | $< 1.0\,\text{ms}$ | **$0.26\,\text{ms}$** | **PASS** |
| **Gearbox Thermal RMSE** | Limitation | **$4.92^\circ\text{C}$** | **LIMITATION (OD-P8-05)** |
| **Generator Thermal RMSE** | Limitation | **$6.06^\circ\text{C}$** | **LIMITATION (OD-P8-05)** |
| **Curtailment False Alarm Suppression** | $\ge 90.0\%$ | **$100.0\%$ ($540/540$)** | **PASS** |
| **False Alarm Rate (FAR)** | $\le 5.0\%$ | **$3.64\%$** | **PASS** |
| **RAG Mean Reciprocal Rank (MRR)** | $\ge 0.80$ | **$1.0000$ ($15/15$)** | **PASS** |
| **RAG Operational Recall@3** | $\ge 85.0\%$ | **$96.67\%$ ($29/30$)** | **PASS** |
| **RAG Retrieval Latency** | $< 50.0\,\text{ms}$ | **$1.14\,\text{ms}$** | **PASS** |
| **Advisory Numerical Fidelity** | $= 100.0\%$ | **$100.0\%$ ($60/60$)** | **PASS** |
| **Negative Guardrail Catch Rate** | $= 100.0\%$ | **$100.0\%$ ($5/5$)** | **PASS** |
| **Full Pipeline SLA Latency** | $\le 2500.0\,\text{ms}$ | **$185.57\,\text{ms}$** | **PASS** |
| **SCADA Actuation Routes** | Exactly $0$ | **$0$** | **PASS** |
| **Cloud LLM API Sockets** | Exactly $0$ | **$0$** | **PASS** |

---

## 7. Interactive 10-Stage Operator Studio

The web dashboard includes a built-in 10-stage interactive operator walkthrough demonstrating complete end-to-end lifecycle diagnostics:

1. **Stage 1 — Clean Fleet Baseline**: Normal power generation under standard conditions.
2. **Stage 2 — Gearbox Overheating Inception**: Early thermal anomaly detection prior to alarm trip.
3. **Stage 3 — Grid Curtailment Order**: Power derate without false alarm generation (100% suppression).
4. **Stage 4 — Generator Stator Thermal Runaway**: High-severity thermal runaway with priority escalation.
5. **Stage 5 — Aerodynamic Blade Pitch Misalignment**: Aerodynamic underperformance detection.
6. **Stage 6 — Ambient Heatwave Transients**: High-ambient thermal compensation without false alert.
7. **Stage 7 — Sensor Dropout & Communication Loss**: Frozen/zero sensor dropout isolation.
8. **Stage 8 — Complex Cascading Mechanical Fault**: Multi-component anomaly diagnosis.
9. **Stage 9 — Prospective Revenue Loss Calculation**: Real-time monetary loss estimation across 4 tariff tiers.
10. **Stage 10 — Human-in-the-Loop Advisory & Work Order**: Human case decision logging and printable work order.

---

## 8. Hard Safety Boundaries & Governance Rules

* **SCADA Actuation — Permanently Prohibited**: WindGuard AI has exactly **0 control, override, or actuation routes**. It cannot start, stop, yaw, pitch, or throttle physical turbines.
* **100% Offline Local Operation**: Deterministic Mode A operates entirely offline. No SCADA data or diagnostic prompts are transmitted to third-party cloud providers.
* **Human Oversight (HITL)**: All maintenance recommendations require human review. Decisions (`ACKNOWLEDGE`, `INVESTIGATE`, `ESCALATE`, `DISMISS`) are appended to an immutable audit trail (`audit_log.jsonl`).
* **Frozen Engineering Baseline**: Phases 1 through 8 are immutable and sealed.

---

## 9. Comprehensive Documentation Sitemap

| Category | Primary Documents |
| :--- | :--- |
| **Architecture & Specifications** | [`docs/08_system_architecture.md`](docs/08_system_architecture.md), [`docs/09_technical_design.md`](docs/09_technical_design.md), [`docs/MASTER_TECHNICAL_REPORT.md`](docs/MASTER_TECHNICAL_REPORT.md) |
| **Requirements & Governance** | [`docs/06_prd.md`](docs/06_prd.md), [`docs/07_srs.md`](docs/07_srs.md), [`docs/00_documentation_index.md`](docs/00_documentation_index.md) |
| **Model Cards & RAG** | [`docs/MODEL_CARDS.md`](docs/MODEL_CARDS.md), [`docs/RAG_KNOWLEDGE_CATALOG.md`](docs/RAG_KNOWLEDGE_CATALOG.md) |
| **Responsible AI & Safety** | [`docs/RESPONSIBLE_AI_AND_SDG.md`](docs/RESPONSIBLE_AI_AND_SDG.md) |
| **Presentation & Defense** | [`docs/PRESENTATION_DECK_18_SLIDES.md`](docs/PRESENTATION_DECK_18_SLIDES.md), [`docs/DEMO_WALKTHROUGH_GUIDE.md`](docs/DEMO_WALKTHROUGH_GUIDE.md), [`docs/VIVA_DEFENSE_PREPARATION.md`](docs/VIVA_DEFENSE_PREPARATION.md) |
| **Evaluation & Verification** | [`docs/EVALUATION_REPORT.md`](docs/EVALUATION_REPORT.md), [`docs/PHASE_8_FINAL_SIGNOFF.md`](docs/PHASE_8_FINAL_SIGNOFF.md), [`docs/PHASE_9_VERIFICATION.md`](docs/PHASE_9_VERIFICATION.md) |

---

## 10. Authors & Citation

**Academic Lineage Reference**:
```bibtex
@article{bhagwatikar2026explainable,
  title={Explainable Artificial Intelligence for Wind Turbine Condition Monitoring: From Black-Box Models to Physical-Informed Hybrid Decision Support},
  author={Bhagwatikar, G. and Bhagwatikar, S.},
  journal={Renewable and Sustainable Energy Reviews},
  year={2026}
}
```

---
*WindGuard AI — Engineering Rigor, Physics-Informed Transparency, Clean Energy Assurance.*
