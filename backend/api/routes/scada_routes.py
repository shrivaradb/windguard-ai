"""SCADA Ingestion, Benchmark Simulation & Telemetry Query Routes (Layer 6).

Supports synthetic benchmark generation, flexible universal real-world SCADA ingestion,
interactive column inspection & mapping, and 1-click real dataset loading.
"""

import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
import pandas as pd

from backend.api.dependencies import get_telemetry_store
from backend.api.schemas import (
    CSVInspectResponse,
    IngestRequest,
    IngestResponse,
    SampleDatasetItem,
    ScenarioCatalogItem,
    SimulateResponse,
)
from backend.config import settings
from backend.data.dataset_loader import SCADADataLoader
from backend.data.real_data_pipeline import UniversalSCADAPipeline
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import (
    BenchmarkScenarioType,
    SimulationConfig,
    TelemetryRecord,
)
from backend.storage.telemetry_store import TelemetryStore

router = APIRouter(tags=["SCADA Ingestion & Telemetry"])
data_loader = SCADADataLoader()
simulator = SCADASimulator()
universal_pipeline = UniversalSCADAPipeline()

# Enhanced limits supporting large real-world multi-week/month SCADA datasets
MAX_CSV_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_LEGACY_CSV_ROWS = 2016                   # 14 days @ 10-min resolution (REQ-SPEC-05 legacy limit)
MAX_CSV_ROWS = 50000                         # 50,000 rows (~1 year @ 10-min resolution for universal studio)

# Real-world benchmark dataset catalog
SAMPLE_DATASETS_DIR = Path("data/samples")
SAMPLE_DATASET_CATALOG: List[SampleDatasetItem] = [
    SampleDatasetItem(
        dataset_id="engie_lahauteborne",
        name="Engie La Haute Borne Wind Farm",
        origin="Champagne-Ardenne, France (Open SCADA)",
        turbine_model="Senvion MM82 2.05MW",
        rated_power_kw=2050.0,
        row_count=288,
        description="48-hour 10-min SCADA telemetry capturing turbulent spring wind conditions with early high-speed bearing friction degradation onset.",
        key_features=["Non-linear power curve", "Bearing thermal drift", "Turbulent gusts", "Realistic sensor noise"],
        scenario_type="REAL_WORLD_CMS_ONSET",
    ),
    SampleDatasetItem(
        dataset_id="kelmarsh_uk",
        name="Kelmarsh Wind Farm",
        origin="Northamptonshire, UK (Open Data)",
        turbine_model="Senvion MM92 2.05MW",
        rated_power_kw=2050.0,
        row_count=288,
        description="48-hour SCADA telemetry with National Grid transmission curtailment orders (active power derated to 800 kW via pitch shedding).",
        key_features=["Grid curtailment setpoint", "Aerodynamic pitch regulation", "False-alarm challenge", "UK corridor wind"],
        scenario_type="REAL_WORLD_CURTAILMENT",
    ),
    SampleDatasetItem(
        dataset_id="tamilnadu_corridor",
        name="Tamil Nadu High-Ambient Corridor",
        origin="Muppandal Wind Corridor, India",
        turbine_model="Suzlon S111 / Gamesa G97 2.1MW",
        rated_power_kw=2100.0,
        row_count=288,
        description="48-hour SCADA telemetry under severe summer heatwave (>40°C ambient) demonstrating high ambient thermal derating without false positive trip.",
        key_features=["High ambient heatwave (42°C)", "Thermal equilibrium compensation", "Indian PPA tariff tracking", "Monsoon wind surge"],
        scenario_type="REAL_WORLD_HIGH_AMBIENT",
    ),
]


