"""Acceptance and Unit Tests for Layer 2 ML Models API Routes (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.2
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §7 (GOV-TRAIN-01)
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_model_status_endpoint(client: TestClient):
    """Verifies that GET /api/models/status returns operational ML configuration."""
    response = client.get("/api/models/status")
    assert response.status_code == 200
    data = response.json()
    assert data["is_trained"] is True
    assert data["model_version"] == "1.0.0"
    assert data["power_algorithm"] == "GradientBoostingRegressor"
    assert data["thermal_algorithm"] == "RandomForestRegressor"
    assert "baseline_stats" in data
    assert data["baseline_stats"]["sigma_p"] > 0


def test_compute_single_residual_vector(client: TestClient):
    """Verifies that POST /api/models/residuals calculates residuals for single record."""
    record = {
        "timestamp": "2026-09-20T12:00:00Z",
        "turbine_id": "WTG-07",
        "wind_speed": 8.5,
        "wind_direction": 225.0,
        "ambient_temp": 28.0,
        "active_power": 1640.0,
        "reactive_power": 110.0,
        "rotor_speed": 14.5,
        "generator_speed": 1450.0,
        "gearbox_bearing_temp": 68.0,
        "generator_stator_temp": 70.0,
        "nacelle_temp": 33.0,
        "pitch_angle": 0.5,
        "is_curtailed": False,
        "operating_status": "Running",
    }
    response = client.post("/api/models/residuals", json=record)
    assert response.status_code == 200
    data = response.json()
    assert "expected_power_kw" in data
    assert "residual_power_kw" in data
    assert "z_power" in data
    assert "expected_gb_temp_c" in data
    assert "residual_gb_temp_c" in data
    assert "z_gb" in data


def test_compute_batch_residuals(client: TestClient):
    """Verifies that POST /api/models/residuals calculates residuals for batch of records."""
    records = [
        {
            "timestamp": f"2026-09-20T12:{i*10:02d}:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": 8.0,
            "ambient_temp": 25.0,
            "active_power": 1500.0,
            "rotor_speed": 14.0,
            "generator_speed": 1400.0,
            "gearbox_bearing_temp": 60.0,
            "generator_stator_temp": 65.0,
            "pitch_angle": 0.5,
            "is_curtailed": False,
        }
        for i in range(3)
    ]
    response = client.post("/api/models/residuals", json=records)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3


def test_model_training_endpoint_prohibited(client: TestClient):
    """GOV-TRAIN-01: Verifies that runtime model retraining (POST /api/models/train) is NOT exposed."""
    response = client.post("/api/models/train")
    # Must be 404 or 405 (Not Found / Method Not Allowed), proving it is NOT a valid Phase 6 route
    assert response.status_code in (404, 405)
