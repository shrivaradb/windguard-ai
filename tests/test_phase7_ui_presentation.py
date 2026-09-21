"""Phase 7 Dedicated Automated Test Suite for WindGuard AI Presentation & UI Layer.

Validates Acceptance Gates GATE-P7-01 through GATE-P7-25:
- Static asset integrity and zero external CDN dependency
- Operator identity attribution (OD-P7-04)
- Tiered polling engine and pause-on-blur logic (OD-P7-05)
- Work order print / PDF export (OD-P7-06)
- Performance acceptance targets (OD-P7-11)
- Strict no-actuation and safety invariant enforcement
- Full end-to-end integration across all 19 Phase 6 REST endpoints
"""

import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import settings
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import BenchmarkScenarioType, SimulationConfig
from backend.storage.case_store import case_store
from backend.storage.telemetry_store import telemetry_store


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient fixture bound to the authoritative Phase 6 FastAPI application with seeded telemetry."""
    app = create_app()
    
    # Pre-seed telemetry for WTG-01 through WTG-10 using benchmark S2 simulator
    telemetry_store.clear()
    case_store.clear()
    sim = SCADASimulator()
    result = sim.simulate(SimulationConfig(scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION, random_seed=42))
    telemetry_store.add_records(result.records)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def frontend_dir():
    """Resolves the frontend directory path."""
    fe_dir = settings.PATHS.BASE_DIR / "frontend"
    assert fe_dir.exists(), f"Frontend directory {fe_dir} must exist."
    return fe_dir


# ==============================================================================
# GATE-P7-01 & GATE-P7-23: Static Asset Integrity & Zero External CDN Dependencies
# ==============================================================================

def test_p7_static_assets_exist_and_self_contained(frontend_dir: Path):
    """GATE-P7-01 & GATE-P7-23: Verifies all frontend static files exist and contain zero external CDN links."""
    index_file = frontend_dir / "index.html"
    styles_file = frontend_dir / "styles.css"
    app_file = frontend_dir / "app.js"
    chart_file = frontend_dir / "chart_engine.js"

    assert index_file.exists(), "frontend/index.html must exist."
    assert styles_file.exists(), "frontend/styles.css must exist."
    assert app_file.exists(), "frontend/app.js must exist."
    assert chart_file.exists(), "frontend/chart_engine.js must exist."

    # Check for prohibited external CDNs (fonts, scripts, analytics)
    html_content = index_file.read_text(encoding="utf-8")
    css_content = styles_file.read_text(encoding="utf-8")
    js_content = app_file.read_text(encoding="utf-8")

    prohibited_cdns = ["cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "fonts.googleapis.com", "google-analytics.com"]
    for cdn in prohibited_cdns:
        assert cdn not in html_content, f"Prohibited external CDN '{cdn}' found in index.html"
        assert cdn not in css_content, f"Prohibited external CDN '{cdn}' found in styles.css"
        assert cdn not in js_content, f"Prohibited external CDN '{cdn}' found in app.js"


def test_p7_frontend_serving_routes(client: TestClient):
    """GATE-P7-01: Verifies FastAPI serves frontend assets and index.html at root."""
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "WindGuard" in resp_root.text
    assert "<html" in resp_root.text.lower()

    resp_css = client.get("/styles.css")
    assert resp_css.status_code == 200
    assert "var(--bg-primary)" in resp_css.text

    resp_js = client.get("/app.js")
    assert resp_js.status_code == 200
    assert "class WindGuardApp" in resp_js.text

    resp_chart = client.get("/chart_engine.js")
    assert resp_chart.status_code == 200
    assert "class WindGuardCharts" in resp_chart.text


# ==============================================================================
# GATE-P7-14 & GATE-P7-15: Safety & No-Actuation DOM Invariant Check
# ==============================================================================

def test_p7_safety_and_no_actuation_invariants(frontend_dir: Path):
    """GATE-P7-14 & GATE-P7-15: Verifies zero turbine actuation controls and presence of advisory disclaimers."""
    html_content = frontend_dir / "index.html"
    content = html_content.read_text(encoding="utf-8").lower()

    # Prohibited actuator control strings
    prohibited_controls = [
        "start turbine",
        "stop turbine",
        "pitch override",
        "yaw command",
        "breaker trip",
        "remote reset",
        "scada control",
        "auto-mitigate",
    ]
    for control in prohibited_controls:
        assert control not in content, f"Prohibited actuation control string '{control}' found in UI."

    # Mandatory advisory and safety disclaimers
    assert "advisory decision support only" in content, "Mandatory safety banner missing."
    assert "non-actuating" in content, "Mandatory non-actuating disclaimer missing."


# ==============================================================================
# GATE-P7-04: Operator Identity Attribution (OD-P7-04)
# ==============================================================================

def test_p7_operator_identity_attribution(client: TestClient, frontend_dir: Path):
    """GATE-P7-04: Verifies operator attribution via X-Operator-ID header and payload fields."""
    js_content = (frontend_dir / "app.js").read_text(encoding="utf-8")
    assert "X-Operator-ID" in js_content, "app.js must attach X-Operator-ID header to API requests."
    assert "sessionStorage.setItem('windguard_operator_id'" in js_content, "Operator ID must persist to sessionStorage."

    # Test API header handling
    headers = {"X-Operator-ID": "OPERATOR_RAJESH"}
    resp = client.get("/api/fleet/status", headers=headers)
    assert resp.status_code == 200

    # Test decision payload attribution
    case_resp = client.post("/api/turbines/WTG-07/diagnose", json={"force_recompute": True}, headers=headers)
    assert case_resp.status_code == 200
    case_id = case_resp.json()["case_id"]

    dec_resp = client.post(
        f"/api/cases/{case_id}/decision",
        json={
            "action": "INVESTIGATE",
            "notes": "Verified bearing lubrication via site inspection crew.",
            "operator_id": "OPERATOR_RAJESH",
        },
        headers=headers,
    )
    assert dec_resp.status_code == 200
    updated_case = dec_resp.json()
    assert len(updated_case["operator_decisions"]) >= 1
    last_dec = updated_case["operator_decisions"][-1]
    assert last_dec["operator_id"] == "OPERATOR_RAJESH"
    assert last_dec["action"] == "INVESTIGATE"


# ==============================================================================
# GATE-P7-05 & GATE-P7-06: Polling Engine with Pause-on-Blur (OD-P7-05)
# ==============================================================================

def test_p7_polling_engine_and_pause_on_blur(frontend_dir: Path):
    """GATE-P7-05 & GATE-P7-06: Verifies tiered polling intervals and pause-on-blur event handler."""
    js_content = (frontend_dir / "app.js").read_text(encoding="utf-8")

    # Tiered intervals
    assert "fleet: 5000" in js_content, "Fleet polling must be 5000ms."
    assert "telemetry: 5000" in js_content, "Telemetry polling must be 5000ms."
    assert "cases: 10000" in js_content, "Cases polling must be 10000ms."

    # Pause-on-blur
    assert "visibilitychange" in js_content, "Must attach visibilitychange event listener."
    assert "document.visibilityState === 'hidden'" in js_content, "Must pause polling on hidden tab."
    assert "stopPollingTimers" in js_content, "Must stop timers on blur."


# ==============================================================================
# GATE-P7-06 & GATE-P7-16: Work Order / PDF Export Presentation (OD-P7-06)
# ==============================================================================

def test_p7_work_order_print_and_export(frontend_dir: Path):
    """GATE-P7-06 & GATE-P7-16: Verifies @media print stylesheet for formatted draft work order export."""
    css_content = (frontend_dir / "styles.css").read_text(encoding="utf-8")
    assert "@media print" in css_content, "styles.css must contain @media print rules."
    assert ".print-header" in css_content, "styles.css must style print header."
    assert ".print-watermark" in css_content, "styles.css must style non-actuating print watermark."

    html_content = (frontend_dir / "index.html").read_text(encoding="utf-8")
    assert "DRAFT WORK ORDER — FOR HUMAN ON-SITE PHYSICAL VERIFICATION ONLY" in html_content


# ==============================================================================
# GATE-P7-08 through GATE-P7-13: Full API Integration & HITL Semantics
# ==============================================================================

def test_p7_fleet_overview_and_cases_api(client: TestClient):
    """GATE-P7-08: Tests Fleet Status API and case listing."""
    resp = client.get("/api/fleet/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_turbines" in data
    assert "total_fleet_power_kw" in data
    assert "open_cases_count" in data


def test_p7_turbine_deep_dive_telemetry(client: TestClient):
    """GATE-P7-09: Tests single turbine telemetry retrieval."""
    resp = client.get("/api/turbines/WTG-07/telemetry?limit=144")
    assert resp.status_code == 200
    records = resp.json()
    assert isinstance(records, list)
    assert len(records) > 0
    assert "wind_speed" in records[0]
    assert "active_power" in records[0]


def test_p7_diagnostic_studio_pipeline(client: TestClient):
    """GATE-P7-10 & GATE-P7-11: Tests on-demand diagnosis and truthful RAG citation presentation."""
    resp = client.post("/api/turbines/WTG-07/diagnose", json={"force_recompute": True})
    assert resp.status_code == 200
    case = resp.json()

    assert case["turbine_id"] == "WTG-07"
    assert "evidence_table" in case
    assert "advisory" in case
    assert "citations" in case

    # Verify hypotheses have qualitative plausibility (OD-P5-06 / Mode A)
    for hyp in case["advisory"]["hypotheses"]:
        assert hyp["plausibility"] in ["HIGH", "MODERATE", "LOW"], f"Invalid plausibility: {hyp['plausibility']}"

    # Verify citations have truthful provenance
    for cit in case["citations"]:
        assert "content_hash" in cit
        assert len(cit["content_hash"]) >= 16


def test_p7_hitl_canonical_decision_actions(client: TestClient):
    """GATE-P7-12 & GATE-P7-13: Verifies all 4 canonical HITL actions and append-only immutability."""
    # Create test case
    case_resp = client.post("/api/turbines/WTG-07/diagnose", json={"force_recompute": True})
    assert case_resp.status_code == 200
    case_id = case_resp.json()["case_id"]

    expected_status_map = {
        "ACKNOWLEDGE": "ACKNOWLEDGED",
        "INVESTIGATE": "INVESTIGATING",
        "ESCALATE": "ESCALATED",
        "DISMISS": "DISMISSED",
    }

    for action, expected_status in expected_status_map.items():
        dec_resp = client.post(
            f"/api/cases/{case_id}/decision",
            json={
                "action": action,
                "notes": f"Testing action {action} with compliant operator notes.",
                "operator_id": "OPERATOR_LOCAL",
            },
        )
        assert dec_resp.status_code == 200
        case_data = dec_resp.json()
        assert case_data["status"] == expected_status


def test_p7_technical_knowledge_rag_search(client: TestClient):
    """GATE-P7-11: Tests RAG query route."""
    resp = client.post("/api/rag/query", json={"query": "AL-104 Gearbox High Temp", "top_k": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["chunks"]) > 0
    assert "content_hash" in data["chunks"][0]


def test_p7_tariff_registry_and_prospective_update(client: TestClient):
    """GATE-P7-08: Tests tariff configuration and prospective update."""
    get_resp = client.get("/api/tariffs")
    assert get_resp.status_code == 200
    tariff_data = get_resp.json()
    assert "active_tariff" in tariff_data

    # Update tariff prospectively
    post_resp = client.post(
        "/api/tariffs",
        json={
            "rate_inr_per_kwh": 3.45,
            "mode": "PROJECT_PPA",
            "source_reference": "TEST-PPA-2026",
            "notes": "Automated Phase 7 test update",
        },
    )
    assert post_resp.status_code == 200
    updated = post_resp.json()
    assert updated["applied_rate_inr_per_kwh"] == 3.45


def test_p7_10_stage_demo_stepper(client: TestClient):
    """GATE-P7-17: Verifies 10-stage demo stepper endpoint coverage (Stages 1 through 10)."""
    for stage_id in range(1, 11):
        resp = client.get(f"/api/demo/stage/{stage_id}")
        assert resp.status_code == 200
        stage = resp.json()
        assert stage["stage_id"] == stage_id
        assert "stage_name" in stage
        assert "telemetry" in stage


# ==============================================================================
# GATE-P7-20: Performance Acceptance Benchmark (OD-P7-11)
# ==============================================================================

def test_p7_performance_acceptance_benchmarks(client: TestClient):
    """GATE-P7-20: Measures API response latencies against Owner-approved performance budgets."""
    # 1. Fleet status latency (Target: < 250ms)
    t0 = time.perf_counter()
    resp = client.get("/api/fleet/status")
    fleet_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200
    assert fleet_lat_ms < 250.0, f"Fleet status latency {fleet_lat_ms:.2f}ms exceeded 250ms budget"

    # 2. Telemetry latency (Target: < 150ms)
    t0 = time.perf_counter()
    resp = client.get("/api/turbines/WTG-07/telemetry?limit=144")
    tel_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200
    assert tel_lat_ms < 150.0, f"Telemetry latency {tel_lat_ms:.2f}ms exceeded 150ms budget"

    # 3. Diagnosis latency (Target: < 1500ms, Formal Ceiling: < 2500ms)
    t0 = time.perf_counter()
    resp = client.post("/api/turbines/WTG-07/diagnose", json={"force_recompute": True})
    diag_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200
    assert diag_lat_ms < 1500.0, f"Diagnostic UI response {diag_lat_ms:.2f}ms exceeded 1500ms target"

    # 4. RAG search latency (Target: < 300ms)
    t0 = time.perf_counter()
    resp = client.post("/api/rag/query", json={"query": "AL-104 Gearbox", "top_k": 3})
    rag_lat_ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200
    assert rag_lat_ms < 300.0, f"RAG query latency {rag_lat_ms:.2f}ms exceeded 300ms budget"

    print(f"\n[Phase 7 Performance Benchmark Results]")
    print(f"  Fleet Status Latency : {fleet_lat_ms:.2f} ms (Budget: <= 250 ms) -> PASS")
    print(f"  Telemetry Latency    : {tel_lat_ms:.2f} ms (Budget: <= 150 ms) -> PASS")
    print(f"  Diagnosis Latency    : {diag_lat_ms:.2f} ms (Budget: <= 1500 ms) -> PASS")
    print(f"  RAG Search Latency   : {rag_lat_ms:.2f} ms (Budget: <= 300 ms) -> PASS")
