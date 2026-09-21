---
document: 11_ai_ml_design
version: 0.2
status: REVIEW
last_updated: 2026-09-20
author: WindGuard AI AI/ML Engineering Team
depends_on:
  - docs/06_prd.md
  - docs/07_srs.md
  - docs/08_system_architecture.md
  - docs/09_technical_design.md
  - docs/10_data_architecture.md
---

# 11. AI/ML Design — WindGuard AI

## 1. AI/ML Objectives & Scope

The AI/ML subsystem of **WindGuard AI** is designed to provide robust, explainable, and computationally efficient decision support for wind turbine condition monitoring. In alignment with Academic Literature (2026) [Established], the AI/ML design strictly enforces:
1. **Physics-Grounded Expected Behaviour Modeling**: Modeling the non-linear aerodynamic power curve and thermodynamic component equilibrium.
2. **Context-Aware Residual Filtering**: Discriminating between true equipment degradation and environmental/grid operational transients (`is_curtailed`, heatwaves, low-wind idle).
3. **Multi-Signal Subsystem Attribution**: Isolating mechanical, electrical, aerodynamic, and sensor failure modes.
4. **Evidence-Grounded Generative Synthesis**: The architecture prevents the generative layer from independently generating or modifying numerical diagnostic values by enforcing strict schema bounding over deterministic analytical ML outputs.

---

## 2. Mathematical Problem Formulation

### 2.1 Expected Power Regression
Let $\mathbf{x}_{\text{aero}}(t) = [v_{\text{wind}}(t), T_{\text{ambient}}(t), \theta_{\text{pitch}}(t)]^T \in \mathbb{R}^3$ be the operational aerodynamic input vector. We seek a regressor $f: \mathbb{R}^3 \to \mathbb{R}^+$ such that:

$$\hat{P}(t) = f(\mathbf{x}_{\text{aero}}(t))$$

The power residual is defined as:

$$R_{\text{power}}(t) = P_{\text{actual}}(t) - \hat{P}(t)$$

### 2.2 Component Thermal Equilibrium Baselines
Let $\mathbf{x}_{\text{therm}}(t) = [P_{\text{active}}(t), T_{\text{ambient}}(t), \omega_{\text{rotor}}(t)]^T \in \mathbb{R}^3$. We define thermal equilibrium estimators $g_{\text{GB}}$ and $h_{\text{Gen}}$:

$$\hat{T}_{\text{GB}}(t) = g_{\text{GB}}(\mathbf{x}_{\text{therm}}(t)), \quad \hat{T}_{\text{Gen}}(t) = h_{\text{Gen}}(\mathbf{x}_{\text{therm}}(t))$$

Thermal residuals are formulated as:

$$R_{\text{GB}}(t) = T_{\text{GB\_actual}}(t) - \hat{T}_{\text{GB}}(t), \quad R_{\text{Gen}}(t) = T_{\text{Gen\_actual}}(t) - \hat{T}_{\text{Gen}}(t)$$

### 2.3 Statistical Standardization & Anomaly Persistence
To make residuals comparable across different operating regimes, we compute rolling standardized $z$-scores over a sliding baseline window:

$$z_i(t) = \frac{R_i(t) - \mu_{R_i}}{\sigma_{R_i}}$$

An anomaly is considered **persistent** if its $z$-score exceeds a statistical threshold $\theta_{\text{thresh}}$ for at least $K$ out of $W$ consecutive 10-minute intervals:

$$\text{Persistence}(t) = \frac{1}{W} \sum_{k=0}^{W-1} \mathbb{I}\left(|z_i(t-k)| \ge \theta_{\text{thresh}}\right) \ge 0.80$$

For 10-minute SCADA data, $W=6$ intervals represents a 1-hour persistence filter.

---

## 3. Feature Engineering Pipeline

| Raw SCADA Parameter | Derived Feature | Physical Rationale | Formula / Definition |
| :--- | :--- | :--- | :--- |
| `wind_speed`, `ambient_temp` | $\rho_{\text{air}}$ (Air Density) | Accounts for seasonal air density shifts on aerodynamic thrust. | $\rho = \frac{101325}{287.05 \times (T_{\text{ambient}} + 273.15)}$ |
| `active_power`, `rated_power` | $\text{Load Ratio}$ | Normalizes thermal dissipation against electrical loading. | $\text{Load} = \frac{P_{\text{active}}}{P_{\text{rated}}}$ |
| `rotor_speed`, `generator_speed` | $\text{Gearbox Ratio Slip}$ | Identifies drivetrain mechanical slippage or clutch degradation. | $\text{Slip} = \frac{\omega_{\text{gen}}}{\omega_{\text{rotor}}} - \text{Ratio}_{\text{nominal}}$ |
| `gearbox_temp`, `ambient_temp` | $\Delta T_{\text{GB\_rise}}$ | Measures internal thermal rise above ambient baseline. | $\Delta T_{\text{rise}} = T_{\text{GB}} - T_{\text{ambient}}$ |
| `is_curtailed` | $\text{Curtailment State}$ | Tags deliberate power cap dispatch to prevent false alarms. | Binary boolean flag |
| $R_{\text{power}}, R_{\text{GB}}, R_{\text{Gen}}$ | Rolling $z$-scores ($6\,\text{steps}$) | Suppresses single-interval transient sensor noise. | Rolling mean & standard deviation normalization |

