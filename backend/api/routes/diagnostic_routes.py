"""End-to-End Diagnostic Pipeline Orchestrator Route for WindGuard AI (Layer 6).

Executes the sequential 6-layer diagnostic evaluation pipeline:
  1. SCADA Telemetry Extraction (Layer 1)
  2. Physics-Informed ML Residuals (Layer 2)
  3. Operational Context & Subsystem Attribution (Layer 3)
  4. Deterministic Loss & Multi-Criteria Prioritization (Layer 3)
  5. Local Hybrid Technical RAG Search (Layer 4)
  6. Constrained Advisory Synthesis & Guardrail Validation (Layer 5)
  7. Persistent Case Store & Audit Trail Persistence (Layer 6)

Source:
- docs/07_srs.md §4.1
- docs/08_system_architecture.md §2, §3
- docs/09_technical_design.md §2.6, §3
- docs/10_data_architecture.md §4.3
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-07)
"""

from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.api.dependencies import (
    get_advisory_engine,
    get_audit_logger,
    get_case_store,
    get_context_engine,
    get_knowledge_base,
    get_loss_calculator,
    get_operator_id,
    get_prioritization_engine,
    get_reasoner,
    get_residual_engine,
    get_telemetry_store,
)
from backend.api.schemas import (
    CaseStatus,
    DerivedAnalyticsSummary,
    DiagnoseRequest,
    MaintenanceCase,
    SourceTelemetrySummary,
)
from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.engine.context_engine import ContextFilterEngine
from backend.engine.loss_calculator import LossCalculator
from backend.engine.prioritization import PrioritizationEngine
from backend.engine.reasoner import MultiSignalReasoner
from backend.llm.advisory_engine import AdvisoryEngine
from backend.models.residual_engine import ResidualEngine
from backend.rag.knowledge_base import VectorKnowledgeBase
from backend.storage.audit_logger import AuditLogger
from backend.storage.case_store import CaseStore
from backend.storage.telemetry_store import TelemetryStore

router = APIRouter(prefix="/turbines", tags=["Diagnostic Pipeline Orchestrator"])


