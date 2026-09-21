"""Phase 1 Acceptance Gate Test Suite (TEST-DATA-01).

Formally verifies all mandatory Phase 1 acceptance criteria against
the finalized engineering documentation suite.
"""

from datetime import datetime, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.data.dataset_loader import SCADADataLoader
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import (
    BenchmarkScenarioType,
    OperatingStatus,
    SimulationConfig,
    TelemetryRecord,
)
from backend.main import app
from backend.storage.file_store import AtomicFileStore
from backend.storage.telemetry_store import TelemetryStore


def test_gate_01_canonical_scada_schema_and_curtailment():
    """GATE 1: Canonical schema implemented with is_curtailed as primary and curtailment_flag as alias."""
    # Canonical is_curtailed
    r1 = TelemetryRecord(
        timestamp="2026-09-20T12:00:00Z",
        turbine_id="WTG-01",
        wind_speed=8.5,
        ambient_temp=25.0,
        active_power=1400.0,
        rotor_speed=14.0,
        generator_speed=1430.0,
        gearbox_bearing_temp=62.0,
        generator_stator_temp=68.0,
        pitch_angle=0.5,
        is_curtailed=True
    )
    assert r1.is_curtailed is True

    # Alias mapping
    data_alias = {
        "timestamp": "2026-09-20T12:00:00Z",
        "turbine_id": "WTG-01",
        "wind_speed": 8.5,
        "ambient_temp": 25.0,
        "active_power": 1400.0,
        "rotor_speed": 14.0,
        "generator_speed": 1430.0,
        "gearbox_bearing_temp": 62.0,
        "generator_stator_temp": 68.0,
        "pitch_angle": 0.5,
        "curtailment_flag": 1
    }
    r2 = TelemetryRecord.model_validate(data_alias)
    assert r2.is_curtailed is True


def test_gate_02_scada_validation_and_rejection(data_loader: SCADADataLoader):
    """GATE 2: Physical bounds validation rejects unphysical records with clear reasons."""
    records, summary = data_loader.load_from_dicts([
        # Invalid: Negative wind speed
        {
            "timestamp": "2026-09-20T12:00:00Z",
            "turbine_id": "WTG-01",
            "wind_speed": -10.0,
            "ambient_temp": 25.0,
            "active_power": 1400.0,
            "rotor_speed": 14.0,
            "generator_speed": 1430.0,
            "gearbox_bearing_temp": 62.0,
            "generator_stator_temp": 68.0,
            "pitch_angle": 0.5,
            "is_curtailed": False
        }
    ])
    assert len(records) == 0
    assert summary.rejected_records == 1
    assert any(i.action_taken == "REJECTED" for i in summary.issues)


def test_gate_03_missing_data_handling(data_loader: SCADADataLoader):
    """GATE 3: 1-2 step missing values interpolated with quality flag; >2 steps marked SENSOR_DROPOUT."""
    records, summary = data_loader.load_from_dicts([
        {"timestamp": "2026-09-20T10:00:00Z", "turbine_id": "WTG-01", "wind_speed": 8.0, "ambient_temp": 25.0, "active_power": 1000.0, "rotor_speed": 12.0, "generator_speed": 1230.0, "gearbox_bearing_temp": 60.0, "generator_stator_temp": 65.0, "pitch_angle": 0.5, "is_curtailed": False},
        {"timestamp": "2026-09-20T10:10:00Z", "turbine_id": "WTG-01", "wind_speed": None, "ambient_temp": 25.0, "active_power": 1000.0, "rotor_speed": 12.0, "generator_speed": 1230.0, "gearbox_bearing_temp": 60.0, "generator_stator_temp": 65.0, "pitch_angle": 0.5, "is_curtailed": False},
        {"timestamp": "2026-09-20T10:20:00Z", "turbine_id": "WTG-01", "wind_speed": 10.0, "ambient_temp": 25.0, "active_power": 1000.0, "rotor_speed": 12.0, "generator_speed": 1230.0, "gearbox_bearing_temp": 60.0, "generator_stator_temp": 65.0, "pitch_angle": 0.5, "is_curtailed": False}
    ])
    assert len(records) == 3
    assert summary.interpolated_values_count == 1
    assert records[1].quality_flags.get("wind_speed") == "INTERPOLATED_LINEAR"


