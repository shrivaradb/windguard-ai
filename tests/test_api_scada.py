"""Acceptance and Unit Tests for SCADA Ingestion, Upload Limits & Simulation (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.1
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6 (REQ-SPEC-05)
"""

import io
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig
from backend.storage.telemetry_store import telemetry_store


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_list_scenarios_endpoint(client: TestClient):
    """Verifies that GET /api/scada/scenarios returns all 5 documented scenarios."""
    response = client.get("/api/scada/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 5
    ids = [s["scenario_id"] for s in scenarios]
    assert "S1_BASELINE_HEALTHY" in ids
    assert "S2_GEARBOX_BEARING_DEGRADATION" in ids
    assert "S3_PITCH_ASYMMETRY" in ids
    assert "S4_GRID_CURTAILMENT_HEATWAVE" in ids
    assert "S5_SENSOR_DROPOUT" in ids


def test_json_telemetry_ingestion(client: TestClient):
    """Verifies that POST /api/scada/ingest accepts valid JSON telemetry records."""
    telemetry_store.clear()
    payload = {
        "records": [
            {
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
        ]
    }
    response = client.post("/api/scada/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["ingested_count"] == 1
    assert data["summary"]["accepted_records"] == 1

    # Verify telemetry query
    tel_resp = client.get("/api/turbines/WTG-07/telemetry")
    assert tel_resp.status_code == 200
    records = tel_resp.json()
    assert len(records) == 1
    assert records[0]["turbine_id"] == "WTG-07"


def test_empty_json_ingestion_rejected(client: TestClient):
    """Verifies that empty JSON ingestion payloads are rejected with 422 or 400."""
    response = client.post("/api/scada/ingest", json={"records": []})
    assert response.status_code in (400, 422)


def test_csv_file_upload_ingestion(client: TestClient):
    """Verifies that POST /api/scada/ingest/file accepts valid CSV files."""
    telemetry_store.clear()
    df = pd.DataFrame([
        {
            "timestamp": "2026-09-20T12:00:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": 9.0,
            "wind_direction": 180.0,
            "ambient_temp": 25.0,
            "active_power": 1700.0,
            "reactive_power": 100.0,
            "rotor_speed": 14.8,
            "generator_speed": 1480.0,
            "gearbox_bearing_temp": 63.0,
            "generator_stator_temp": 68.0,
            "nacelle_temp": 30.0,
            "pitch_angle": 0.5,
            "is_curtailed": False,
            "operating_status": "Running",
        }
    ])
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    response = client.post(
        "/api/scada/ingest/file",
        files={"file": ("test_scada.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["ingested_count"] == 1


def test_csv_upload_row_limit_enforced(client: TestClient):
    """Verifies that CSV uploads exceeding REQ-SPEC-05 row limit (2016 rows) are rejected."""
    # Create DataFrame with 2050 rows (exceeds 2016 limit)
    rows = [
        {
            "timestamp": f"2026-09-20T{i%24:02d}:00:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": 8.0,
            "active_power": 1500.0,
            "ambient_temp": 25.0,
            "gearbox_bearing_temp": 60.0,
            "generator_stator_temp": 65.0,
            "pitch_angle": 0.5,
            "rotor_speed": 14.0,
            "generator_speed": 1400.0,
            "is_curtailed": False,
        }
        for i in range(2050)
    ]
    df = pd.DataFrame(rows)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    response = client.post(
        "/api/scada/ingest/file",
        files={"file": ("oversized.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 400
    assert "exceeding maximum batch limit" in response.json()["message"]


def test_simulation_execution_endpoint(client: TestClient):
    """Verifies that POST /api/scada/simulate generates benchmark telemetry."""
    telemetry_store.clear()
    payload = {
        "scenario": "S2_GEARBOX_BEARING_DEGRADATION",
        "num_turbines": 5,
        "duration_hours": 6.0,
        "random_seed": 42,
    }
    response = client.post("/api/scada/simulate", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["scenario"] == "S2_GEARBOX_BEARING_DEGRADATION"
    assert data["total_records"] > 0
    assert len(data["sample_records"]) > 0


def test_telemetry_query_404_for_unknown_turbine(client: TestClient):
    """Verifies that GET /api/turbines/{id}/telemetry returns 404 for unknown turbine."""
    telemetry_store.clear()
    response = client.get("/api/turbines/UNKNOWN_TURBINE/telemetry")
    assert response.status_code == 404
