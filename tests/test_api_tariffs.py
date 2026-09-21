"""Acceptance and Unit Tests for Multi-Mode Tariff Registry API Routes (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.3
- docs/10_data_architecture.md §4.2
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6 (REQ-SPEC-04)
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_tariff_registry
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig
from backend.storage.case_store import case_store
from backend.storage.telemetry_store import telemetry_store


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_tariff_configuration(client: TestClient):
    """Verifies that GET /api/tariffs returns active tariff and available modes."""
    response = client.get("/api/tariffs")
    assert response.status_code == 200
    data = response.json()
    assert "active_tariff" in data
    assert data["active_tariff"]["applied_rate_inr_per_kwh"] > 0
    assert "available_modes" in data
    assert "PROJECT_PPA" in data["available_modes"]
    assert "REGULATORY_BENCHMARK" in data["available_modes"]
    assert "CONFIGURED_BASELINE" in data["available_modes"]


def test_update_tariff_valid_ppa(client: TestClient):
    """Verifies updating active tariff to a custom Project PPA rate."""
    payload = {
        "rate_inr_per_kwh": 4.25,
        "mode": "PROJECT_PPA",
        "source_reference": "State DISCOM PPA Contract #GJ-WIND-2026-08",
        "notes": "Verified tariff amendment.",
    }
    response = client.post("/api/tariffs", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["applied_rate_inr_per_kwh"] == 4.25
    assert updated["mode"] == "PROJECT_PPA"
    assert updated["source_reference"] == "State DISCOM PPA Contract #GJ-WIND-2026-08"
    assert updated["is_baseline_assumption"] is False


def test_tariff_rate_bounds_validation(client: TestClient):
    """Verifies that out-of-bounds rates (< ₹0.01 or > ₹20.00) are rejected."""
    # Test rate = 0.00
    resp_low = client.post(
        "/api/tariffs",
        json={"rate_inr_per_kwh": 0.0, "mode": "PROJECT_PPA", "source_reference": "Test"},
    )
    assert resp_low.status_code == 422

    # Test rate = 25.00
    resp_high = client.post(
        "/api/tariffs",
        json={"rate_inr_per_kwh": 25.0, "mode": "PROJECT_PPA", "source_reference": "Test"},
    )
    assert resp_high.status_code == 422


def test_tariff_prospective_application_preserves_historical_cases(client: TestClient):
    """REQ-SPEC-04: Verifies that changing the active tariff does NOT alter existing historical cases."""
    telemetry_store.clear()
    case_store.clear()

    # Reset tariff to baseline ₹3.20/kWh
    reg = get_tariff_registry()
    reg.reset_to_baseline()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY, random_seed=42))
    telemetry_store.add_records(result.records)

    # 1. Diagnose case under baseline tariff (₹3.20/kWh)
    c1 = client.post("/api/turbines/WTG-03/diagnose").json()
    case_id_1 = c1["case_id"]
    loss_inr_1 = c1["derived_analytics"]["financial_loss_inr"]
    rate_1 = c1["derived_analytics"]["tariff_provenance"]["applied_rate_inr_per_kwh"]
    assert rate_1 == 3.20
    assert loss_inr_1 > 0.0

    # 2. Update active tariff to ₹5.00/kWh
    client.post(
        "/api/tariffs",
        json={"rate_inr_per_kwh": 5.0, "mode": "PROJECT_PPA", "source_reference": "Updated PPA Rate"},
    )

    # 3. Retrieve historical case 1 by ID and assert loss & tariff remain strictly unchanged
    c1_retrieved = client.get(f"/api/cases/{case_id_1}").json()
    assert c1_retrieved["derived_analytics"]["tariff_provenance"]["applied_rate_inr_per_kwh"] == 3.20
    assert c1_retrieved["derived_analytics"]["financial_loss_inr"] == loss_inr_1
