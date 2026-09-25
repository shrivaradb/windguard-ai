"""Authoritative tests for Universal Real-World SCADA Ingestion Pipeline & Sample Datasets."""

import io
from pathlib import Path
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest

from backend.api.app import create_app
from backend.data.dataset_loader import SCADADataLoader
from backend.data.real_data_pipeline import UniversalSCADAPipeline
from backend.data.schema import OperatingStatus


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def pipeline():
    return UniversalSCADAPipeline()


def test_fuzzy_column_matching_variations(pipeline):
    """Verifies that fuzzy header matcher recognizes diverse OEM and open SCADA naming conventions."""
    headers = [
        "Date_and_time",
        "Wspd_Avg (m/s)",
        "P_Active_kW",
        "Temp_Ambient_degC",
        "Gearbox_bearing_temperature",
        "Generator_stator_temperature",
        "Blade_Pitch_Avg",
        "Asset_ID",
    ]
    matched = pipeline.auto_match_columns(headers)

    assert matched["wind_speed"]["raw_column"] == "Wspd_Avg (m/s)"
    assert matched["active_power"]["raw_column"] == "P_Active_kW"
    assert matched["ambient_temp"]["raw_column"] == "Temp_Ambient_degC"
    assert matched["gearbox_bearing_temp"]["raw_column"] == "Gearbox_bearing_temperature"
    assert matched["generator_stator_temp"]["raw_column"] == "Generator_stator_temperature"
    assert matched["pitch_angle"]["raw_column"] == "Blade_Pitch_Avg"
    assert matched["turbine_id"]["raw_column"] == "Asset_ID"
    assert matched["timestamp"]["raw_column"] == "Date_and_time"


def test_flexible_timestamp_parsing(pipeline):
    """Verifies parsing of diverse timestamp formats."""
    # Standard ISO
    ts1 = pipeline.parse_flexible_timestamp("2024-03-15T12:30:00Z")
    assert "2024-03-15" in ts1

    # Standard SQL format
    ts2 = pipeline.parse_flexible_timestamp("2024-03-15 12:30:00")
    assert "2024-03-15" in ts2

    # European format
    ts3 = pipeline.parse_flexible_timestamp("15/03/2024 12:30")
    assert "2024" in ts3

    # Epoch milliseconds
    ts4 = pipeline.parse_flexible_timestamp(1710505800000)
    assert "2024" in ts4


def test_smart_fallback_physics_estimations(pipeline):
    """Verifies that datasets with missing optional sensors are gracefully estimated rather than rejected."""
    df_minimal = pd.DataFrame({
        "time": ["2024-01-01 00:00:00", "2024-01-01 00:10:00", "2024-01-01 00:20:00"],
        "wind_speed": [6.5, 9.0, 14.0],
        "active_power": [450.0, 1200.0, 2000.0],
        "turbine": ["WTG-05", "WTG-05", "WTG-05"]
    })

    records, summary, meta = pipeline.process_dataframe(df_minimal)

    assert summary.accepted_records == 3
    assert len(records) == 3
    # Check that estimated channels are populated with plausible values
    assert records[0].rotor_speed > 0.0
    assert records[0].generator_speed > 0.0
    assert records[0].gearbox_bearing_temp > 25.0
    assert records[0].pitch_angle >= 0.0
    assert records[0].quality_flags is not None
    assert "rotor_speed" in records[0].quality_flags


def test_sample_datasets_catalog_and_loader(client):
    """Verifies GET /api/scada/sample-datasets and POST /api/scada/load-sample/{dataset_id}."""
    res_list = client.get("/api/scada/sample-datasets")
    assert res_list.status_code == 200
    catalog = res_list.json()
    assert len(catalog) >= 3

    dataset_ids = [d["dataset_id"] for d in catalog]
    assert "engie_lahauteborne" in dataset_ids
    assert "kelmarsh_uk" in dataset_ids
    assert "tamilnadu_corridor" in dataset_ids

    # Load Engie sample
    res_load = client.post("/api/scada/load-sample/engie_lahauteborne")
    assert res_load.status_code == 200
    data = res_load.json()
    assert data["status"] == "success"
    assert data["ingested_count"] == 288


def test_inspect_csv_endpoint(client):
    """Verifies POST /api/scada/inspect returns column matching and quality metrics."""
    csv_content = (
        "Date,Wspd,Power_kW,Amb_T\n"
        "2024-01-01 00:00,8.5,1100.5,18.2\n"
        "2024-01-01 00:10,9.2,1350.0,18.4\n"
        "2024-01-01 00:20,10.0,1600.0,18.1\n"
    )
    files = {"file": ("test_turb.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/scada/inspect", files=files)
    assert res.status_code == 200
    inspect_data = res.json()

    assert inspect_data["total_rows"] == 3
    assert inspect_data["total_columns"] == 4
    assert inspect_data["column_mappings"]["wind_speed"]["raw_column"] == "Wspd"
    assert inspect_data["column_mappings"]["active_power"]["raw_column"] == "Power_kW"
    assert inspect_data["column_mappings"]["ambient_temp"]["raw_column"] == "Amb_T"


def test_turbine_id_normalization(pipeline):
    """Verifies that arbitrary turbine ID conventions normalize to clean standard identifiers."""
    assert pipeline.normalize_turbine_id("R80711 (WTG-01)") == "WTG-01"
    assert pipeline.normalize_turbine_id("T06") == "WTG-06"
    assert pipeline.normalize_turbine_id("Turbine_3") == "WTG-03"
    assert pipeline.normalize_turbine_id("WTG04") == "WTG-04"
    assert pipeline.normalize_turbine_id("5") == "WTG-05"
    assert pipeline.normalize_turbine_id(None) == "WTG-01"
    assert pipeline.normalize_turbine_id("") == "WTG-01"


def test_end_to_end_real_data_diagnose(client):
    """Verifies full end-to-end flow: load real dataset -> run diagnose -> verify complete diagnostic schema."""
    # 1. Load real sample dataset
    res_load = client.post("/api/scada/load-sample/engie_lahauteborne")
    assert res_load.status_code == 200

    # 2. Check telemetry is accessible for WTG-01
    res_tel = client.get("/api/turbines/WTG-01/telemetry")
    assert res_tel.status_code == 200
    telemetry = res_tel.json()
    assert len(telemetry) > 0

    # 3. Trigger diagnostic analysis
    res_diag = client.post("/api/turbines/WTG-01/diagnose")
    assert res_diag.status_code == 200
    case = res_diag.json()

    assert case["turbine_id"] == "WTG-01"
    assert "advisory" in case
    advisory = case["advisory"]
    assert "hypotheses" in advisory
    assert len(advisory["hypotheses"]) >= 1
    # Check hypothesis fields match frontend expectations
    for hyp in advisory["hypotheses"]:
        assert "hypothesis" in hyp
        assert "plausibility" in hyp
        assert "grounding_evidence" in hyp
        assert "missing_evidence" in hyp

    assert "citations" in case
    # Check citation fields
    for cit in case["citations"]:
        assert "title" in cit
        assert "section" in cit
        assert "relevance_score" in cit

    assert "derived_analytics" in case
    assert "financial_loss_inr" in case["derived_analytics"]


