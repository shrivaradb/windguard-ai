"""Fleet Status & Overview REST API Routes for WindGuard AI (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/10_data_architecture.md §6
"""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_case_store, get_telemetry_store
from backend.api.schemas import CaseStatus, FleetStatusResponse, SeverityLevel
from backend.storage.case_store import CaseStore
from backend.storage.telemetry_store import TelemetryStore

router = APIRouter(prefix="/fleet", tags=["Fleet Overview & Status"])


@router.get("/status", response_model=FleetStatusResponse)
def get_fleet_status(
    tel_store: TelemetryStore = Depends(get_telemetry_store),
    case_st: CaseStore = Depends(get_case_store),
) -> FleetStatusResponse:
    """Calculates fleet-wide aggregated operational metrics, open case counts, and losses."""
    summary = tel_store.get_fleet_summary()

    # Aggregate metrics from persisted cases
    all_cases, _ = case_st.list_cases(limit=100, offset=0)
    open_cases = [c for c in all_cases if c.status == CaseStatus.OPEN or c.status == CaseStatus.INVESTIGATING]
    critical_cases = [c for c in all_cases if c.severity == SeverityLevel.CRITICAL]

    # Calculate active persistent anomalies count (unique turbines with OPEN cases)
    anomalous_turbines = set(c.turbine_id for c in open_cases)

    # Calculate fleet-wide losses from stored cases
    total_energy_loss = sum(c.derived_analytics.energy_loss_kwh for c in open_cases)
    total_financial_loss = sum(c.derived_analytics.financial_loss_inr for c in open_cases)

    return FleetStatusResponse(
        total_turbines=summary["total_turbines"],
        active_turbines=summary["active_turbines"],
        latest_timestamp=summary["latest_timestamp"],
        total_fleet_power_kw=summary["total_fleet_power_kw"],
        average_wind_speed_mps=summary["average_wind_speed_mps"],
        curtailed_turbines_count=summary["curtailed_turbines_count"],
        active_anomalies_count=len(anomalous_turbines),
        open_cases_count=len(open_cases),
        critical_cases_count=len(critical_cases),
        total_fleet_energy_loss_kwh=round(total_energy_loss, 2),
        total_fleet_financial_loss_inr=round(total_financial_loss, 2),
    )
