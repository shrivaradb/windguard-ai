"""Acceptance and Unit Tests for 10-Stage Demo Stepper API Routes (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-10)
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.mark.parametrize("stage_id", range(1, 11))
def test_get_demo_stages_1_through_10(client: TestClient, stage_id: int):
    """Verifies that all 10 demo stepper stages return 200 OK and valid telemetry states."""
    response = client.get(f"/api/demo/stage/{stage_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["stage_id"] == stage_id
    assert "stage_name" in data
    assert "scenario_type" in data
    assert "telemetry" in data
    assert "expected_status" in data
    assert data["telemetry"]["wind_speed"] >= 0.0


def test_invalid_demo_stage_returns_404_or_422(client: TestClient):
    """Verifies that stage_id outside 1-10 returns 404 or 422."""
    resp_0 = client.get("/api/demo/stage/0")
    assert resp_0.status_code in (404, 422)

    resp_11 = client.get("/api/demo/stage/11")
    assert resp_11.status_code in (404, 422)
