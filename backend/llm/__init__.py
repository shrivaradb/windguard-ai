"""WindGuard AI Advisory Reasoning & Guardrail Subsystem (Layer 5).

Source of Truth:
- docs/06_prd.md §7 (FR-009, FR-011, FR-012)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/PHASE_5_SCOPE_REVIEW.md
"""

from backend.llm.advisory_engine import AdvisoryEngine
from backend.llm.fallback import LocalTemplateSynthesizer
from backend.llm.guardrails import GuardrailValidator
from backend.llm.prompts import (
    MANDATORY_SAFETY_DISCLAIMER,
    SYSTEM_PROMPT,
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
    EvidenceType,
    GuardrailStatusBlock,
    GuardrailVerdict,
    HypothesisItem,
    OperatorAdvisory,
    PlausibilityRating,
    RecommendedActionItem,
    ReviewStatus,
)

__all__ = [
    "AdvisoryEngine",
    "LocalTemplateSynthesizer",
    "GuardrailValidator",
    "BaseAdvisoryProvider",
    "LocalTemplateProvider",
    "AdvisoryStatus",
    "GuardrailVerdict",
    "EvidenceType",
    "ReviewStatus",
    "PlausibilityRating",
    "EvidenceItem",
    "CitationItem",
    "HypothesisItem",
    "RecommendedActionItem",
    "GuardrailStatusBlock",
    "OperatorAdvisory",
    "AuditSnapshot",
    "MANDATORY_SAFETY_DISCLAIMER",
    "SYSTEM_PROMPT",
    "assemble_evidence_items",
    "assemble_citations",
    "build_isolated_context_xml",
]
