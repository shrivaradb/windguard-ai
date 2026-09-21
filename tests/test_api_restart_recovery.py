"""Persistence Recovery & Service Restart Determinism Tests (Layer 6).

Source:
- docs/08_system_architecture.md ADR-006
- docs/09_technical_design.md §4
- docs/10_data_architecture.md §6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §10
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig
from backend.storage.case_store import CaseStore, case_store
from backend.storage.telemetry_store import telemetry_store


def test_server_restart_case_store_recovery(tmp_path: Path):
    """Verifies that all stored cases and operator decisions survive service restart."""
    telemetry_store.clear()
    case_store.clear()

    # Step 1: Initial Service Session
    app1 = create_app()
    client1 = TestClient(app1)

    # Ingest S2 scenario telemetry
    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    # Diagnose case on Session 1
    c1 = client1.post("/api/turbines/WTG-07/diagnose").json()
    case_id = c1["case_id"]

    # Record HITL decision on Session 1
    client1.post(
        f"/api/cases/{case_id}/decision",
        json={"action": "INVESTIGATE", "notes": "Technician dispatched to inspect gearbox."},
    )

    # Step 2: Simulate Full Service Restart (New FastAPI instance and reloaded CaseStore)
    app2 = create_app()
    client2 = TestClient(app2)

    # Step 3: Verify Case is immediately accessible on Session 2
    resp_cases = client2.get("/api/cases")
    assert resp_cases.status_code == 200
    cases_data = resp_cases.json()
    assert cases_data["total_count"] >= 1

    resp_case = client2.get(f"/api/cases/{case_id}")
    assert resp_case.status_code == 200
    reloaded_case = resp_case.json()
    assert reloaded_case["case_id"] == case_id
    assert reloaded_case["turbine_id"] == "WTG-07"
    assert reloaded_case["status"] == "INVESTIGATING"
    assert len(reloaded_case["operator_decisions"]) == 1
    assert reloaded_case["operator_decisions"][0]["action"] == "INVESTIGATE"
