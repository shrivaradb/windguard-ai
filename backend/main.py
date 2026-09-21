"""WindGuard AI FastAPI Application Entrypoint (Layer 6).

Initializes the complete 6-layer WindGuard AI Decision-Support Service API.

Source:
- docs/07_srs.md §4.1
- docs/08_system_architecture.md §2, §3.7
- docs/09_technical_design.md §2.6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-08, OD-P6-12)
"""

from backend.api.app import create_app
from backend.config import settings

app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = getattr(settings, "API_HOST", "127.0.0.1")
    port = getattr(settings, "API_PORT", 8000)
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
