"""Acceptance and Unit Tests for Case Query, Filtering, Pagination & Immutability (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/10_data_architecture.md §4.3
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-05, REQ-SPEC-01)
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


def test_list_cases_empty(client: TestClient):
    """Verifies that GET /api/cases returns empty list when store has no cases."""
    case_store.clear()
    response = client.get("/api/cases")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["cases"] == []


def test_list_and_filter_cases(client: TestClient):
    """Verifies pagination and filtering on GET /api/cases."""
    telemetry_store.clear()
    case_store.clear()

    # Generate cases for S2 (WTG-07) and S3 (WTG-03)
    sim = SCADASimulator()
    res_s2 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    res_s3 = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S3_PITCH_ASYMMETRY, random_seed=42))
    telemetry_store.add_records(res_s2.records)
    telemetry_store.add_records(res_s3.records)

    c1 = client.post("/api/turbines/WTG-07/diagnose").json()
    c2 = client.post("/api/turbines/WTG-03/diagnose").json()

    # List all cases
    resp = client.get("/api/cases")
    assert resp.status_code == 200
    all_data = resp.json()
    assert all_data["total_count"] == 2

    # Filter by turbine_id
    resp_wtg07 = client.get("/api/cases?turbine_id=WTG-07")
    assert resp_wtg07.status_code == 200
    wtg07_data = resp_wtg07.json()
    assert wtg07_data["total_count"] == 1
    assert wtg07_data["cases"][0]["turbine_id"] == "WTG-07"

    # Pagination: limit=1
    resp_page = client.get("/api/cases?limit=1&offset=0")
    assert resp_page.status_code == 200
    page_data = resp_page.json()
    assert len(page_data["cases"]) == 1
    assert page_data["total_count"] == 2


def test_get_case_by_id(client: TestClient):
    """Verifies retrieval of specific case by case_id."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    created = client.post("/api/turbines/WTG-07/diagnose").json()
    case_id = created["case_id"]

    resp = client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    retrieved = resp.json()
    assert retrieved["case_id"] == case_id
    assert retrieved["turbine_id"] == "WTG-07"
    assert "evidence_table" in retrieved
    assert "citations" in retrieved


def test_get_case_404_for_unknown_id(client: TestClient):
    """Verifies that GET /api/cases/{unknown_id} returns 404."""
    case_store.clear()
    resp = client.get("/api/cases/CASE-UNKNOWN-123")
    assert resp.status_code == 404


def test_case_immutability_no_delete_routes(client: TestClient):
    """OD-P6-05: Verifies that DELETE /api/cases is strictly rejected (zero DELETE routes authorized)."""
    resp_del_collection = client.delete("/api/cases")
    assert resp_del_collection.status_code in (404, 405)

    resp_del_item = client.delete("/api/cases/CASE-WTG07-001")
    assert resp_del_item.status_code in (404, 405)
