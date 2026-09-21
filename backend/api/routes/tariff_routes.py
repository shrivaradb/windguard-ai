"""Multi-Mode Tariff Registry REST API Routes for WindGuard AI (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.3
- docs/10_data_architecture.md §4.2
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §6 (REQ-SPEC-04)

GOVERNANCE DIRECTIVE:
Tariff modifications are strictly prospective.
Updating the active tariff never alters financial loss calculations on historical cases.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_audit_logger, get_operator_id, get_tariff_registry
from backend.api.schemas import (
    TariffMode,
    TariffProvenance,
    TariffRegistryResponse,
    TariffUpdateRequest,
)
from backend.engine.tariff_registry import TariffRegistry
from backend.storage.audit_logger import AuditLogger

router = APIRouter(prefix="/tariffs", tags=["Multi-Mode Tariff Registry"])


@router.get("", response_model=TariffRegistryResponse)
def get_tariff_configuration(
    registry: TariffRegistry = Depends(get_tariff_registry),
) -> TariffRegistryResponse:
    """Returns the currently active electricity tariff, baseline status, and complete provenance history."""
    active = registry.get_active_tariff()
    history = registry.get_history()
    modes = [m.value for m in TariffMode]

    return TariffRegistryResponse(
        active_tariff=active,
        available_modes=modes,
        history_count=len(history),
        history=history,
    )


@router.post("", response_model=TariffProvenance, status_code=status.HTTP_200_OK)
def update_tariff_configuration(
    payload: TariffUpdateRequest,
    operator_id: str = Depends(get_operator_id),
    registry: TariffRegistry = Depends(get_tariff_registry),
    audit_log: AuditLogger = Depends(get_audit_logger),
) -> TariffProvenance:
    """Updates the active electricity tariff configuration with immutable provenance metadata."""
    try:
        updated_tariff = registry.set_tariff(
            rate_inr_per_kwh=payload.rate_inr_per_kwh,
            mode=payload.mode,
            source_reference=payload.source_reference,
            effective_date=payload.effective_date,
            notes=payload.notes,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tariff parameters: {val_err}",
        )

    # Log immutable audit event
    audit_log.log_event(
        event_type="TARIFF_CONFIGURATION_UPDATE",
        payload={
            "applied_rate_inr_per_kwh": updated_tariff.applied_rate_inr_per_kwh,
            "mode": updated_tariff.mode.value,
            "source_reference": updated_tariff.source_reference,
            "effective_date": updated_tariff.effective_date,
            "notes": payload.notes,
        },
        actor=operator_id,
    )

    return updated_tariff
