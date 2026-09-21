"""SCADA Ingestion, Benchmark Simulation & Telemetry Query Routes (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6 (REQ-SPEC-05)
"""

import io
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
import pandas as pd

from backend.api.dependencies import get_telemetry_store
from backend.api.schemas import (
    IngestRequest,
    IngestResponse,
    ScenarioCatalogItem,
    SimulateResponse,
)
from backend.config import settings
from backend.data.dataset_loader import SCADADataLoader
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

# Limits from REQ-SPEC-05
MAX_CSV_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_CSV_ROWS = 2016                          # 14 days @ 10-min resolution


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
    """Ingests SCADA records from an uploaded CSV file with strict REQ-SPEC-05 size and row limits."""
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

    if len(df) > MAX_CSV_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded CSV contains {len(df)} rows, exceeding maximum batch limit of {MAX_CSV_ROWS} rows.",
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
    limit: Optional[int] = Query(default=144, ge=1, le=1008, description="Maximum number of latest records to return"),
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
