"""Acceptance and Unit Tests for System Lifecycle, Health, Readiness & Status (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6 (REQ-SPEC-03)
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_telemetry_store
from backend.storage.telemetry_store import TelemetryStore


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_health_check_endpoint(client: TestClient):
    """Verifies that GET /api/health returns 200 OK and valid health schema."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "WindGuard AI Decision-Support Service"
    assert data["phase"] == 6
    assert data["version"] == "0.6.0"
    assert isinstance(data["uptime_seconds"], (int, float))
    assert "timestamp" in data


def test_readiness_check_endpoint_all_ready(client: TestClient):
    """Verifies that GET /api/ready returns 200 OK when all subsystems are operational."""
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["status"] == "READY"
    assert data["phase"] == 6
    subsystems = data["subsystems"]
    assert "telemetry_cache" in subsystems
    assert "ml_models" in subsystems
    assert "knowledge_base" in subsystems
    assert "case_store" in subsystems
    assert "tariff_registry" in subsystems
    assert subsystems["telemetry_cache"]["ready"] is True
    assert subsystems["ml_models"]["ready"] is True
    assert subsystems["knowledge_base"]["ready"] is True
    assert subsystems["case_store"]["ready"] is True
    assert subsystems["tariff_registry"]["ready"] is True


def test_system_status_endpoint(client: TestClient):
    """Verifies that GET /api/status returns detailed operational summary."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["version"] == "0.6.0"
    assert "active_tariff" in data
    assert data["active_tariff"]["applied_rate_inr_per_kwh"] > 0
    assert data["model_version"] == "1.0.0"
    assert data["total_indexed_chunks"] > 0
    assert isinstance(data["total_cases_stored"], int)


def test_openapi_schema_conformance(client: TestClient):
    """Verifies that OpenAPI schema is properly registered and accessible."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    paths = schema["paths"]
    assert "/api/health" in paths
    assert "/api/ready" in paths
    assert "/api/turbines/{turbine_id}/diagnose" in paths
    assert "/api/cases" in paths
    assert "/api/tariffs" in paths
    assert "/api/rag/query" in paths
    assert "/api/demo/stage/{stage_id}" in paths
