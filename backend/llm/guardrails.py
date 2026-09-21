"""Independent Deterministic Guardrail Validator for WindGuard AI Layer 5.

Source of Truth:
- docs/06_prd.md §7 (FR-011, FR-012, NFR-001, NFR-004)
- docs/07_srs.md §3.7
- docs/08_system_architecture.md §3.6
- docs/09_technical_design.md §2.5
- docs/PHASE_5_SCOPE_REVIEW.md §6.5
- docs/PHASE_5_IMPLEMENTATION_AUTHORIZATION_REVIEW.md §8, §9, §12, §13
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.config import settings
from backend.llm.schema import (
    AdvisoryStatus,
    CitationItem,
    GuardrailStatusBlock,
    GuardrailVerdict,
    OperatorAdvisory,
    SourceType,
)

# Canonical Prohibited Actuation Regex Patterns
PROHIBITED_ACTUATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(adjust|change|increase|decrease|set|modify|command|force|override|execute)\s+(pitch|yaw|torque|generator\s+speed|rotor\s+speed|setpoint|power\s+curve|active\s+power)\b", re.IGNORECASE),
    re.compile(r"\b(open|close|trip|reclose)\s+(breaker|generator\s+breaker|grid\s+contactor)\b", re.IGNORECASE),
    re.compile(r"\b(stop|start|shutdown|restart|reboot|halt|brake|engage\s+mechanical\s+brake)\s+(turbine|wtg\d*|rotor)\b", re.IGNORECASE),
    re.compile(r"\b(write\s+to\s+scada|issue\s+control\s+command|actuate|dispatch\s+command|send\s+actuation)\b", re.IGNORECASE),
    re.compile(r"\b(automate(d)?\s+curtailment|autonomous(ly)?\s+close\s+case|autonomous(ly)?\s+dispatch)\b", re.IGNORECASE),
]


class GuardrailValidator:
    """Independent Deterministic Guardrail Validator Engine.

    Logically isolated from advisory generation models and synthesizers.
    Enforces non-actuation, numerical exact-match consistency, citation provenance,
    and structural integrity across all candidate advisory payloads.
    """

    def __init__(
        self,
        numerical_tolerance: float = 0.01,
        policy: str = "STANDARD",
    ):
        self.numerical_tolerance = numerical_tolerance
        self.policy = policy

    def scan_prohibited_language(self, text: str) -> List[str]:
        """Scans arbitrary text for prohibited control/actuation language."""
        violations: List[str] = []
        for pattern in PROHIBITED_ACTUATION_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(f"Prohibited actuation verb detected: '{match.group(0)}'")
        return violations

    def validate_candidate(
        self,
        candidate_dict: Dict[str, Any],
        upstream_context: Dict[str, Any],
    ) -> Tuple[GuardrailVerdict, GuardrailStatusBlock, Optional[OperatorAdvisory]]:
        """Executes full suite of deterministic guardrail checks on candidate output."""
        violations: List[str] = []
        schema_valid = True
        numerical_valid = True
        citation_valid = True
        lexicon_valid = True
        context_valid = True
        attribution_valid = True
        disclaimer_valid = True

        # 1. Prohibited Lexicon Scan across ALL candidate strings
        candidate_str_repr = str(candidate_dict)
        lexicon_violations = self.scan_prohibited_language(candidate_str_repr)
        if lexicon_violations:
            lexicon_valid = False
            violations.extend(lexicon_violations)

        # 2. Schema Validation (Pydantic v2 extra='forbid')
        validated_advisory: Optional[OperatorAdvisory] = None
        try:
            # First construct without guardrail_status if not present, then attach
            if "guardrail_status" not in candidate_dict:
                temp_status = GuardrailStatusBlock(
                    verdict=GuardrailVerdict.PASS,
                    schema_valid=True,
                    numerical_consistency_valid=True,
                    citation_whitelist_valid=True,
                    lexicon_scan_passed=True,
                    context_consistency_valid=True,
                    attribution_consistency_valid=True,
                    safety_disclaimer_present=True,
                )
                candidate_dict_copy = dict(candidate_dict)
                candidate_dict_copy["guardrail_status"] = temp_status
                validated_advisory = OperatorAdvisory.model_validate(candidate_dict_copy)
            else:
                validated_advisory = OperatorAdvisory.model_validate(candidate_dict)
        except Exception as e:
            schema_valid = False
            violations.append(f"Schema validation failure: {str(e)}")

        # 3. Numerical Exact-Match Verification
        if upstream_context:
            loss_inr = upstream_context.get("financial_loss_inr")
            if loss_inr is not None and "loss_summary_inr" in candidate_dict:
                c_val = float(candidate_dict["loss_summary_inr"])
                u_val = float(loss_inr)
                if abs(c_val - u_val) > self.numerical_tolerance:
                    numerical_valid = False
                    violations.append(f"Financial loss drift: candidate {c_val} vs authoritative {u_val}")

            energy_kwh = upstream_context.get("energy_loss_kwh")
            if energy_kwh is not None and "energy_loss_kwh" in candidate_dict:
                c_val = float(candidate_dict["energy_loss_kwh"])
                u_val = float(energy_kwh)
                if abs(c_val - u_val) > self.numerical_tolerance:
                    numerical_valid = False
                    violations.append(f"Energy loss drift: candidate {c_val} vs authoritative {u_val}")

            prio = upstream_context.get("priority_score")
            if prio is not None and "priority_score" in candidate_dict:
                c_val = float(candidate_dict["priority_score"])
                u_val = float(prio)
                if abs(c_val - u_val) > self.numerical_tolerance:
                    numerical_valid = False
                    violations.append(f"Priority score drift: candidate {c_val} vs authoritative {u_val}")

        # 4. Citation Whitelist & SHA-256 Provenance Verification
        allowed_citations: Dict[str, Dict[str, Any]] = upstream_context.get("allowed_citations", {})
        candidate_citations = candidate_dict.get("citations", [])
        for cit in candidate_citations:
            c_dict = cit if isinstance(cit, dict) else cit.model_dump()
            s_id = c_dict.get("source_id")
            c_hash = c_dict.get("content_hash")
            s_type = c_dict.get("source_type")

            # Check UNVERIFIED source rejection
            if s_type == SourceType.UNVERIFIED or s_type == "UNVERIFIED":
                citation_valid = False
                violations.append(f"Citation references prohibited UNVERIFIED source: '{s_id}'")
                continue

            if s_id not in allowed_citations:
                citation_valid = False
                violations.append(f"Citation source_id '{s_id}' not found in retrieved evidence whitelist")
            else:
                expected_hash = allowed_citations[s_id].get("content_hash")
                if expected_hash and c_hash != expected_hash:
                    citation_valid = False
                    violations.append(f"Citation hash mismatch for source '{s_id}': candidate {c_hash} vs expected {expected_hash}")

        # 5. Context & Attribution Contradiction Checks
        expected_ctx = upstream_context.get("context_state")
        if expected_ctx and candidate_dict.get("context_classification"):
            if str(candidate_dict["context_classification"]) != str(expected_ctx):
                context_valid = False
                violations.append(f"Context contradiction: candidate '{candidate_dict['context_classification']}' vs expected '{expected_ctx}'")

        expected_attr = upstream_context.get("subsystem_attribution")
        if expected_attr and candidate_dict.get("primary_attribution"):
            if str(candidate_dict["primary_attribution"]) != str(expected_attr):
                attribution_valid = False
                violations.append(f"Attribution contradiction: candidate '{candidate_dict['primary_attribution']}' vs expected '{expected_attr}'")

        # 6. Safety Disclaimer Verification
        disclaimer = candidate_dict.get("safety_disclaimer", "")
        if not disclaimer or "ADVISORY ONLY" not in disclaimer or "WindGuard AI does not issue automated control commands" not in disclaimer:
            disclaimer_valid = False
            violations.append("Mandatory non-actuating safety disclaimer missing or malformed")

        # Determine Verdict
        if not lexicon_valid:
            verdict = GuardrailVerdict.BLOCKED
        elif not (schema_valid and numerical_valid and citation_valid and disclaimer_valid):
            verdict = GuardrailVerdict.FALLBACK_APPLIED
        elif not (context_valid and attribution_valid):
            verdict = GuardrailVerdict.FLAGGED
        else:
            verdict = GuardrailVerdict.PASS

        status_block = GuardrailStatusBlock(
            verdict=verdict,
            schema_valid=schema_valid,
            numerical_consistency_valid=numerical_valid,
            citation_whitelist_valid=citation_valid,
            lexicon_scan_passed=lexicon_valid,
            context_consistency_valid=context_valid,
            attribution_consistency_valid=attribution_valid,
            safety_disclaimer_present=disclaimer_valid,
            violations=violations,
        )

        return verdict, status_block, validated_advisory