@router.get("/scada/scenarios", response_model=List[ScenarioCatalogItem], tags=["SCADA Ingestion & Telemetry"])
def list_benchmark_scenarios() -> List[ScenarioCatalogItem]:
    """Returns the catalog of 5 documented benchmark operational scenarios."""
    return [
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S1_BASELINE_HEALTHY,
            name="Baseline Healthy Operation & Weather Transients",
            category="Healthy Baseline",
            description="Multi-turbine fleet operating under normal weather transients and thermal dissipation physics.",
            injected_subsystem=None,
            is_fault=False,
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
            name="Gearbox High-Speed Bearing Friction Degradation",
            category="Mechanical Failure",
            description="High-speed shaft bearing friction degradation causing thermal excursion (+16.5°C) on WTG-07.",
            injected_subsystem="DRIVETRAIN",
            is_fault=True,
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S3_PITCH_ASYMMETRY,
            name="Pitch Asymmetry / Aerodynamic Conversion Loss",
            category="Aerodynamic Fault",
            description="Blade pitch angle misalignment (+2.5°) causing 18% aerodynamic power conversion deficit on WTG-03.",
            injected_subsystem="AERODYNAMIC_ROTOR",
            is_fault=True,
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE,
            name="Grid Curtailment & Ambient Summer Heatwave",
            category="Grid & Environmental Context",
            description="Grid operator active power setpoint capping (1000 kW) during summer heatwave (>=40°C). Not an equipment failure.",
            injected_subsystem="GRID_DISPATCH",
            is_fault=False,
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S5_SENSOR_DROPOUT,
            name="Sensor Dropout & Thermocouple Disconnection",
            category="Instrumentation Fault",
            description="Thermocouple sensor failure on WTG-09 yielding unphysical readings violating thermal plausibility.",
            injected_subsystem="SENSOR_AUXILIARY",
            is_fault=True,
        ),
    ]


@router.get("/scada/sample-datasets", response_model=List[SampleDatasetItem], tags=["SCADA Ingestion & Telemetry"])
def list_sample_datasets() -> List[SampleDatasetItem]:
    """Returns catalog of pre-packaged real-world wind farm benchmark datasets."""
    return SAMPLE_DATASET_CATALOG


@router.post("/scada/load-sample/{dataset_id}", response_model=IngestResponse, tags=["SCADA Ingestion & Telemetry"])
def load_sample_dataset(
    dataset_id: str,
    tel_store: TelemetryStore = Depends(get_telemetry_store),
) -> IngestResponse:
    """Loads a pre-packaged real-world SCADA dataset with 1 click into active fleet telemetry store."""
    file_map = {
        "engie_lahauteborne": SAMPLE_DATASETS_DIR / "real_lahauteborne_sample.csv",
        "kelmarsh_uk": SAMPLE_DATASETS_DIR / "real_kelmarsh_sample.csv",
        "tamilnadu_corridor": SAMPLE_DATASETS_DIR / "real_indian_corridor_sample.csv",
    }

    if dataset_id not in file_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample dataset '{dataset_id}' not found. Available: {list(file_map.keys())}",
        )

    file_path = file_map[dataset_id]
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample dataset file missing on server at: {file_path}",
        )

    try:
        df = pd.read_csv(file_path)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read sample dataset: {err}",
        )

    # Ingest using universal pipeline
    records, summary, meta = universal_pipeline.process_dataframe(df)
    tel_store.add_records(records)

    item = next((d for d in SAMPLE_DATASET_CATALOG if d.dataset_id == dataset_id), None)
    d_name = item.name if item else dataset_id

    return IngestResponse(
        status="success",
        summary=summary,
        ingested_count=len(records),
        message=f"Successfully loaded '{d_name}': {len(records)} records ingested for turbine(s) {meta.get('turbines_ingested', ['WTG-01'])}.",
    )


@router.post("/scada/inspect", response_model=CSVInspectResponse, tags=["SCADA Ingestion & Telemetry"])
async def inspect_scada_csv(
    file: UploadFile = File(...),
) -> CSVInspectResponse:
    """Inspects an uploaded CSV file, auto-detecting column mappings, turbine specs, and data quality."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are supported.",
        )

    content = await file.read()
    if len(content) > MAX_CSV_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded CSV exceeds maximum allowed file size of {MAX_CSV_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV file: {err}",
        )

    inspection = universal_pipeline.inspect_dataframe(df)
    return CSVInspectResponse.model_validate(inspection)


@router.post("/scada/ingest/custom", response_model=IngestResponse, tags=["SCADA Ingestion & Telemetry"])
async def ingest_scada_custom(
    file: UploadFile = File(...),
    column_mapping_json: Optional[str] = Form(default=None),
    rated_power_kw: Optional[float] = Form(default=None),
    tel_store: TelemetryStore = Depends(get_telemetry_store),
) -> IngestResponse:
    """Ingests a real-world CSV with optional user-confirmed column mapping overrides and turbine rating."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are supported.",
        )

    content = await file.read()
    if len(content) > MAX_CSV_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded CSV exceeds maximum allowed file size of {MAX_CSV_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {err}",
        )

    custom_map = None
    if column_mapping_json:
        try:
            custom_map = json.loads(column_mapping_json)
        except Exception:
            custom_map = None

    try:
        records, summary, meta = universal_pipeline.process_dataframe(
            df,
            custom_mapping=custom_map,
            rated_power_kw_override=rated_power_kw
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Universal ingestion error: {err}",
        )

    if summary.accepted_records == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid records could be extracted from the uploaded CSV.",
        )

    tel_store.add_records(records)

    msg = f"Processed {file.filename} ({summary.total_records} rows): {summary.accepted_records} accepted, {summary.rejected_records} rejected, {summary.interpolated_values_count} values interpolated. Turbines: {meta.get('turbines_ingested')}."

    return IngestResponse(
        status="success",
        summary=summary,
        ingested_count=len(records),
        message=msg,
    )