---

## 4. Candidate Model Evaluation & Selection

| Model Architecture | Interpretability | Non-Linear Fit ($R^2$) | Training Time | Inference Latency | Selected Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Linear / Polynomial OLS** | Very High | Poor ($R^2 \approx 0.82$) | $<0.1\,\text{s}$ | $<0.01\,\text{ms}$ | Rejected (Fails on aerodynamic non-linearities) |
| **Random Forest Regressor** | High | `[TARGET]` $R^2 \ge 0.96$ | $\approx 1.2\,\text{s}$ | $\approx 0.2\,\text{ms}$ | **Selected for Thermal Baselines** |
| **Gradient Boosted Trees (GBR)** | High | `[TARGET]` $R^2 \ge 0.97$ | $\approx 2.5\,\text{s}$ | $\approx 0.1\,\text{ms}$ | **Selected for Power Curve Modeling** |
| **Deep LSTM / Transformer** | Very Low (Black Box) | `[BENCHMARK]` $R^2 \ge 0.97$ | $\approx 120.0\,\text{s}$ | $\approx 15.0\,\text{ms}$ | Rejected (High compute, opaque attribution) |

---

## 5. Technical RAG Architecture & Vector Indexing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TECHNICAL RAG EMBEDDING & RETRIEVAL                      │
└─────────────────────────────────────────────────────────────────────────────┘

  OEM Manuals & Alarm SOPs ──► Section Chunker (200-400 tokens + Metadata)
                                            │
                                            ▼
                     Local Dense Embedding / TF-IDF Vectorizer
                                            │
                                            ▼
                   Local Vector Store / Cosine Similarity Index
                                            │
                                            ▼
   Query: "AL-104 Bearing Temp" ──► Hybrid Search (Dense/TF-IDF + BM25)
                                            │
                                            ▼
  Retrieved Chunks: [OEM Sec 4.2: High-Speed Shaft Bearings | Page 114]
```

- **Embedding Models**: Local dense embeddings (e.g. `all-MiniLM-L6-v2`) with a zero-external-dependency TF-IDF + BM25 fallback engine guaranteeing 100% offline operational capability.
- **Chunking Strategy**: Section-aware hierarchical Markdown chunking, preserving procedure lists, alarm tables, and parent document metadata.

---

## 6. Model Evaluation Framework & Target Benchmarks

The AI/ML subsystem is evaluated against a multi-dimensional metric framework:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       EVALUATION METRIC FORMULATIONS                        │
└─────────────────────────────────────────────────────────────────────────────┘

  1. POWER CURVE REGRESSION METRICS
     ├── R²: 1 - (SS_res / SS_tot)                         [TARGET: ≥ 0.95]
     ├── RMSE: sqrt( (1/N) * sum( (P_act - P_exp)^2 ) )    [TARGET: ≤ 45 kW]
     └── MAE: (1/N) * sum( |P_act - P_exp| )               [TARGET: ≤ 30 kW]

  2. ANOMALY DETECTION BENCHMARK METRICS
     ├── Precision: TP / (TP + FP)                         [TARGET: ≥ 0.85]
     ├── Recall: TP / (TP + FN)                            [TARGET: ≥ 0.90]
     ├── F1-Score: 2 * (Precision * Recall) / (P + R)      [TARGET: ≥ 0.87]
     └── False Alarm Rate (FAR): FP / (FP + TN)            [TARGET: ≤ 0.05]

  3. CONTEXT FILTERING METRICS
     └── Curtailment False-Alarm Suppression Rate          [TARGET: ≥ 90% reduction]

  4. GROUNDEDNESS & HALLUCINATION AUDIT
     ├── Numerical Fidelity: Match(Advisory_Num, Telemetry_Num) / Total_Num [TARGET: 100%]
     └── Citation Precision: Valid_Citations / Total_Generated_Citations     [TARGET: 100%]
```

---

## 7. Explainability & Guardrail Safeguards

1. **Deterministic Telemetry & Loss Pass-Through**: All numerical values displayed in the operator advisory (observed power, expected power, residuals, ambient temperature, energy loss in kWh, and financial loss in INR) are calculated deterministically in Layers 2 and 3 and passed directly into formatted output templates.
2. **Prompt Bounding**: The LLM prompt template enforces strict JSON output schema and prohibits the generative layer from inventing unverified numerical quantities or modifying analytical outputs:
   > *"You must ONLY synthesize explanations using the provided telemetry metrics, calculated loss figures, and retrieved document excerpts. You must NOT alter numerical values or invent unverified failure modes."*
3. **Safety Override Disclaimer**: The output payload contains an explicit disclaimer:
   > *"This assessment is an advisory decision-support output. Certified engineering review is required prior to executing safety-critical field actions."*
