"""Unit Tests for Phase 1 REST API Endpoints."""

from fastapi.testclient import TestClient

from backend.config import settings
from backend.data.schema import BenchmarkScenarioType
from backend.storage.telemetry_store import telemetry_store


def test_health_check_endpoint(test_client: TestClient):
    """Verifies GET /api/health endpoint returns Phase 1 healthy status."""
    response = test_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["phase"] == 1


def test_list_scenarios_endpoint(test_client: TestClient):
    """Verifies GET /api/scada/scenarios returns the 5 documented benchmark scenarios."""
    response = test_client.get("/api/scada/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 5
    ids = [s["scenario_id"] for s in scenarios]
    assert BenchmarkScenarioType.S1_BASELINE_HEALTHY.value in ids
    assert BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION.value in ids
    assert BenchmarkScenarioType.S3_PITCH_ASYMMETRY.value in ids
    assert BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE.value in ids
    assert BenchmarkScenarioType.S5_SENSOR_DROPOUT.value in ids


def test_scada_ingest_json_endpoint(test_client: TestClient, valid_telemetry_dict):
    """Verifies POST /api/scada/ingest with JSON records."""
    payload = {"records": [valid_telemetry_dict]}
    response = test_client.post("/api/scada/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["ingested_count"] == 1
    assert data["summary"]["accepted_records"] == 1


def test_scada_ingest_empty_json_rejected(test_client: TestClient):
    """Verifies POST /api/scada/ingest rejects empty list."""
    response = test_client.post("/api/scada/ingest", json={"records": []})
    assert response.status_code == 400


def test_scada_ingest_file_endpoint(test_client: TestClient):
    """Verifies POST /api/scada/ingest/file with CSV file upload."""
    csv_path = settings.PATHS.BENCHMARKS_DIR / "sample_scada.csv"
    with open(csv_path, "rb") as f:
        response = test_client.post(
            "/api/scada/ingest/file",
            files={"file": ("sample_scada.csv", f, "text/csv")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["summary"]["total_records"] == 10
    assert data["summary"]["accepted_records"] == 10


def test_simulate_endpoint(test_client: TestClient):
    """Verifies POST /api/scada/simulate generates and caches synthetic telemetry."""
    payload = {
        "scenario": BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION.value,
        "num_turbines": 2,
        "num_timesteps": 24,
        "random_seed": 42
    }
    response = test_client.post("/api/scada/simulate", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["total_records"] == 2 * 24
    assert data["ground_truth"]["is_fault"] is True
    assert data["ground_truth"]["affected_turbine_id"] == "WTG-07"


def test_get_turbine_telemetry_endpoint(test_client: TestClient, valid_telemetry_dict):
    """Verifies GET /api/turbines/{turbine_id}/telemetry returns cached records."""
    # Seed data
    test_client.post("/api/scada/ingest", json={"records": [valid_telemetry_dict]})

    response = test_client.get("/api/turbines/WTG-01/telemetry?limit=10")
    assert response.status_code == 200
    records = response.json()
    assert len(records) >= 1
    assert records[0]["turbine_id"] == "WTG-01"


def test_get_turbine_telemetry_not_found(test_client: TestClient):
    """Verifies 404 for unknown turbine with no records."""
    telemetry_store.clear()
    response = test_client.get("/api/turbines/WTG-999/telemetry")
    assert response.status_code == 404
