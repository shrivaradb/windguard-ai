"""Unit Tests for Independent Guardrail Validator (Layer 5).

Source of Truth:
- docs/06_prd.md §7 (FR-011, FR-012, NFR-001, NFR-004)
- docs/07_srs.md §3.7
- docs/PHASE_5_SCOPE_REVIEW.md §6.5
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §8, §9
"""

import pytest

from backend.llm.guardrails import GuardrailValidator
from backend.llm.prompts import MANDATORY_SAFETY_DISCLAIMER
from backend.llm.schema import (
    AdvisoryStatus,
    CitationItem,
    GuardrailVerdict,
    ReviewStatus,
    SourceType,
)


@pytest.fixture
def validator():
    return GuardrailValidator(numerical_tolerance=0.01)


@pytest.fixture
def base_candidate():
    return {
        "case_id": "CASE-101",
        "timestamp": "2026-01-01T00:00:00Z",
        "turbine_id": "WTG01",
        "status": AdvisoryStatus.NORMAL_ADVISORY.value,
        "primary_attribution": "DRIVETRAIN_GEARBOX",
        "context_classification": "NORMAL",
        "summary": "Elevated gearbox bearing temperature observed. Recommend physical inspection.",
        "evidence_synthesis": [],
        "hypotheses": [],
        "recommended_actions": [],
        "citations": [
            {
                "source_id": "SRC-AUTH-01",
                "source_type": SourceType.SOURCE_AUTHENTIC.value,
                "title": "Gearbox Manual",
                "chapter": "Ch 4",
                "section": "Sec 4.2",
                "source_locator": "Sec 4.2",
                "source_page": 10,
                "content_hash": "hash_abc_123",
                "relevance_score": 0.85,
            }
        ],
        "loss_summary_inr": 15000.0,
        "energy_loss_kwh": 150.0,
        "priority_score": 72.0,
        "review_status": ReviewStatus.AUTOMATIC.value,
        "safety_disclaimer": MANDATORY_SAFETY_DISCLAIMER,
    }


@pytest.fixture
def base_upstream():
    return {
        "financial_loss_inr": 15000.0,
        "energy_loss_kwh": 150.0,
        "priority_score": 72.0,
        "context_state": "NORMAL",
        "subsystem_attribution": "DRIVETRAIN_GEARBOX",
        "allowed_citations": {
            "SRC-AUTH-01": {"content_hash": "hash_abc_123", "source_type": SourceType.SOURCE_AUTHENTIC}
        },
    }


def test_guardrail_pass_clean(validator, base_candidate, base_upstream):
    verdict, status_block, validated = validator.validate_candidate(base_candidate, base_upstream)
    assert verdict == GuardrailVerdict.PASS
    assert status_block.schema_valid is True
    assert status_block.numerical_consistency_valid is True
    assert status_block.citation_whitelist_valid is True
    assert status_block.lexicon_scan_passed is True
    assert status_block.safety_disclaimer_present is True
    assert validated is not None


def test_guardrail_blocks_prohibited_actuation_verbs(validator, base_candidate, base_upstream):
    prohibited_candidates = [
        "Please adjust pitch angle to 4.5 degrees immediately.",
        "Recommend to change yaw offset by +2.0 deg.",
        "Operator should stop turbine WTG01 immediately.",
        "Trip breaker to isolate generator stator.",
        "Write to SCADA register 4001 to reset setpoint.",
    ]
    for prohibited_text in prohibited_candidates:
        candidate = dict(base_candidate)
        candidate["summary"] = prohibited_text
        verdict, status_block, _ = validator.validate_candidate(candidate, base_upstream)
        assert verdict == GuardrailVerdict.BLOCKED
        assert status_block.lexicon_scan_passed is False
        assert any("Prohibited actuation verb" in v for v in status_block.violations)


def test_guardrail_catches_numerical_drift(validator, base_candidate, base_upstream):
    candidate = dict(base_candidate)
    candidate["loss_summary_inr"] = 15000.50  # Drift of 0.50 > 0.01 epsilon
    verdict, status_block, _ = validator.validate_candidate(candidate, base_upstream)
    assert verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert status_block.numerical_consistency_valid is False
    assert any("Financial loss drift" in v for v in status_block.violations)


def test_guardrail_rejects_unwhitelisted_citation(validator, base_candidate, base_upstream):
    candidate = dict(base_candidate)
    candidate["citations"] = [
        {
            "source_id": "SRC-UNAUTHORIZED-99",
            "source_type": SourceType.SOURCE_AUTHENTIC.value,
            "title": "Unwhitelisted Doc",
            "content_hash": "hash_fake",
            "relevance_score": 0.9,
        }
    ]
    verdict, status_block, _ = validator.validate_candidate(candidate, base_upstream)
    assert verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert status_block.citation_whitelist_valid is False
    assert any("not found in retrieved evidence whitelist" in v for v in status_block.violations)


def test_guardrail_rejects_citation_hash_mismatch(validator, base_candidate, base_upstream):
    candidate = dict(base_candidate)
    candidate["citations"] = [
        {
            "source_id": "SRC-AUTH-01",
            "source_type": SourceType.SOURCE_AUTHENTIC.value,
            "title": "Gearbox Manual",
            "content_hash": "hash_CORRUPTED_999",
            "relevance_score": 0.85,
        }
    ]
    verdict, status_block, _ = validator.validate_candidate(candidate, base_upstream)
    assert verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert status_block.citation_whitelist_valid is False
    assert any("hash mismatch" in v for v in status_block.violations)


def test_guardrail_rejects_unverified_source_type(validator, base_candidate, base_upstream):
    upstream = dict(base_upstream)
    upstream["allowed_citations"]["SRC-UNVERIFIED-01"] = {
        "content_hash": "hash_uv",
        "source_type": SourceType.UNVERIFIED,
    }
    candidate = dict(base_candidate)
    candidate["citations"] = [
        {
            "source_id": "SRC-UNVERIFIED-01",
            "source_type": SourceType.UNVERIFIED.value,
            "title": "Unverified Blog Post",
            "content_hash": "hash_uv",
            "relevance_score": 0.95,
        }
    ]
    verdict, status_block, _ = validator.validate_candidate(candidate, upstream)
    assert verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert status_block.citation_whitelist_valid is False
    assert any("UNVERIFIED" in v for v in status_block.violations)


def test_guardrail_catches_missing_safety_disclaimer(validator, base_candidate, base_upstream):
    candidate = dict(base_candidate)
    candidate["safety_disclaimer"] = "Some generic non-compliant text."
    verdict, status_block, _ = validator.validate_candidate(candidate, base_upstream)
    assert verdict == GuardrailVerdict.FALLBACK_APPLIED
    assert status_block.safety_disclaimer_present is False
