"""Permanent SCADA Actuation Prohibition & Negative API Tests (Layer 6).

Source:
- docs/08_system_architecture.md ADR-003
- docs/06_prd.md NG-01
- docs/07_srs.md §3.7
- docs/PHASE_6_SCOPE_REVIEW.md §12
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §11
"""

import re
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


def test_negative_actuation_route_catalog_scan():
    """NEG-API-01: Verifies that ZERO control/actuation endpoints exist in the FastAPI routing table."""
    app = create_app()
    forbidden_pattern = re.compile(
        r"(actuat|control|pitch_cmd|yaw_cmd|torque_cmd|curtail_cmd|breaker|trip|start_turbine|stop_turbine|setpoint_write|dispatch_crew)",
        re.IGNORECASE,
    )

    registered_paths = [route.path for route in app.routes if hasattr(route, "path")]

    violations = []
    for path in registered_paths:
        if forbidden_pattern.search(path):
            violations.append(path)

    assert len(violations) == 0, f"Found forbidden actuation routes: {violations}"


def test_safety_disclaimer_present_in_all_advisories(client: TestClient):
    """NEG-API-02: Verifies that every diagnostic case contains the mandatory non-actuating safety disclaimer."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    diag_resp = client.post("/api/turbines/WTG-07/diagnose")
    assert diag_resp.status_code == 200
    case = diag_resp.json()

    disclaimer = case["advisory"]["safety_disclaimer"]
    assert "advisory only" in disclaimer.lower()
    assert "does not issue automated control commands" in disclaimer.lower()
    assert "human engineer verification" in disclaimer.lower()


def test_recommended_actions_marked_non_actuating(client: TestClient):
    """NEG-API-03: Verifies that all recommended actions assert is_non_actuating=True and requires_human_approval=True."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    diag_resp = client.post("/api/turbines/WTG-07/diagnose")
    assert diag_resp.status_code == 200
    case = diag_resp.json()

    actions = case["advisory"]["recommended_actions"]
    assert len(actions) > 0
    for act in actions:
        assert act["is_non_actuating"] is True
        assert act["requires_human_approval"] is True
