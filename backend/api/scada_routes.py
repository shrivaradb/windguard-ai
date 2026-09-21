"""Phase 1 REST API Endpoints for SCADA Ingestion, Simulation, and Telemetry Querying.

Source of Truth:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/14_implementation_plan.md Phase 1
"""

import io
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
import pandas as pd
from pydantic import BaseModel, Field

from backend.config import settings
from backend.data.dataset_loader import SCADADataLoader
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import (
    BenchmarkScenarioType,
    GroundTruthLabel,
    SimulationConfig,
    TelemetryRecord,
    ValidationSummary,
)
from backend.storage.telemetry_store import telemetry_store

router = APIRouter(prefix="/api", tags=["SCADA Ingestion & Simulation"])
data_loader = SCADADataLoader()
simulator = SCADASimulator()


class IngestRequest(BaseModel):
    """Payload for direct JSON telemetry ingestion."""
    records: List[Dict[str, Any]] = Field(..., description="List of raw or formatted telemetry dictionaries")


class IngestResponse(BaseModel):
    """Response payload after processing telemetry ingestion."""
    status: str
    summary: ValidationSummary
    ingested_count: int
    message: str


class ScenarioCatalogItem(BaseModel):
    """Metadata describing an available benchmark scenario."""
    scenario_id: BenchmarkScenarioType
    name: str
    category: str
    description: str
    injected_subsystem: Optional[str]
    is_fault: bool


class SimulateResponse(BaseModel):
    """Response payload after executing a simulation scenario."""
    status: str
    scenario: BenchmarkScenarioType
    total_records: int
    ground_truth: GroundTruthLabel
    generated_at: str
    persisted_file: Optional[str] = None
    sample_records: List[TelemetryRecord]


@router.get("/scada/scenarios", response_model=List[ScenarioCatalogItem])
def list_benchmark_scenarios() -> List[ScenarioCatalogItem]:
    """Returns the catalog of 5 documented benchmark operational scenarios."""
    return [
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S1_BASELINE_HEALTHY,
            name="Baseline Healthy Operation & Weather Transients",
            category="Healthy Baseline",
            description="Multi-turbine fleet operating under normal weather transients and thermal dissipation physics.",
            injected_subsystem=None,
            is_fault=False
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
            name="Gearbox High-Speed Bearing Friction Degradation",
            category="Mechanical Failure",
            description="High-speed shaft bearing friction degradation causing thermal excursion (+16.5°C) on WTG-07.",
            injected_subsystem="DRIVETRAIN",
            is_fault=True
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S3_PITCH_ASYMMETRY,
            name="Pitch Asymmetry / Aerodynamic Conversion Loss",
            category="Aerodynamic Fault",
            description="Blade pitch angle misalignment (+2.5°) causing 18% aerodynamic power conversion deficit on WTG-03.",
            injected_subsystem="AERODYNAMIC_ROTOR",
            is_fault=True
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S4_GRID_CURTAILMENT_HEATWAVE,
            name="Grid Curtailment & Ambient Summer Heatwave",
            category="Grid & Environmental Context",
            description="Grid operator active power setpoint capping (1000 kW) during summer heatwave (>=40°C). Not an equipment failure.",
            injected_subsystem="GRID_DISPATCH",
            is_fault=False
        ),
        ScenarioCatalogItem(
            scenario_id=BenchmarkScenarioType.S5_SENSOR_DROPOUT,
            name="Sensor Dropout & Thermocouple Disconnection",
            category="Instrumentation Fault",
            description="Thermocouple sensor failure on WTG-09 yielding unphysical readings violating thermal plausibility.",
            injected_subsystem="SENSOR_AUXILIARY",
            is_fault=True
        )
    ]


@router.post("/scada/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
def ingest_scada_records(payload: IngestRequest) -> IngestResponse:
    """Ingests, validates, standardizes, and caches raw SCADA records from a JSON list."""
    if not payload.records:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Records list cannot be empty.")

    valid_records, summary = data_loader.load_from_dicts(payload.records)
    telemetry_store.add_records(valid_records)

    msg = f"Processed {summary.total_records} records: {summary.accepted_records} accepted, {summary.rejected_records} rejected, {summary.interpolated_values_count} values interpolated."

    return IngestResponse(
        status="success" if summary.accepted_records > 0 else "rejected",
        summary=summary,
        ingested_count=len(valid_records),
        message=msg
    )


@router.post("/scada/ingest/file", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest_scada_file(file: UploadFile = File(...)) -> IngestResponse:
    """Ingests SCADA records from an uploaded CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files (.csv) are currently supported for file upload."
        )

    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse uploaded CSV: {err}"
        )

    valid_records, summary = data_loader.process_dataframe(df)
    telemetry_store.add_records(valid_records)

    msg = f"Processed {file.filename} ({summary.total_records} rows): {summary.accepted_records} accepted, {summary.rejected_records} rejected, {summary.interpolated_values_count} values interpolated."

    return IngestResponse(
        status="success" if summary.accepted_records > 0 else "rejected",
        summary=summary,
        ingested_count=len(valid_records),
        message=msg
    )


@router.post("/scada/simulate", response_model=SimulateResponse, status_code=status.HTTP_201_CREATED)
def run_simulation(config: Optional[SimulationConfig] = None) -> SimulateResponse:
    """Executes a physics-informed deterministic simulation run for the requested scenario."""
    cfg = config or SimulationConfig()
    result = simulator.simulate(cfg)

    # Cache generated records in telemetry store
    telemetry_store.add_records(result.records)

    # Persist dataset to synthetic directory
    filename = f"synthetic_{cfg.scenario.value.lower()}_seed{cfg.random_seed}.json"
    persisted_path = settings.PATHS.SYNTHETIC_DIR / filename
    data_loader.export_to_json(result.records, persisted_path)

    # Return summary with first 10 sample records
    sample_records = result.records[:10]

    return SimulateResponse(
        status="success",
        scenario=cfg.scenario,
        total_records=result.total_records,
        ground_truth=result.ground_truth,
        generated_at=result.generated_at,
        persisted_file=str(persisted_path.name),
        sample_records=sample_records
    )


@router.get("/turbines/{turbine_id}/telemetry", response_model=List[TelemetryRecord])
def get_turbine_telemetry(
    turbine_id: str,
    limit: Optional[int] = Query(default=144, ge=1, le=1008, description="Maximum number of latest records to return")
) -> List[TelemetryRecord]:
    """Retrieves cached time-series telemetry records for a specific turbine."""
    records = telemetry_store.get_telemetry(turbine_id, limit=limit)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry records found for turbine '{turbine_id}'."
        )
    return records