@router.post("/scada/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK, tags=["SCADA Ingestion & Telemetry"])
def ingest_scada_records(
    payload: IngestRequest,
    tel_store: TelemetryStore = Depends(get_telemetry_store),
) -> IngestResponse:
    """Ingests, validates, standardizes, and caches raw SCADA records from a JSON list."""
    if not payload.records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Records list cannot be empty.",
        )

    valid_records, summary = data_loader.load_from_dicts(payload.records)
    if summary.accepted_records == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All {summary.total_records} records failed validation and were rejected.",
        )
    tel_store.add_records(valid_records)

    msg = f"Processed {summary.total_records} records: {summary.accepted_records} accepted, {summary.rejected_records} rejected, {summary.interpolated_values_count} values interpolated."

    return IngestResponse(
        status="success",
        summary=summary,
        ingested_count=len(valid_records),
        message=msg,
    )


@router.post("/scada/ingest/file", response_model=IngestResponse, status_code=status.HTTP_200_OK, tags=["SCADA Ingestion & Telemetry"])
async def ingest_scada_file(
    file: UploadFile = File(...),
    tel_store: TelemetryStore = Depends(get_telemetry_store),
) -> IngestResponse:
    """Ingests SCADA records from an uploaded CSV file with universal format compatibility."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are currently supported for file upload.",
        )

    content = await file.read()
    if len(content) > MAX_CSV_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded CSV exceeds maximum allowed file size of {MAX_CSV_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse uploaded CSV: {err}",
        )

    if len(df) > MAX_LEGACY_CSV_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded CSV contains {len(df)} rows, exceeding maximum batch limit of {MAX_LEGACY_CSV_ROWS} rows.",
        )

    valid_records, summary = data_loader.process_dataframe(df)
    tel_store.add_records(valid_records)

    msg = f"Processed {file.filename} ({summary.total_records} rows): {summary.accepted_records} accepted, {summary.rejected_records} rejected, {summary.interpolated_values_count} values interpolated."

    return IngestResponse(
        status="success" if summary.accepted_records > 0 else "rejected",
        summary=summary,
        ingested_count=len(valid_records),
        message=msg,
    )


@router.post("/scada/simulate", response_model=SimulateResponse, status_code=status.HTTP_201_CREATED, tags=["SCADA Ingestion & Telemetry"])
def run_simulation(
    config: Optional[SimulationConfig] = None,
    tel_store: TelemetryStore = Depends(get_telemetry_store),
) -> SimulateResponse:
    """Executes a physics-informed deterministic simulation run for the requested scenario."""
    cfg = config or SimulationConfig()
    result = simulator.simulate(cfg)

    # Cache generated records in telemetry store
    tel_store.add_records(result.records)

    # Persist dataset to synthetic directory
    filename = f"synthetic_{cfg.scenario.value.lower()}_seed{cfg.random_seed}.json"
    persisted_path = settings.PATHS.SYNTHETIC_DIR / filename
    data_loader.export_to_json(result.records, persisted_path)

    sample_records = result.records[:10]

    return SimulateResponse(
        status="success",
        scenario=cfg.scenario,
        total_records=result.total_records,
        ground_truth=result.ground_truth,
        generated_at=result.generated_at,
        persisted_file=str(persisted_path.name),
        sample_records=sample_records,
    )


@router.get("/turbines/{turbine_id}/telemetry", response_model=List[TelemetryRecord], tags=["SCADA Ingestion & Telemetry"])
def get_turbine_telemetry(
    turbine_id: str,
    limit: Optional[int] = Query(default=144, ge=1, le=5000, description="Maximum number of latest records to return"),
    tel_store: TelemetryStore = Depends(get_telemetry_store),
) -> List[TelemetryRecord]:
    """Retrieves cached time-series telemetry records for a specific turbine."""
    records = tel_store.get_telemetry(turbine_id, limit=limit)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry records found for turbine '{turbine_id}'.",
        )
    return records
