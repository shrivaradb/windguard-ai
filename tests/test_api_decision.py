"""Acceptance and Unit Tests for Operator Decision & HITL Review Actions (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/10_data_architecture.md §4.3
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-04, REQ-SPEC-02)
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


def test_operator_decision_acknowledge(client: TestClient):
    """Verifies that recording ACKNOWLEDGE updates case status and appends decision."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    created = client.post("/api/turbines/WTG-07/diagnose").json()
    case_id = created["case_id"]

    decision_payload = {
        "action": "ACKNOWLEDGE",
        "operator_id": "OPERATOR_RAVI_01",
        "notes": "Acknowledged initial gearbox temperature rise. Monitoring next 3 intervals.",
    }
    resp = client.post(f"/api/cases/{case_id}/decision", json=decision_payload)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "ACKNOWLEDGED"
    assert len(updated["operator_decisions"]) == 1
    dec = updated["operator_decisions"][0]
    assert dec["action"] == "ACKNOWLEDGE"
    assert dec["operator_id"] == "OPERATOR_RAVI_01"
    assert "Acknowledged initial" in dec["notes"]


def test_sequential_hitl_decisions_append_only(client: TestClient):
    """Verifies that multiple operator decisions are stored in append-only history."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    created = client.post("/api/turbines/WTG-07/diagnose").json()
    case_id = created["case_id"]

    # Step 1: Acknowledge
    client.post(
        f"/api/cases/{case_id}/decision",
        json={"action": "ACKNOWLEDGE", "notes": "Seen and noted."},
    )

    # Step 2: Investigate
    client.post(
        f"/api/cases/{case_id}/decision",
        json={"action": "INVESTIGATE", "notes": "Dispatched technician to check lube oil level."},
    )

    # Step 3: Escalate
    client.post(
        f"/api/cases/{case_id}/decision",
        json={"action": "ESCALATE", "notes": "Ferrographic debris detected; scheduled bearing replacement."},
    )

    # Step 4: Dismiss / Close triage
    final_resp = client.post(
        f"/api/cases/{case_id}/decision",
        json={"action": "DISMISS", "notes": "Maintenance executed and physical inspection completed; closing case."},
    )

    assert final_resp.status_code == 200
    final_case = final_resp.json()
    assert final_case["status"] == "DISMISSED"
    assert len(final_case["operator_decisions"]) == 4
    actions = [d["action"] for d in final_case["operator_decisions"]]
    assert actions == ["ACKNOWLEDGE", "INVESTIGATE", "ESCALATE", "DISMISS"]


def test_decision_with_empty_notes_rejected(client: TestClient):
    """Verifies that decision requests with empty notes are rejected with 422."""
    telemetry_store.clear()
    case_store.clear()

    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    created = client.post("/api/turbines/WTG-07/diagnose").json()
    case_id = created["case_id"]

    resp = client.post(
        f"/api/cases/{case_id}/decision",
        json={"action": "ACKNOWLEDGE", "notes": ""},
    )
    assert resp.status_code == 422


def test_decision_on_unknown_case_returns_404(client: TestClient):
    """Verifies that recording a decision on an unknown case returns 404."""
    case_store.clear()
    resp = client.post(
        "/api/cases/CASE-UNKNOWN-999/decision",
        json={"action": "ACKNOWLEDGE", "notes": "Valid note."},
    )
    assert resp.status_code == 404
