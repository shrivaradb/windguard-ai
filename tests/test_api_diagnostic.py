"""Acceptance and Unit Tests for End-to-End Diagnostic Pipeline Route (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/08_system_architecture.md §2, §3
- docs/09_technical_design.md §2.6, §3
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-07)
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig
from backend.storage.case_store import case_store
from backend.storage.telemetry_store import telemetry_store


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_diagnose_s1_baseline_healthy(client: TestClient):
    """Verifies end-to-end diagnosis of S1 healthy baseline telemetry."""
    telemetry_store.clear()
    case_store.clear()

    # Simulate S1
    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, random_seed=42))
    telemetry_store.add_records(result.records)

    response = client.post("/api/turbines/WTG-01/diagnose")
    assert response.status_code == 200
    case = response.json()
    assert case["turbine_id"] == "WTG-01"
    assert case["status"] == "OPEN"
    assert case["guardrails"]["verdict"] == "PASS"
    assert case["guardrails"]["schema_valid"] is True
    assert case["guardrails"]["numerical_consistency_valid"] is True
    assert "safety_disclaimer" in case["advisory"]
    assert case["derived_analytics"]["subsystem_attribution"] == "NORMAL_OPERATION"


def test_diagnose_s2_gearbox_degradation(client: TestClient):
    """Verifies end-to-end diagnosis of S2 gearbox bearing thermal excursion on WTG-07."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    response = client.post("/api/turbines/WTG-07/diagnose")
    assert response.status_code == 200
    case = response.json()
    assert case["turbine_id"] == "WTG-07"
    assert case["derived_analytics"]["subsystem_attribution"] == "DRIVETRAIN_GEARBOX"
    assert case["derived_analytics"]["residual_gb_temp_c"] > 5.0
    assert case["priority_score"] >= 40.0
    assert case["guardrails"]["verdict"] == "PASS"
    assert len(case["citations"]) > 0


def test_diagnose_s3_pitch_asymmetry(client: TestClient):
    """Verifies end-to-end diagnosis of S3 pitch asymmetry on WTG-03."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY, random_seed=42))
    telemetry_store.add_records(result.records)

    response = client.post("/api/turbines/WTG-03/diagnose")
    assert response.status_code == 200
    case = response.json()
    assert case["turbine_id"] == "WTG-03"
    assert case["derived_analytics"]["subsystem_attribution"] == "AERODYNAMIC_PITCH"
    assert case["derived_analytics"]["energy_loss_kwh"] > 0.0
    assert case["derived_analytics"]["financial_loss_inr"] > 0.0
    assert case["guardrails"]["verdict"] == "PASS"


def test_diagnose_s4_curtailment_heatwave(client: TestClient):
    """Verifies end-to-end diagnosis of S4 grid curtailment correctly suppresses alarm on WTG-05."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE, random_seed=42))
    telemetry_store.add_records(result.records)

    response = client.post("/api/turbines/WTG-05/diagnose")
    assert response.status_code == 200
    case = response.json()
    assert case["derived_analytics"]["is_context_suppressed"] is True
    assert case["derived_analytics"]["context_state"] in ("CURTAILED", "HIGH_AMBIENT_DERATE")
    # Maintenance loss should be 0.0 for curtailed capacity
    assert case["derived_analytics"]["financial_loss_inr"] == 0.0


def test_diagnose_idempotency_behavior(client: TestClient):
    """OD-P6-07: Verifies diagnostic request idempotency and force_recompute behavior."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    # First diagnostic call
    resp1 = client.post("/api/turbines/WTG-07/diagnose")
    assert resp1.status_code == 200
    case1 = resp1.json()

    # Second diagnostic call without force_recompute (should return identical case)
    resp2 = client.post("/api/turbines/WTG-07/diagnose")
    assert resp2.status_code == 200
    case2 = resp2.json()
    assert case2["case_id"] == case1["case_id"]

    # Third diagnostic call with force_recompute=True (should produce fresh case)
    resp3 = client.post("/api/turbines/WTG-07/diagnose", json={"force_recompute": True})
    assert resp3.status_code == 200
    case3 = resp3.json()
    assert case3["case_id"] != case1["case_id"]


def test_diagnose_unknown_turbine_returns_404(client: TestClient):
    """Verifies that diagnosing an unknown turbine returns 404."""
    telemetry_store.clear()
    response = client.post("/api/turbines/UNKNOWN_99/diagnose")
    assert response.status_code == 404
