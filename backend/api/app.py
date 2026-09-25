"""FastAPI Application Factory & Lifecycle Management for WindGuard AI (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/08_system_architecture.md §2, §3.7
- docs/09_technical_design.md §2.6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §10, §16
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import time
import uuid
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.dependencies import (
    get_case_store,
    get_knowledge_base,
    get_residual_engine,
    get_telemetry_store,
)
from backend.api.routes import (
    case_router,
    demo_router,
    diagnostic_router,
    fleet_router,
    model_router,
    rag_router,
    scada_router,
    system_router,
    tariff_router,
)
from backend.api.schemas import StandardErrorEnvelope
from backend.config import settings

# Structured application logger
logger = logging.getLogger("windguard.api")
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages service startup verification, dependency initialization, and graceful shutdown."""
    # 1. Startup Initialization
    logger.info("Initializing WindGuard AI Service (Layer 6)...")

    # Ensure required storage and synthetic directories exist
    settings.PATHS.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    settings.PATHS.SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    settings.PATHS.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize analytical models
    try:
        _ = get_residual_engine()
        logger.info("Layer 2 ML analytical models verified.")
    except Exception as err:
        logger.error(f"Critical: Failed to load Phase 2 ML models: {err}")
        raise RuntimeError(f"Fail-closed: Missing ML model artifacts: {err}")

    # Initialize technical knowledge base (RAG)
    try:
        kb = get_knowledge_base()
        logger.info(f"Layer 4 RAG knowledge base indexed ({len(kb.chunks)} chunks).")
    except Exception as err:
        logger.error(f"Critical: Failed to index Phase 4 RAG knowledge base: {err}")
        raise RuntimeError(f"Fail-closed: Missing RAG corpus: {err}")

    # Initialize case store and telemetry store
    tel_store = get_telemetry_store()
    case_st = get_case_store()
    if len(tel_store.get_turbine_ids()) == 0:
        try:
            from backend.data.scada_generator import SCADASimulator
            from backend.data.schema import SimulationConfig, BenchmarkScenarioType
            sim = SCADASimulator()
            sim_res = sim.simulate(SimulationConfig(
                scenario=BenchmarkScenarioType.S2_GEARBOX_BEARING_DEGRADATION,
                num_turbines=10,
                num_timesteps=72,
                random_seed=42,
            ))
            tel_store.add_records(sim_res.records)
            logger.info(f"Telemetry cache auto-seeded with 10-turbine benchmark fleet ({len(sim_res.records)} records).")
        except Exception as seed_err:
            logger.warning(f"Could not auto-seed telemetry cache on startup: {seed_err}")

    logger.info("Layer 6 Storage and Telemetry Cache initialized.")

    logger.info("WindGuard AI REST Service ready.")
    yield

    # 2. Graceful Shutdown
    logger.info("Shutting down WindGuard AI Service... Flushing storage buffers.")
    try:
        tel_store = get_telemetry_store()
        case_st = get_case_store()
        # Save any in-memory state
        case_st.save_to_disk()
    except Exception as err:
        logger.warning(f"Error flushing storage during shutdown: {err}")
    logger.info("WindGuard AI Service shutdown complete.")


def create_app() -> FastAPI:
    """Creates and configures the authoritative FastAPI application."""
    app = FastAPI(
        title="WindGuard AI — Decision-Support Service API",
        description="Explainable, Physics-Informed Wind Turbine Decision Support & Advisory Service (Layer 6).",
        version="0.6.0",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers for Sanitized Deterministic Error Responses
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = str(uuid.uuid4())
        iso_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        logger.warning(f"Request validation error [{req_id}] on {request.url.path}: {exc.errors()}")

        error_envelope = StandardErrorEnvelope(
            error_code="ERR_VALIDATION_FAILED",
            message="Request body or query parameters failed validation.",
            timestamp=iso_now,
            request_id=req_id,
            details={"errors": exc.errors()},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_envelope.model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = str(uuid.uuid4())
        iso_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # If detail is already a dict, use it; otherwise wrap message
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_code_map = {
            400: "ERR_BAD_REQUEST",
            404: "ERR_RESOURCE_NOT_FOUND",
            409: "ERR_CONCURRENCY_CONFLICT",
            413: "ERR_PAYLOAD_TOO_LARGE",
            422: "ERR_UNPROCESSABLE_ENTITY",
            503: "ERR_SERVICE_UNAVAILABLE",
        }
        err_code = error_code_map.get(exc.status_code, "ERR_HTTP_EXCEPTION")

        error_envelope = StandardErrorEnvelope(
            error_code=err_code,
            message=detail_msg,
            timestamp=iso_now,
            request_id=req_id,
            details={"path": str(request.url.path), "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope.model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = str(uuid.uuid4())
        iso_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # Log full traceback internally for operations
        logger.error(f"Unhandled server exception [{req_id}] on {request.url.path}: {exc}", exc_info=True)

        # Return sanitized operator-safe response without leaking stack traces or internal secrets
        error_envelope = StandardErrorEnvelope(
            error_code="ERR_INTERNAL_SERVER_ERROR",
            message="An internal pipeline error occurred during execution. Diagnostic details have been logged.",
            timestamp=iso_now,
            request_id=req_id,
            details={"path": str(request.url.path)},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_envelope.model_dump(),
        )

    # Mount all Phase 6 REST routers under /api namespace
    app.include_router(system_router, prefix="/api")
    app.include_router(fleet_router, prefix="/api")
    app.include_router(scada_router, prefix="/api")
    app.include_router(model_router, prefix="/api")
    app.include_router(diagnostic_router, prefix="/api")
    app.include_router(case_router, prefix="/api")
    app.include_router(tariff_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")
    app.include_router(demo_router, prefix="/api")

    # Mount static frontend directory (Layer 6 UI / Phase 7 Presentation)
    frontend_dir = settings.PATHS.BASE_DIR / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
