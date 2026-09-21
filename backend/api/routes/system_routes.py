"""System Health, Readiness Probes & Status Routes for WindGuard AI (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6 (REQ-SPEC-03)
"""

from datetime import datetime, timezone
import time
from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    get_case_store,
    get_knowledge_base,
    get_residual_engine,
    get_tariff_registry,
    get_telemetry_store,
)
from backend.api.schemas import (
    HealthResponse,
    ReadinessResponse,
    SubsystemHealth,
    SystemStatusResponse,
)
from backend.config import settings
from backend.storage.case_store import CaseStore
from backend.storage.telemetry_store import TelemetryStore

router = APIRouter(tags=["System Lifecycle & Diagnostics"])
_STARTUP_TIME = time.time()


@router.get("/health", response_model=HealthResponse, tags=["System Lifecycle & Diagnostics"])
def health_check() -> HealthResponse:
    """System liveness probe returning process uptime and basic service health."""
    uptime = time.time() - _STARTUP_TIME
    iso_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return HealthResponse(
        status="healthy",
        service="WindGuard AI Decision-Support Service",
        version="0.6.0",
        phase=6,
        uptime_seconds=round(uptime, 2),
        timestamp=iso_now,
    )


@router.get("/ready", response_model=ReadinessResponse, tags=["System Lifecycle & Diagnostics"])
def readiness_check(
    tel_store: TelemetryStore = Depends(get_telemetry_store),
    case_st: CaseStore = Depends(get_case_store),
) -> ReadinessResponse:
    """Comprehensive readiness probe verifying internal subsystem dependencies."""
    iso_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    subsystems = {}
    all_ready = True

    # 1. Telemetry Cache Probe
    t0 = time.perf_counter()
    try:
        _ = tel_store.get_turbine_ids()
        subsystems["telemetry_cache"] = SubsystemHealth(
            name="TelemetryStore",
            ready=True,
            message="Sliding window telemetry cache operational",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )
    except Exception as err:
        all_ready = False
        subsystems["telemetry_cache"] = SubsystemHealth(
            name="TelemetryStore",
            ready=False,
            message=f"Telemetry cache failure: {err}",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )

    # 2. ML Residual Engine Probe
    t0 = time.perf_counter()
    try:
        engine = get_residual_engine()
        subsystems["ml_models"] = SubsystemHealth(
            name="ResidualEngine",
            ready=True,
            message="Layer 2 Expected Power & Thermal models loaded",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )
    except Exception as err:
        all_ready = False
        subsystems["ml_models"] = SubsystemHealth(
            name="ResidualEngine",
            ready=False,
            message=f"ML model loading failure: {err}",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )

    # 3. Knowledge Base RAG Probe
    t0 = time.perf_counter()
    try:
        kb = get_knowledge_base()
        subsystems["knowledge_base"] = SubsystemHealth(
            name="VectorKnowledgeBase",
            ready=True,
            message=f"Layer 4 technical corpus indexed ({len(kb.chunks)} chunks)",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )
    except Exception as err:
        all_ready = False
        subsystems["knowledge_base"] = SubsystemHealth(
            name="VectorKnowledgeBase",
            ready=False,
            message=f"RAG knowledge base failure: {err}",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )

    # 4. Persistent Case Store Probe
    t0 = time.perf_counter()
    try:
        _ = case_st.count()
        subsystems["case_store"] = SubsystemHealth(
            name="CaseStore",
            ready=True,
            message="Case storage and atomic file lock accessible",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )
    except Exception as err:
        all_ready = False
        subsystems["case_store"] = SubsystemHealth(
            name="CaseStore",
            ready=False,
            message=f"Case store access failure: {err}",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )

    # 5. Tariff Registry Probe
    t0 = time.perf_counter()
    try:
        reg = get_tariff_registry()
        active = reg.get_active_tariff()
        subsystems["tariff_registry"] = SubsystemHealth(
            name="TariffRegistry",
            ready=True,
            message=f"Active tariff: ₹{active.applied_rate_inr_per_kwh:.2f}/kWh ({active.mode.value})",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )
    except Exception as err:
        all_ready = False
        subsystems["tariff_registry"] = SubsystemHealth(
            name="TariffRegistry",
            ready=False,
            message=f"Tariff registry failure: {err}",
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 4),
        )

    resp = ReadinessResponse(
        ready=all_ready,
        status="READY" if all_ready else "UNAVAILABLE",
        phase=6,
        timestamp=iso_now,
        subsystems=subsystems,
    )

    if not all_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=resp.model_dump(),
        )

    return resp


@router.get("/status", response_model=SystemStatusResponse, tags=["System Lifecycle & Diagnostics"])
def system_status(
    tel_store: TelemetryStore = Depends(get_telemetry_store),
    case_st: CaseStore = Depends(get_case_store),
) -> SystemStatusResponse:
    """Returns detailed operational status and component versions across all layers."""
    kb = get_knowledge_base()
    tariff_reg = get_tariff_registry()
    active_tariff = tariff_reg.get_active_tariff()

    return SystemStatusResponse(
        status="OPERATIONAL",
        version="0.6.0",
        host=getattr(settings, "API_HOST", "127.0.0.1"),
        active_tariff=active_tariff,
        model_version="1.0.0",
        rag_corpus_version=kb.search_engine.corpus_version,
        total_indexed_chunks=len(kb.chunks),
        active_turbines_cached=len(tel_store.get_turbine_ids()),
        total_cases_stored=case_st.count(),
    )
