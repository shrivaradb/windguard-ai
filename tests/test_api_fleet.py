"""Acceptance and Unit Tests for Fleet Status & Summary API Routes (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/10_data_architecture.md §6
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import SimulationConfig
from backend.storage.case_store import case_store
from backend.storage.telemetry_store import telemetry_store


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_fleet_status_empty_cache(client: TestClient):
    """Verifies fleet status behavior when cache is empty."""
    telemetry_store.clear()
    case_store.clear()

    response = client.get("/api/fleet/status")
    assert response.status_code == 200
    data = response.json()
    assert data["total_turbines"] == 0
    assert data["active_turbines"] == []
    assert data["total_fleet_power_kw"] == 0.0
    assert data["active_anomalies_count"] == 0
    assert data["open_cases_count"] == 0


def test_fleet_status_with_simulated_fleet(client: TestClient):
    """Verifies fleet summary metrics after simulating multi-turbine operational data."""
    telemetry_store.clear()
    case_store.clear()

    # Simulate S1 healthy fleet
    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(random_seed=42))
    telemetry_store.add_records(result.records)

    response = client.get("/api/fleet/status")
    assert response.status_code == 200
    data = response.json()
    assert data["total_turbines"] > 0
    assert len(data["active_turbines"]) > 0
    assert data["total_fleet_power_kw"] > 0.0
    assert data["average_wind_speed_mps"] > 0.0
    assert data["latest_timestamp"] is not None
