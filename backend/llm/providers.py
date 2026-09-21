"""Advisory Provider Abstraction & Local Mode A Provider for WindGuard AI Layer 5.

Source of Truth:
- docs/06_prd.md §7 (FR-009)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/PHASE_5_SCOPE_REVIEW.md §6.4
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §3, §4, §7
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from backend.llm.fallback import LocalTemplateSynthesizer
from backend.llm.schema import OperatorAdvisory


class BaseAdvisoryProvider(ABC):
    """Abstract Base Class for Layer 5 Advisory Reasoning Providers.

    Establishes the strict interface contract for candidate advisory generation.
    Enables pluggable provider implementations while isolating provider-specific
    mechanics from the core advisory coordinator and guardrail firewall.
    """

    @property
    @abstractmethod
    def provider_mode(self) -> str:
        """Unique categorical provider mode identifier (e.g. MODE_A, MODE_C)."""
        pass

    @abstractmethod
    def generate_candidate(
        self,
        prompt_context_xml: str,
        structured_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generates a candidate advisory payload dictionary.

        Args:
            prompt_context_xml: Delimited XML context string containing isolated upstream facts.
            structured_context: Dictionary of structured upstream domain objects and citations.

        Returns:
            Dict representing candidate OperatorAdvisory fields to be validated by GuardrailValidator.
        """
        pass


class LocalTemplateProvider(BaseAdvisoryProvider):
    """Deterministic Mode A Local Advisory Provider (100% Offline CPU Engine).

    Consumes structured upstream evidence directly and applies deterministic
    template synthesis to produce high-fidelity operator advisories.
    Operates without cloud connectivity, external SDKs, or external API keys.
    """

    def __init__(self, synthesizer: Optional[LocalTemplateSynthesizer] = None):
        self._synthesizer = synthesizer or LocalTemplateSynthesizer()

    @property
    def provider_mode(self) -> str:
        return "MODE_A"

    def generate_candidate(
        self,
        prompt_context_xml: str,
        structured_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generates candidate payload using deterministic local template synthesizer."""
        advisory: OperatorAdvisory = self._synthesizer.synthesize(
            case_id=structured_context.get("case_id", "CASE-UNKNOWN"),
            turbine_id=structured_context.get("turbine_id", "WTG01"),
            timestamp=structured_context.get("timestamp", "2026-01-01T00:00:00Z"),
            context_state=structured_context.get("context_state", "NORMAL"),
            subsystem_attribution=structured_context.get("subsystem_attribution", "NORMAL_OPERATION"),
            financial_loss_inr=structured_context.get("financial_loss_inr", 0.0),
            energy_loss_kwh=structured_context.get("energy_loss_kwh", 0.0),
            priority_score=structured_context.get("priority_score", 0.0),
            evidence_synthesis=structured_context.get("evidence_synthesis", []),
            citations=structured_context.get("citations", []),
            fallback_reason=structured_context.get("fallback_reason"),
            is_abstention=structured_context.get("is_abstention", False),
            abstention_reason=structured_context.get("abstention_reason"),
            conflicting_signals=structured_context.get("conflicting_signals", False),
        )
        return advisory.model_dump()
