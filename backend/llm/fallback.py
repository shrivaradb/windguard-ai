"""Deterministic Mode A Template Synthesis Engine for WindGuard AI Layer 5.

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/PHASE_5_SCOPE_REVIEW.md §6.4
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §5, §10, §11
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.engine.context_engine import OperationalContextState
from backend.engine.reasoner import SubsystemLabel
from backend.llm.prompts import MANDATORY_SAFETY_DISCLAIMER
from backend.llm.schema import (
    AdvisoryStatus,
    CitationItem,
    EvidenceItem,
    GuardrailStatusBlock,
    GuardrailVerdict,
    HypothesisItem,
    OperatorAdvisory,
    PlausibilityRating,
    RecommendedActionItem,
    ReviewStatus,
)


class LocalTemplateSynthesizer:
    """Deterministic Offline High-Fidelity Advisory Synthesizer (Mode A Engine).

    Operates 100% locally on CPU without external networks, APIs, or credentials.
    Consumes upstream deterministic facts and generates strictly grounded,
    non-actuating operator advisories conforming to OperatorAdvisory schema.
    """

    def __init__(
        self,
        critical_loss_ceiling_inr: float = 25000.0,
        high_priority_ceiling: float = 80.0,
    ):
        self.critical_loss_ceiling_inr = critical_loss_ceiling_inr
        self.high_priority_ceiling = high_priority_ceiling

    def synthesize(
        self,
        case_id: str,
        turbine_id: str,
        timestamp: str,
        context_state: str,
        subsystem_attribution: str,
        financial_loss_inr: float,
        energy_loss_kwh: float,
        priority_score: float,
        evidence_synthesis: List[EvidenceItem],
        citations: List[CitationItem],
        fallback_reason: Optional[str] = None,
        is_abstention: bool = False,
        abstention_reason: Optional[str] = None,
        conflicting_signals: bool = False,
    ) -> OperatorAdvisory:
        """Synthesizes a structured OperatorAdvisory deterministically."""
        # 1. Determine Review Escalation Status
        if (
            financial_loss_inr >= self.critical_loss_ceiling_inr
            or priority_score >= self.high_priority_ceiling
            or is_abstention
            or subsystem_attribution in [SubsystemLabel.DRIVETRAIN_GEARBOX.value, SubsystemLabel.GENERATOR_COOLING.value]
        ):
            review_status = ReviewStatus.MANDATORY_HUMAN_REVIEW_REQUIRED
        else:
            review_status = ReviewStatus.AUTOMATIC

        # 2. Determine Output Status & Content based on Scenario Context
        hypotheses: List[HypothesisItem] = []
        actions: List[RecommendedActionItem] = []
        missing_evidence_summary: Optional[str] = None

        if is_abstention or context_state == OperationalContextState.SENSOR_ANOMALY.value or subsystem_attribution == SubsystemLabel.SENSOR_ANOMALY.value:
            status = AdvisoryStatus.ABSTENTION
            summary = (
                f"Advisory diagnostic abstention on {turbine_id}: Telemetry corruption or sensor dropout detected. "
                "Causal mechanical degradation claims are abstained to prevent unwarranted maintenance teardown."
            )
            abstention_reason = abstention_reason or "Sensor dropout or corrupt telemetry stream."
            missing_evidence_summary = "Valid continuous thermocouple/power telemetry and sensor calibration data."
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Candidate explanation: Telemetry transmission failure or thermocouple circuit fault.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=["EVD-CTX-STATE"],
                    missing_evidence=["Continuous SCADA stream", "Loop resistance verification test"],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-DIAG-SENSOR-01",
                    action_text="Verify sensor wiring continuity, loop power, and DAC calibration on turbine SCADA terminal block.",
                    urgency="SCHEDULED",
                    target_subsystem="SENSOR_INSTRUMENTATION",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif fallback_reason is not None:
            status = AdvisoryStatus.FALLBACK_ADVISORY
            summary = (
                f"Deterministic fallback advisory for {turbine_id}: {subsystem_attribution} anomaly active. "
                f"Financial loss impact: INR {financial_loss_inr:,.2f} ({energy_loss_kwh:.2f} kWh). "
                f"Advisory synthesized via deterministic fallback engine due to: {fallback_reason}."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis=f"Evidence-grounded candidate explanation: Component degradation consistent with {subsystem_attribution}.",
                    plausibility=PlausibilityRating.HIGH if citations else PlausibilityRating.MODERATE,
                    grounding_evidence=[c.source_id for c in citations] if citations else ["EVD-ATTR-SUBSYSTEM"],
                    missing_evidence=[] if citations else ["OEM inspection manual citation"],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-FALLBACK-01",
                    action_text=f"Perform physical on-site diagnostic inspection of {subsystem_attribution} following standard engineering procedures.",
                    urgency="IMMEDIATE" if priority_score >= 60.0 else "SCHEDULED",
                    target_subsystem=subsystem_attribution,
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif context_state == OperationalContextState.CURTAILED.value or subsystem_attribution == SubsystemLabel.GRID_CURTAILMENT.value:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Operational context confirmed as Grid Curtailment on {turbine_id}. "
                f"Deemed generation capacity of {energy_loss_kwh:.2f} kWh is tracked for settlement. "
                "Mechanical alarms are suppressed as power reduction is dispatch-commanded."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: Active power curtailment enforced by Grid Operator dispatch directive.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=["EVD-CTX-STATE"],
                    missing_evidence=[],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-CURTAIL-01",
                    action_text="Log deemed generation capacity in commercial settlement log and confirm dispatch setpoint release with SLDC/LDC.",
                    urgency="MONITORING",
                    target_subsystem="GRID_INTERFACE",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif context_state == OperationalContextState.LOW_WIND_IDLE.value:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Turbine {turbine_id} is in benign Low-Wind Idling state below cut-in threshold (3.0 m/s). "
                "Zero power output is expected; alarms suppressed."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: Ambient wind resource below turbine aerodynamic cut-in threshold.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=["EVD-TEL-WIND_SPEED_MPS"],
                    missing_evidence=[],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-IDLE-01",
                    action_text="Maintain passive monitoring until ambient wind speed exceeds cut-in threshold (3.0 m/s).",
                    urgency="MONITORING",
                    target_subsystem="AERODYNAMIC_ROTOR",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif subsystem_attribution == SubsystemLabel.DRIVETRAIN_GEARBOX.value:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Persistent Gearbox Bearing thermal anomaly detected on {turbine_id}. "
                f"Estimated financial loss: INR {financial_loss_inr:,.2f} with Priority Score {priority_score:.1f}."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: High-speed shaft bearing mechanical wear or lubrication degradation causing thermal rise.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=[c.source_id for c in citations] if citations else ["EVD-RES-RESIDUAL_GEARBOX_TEMP_C"],
                    missing_evidence=[] if citations else ["Vibration spectrum FFT"],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-GB-INSPECT-01",
                    action_text="Inspect gearbox high-speed shaft bearing lubrication levels, filter differential pressure, and oil particulate debris.",
                    urgency="IMMEDIATE" if priority_score >= 60.0 else "SCHEDULED",
                    target_subsystem="DRIVETRAIN_GEARBOX",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif subsystem_attribution == SubsystemLabel.GENERATOR_COOLING.value:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Generator Stator thermal anomaly detected on {turbine_id}. "
                f"Estimated financial loss: INR {financial_loss_inr:,.2f} with Priority Score {priority_score:.1f}."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: Generator stator cooling circuit obstruction or heat exchanger blower degradation.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=[c.source_id for c in citations] if citations else ["EVD-RES-RESIDUAL_GENERATOR_TEMP_C"],
                    missing_evidence=[],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-GEN-INSPECT-01",
                    action_text="Inspect generator cooling duct airflow, heat exchanger radiator fins, and stator thermocouple wiring.",
                    urgency="IMMEDIATE" if priority_score >= 60.0 else "SCHEDULED",
                    target_subsystem="GENERATOR_COOLING",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif subsystem_attribution == SubsystemLabel.AERODYNAMIC_PITCH.value:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Aerodynamic power deficit / pitch asymmetry anomaly detected on {turbine_id}. "
                f"Estimated financial loss: INR {financial_loss_inr:,.2f} with Priority Score {priority_score:.1f}."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: Blade pitch offset error or aerodynamic degradation resulting in under-generation.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=[c.source_id for c in citations] if citations else ["EVD-RES-RESIDUAL_POWER_KW"],
                    missing_evidence=[],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-PITCH-INSPECT-01",
                    action_text="Perform physical 0-degree pitch calibration check and inspect blade surface leading edges for fouling/erosion.",
                    urgency="SCHEDULED",
                    target_subsystem="AERODYNAMIC_PITCH",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        elif conflicting_signals:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Conflicting multi-signal telemetry observed on {turbine_id}: Co-occurring thermal elevation and power variance. "
                "Independent physical verification recommended."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: Coupled drivetrain friction versus electrical sensor offset.",
                    plausibility=PlausibilityRating.MODERATE,
                    grounding_evidence=["EVD-ATTR-SUBSYSTEM"],
                    missing_evidence=["High-frequency acoustic emission sensor data", "Oil particle laboratory analysis"],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-CONF-01",
                    action_text="Perform cross-subsystem diagnostic screening before executing intrusive maintenance.",
                    urgency="SCHEDULED",
                    target_subsystem="DRIVETRAIN_AND_ELECTRICAL",
                    requires_human_approval=True,
                    is_non_actuating=True,
                )
            )

        else:
            status = AdvisoryStatus.NORMAL_ADVISORY
            summary = (
                f"Turbine {turbine_id} operating within normal nominal design envelope. "
                "Zero anomalies or physical degradation detected."
            )
            hypotheses.append(
                HypothesisItem(
                    hypothesis="Evidence-grounded candidate explanation: Turbine is operating nominally in accordance with OEM baseline curve.",
                    plausibility=PlausibilityRating.HIGH,
                    grounding_evidence=["EVD-CTX-STATE"],
                    missing_evidence=[],
                )
            )
            actions.append(
                RecommendedActionItem(
                    action_id="ACT-NOMINAL-01",
                    action_text="Continue routine supervisory monitoring. Zero maintenance intervention required.",
                    urgency="MONITORING",
                    target_subsystem="TURBINE_SYSTEM",
                    requires_human_approval=False,
                    is_non_actuating=True,
                )
            )

        # Default guardrail status block for clean Mode A generation
        guardrail_status = GuardrailStatusBlock(
            verdict=GuardrailVerdict.PASS if fallback_reason is None else GuardrailVerdict.FALLBACK_APPLIED,
            schema_valid=True,
            numerical_consistency_valid=True,
            citation_whitelist_valid=True,
            lexicon_scan_passed=True,
            context_consistency_valid=True,
            attribution_consistency_valid=True,
            safety_disclaimer_present=True,
            violations=[f"Fallback engaged: {fallback_reason}"] if fallback_reason else [],
        )

        return OperatorAdvisory(
            case_id=case_id,
            timestamp=timestamp,
            turbine_id=turbine_id,
            status=status,
            primary_attribution=subsystem_attribution,
            context_classification=context_state,
            summary=summary,
            evidence_synthesis=evidence_synthesis,
            hypotheses=hypotheses,
            recommended_actions=actions,
            citations=citations,
            loss_summary_inr=float(financial_loss_inr),
            energy_loss_kwh=float(energy_loss_kwh),
            priority_score=float(priority_score),
            review_status=review_status,
            guardrail_status=guardrail_status,
            safety_disclaimer=MANDATORY_SAFETY_DISCLAIMER,
            missing_evidence_summary=missing_evidence_summary,
            abstention_reason=abstention_reason,
            fallback_reason=fallback_reason,
            blocked_reason=None,
        )
