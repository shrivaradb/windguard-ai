"""WindGuard AI REST API Route Handlers (Layer 6)."""

from backend.api.routes.case_routes import router as case_router
from backend.api.routes.demo_routes import router as demo_router
from backend.api.routes.diagnostic_routes import router as diagnostic_router
from backend.api.routes.fleet_routes import router as fleet_router
from backend.api.routes.model_routes import router as model_router
from backend.api.routes.rag_routes import router as rag_router
from backend.api.routes.scada_routes import router as scada_router
from backend.api.routes.system_routes import router as system_router
from backend.api.routes.tariff_routes import router as tariff_router

__all__ = [
    "system_router",
    "fleet_router",
    "scada_router",
    "model_router",
    "diagnostic_router",
    "case_router",
    "tariff_router",
    "rag_router",
    "demo_router",
]