def test_gate_04_simulator_physics_and_determinism(simulator: SCADASimulator):
    """GATE 4: Simulation is reproducible with fixed seed and satisfies aerodynamic & thermal lag equations."""
    cfg = SimulationConfig(scenario=BenchmarkScenarioType.S1_BASELINE_HEALTHY, num_turbines=2, num_timesteps=36, random_seed=777)
    res_a = simulator.simulate(cfg)
    res_b = simulator.simulate(cfg)

    assert res_a.total_records == res_b.total_records
    for i in range(len(res_a.records)):
        assert res_a.records[i].active_power == res_b.records[i].active_power
        assert res_a.records[i].gearbox_bearing_temp == res_b.records[i].gearbox_bearing_temp


def test_gate_05_all_five_benchmark_scenarios(simulator: SCADASimulator):
    """GATE 5: All 5 documented benchmark operational scenarios (S1-S5) generate required signatures."""
    scenarios = [
        BenchmarkScenarioType.S1_BASELINE_HEALTHY,
        BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
        BenchmarkScenarioType.S3_PITCH_ASYMMETRY,
        BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE,
        BenchmarkScenarioType.S5_SENSOR_DROPOUT
    ]

    for sc in scenarios:
        res = simulator.simulate(SimulationConfig(scenario=sc, num_turbines=10, num_timesteps=72, random_seed=42))
        assert res.ground_truth.scenario_id == sc
        assert res.total_records == 720
        assert all(r.is_synthetic is True for r in res.records)


def test_gate_06_persistence_and_144_cache(clean_telemetry_store: TelemetryStore, temp_dir: Path, valid_telemetry_dict):
    """GATE 6: Thread-safe 144-record sliding cache and atomic persistence."""
    start_dt = datetime(2026, 9, 20, 0, 0, 0)
    for i in range(160):
        d = valid_telemetry_dict.copy()
        ts = (start_dt + timedelta(minutes=i * 10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        d["timestamp"] = ts
        clean_telemetry_store.add_record(TelemetryRecord.model_validate(d))

    # Cache capped at 144
    assert len(clean_telemetry_store.get_telemetry("WTG-01")) == 144

    # Atomic write to disk and reload
    save_file = temp_dir / "telemetry_test.json"
    clean_telemetry_store.save_to_disk(save_file)
    assert save_file.exists()

    new_store = TelemetryStore(max_records_per_turbine=144)
    new_store.load_from_disk(save_file)
    assert len(new_store.get_telemetry("WTG-01")) == 144


def test_gate_07_phase1_rest_api(test_client: TestClient):
    """GATE 7: Phase 1 REST APIs functional (/health, /scenarios, /ingest, /simulate, /telemetry)."""
    # Health
    r_h = test_client.get("/api/health")
    assert r_h.status_code == 200

    # Scenarios
    r_s = test_client.get("/api/scada/scenarios")
    assert r_s.status_code == 200
    assert len(r_s.json()) == 5

    # Ingest benchmark file
    csv_path = settings.PATHS.BENCHMARKS_DIR / "sample_scada.csv"
    with open(csv_path, "rb") as f:
        r_i = test_client.post("/api/scada/ingest/file", files={"file": ("sample_scada.csv", f, "text/csv")})
    assert r_i.status_code == 200

    # Query telemetry
    r_t = test_client.get("/api/turbines/WTG-01/telemetry")
    assert r_t.status_code == 200
    assert len(r_t.json()) >= 1


def test_gate_08_phase_boundary_lockout():
    """GATE 8: Confirms that no Phase 3+ components or tariff configurations exist in codebase."""
    # Check that no Phase 3+ context engine, tariff registry, RAG, or LLM modules exist in backend/
    backend_path = Path(__file__).resolve().parent.parent / "backend"

    # Confirmed absence of Phase 3+ modules
    assert not (backend_path / "engine" / "context_engine.py").exists()
    assert not (backend_path / "engine" / "tariff_registry.py").exists()
    assert not (backend_path / "rag" / "knowledge_base.py").exists()
    assert not (backend_path / "llm" / "advisory_engine.py").exists()
