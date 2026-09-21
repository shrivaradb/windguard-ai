"""Advisory Engine Coordinator & Four-State Dispatcher for WindGuard AI Layer 5.

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011, FR-012)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/10_data_architecture.md §4.5
- docs/PHASE_5_SCOPE_REVIEW.md §6.4, §6.5
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §5, §8, §9, §10
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.loss_calculator import RecordLossResult
from backend.engine.prioritization import PriorityScoreBreakdown
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.llm.fallback import LocalTemplateSynthesizer
from backend.llm.guardrails import GuardrailValidator
from backend.llm.prompts import (
    MANDATORY_SAFETY_DISCLAIMER,
    assemble_citations,
    assemble_evidence_items,
    build_isolated_context_xml,
)
from backend.llm.providers import BaseAdvisoryProvider, LocalTemplateProvider
from backend.llm.schema import (
    AdvisoryStatus,
    AuditSnapshot,
    CitationItem,
    EvidenceItem,
    GuardrailStatusBlock,
    GuardrailVerdict,
    OperatorAdvisory,
    ReviewStatus,
    SourceType,
)
from backend.models.residual_engine import ResidualVector
from backend.rag.schema import DocumentChunk, RetrievalResult


class AdvisoryEngine:
    """Layer 5 Advisory Engine Coordinator and Dispatcher.

    Orchestrates evidence context assembly, candidate generation via provider abstraction,
    independent guardrail verification, deterministic fallback routing, and audit trail snapshots.
    """

    def __init__(
        self,
        default_provider: Optional[BaseAdvisoryProvider] = None,
        guardrail_validator: Optional[GuardrailValidator] = None,
        fallback_synthesizer: Optional[LocalTemplateSynthesizer] = None,
    ):
        self.provider = default_provider or LocalTemplateProvider()
        self.guardrail_validator = guardrail_validator or GuardrailValidator(
            numerical_tolerance=settings.LLM.NUMERICAL_TOLERANCE_EPSILON
        )
        self.fallback_synthesizer = fallback_synthesizer or LocalTemplateSynthesizer(
            critical_loss_ceiling_inr=settings.LLM.CRITICAL_REVIEW_LOSS_CEILING_INR
        )

    def generate_advisory(
        self,
        case_id: str,
        turbine_id: str,
        timestamp: Optional[str] = None,
        telemetry: Optional[Union[TelemetryRecord, Dict[str, Any]]] = None,
        residuals: Optional[Union[ResidualVector, Dict[str, Any]]] = None,
        context: Optional[Union[ContextResult, Dict[str, Any]]] = None,
        attribution: Optional[Union[AttributionResult, Dict[str, Any]]] = None,
        loss: Optional[Union[RecordLossResult, Dict[str, Any]]] = None,
        priority: Optional[Union[PriorityScoreBreakdown, Dict[str, Any]]] = None,
        rag_result: Optional[Union[RetrievalResult, List[DocumentChunk]]] = None,
        custom_provider: Optional[BaseAdvisoryProvider] = None,
        is_abstention: bool = False,
        abstention_reason: Optional[str] = None,
        conflicting_signals: bool = False,
    ) -> Tuple[OperatorAdvisory, AuditSnapshot]:
        """Executes the full Layer 5 advisory reasoning pipeline."""
        t_start = time.perf_counter()
        iso_timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        active_provider = custom_provider or self.provider

        # 1. Assemble Structured Evidence and Citations
        evidence_items: List[EvidenceItem] = assemble_evidence_items(
            telemetry=telemetry,
            residuals=residuals,
            context=context,
            attribution=attribution,
            loss=loss,
            priority=priority,
        )
        citations: List[CitationItem] = assemble_citations(
            rag_result=rag_result,
            min_score_floor=settings.LLM.RELEVANCE_SCORE_FLOOR,
        )

        # 2. Extract Authoritative Domain Fields
        tel_dict = telemetry.model_dump() if hasattr(telemetry, "model_dump") else dict(telemetry or {})
        res_dict = residuals.model_dump() if hasattr(residuals, "model_dump") else dict(residuals or {})
        ctx_dict = context.model_dump() if hasattr(context, "model_dump") else dict(context or {})
        attr_dict = attribution.model_dump() if hasattr(attribution, "model_dump") else dict(attribution or {})
        loss_dict = loss.model_dump() if hasattr(loss, "model_dump") else dict(loss or {})
        prio_dict = priority.model_dump() if hasattr(priority, "model_dump") else dict(priority or {})

        raw_state = ctx_dict.get("state", OperationalContextState.NORMAL.value)
        context_state = raw_state.value if hasattr(raw_state, "value") else str(raw_state)

        raw_sub = attr_dict.get("subsystem", SubsystemLabel.NORMAL_OPERATION.value)
        subsystem_attr = raw_sub.value if hasattr(raw_sub, "value") else str(raw_sub)

        financial_loss_inr = float(loss_dict.get("financial_loss_inr", 0.0))
        energy_loss_kwh = float(loss_dict.get("eligible_degradation_energy_kwh", 0.0))
        priority_score = float(prio_dict.get("priority_score", 0.0))

        # Build Allowed Citations Mapping for Guardrail Whitelist
        allowed_citations: Dict[str, Dict[str, Any]] = {}
        retrieved_chunk_list: List[DocumentChunk] = []
        if isinstance(rag_result, RetrievalResult):
            retrieved_chunk_list = rag_result.chunks
        elif isinstance(rag_result, list):
            retrieved_chunk_list = rag_result

        for chunk in retrieved_chunk_list:
            allowed_citations[chunk.source_id] = {
                "content_hash": chunk.content_hash,
                "source_type": chunk.source_type,
                "chunk_id": chunk.chunk_id,
            }

        # Upstream Context Dictionary for Guardrail Verification
        upstream_context = {
            "financial_loss_inr": financial_loss_inr,
            "energy_loss_kwh": energy_loss_kwh,
            "priority_score": priority_score,
            "context_state": context_state,
            "subsystem_attribution": subsystem_attr,
            "allowed_citations": allowed_citations,
        }

        # 3. Construct Isolated Delimited XML Context
        prompt_context_xml = build_isolated_context_xml(
            case_id=case_id,
            turbine_id=turbine_id,
            timestamp=iso_timestamp,
            telemetry_dict=tel_dict,
            residuals_dict=res_dict,
            context_dict=ctx_dict,
            attribution_dict=attr_dict,
            loss_dict=loss_dict,
            priority_dict=prio_dict,
            citations=citations,
            retrieved_chunks=retrieved_chunk_list,
        )

        structured_context = {
            "case_id": case_id,
            "turbine_id": turbine_id,
            "timestamp": iso_timestamp,
            "context_state": context_state,
            "subsystem_attribution": subsystem_attr,
            "financial_loss_inr": financial_loss_inr,
            "energy_loss_kwh": energy_loss_kwh,
            "priority_score": priority_score,
            "evidence_synthesis": evidence_items,
            "citations": citations,
            "is_abstention": is_abstention,
            "abstention_reason": abstention_reason,
            "conflicting_signals": conflicting_signals,
        }

        raw_input_snapshot = {
            "case_id": case_id,
            "turbine_id": turbine_id,
            "timestamp": iso_timestamp,
            "telemetry": tel_dict,
            "residuals": res_dict,
            "context": ctx_dict,
            "attribution": attr_dict,
            "loss": loss_dict,
            "priority": prio_dict,
            "retrieved_chunk_count": len(retrieved_chunk_list),
        }

        # 4. Generate Candidate Advisory Payload
        candidate_dict: Optional[Dict[str, Any]] = None
        generation_error: Optional[str] = None
        try:
            candidate_dict = active_provider.generate_candidate(
                prompt_context_xml=prompt_context_xml,
                structured_context=structured_context,
            )
        except Exception as e:
            generation_error = f"Provider invocation error: {str(e)}"
            candidate_dict = None

        # 5. Independent Guardrail Verification & Four-State Dispatching
        final_advisory: OperatorAdvisory
        final_status: AdvisoryStatus
        guardrail_status: GuardrailStatusBlock

        if candidate_dict is None:
            # Automatic Fallback on Provider Failure/Timeout
            fallback_reason_str = generation_error or "Provider execution failure"
            final_advisory = self.fallback_synthesizer.synthesize(
                case_id=case_id,
                turbine_id=turbine_id,
                timestamp=iso_timestamp,
                context_state=context_state,
                subsystem_attribution=subsystem_attr,
                financial_loss_inr=financial_loss_inr,
                energy_loss_kwh=energy_loss_kwh,
                priority_score=priority_score,
                evidence_synthesis=evidence_items,
                citations=citations,
                fallback_reason=fallback_reason_str,
                is_abstention=is_abstention,
                abstention_reason=abstention_reason,
                conflicting_signals=conflicting_signals,
            )
            final_status = final_advisory.status
            guardrail_status = final_advisory.guardrail_status

        else:
            # Validate Candidate through Guardrail Validator
            verdict, guardrail_status, validated_advisory = self.guardrail_validator.validate_candidate(
                candidate_dict=candidate_dict,
                upstream_context=upstream_context,
            )

            if verdict == GuardrailVerdict.BLOCKED:
                final_status = AdvisoryStatus.BLOCKED_OUTPUT
                final_advisory = OperatorAdvisory(
                    case_id=case_id,
                    timestamp=iso_timestamp,
                    turbine_id=turbine_id,
                    status=AdvisoryStatus.BLOCKED_OUTPUT,
                    primary_attribution=subsystem_attr,
                    context_classification=context_state,
                    summary="OUTPUT BLOCKED: Prohibited actuation or control command language detected in generated output.",
                    evidence_synthesis=evidence_items,
                    hypotheses=[],
                    recommended_actions=[],
                    citations=[],
                    loss_summary_inr=financial_loss_inr,
                    energy_loss_kwh=energy_loss_kwh,
                    priority_score=priority_score,
                    review_status=ReviewStatus.MANDATORY_HUMAN_REVIEW_REQUIRED,
                    guardrail_status=guardrail_status,
                    safety_disclaimer=MANDATORY_SAFETY_DISCLAIMER,
                    blocked_reason="; ".join(guardrail_status.violations),
                )

            elif verdict == GuardrailVerdict.FALLBACK_APPLIED:
                violations_text = "; ".join(guardrail_status.violations)
                final_advisory = self.fallback_synthesizer.synthesize(
                    case_id=case_id,
                    turbine_id=turbine_id,
                    timestamp=iso_timestamp,
                    context_state=context_state,
                    subsystem_attribution=subsystem_attr,
                    financial_loss_inr=financial_loss_inr,
                    energy_loss_kwh=energy_loss_kwh,
                    priority_score=priority_score,
                    evidence_synthesis=evidence_items,
                    citations=citations,
                    fallback_reason=f"Guardrail violation: {violations_text}",
                    is_abstention=is_abstention,
                    abstention_reason=abstention_reason,
                    conflicting_signals=conflicting_signals,
                )
                final_status = final_advisory.status

            else:
                # PASS or FLAGGED
                assert validated_advisory is not None
                # Ensure the final guardrail block reflects actual verdict
                advisory_data = validated_advisory.model_dump()
                advisory_data["guardrail_status"] = guardrail_status
                final_advisory = OperatorAdvisory.model_validate(advisory_data)
                final_status = final_advisory.status

        # 6. Build Audit Snapshot
        t_end = time.perf_counter()
        duration_ms = round((t_end - t_start) * 1000.0, 4)

        audit_snapshot = AuditSnapshot(
            audit_id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
            timestamp=iso_timestamp,
            case_id=case_id,
            turbine_id=turbine_id,
            provider_mode=active_provider.provider_mode,
            raw_input_snapshot=raw_input_snapshot,
            candidate_output=candidate_dict,
            guardrail_results=guardrail_status,
            final_status=final_status,
            final_advisory=final_advisory.model_dump() if final_status != AdvisoryStatus.BLOCKED_OUTPUT else None,
            duration_ms=duration_ms,
        )

        return final_advisory, audit_snapshot
