"""Case Management & Human-in-the-Loop Review Routes for WindGuard AI (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/09_technical_design.md §2.6
- docs/10_data_architecture.md §4.3
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-04, OD-P6-05)

GOVERNANCE DIRECTIVE:
Case records are strictly append-only and immutable.
Zero DELETE endpoints are authorized.
"""

from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_audit_logger, get_case_store, get_operator_id
from backend.api.schemas import (
    CaseStatus,
    MaintenanceCase,
    OperatorDecision,
    OperatorDecisionRequest,
    PaginatedCasesResponse,
    SeverityLevel,
)
from backend.storage.audit_logger import AuditLogger
from backend.storage.case_store import CaseStore

router = APIRouter(prefix="/cases", tags=["Case Management & HITL Governance"])


@router.get("", response_model=PaginatedCasesResponse)
def list_cases(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum cases to return per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    turbine_id: Optional[str] = Query(default=None, description="Filter by turbine identifier (e.g. WTG-07)"),
    status_filter: Optional[CaseStatus] = Query(default=None, alias="status", description="Filter by review status"),
    severity: Optional[SeverityLevel] = Query(default=None, description="Filter by anomaly severity tier"),
    case_st: CaseStore = Depends(get_case_store),
) -> PaginatedCasesResponse:
    """Lists and filters stored maintenance diagnostic cases with stable pagination."""
    paginated_cases, total_count = case_st.list_cases(
        limit=limit,
        offset=offset,
        turbine_id=turbine_id,
        status=status_filter,
        severity=severity,
    )
    return PaginatedCasesResponse(
        total_count=total_count,
        limit=limit,
        offset=offset,
        cases=paginated_cases,
    )


@router.get("/{case_id}", response_model=MaintenanceCase)
def get_case_details(
    case_id: str,
    case_st: CaseStore = Depends(get_case_store),
) -> MaintenanceCase:
    """Retrieves full diagnostic case details, grounding evidence table, and RAG citations."""
    case = case_st.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance case '{case_id}' not found.",
        )
    return case


@router.post("/{case_id}/decision", response_model=MaintenanceCase, status_code=status.HTTP_200_OK)
def record_operator_decision(
    case_id: str,
    payload: OperatorDecisionRequest,
    header_operator_id: str = Depends(get_operator_id),
    case_st: CaseStore = Depends(get_case_store),
    audit_log: AuditLogger = Depends(get_audit_logger),
) -> MaintenanceCase:
    """Records a human-in-the-loop triage action (ACK, INV, ESC, DIS) with mandatory engineering notes."""
    existing_case = case_st.get_case(case_id)
    if not existing_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot record decision: case '{case_id}' does not exist.",
        )

    # Resolve operator attribution
    attributed_op = payload.operator_id or header_operator_id or "OPERATOR_LOCAL"
    iso_timestamp = payload.timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    decision_uid = f"DEC-{case_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    decision = OperatorDecision(
        decision_id=decision_uid,
        action=payload.action,
        operator_id=attributed_op,
        timestamp=iso_timestamp,
        notes=payload.notes,
    )

    try:
        updated_case = case_st.record_decision(case_id, decision)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found.",
        )

    # Log immutable audit event
    audit_log.log_event(
        event_type="OPERATOR_HITL_DECISION",
        payload={
            "case_id": case_id,
            "decision_id": decision_uid,
            "action": payload.action.value,
            "new_status": updated_case.status.value,
            "notes": payload.notes,
        },
        actor=attributed_op,
        case_id=case_id,
        turbine_id=updated_case.turbine_id,
    )

    return updated_case