@router.post("/{turbine_id}/diagnose", response_model=MaintenanceCase, status_code=status.HTTP_200_OK)
def run_turbine_diagnosis(
    turbine_id: str,
    payload: Optional[DiagnoseRequest] = None,
    operator_id: str = Depends(get_operator_id),
    tel_store: TelemetryStore = Depends(get_telemetry_store),
    residual_eng: ResidualEngine = Depends(get_residual_engine),
    context_eng: ContextFilterEngine = Depends(get_context_engine),
    reasoner: MultiSignalReasoner = Depends(get_reasoner),
    loss_calc: LossCalculator = Depends(get_loss_calculator),
    prio_eng: PrioritizationEngine = Depends(get_prioritization_engine),
    rag_kb: VectorKnowledgeBase = Depends(get_knowledge_base),
    advisory_eng: AdvisoryEngine = Depends(get_advisory_engine),
    case_st: CaseStore = Depends(get_case_store),
    audit_log: AuditLogger = Depends(get_audit_logger),
) -> MaintenanceCase:
    """Master end-to-end diagnostic pipeline orchestrator."""
    # 1. Resolve Telemetry Record
    telemetry: Optional[TelemetryRecord] = None
    if payload and payload.telemetry_record:
        telemetry = payload.telemetry_record
        if telemetry.turbine_id != turbine_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mismatched turbine_id: URL path specifies '{turbine_id}', payload specifies '{telemetry.turbine_id}'.",
            )
    else:
        telemetry = tel_store.get_latest_record(turbine_id)

    if not telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry records found for turbine '{turbine_id}'. Ingest or simulate data first.",
        )

    # 2. Idempotency Check (OD-P6-07)
    force_recompute = payload.force_recompute if payload else False
    if not force_recompute:
        existing_case = case_st.find_case_by_telemetry(turbine_id, telemetry.timestamp)
        if existing_case:
            audit_log.log_event(
                event_type="DIAGNOSTIC_IDEMPOTENT_HIT",
                payload={"case_id": existing_case.case_id, "timestamp": telemetry.timestamp},
                actor=operator_id,
                case_id=existing_case.case_id,
                turbine_id=turbine_id,
            )
            return existing_case

    # 3. Layer 2: Compute Residuals
    residuals = residual_eng.compute_residuals(telemetry)

    # 4. Layer 3: Evaluate Operational Context
    context_result = context_eng.evaluate_record(telemetry, residuals)

    # 5. Layer 3: Multi-Signal Subsystem Attribution
    attribution = reasoner.evaluate_record(telemetry, residuals, context_result)

    # 6. Layer 3: Deterministic Financial & Energy Loss
    loss_result = loss_calc.calculate_record_loss(telemetry, residuals, context_result, attribution)

    # 7. Layer 3: 5-Factor Priority Scoring
    priority_score = prio_eng.compute_priority_score(residuals, attribution, loss_result)

    # 8. Layer 4: Technical Knowledge Base RAG Search
    rag_query = f"{attribution.subsystem.value} {attribution.matched_rule} {attribution.explanation}"
    rag_result = rag_kb.search(query=rag_query, top_k=3)
    seen_sources = set()
    distinct_chunks = []
    distinct_scores = []
    for chunk, score in zip(rag_result.chunks, rag_result.scores):
        if chunk.source_id not in seen_sources:
            seen_sources.add(chunk.source_id)
            distinct_chunks.append(chunk)
            distinct_scores.append(score)
    rag_result = rag_result.model_copy(update={"chunks": distinct_chunks, "scores": distinct_scores})

    # 9. Layer 5: Constrained Advisory Synthesis & Guardrail Validation
    iso_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    case_uid = f"CASE-{turbine_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    advisory, audit_snapshot = advisory_eng.generate_advisory(
        case_id=case_uid,
        turbine_id=turbine_id,
        timestamp=telemetry.timestamp,
        telemetry=telemetry,
        residuals=residuals,
        context=context_result,
        attribution=attribution,
        loss=loss_result,
        priority=priority_score,
        rag_result=rag_result,
    )

    # 10. Assemble Authoritative Case Schema (Layer 6)
    source_summary = SourceTelemetrySummary(
        timestamp=telemetry.timestamp,
        turbine_id=telemetry.turbine_id,
        wind_speed=telemetry.wind_speed,
        active_power=telemetry.active_power,
        ambient_temp=telemetry.ambient_temp,
        gearbox_bearing_temp=telemetry.gearbox_bearing_temp,
        generator_stator_temp=telemetry.generator_stator_temp,
        pitch_angle=telemetry.pitch_angle,
        rotor_speed=telemetry.rotor_speed,
        is_curtailed=telemetry.is_curtailed,
        operating_status=telemetry.operating_status,
        source_provenance="SOURCE_AUTHENTIC",
    )

    derived_summary = DerivedAnalyticsSummary(
        expected_power_kw=residuals.expected_power_kw,
        residual_power_kw=residuals.residual_power_kw,
        z_power=residuals.z_power,
        expected_gb_temp_c=residuals.expected_gb_temp_c,
        residual_gb_temp_c=residuals.residual_gb_temp_c,
        z_gb=residuals.z_gb,
        expected_gen_temp_c=residuals.expected_gen_temp_c,
        residual_gen_temp_c=residuals.residual_gen_temp_c,
        z_gen=residuals.z_gen,
        context_state=context_result.state,
        is_context_suppressed=context_result.is_suppressed,
        subsystem_attribution=attribution.subsystem,
        attribution_confidence=attribution.rule_confidence,
        energy_loss_kwh=loss_result.eligible_degradation_energy_kwh,
        financial_loss_inr=loss_result.financial_loss_inr,
        tariff_provenance=loss_result.tariff_provenance,
        priority_score=priority_score.priority_score,
        severity=priority_score.severity,
        priority_breakdown=priority_score,
    )

    maintenance_case = MaintenanceCase(
        case_id=case_uid,
        turbine_id=turbine_id,
        created_at=iso_now,
        status=CaseStatus.OPEN,
        severity=priority_score.severity,
        priority_score=priority_score.priority_score,
        source_telemetry=source_summary,
        derived_analytics=derived_summary,
        evidence_table=advisory.evidence_synthesis,
        citations=advisory.citations,
        advisory=advisory,
        guardrails=advisory.guardrail_status,
        review_status=advisory.review_status,
        operator_decisions=[],
        schema_version="1.0.0",
    )

    # 11. Persistent Case Storage & Audit Logging
    case_st.save_case(maintenance_case)
    audit_log.log_event(
        event_type="DIAGNOSTIC_EVALUATION",
        payload={
            "case_id": case_uid,
            "turbine_id": turbine_id,
            "status": advisory.status.value,
            "guardrail_verdict": advisory.guardrail_status.verdict.value,
            "priority_score": priority_score.priority_score,
            "financial_loss_inr": loss_result.financial_loss_inr,
            "audit_snapshot": audit_snapshot.model_dump(),
        },
        actor=operator_id,
        case_id=case_uid,
        turbine_id=turbine_id,
    )

    return maintenance_case
