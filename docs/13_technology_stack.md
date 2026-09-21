---
document: 13_technology_stack
version: 0.2
status: REVIEW
last_updated: 2026-09-20
author: WindGuard AI Engineering Team
depends_on:
  - docs/06_prd.md
  - docs/07_srs.md
  - docs/08_system_architecture.md
  - docs/09_technical_design.md
---

# 13. Technology Stack — WindGuard AI

## 1. Executive Summary

This document specifies the evaluated, selected, and proposed technology stack for the **WindGuard AI** platform. Every technology choice is justified against technical requirements, performance constraints, reproducibility mandates, and the lightweight edge/cloud operational profile across the canonical **6-Layer System Architecture**.

---

## 2. Technology Selection Matrix Across the 6 Canonical Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       WINDGUARD AI TECHNOLOGY MATRIX                        │
└─────────────────────────────────────────────────────────────────────────────┘

  LAYER 1: DATA INGESTION & SCADA SIMULATOR
  ├── Python 3.11+ / NumPy / Pandas / Pydantic v2
  └── Status: SELECTED (FINAL) | Role: Ingestion, schema validation, physics-based simulator.

  LAYER 2: DETERMINISTIC ANALYTICAL ML & RESIDUAL ENGINE
  ├── Scikit-Learn (GradientBoosting / RandomForest) / SciPy
  └── Status: SELECTED (FINAL) | Role: Expected power/thermal curves, statistical z-scores.

  LAYER 3: OPERATIONAL CONTEXT FILTER, REASONER & TARIFF LOSS ENGINE
  ├── Python 3.11+ / Custom Rule & Reasoning Engine / Tariff Registry
  └── Status: SELECTED (FINAL) | Role: False-alarm suppression, multi-signal attribution, loss calculation.

  LAYER 4: TECHNICAL KNOWLEDGE RETRIEVAL (RAG) ENGINE
  ├── Local Hybrid TF-IDF & Dense Cosine Vector Index / SentenceTransformers
  └── Status: SELECTED (FINAL) | Role: Low-latency semantic & keyword search over technical corpus.

  LAYER 5: EVIDENCE SYNTHESIS, GUARDRAIL & DIAGNOSTIC GENERATION
  ├── Local High-Fidelity Deterministic Guardrail Engine (Default / Offline)
  │   └── Status: SELECTED (FINAL) | Guaranteed 100% offline uptime & zero hallucination.
  ├── IBM Granite / OpenAI API / Gemini API (Pluggable Cloud Option)
  │   └── Status: PROPOSED (OPTIONAL / PLUGGABLE) | Optional cloud LLM reasoning adapters.

  LAYER 6: PRESENTATION, REST API & HITL GOVERNANCE
  ├── FastAPI / Uvicorn / Modern HTML5 / Vanilla ES6 / Tailwind CSS / Chart.js / Lucide Icons
  │   └── Status: SELECTED (FINAL) | Role: High-performance async REST API & zero-build SPA.
  ├── Local JSON / SQLite with Atomic File Locking (portalocker)
  │   └── Status: SELECTED (FINAL) | Role: Case persistence, telemetry cache, append-only audit trail.

  CROSS-CUTTING: AUTOMATED TESTING & BENCHMARKING
  ├── Pytest / Evaluation Benchmark Suite
  │   └── Status: SELECTED (FINAL) | Role: Unit tests, regression baselines, citation verification.
```

---

## 3. Detailed Technology Evaluation & Justifications

### 3.1 Backend & Web Framework

| Technology | Role in System | Justification | Alternatives Considered | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Python 3.11+** | Core Runtime Environment | Rich scientific ecosystem (Scikit-Learn, Pandas, SciPy), rapid development, native async. | C++, Java, Node.js | **SELECTED (FINAL)** |
| **FastAPI** | High-Performance REST API | Native async support, automatic OpenAPI/Swagger documentation, Pydantic type safety. | Flask, Django, Express.js | **SELECTED (FINAL)** |
| **Uvicorn** | ASGI Web Server | Lightning-fast asynchronous server for hosting FastAPI applications. | Gunicorn, Hypercorn | **SELECTED (FINAL)** |
| **Pydantic v2** | Data Schema Validation | Strict type validation for incoming SCADA streams and outgoing advisory JSON schemas. | Marshmallow, Cerberus | **SELECTED (FINAL)** |

---

### 3.2 Machine Learning & Scientific Computing

| Technology | Role in System | Justification | Alternatives Considered | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Scikit-Learn** | Regression & Anomaly Modeling | Proven algorithms (GradientBoosting, RandomForest), deterministic training, zero heavy GPU requirement. | PyTorch, TensorFlow, XGBoost | **SELECTED (FINAL)** |
| **NumPy & Pandas** | Tabular Telemetry Ingestion | Vectorized array operations, rolling window calculations, canonical schema mapping. | Polars, Dask | **SELECTED (FINAL)** |
| **SciPy** | Statistical Residual Normalization | Rolling $z$-scores, quantile computation, and statistical hypothesis testing. | Statsmodels | **SELECTED (FINAL)** |

---

### 3.3 Vector Search & Technical RAG Subsystem

| Technology | Role in System | Justification | Alternatives Considered | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Local Dense & TF-IDF Vector Engine** | Technical Manual Retrieval | Zero-dependency, offline-capable hybrid search over chunked markdown documents. | Pinecone, Milvus, ChromaDB | **SELECTED (FINAL)** |
| **Local Deterministic Advisory Engine** | Rule-Based Grounded Synthesis | Schema-enforced template synthesis ensuring 100% numerical fidelity and zero unverified claims. | Pure LLM Generation | **SELECTED (FINAL)** |
| **IBM Granite / Cloud LLMs** | Conversational Engineering Synthesis | Pluggable generative models for natural-language case narrative and conversational assistant. | Llama-3, Mistral, OpenAI | **PROPOSED (PLUGGABLE)** |

---

### 3.4 Frontend & Visualization

| Technology | Role in System | Justification | Alternatives Considered | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Modern HTML5 / ES6 / Tailwind CSS** | Operator Web Dashboard | Zero-build-step deployment; instant browser loading; clean responsive styling. | React / Next.js, Vue, Angular | **SELECTED (FINAL)** |
| **Chart.js** | Interactive Time-Series & Power Curves | Lightweight canvas-based charting; smooth animations for real-time telemetry and power curves. | D3.js, Plotly, Recharts | **SELECTED (FINAL)** |
| **Lucide Icons** | Industrial UI Iconography | Clean, modern SVG icon set for turbine health, alarms, and navigation. | FontAwesome, Feather | **SELECTED (FINAL)** |

---

### 3.5 Storage & Audit Logging

| Technology | Role in System | Justification | Alternatives Considered | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Local JSON & SQLite Store** | Telemetry Cache & Audit Log | File-based, zero-configuration persistence; completely self-contained. | PostgreSQL, MongoDB | **SELECTED (FINAL)** |
| **portalocker / OS File Locking** | Concurrent Write Protection | Prevents file corruption and race conditions during simultaneous operator decision reviews. | Redis Locks, DB Row Locks | **SELECTED (FINAL)** |
