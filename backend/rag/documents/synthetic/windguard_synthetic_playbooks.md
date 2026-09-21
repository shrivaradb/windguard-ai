---
document_title: "WindGuard Synthetic Operational Diagnostic Playbooks & Grid Curtailment Guides"
source_id: "SRC-SYNTHETIC-PLAYBOOK-2026"
source_type: "PROJECT_SYNTHETIC"
publisher: "WindGuard AI Project Synthetic Benchmarks"
document_version: "1.0.0"
publication_date: "2026-09-20"
content_type: "PROJECT_SYNTHETIC"
tags: ["synthetic", "playbook", "curtailment", "grid_dispatch", "feathering", "deemed_generation"]
---

# Synthetic Diagnostic Playbooks & Grid Dispatch Guides

## Chapter 1: Grid Curtailment & Active Power Derating

### Section 1.1: Active Power Derate Setpoint Management Under Grid Dispatch
<!-- chunk_id: CHK-GRD-001 -->
Grid curtailment active power derate setpoint: During periods of regional transmission congestion or low grid demand, State Load Despatch Centres (SLDC) issue mandatory active power curtailment orders. The wind power plant supervisory control system receives an active power derate setpoint (e.g. capping a 2000 kW turbine at 1000 kW). WindGuard AI's context filter identifies `is_curtailed == True` to decouple intentional power restrictions from aerodynamic or mechanical degradation. Active power deficits occurring under grid curtailment derate setpoints are classified as deemed generation events rather than equipment faults, preventing spurious maintenance work orders.

### Section 1.2: Aerodynamic Pitch Regulation and Power Shedding Under Curtailment
<!-- chunk_id: CHK-GRD-002 -->
Grid curtailment active power derate setpoint and feathered pitch power shedding during strong wind: To enforce an active power derate setpoint when incoming wind speed exceeds rated conditions ($>12.0\,\text{m/s}$), turbine controllers rotate blade pitch angles into the wind (typically pitching to $+10.0^\circ$ to $+25.0^\circ$). This feathered pitch power shedding intentionally spills excess aerodynamic energy. Operators and analytical engines must recognize that high pitch angles accompanied by low power output under strong winds represent normal grid curtailment execution, not encoder calibration drift or hydraulic cylinder degradation.

## Chapter 2: High Wind Aerodynamic Power Shedding

### Section 2.1: Feathered Pitch Operations in High Wind Conditions
<!-- chunk_id: CHK-GRD-003 -->
Feathered pitch power shedding during strong wind: In storm-ride-through and high-wind soft cut-out regimes ($20.0\,\text{m/s} \le v_{\text{wind}} \le 25.0\,\text{m/s}$), aerodynamic power shedding via feathered pitch angles protects the drive train and tower from extreme thrust loads. Blades are pitched progressively toward feather ($+15.0^\circ$ to $+30.0^\circ$) to taper electrical output smoothly. The reasoner verifies whether pitch angle elevation aligns with the expected high-wind derate schedule before raising aerodynamic pitch asymmetry alarms.

### Section 2.2: Commercial Settlement and Deemed Generation Accounting
<!-- chunk_id: CHK-GRD-004 -->
Deemed generation capacity accounting under dispatch: Under Indian regulatory frameworks (CERC / SERC grid codes), energy curtailed due to grid dispatch directives is accounted as deemed generation capacity. Deemed generation energy is computed as the integral over time of the difference between unconstrained expected power ($P_{\text{exp}}$) and the curtailed active power ($P_{\text{act}}$). Commercial accounting logs this energy for utility availability compensation, while maintenance loss engines strictly exclude deemed curtailment energy from equipment financial loss calculations.

## Chapter 3: Benchmark Diagnostic Scenario Playbooks

### Section 3.1: Scenario S4 Multi-Condition Diagnostic Protocol
<!-- chunk_id: CHK-GRD-005 -->
Grid curtailment active power derate setpoint and Scenario S4 diagnostic playbook: Scenario S4 demonstrates the co-occurrence of active utility grid curtailment ($1000\,\text{kW}$ setpoint) and extreme ambient heatwave conditions ($T_{\text{amb}} \ge 38.0^\circ\text{C}$). The diagnostic playbook instructs operators to verify that power suppression is driven by utility dispatch while component thermal rise is driven by high ambient air. Priority scores for S4 are maintained at LOW/NORMAL, confirming zero eligible maintenance financial loss.
