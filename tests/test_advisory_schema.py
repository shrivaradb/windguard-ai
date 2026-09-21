"""Unit Tests for Layer 5 Advisory Data Schemas.

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011, FR-012)
- docs/07_srs.md §3.7
- docs/PHASE_5_SCOPE_REVIEW.md §6.2
"""

import pytest
from pydantic import ValidationError

from backend.llm.schema import (
    AdvisoryStatus,
    AuditSnapshot,
    CitationItem,
    EvidenceItem,
    EvidenceType,
    GuardrailStatusBlock,
    GuardrailVerdict,
    HypothesisItem,
    OperatorAdvisory,
    PlausibilityRating,
    RecommendedActionItem,
    ReviewStatus,
    SourceType,
)


def sample_guardrail_block() -> GuardrailStatusBlock:
    return GuardrailStatusBlock(
        verdict=GuardrailVerdict.PASS,
        schema_valid=True,
        numerical_consistency_valid=True,
        citation_whitelist_valid=True,
        lexicon_scan_passed=True,
        context_consistency_valid=True,
        attribution_consistency_valid=True,
        safety_disclaimer_present=True,
        violations=[],
    )


def test_evidence_item_schema_valid():
    item = EvidenceItem(
        evidence_id="EVD-001",
        evidence_type=EvidenceType.SCADA_TELEMETRY,
        field_name="active_power_kw",
        value=1850.5,
        unit="kW",
        source_reference="SCADA_TELEMETRY_INGESTION",
    )
    assert item.evidence_id == "EVD-001"
    assert item.value == 1850.5
    assert item.unit == "kW"


def test_citation_item_schema_valid():
    cit = CitationItem(
        source_id="SRC-AUTHENTIC-GB-01",
        source_type=SourceType.SOURCE_AUTHENTIC,
        title="OEM Gearbox Manual",
        chapter="Chapter 4",
        section="Section 4.2 Bearing Inspection",
        source_locator="Sec 4.2",
        source_page=45,
        content_hash="a" * 64,
        relevance_score=0.92,
    )
    assert cit.source_id == "SRC-AUTHENTIC-GB-01"
    assert cit.source_page == 45
    assert cit.relevance_score == 0.92


def test_hypothesis_item_schema():
    hyp = HypothesisItem(
        hypothesis="Evidence-grounded candidate explanation: Gearbox bearing wear.",
        plausibility=PlausibilityRating.HIGH,
        grounding_evidence=["EVD-001", "SRC-AUTHENTIC-GB-01"],
        missing_evidence=["Vibration FFT"],
    )
    assert hyp.plausibility == PlausibilityRating.HIGH
    assert len(hyp.grounding_evidence) == 2
    assert len(hyp.missing_evidence) == 1


def test_recommended_action_item_schema():
    act = RecommendedActionItem(
        action_id="ACT-01",
        action_text="Perform non-actuating inspection of bearing lubrication.",
        urgency="IMMEDIATE",
        target_subsystem="DRIVETRAIN_GEARBOX",
        requires_human_approval=True,
        is_non_actuating=True,
    )
    assert act.requires_human_approval is True
    assert act.is_non_actuating is True


def test_operator_advisory_extra_fields_forbidden():
    status_block = sample_guardrail_block()
    with pytest.raises(ValidationError):
        OperatorAdvisory(
            case_id="CASE-001",
            timestamp="2026-01-01T00:00:00Z",
            turbine_id="WTG01",
            status=AdvisoryStatus.NORMAL_ADVISORY,
            primary_attribution="DRIVETRAIN_GEARBOX",
            context_classification="NORMAL",
            summary="Test summary",
            evidence_synthesis=[],
            hypotheses=[],
            recommended_actions=[],
            citations=[],
            loss_summary_inr=12500.0,
            energy_loss_kwh=120.0,
            priority_score=65.5,
            review_status=ReviewStatus.AUTOMATIC,
            guardrail_status=status_block,
            safety_disclaimer="ADVISORY ONLY — WindGuard AI does not issue automated control commands to turbine actuators.",
            unauthorized_extra_field="ILLEGAL",  # Extra field must trigger ValidationError
        )


def test_operator_advisory_immutability():
    status_block = sample_guardrail_block()
    advisory = OperatorAdvisory(
        case_id="CASE-001",
        timestamp="2026-01-01T00:00:00Z",
        turbine_id="WTG01",
        status=AdvisoryStatus.NORMAL_ADVISORY,
        primary_attribution="DRIVETRAIN_GEARBOX",
        context_classification="NORMAL",
        summary="Test summary",
        evidence_synthesis=[],
        hypotheses=[],
        recommended_actions=[],
        citations=[],
        loss_summary_inr=12500.0,
        energy_loss_kwh=120.0,
        priority_score=65.5,
        review_status=ReviewStatus.AUTOMATIC,
        guardrail_status=status_block,
        safety_disclaimer="ADVISORY ONLY — WindGuard AI does not issue automated control commands to turbine actuators.",
    )
    with pytest.raises(ValidationError):
        advisory.loss_summary_inr = 99999.0  # Frozen instance assignment


def test_audit_snapshot_serialization():
    status_block = sample_guardrail_block()
    snapshot = AuditSnapshot(
        audit_id="AUD-001",
        timestamp="2026-01-01T00:00:00Z",
        case_id="CASE-001",
        turbine_id="WTG01",
        provider_mode="MODE_A",
        raw_input_snapshot={"key": "val"},
        candidate_output=None,
        guardrail_results=status_block,
        final_status=AdvisoryStatus.NORMAL_ADVISORY,
        final_advisory={"summary": "test"},
        duration_ms=12.5,
    )
    dump = snapshot.model_dump()
    assert dump["audit_id"] == "AUD-001"
    assert dump["duration_ms"] == 12.5
    assert dump["final_status"] == "NORMAL_ADVISORY"
