"""FastAPI Dependency Providers & Subsystem Singletons for WindGuard AI (Layer 6).

Coordinates dependency injection for analytical models, context engine, knowledge base,
advisory engine, tariff registry, and persistent stores.

Source:
- docs/08_system_architecture.md §3.7
- docs/09_technical_design.md §2.6
- docs/PHASE_6_SCOPE_REVIEW.md §8
"""

from pathlib import Path
from typing import Optional
from fastapi import Header

from backend.config import settings
from backend.engine.context_engine import ContextFilterEngine
from backend.engine.loss_calculator import LossCalculator
from backend.engine.prioritization import PrioritizationEngine
from backend.engine.reasoner import MultiSignalReasoner
from backend.engine.tariff_registry import TariffRegistry
from backend.llm.advisory_engine import AdvisoryEngine
from backend.llm.fallback import LocalTemplateSynthesizer
from backend.llm.guardrails import GuardrailValidator
from backend.llm.providers import LocalTemplateProvider
from backend.models.expected_power import ExpectedPowerModel
from backend.models.residual_engine import BaselineStats, ResidualEngine
from backend.models.thermal_model import ExpectedThermalModel
from backend.rag.knowledge_base import VectorKnowledgeBase
from backend.storage.audit_logger import AuditLogger, audit_logger
from backend.storage.case_store import CaseStore, case_store
from backend.storage.telemetry_store import TelemetryStore, telemetry_store


# Subsystem singletons
_residual_engine: Optional[ResidualEngine] = None
_context_engine: Optional[ContextFilterEngine] = None
_reasoner: Optional[MultiSignalReasoner] = None
_tariff_registry: Optional[TariffRegistry] = None
_loss_calculator: Optional[LossCalculator] = None
_prioritization_engine: Optional[PrioritizationEngine] = None
_knowledge_base: Optional[VectorKnowledgeBase] = None
_advisory_engine: Optional[AdvisoryEngine] = None


def get_telemetry_store() -> TelemetryStore:
    """Returns the global TelemetryStore singleton."""
    return telemetry_store


def get_case_store() -> CaseStore:
    """Returns the global CaseStore singleton."""
    return case_store


def get_audit_logger() -> AuditLogger:
    """Returns the global AuditLogger singleton."""
    return audit_logger


def get_residual_engine() -> ResidualEngine:
    """Lazy loader and provider for Layer 2 ResidualEngine."""
    global _residual_engine
    if _residual_engine is None:
        power_path = settings.PATHS.MODELS_DIR / "expected_power_gbr_v1.joblib"
        thermal_path = settings.PATHS.MODELS_DIR / "expected_thermal_rf_v1.joblib"
        stats_path = settings.PATHS.MODELS_DIR / "baseline_stats_v1.json"

        if not power_path.exists() or not thermal_path.exists() or not stats_path.exists():
            from backend.models.trainer import ModelTrainer
            trainer = ModelTrainer(output_dir=settings.PATHS.MODELS_DIR)
            _ = trainer.train_and_evaluate(save_artifacts=True)

        power_model = ExpectedPowerModel.load(power_path)
        thermal_model = ExpectedThermalModel.load(thermal_path)
        baseline_stats = BaselineStats.load(stats_path)

        _residual_engine = ResidualEngine(
            power_model=power_model,
            thermal_model=thermal_model,
            baseline_stats=baseline_stats,
            persistence_threshold=settings.ML.PERSISTENCE_THRESHOLD_SIGMA,
            persistence_window=settings.ML.PERSISTENCE_WINDOW_STEPS,
            persistence_ratio=settings.ML.PERSISTENCE_RATIO_THRESHOLD,
        )
    return _residual_engine


def get_context_engine() -> ContextFilterEngine:
    """Returns the global ContextFilterEngine singleton."""
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextFilterEngine()
    return _context_engine


def get_reasoner() -> MultiSignalReasoner:
    """Returns the global MultiSignalReasoner singleton."""
    global _reasoner
    if _reasoner is None:
        _reasoner = MultiSignalReasoner()
    return _reasoner


def get_tariff_registry() -> TariffRegistry:
    """Returns the global TariffRegistry singleton."""
    global _tariff_registry
    if _tariff_registry is None:
        _tariff_registry = TariffRegistry()
    return _tariff_registry


def get_loss_calculator() -> LossCalculator:
    """Returns the global LossCalculator singleton."""
    global _loss_calculator
    if _loss_calculator is None:
        _loss_calculator = LossCalculator(tariff_registry=get_tariff_registry())
    return _loss_calculator


def get_prioritization_engine() -> PrioritizationEngine:
    """Returns the global PrioritizationEngine singleton."""
    global _prioritization_engine
    if _prioritization_engine is None:
        _prioritization_engine = PrioritizationEngine()
    return _prioritization_engine


def get_knowledge_base() -> VectorKnowledgeBase:
    """Lazy loader and provider for Layer 4 VectorKnowledgeBase."""
    global _knowledge_base
    if _knowledge_base is None:
        kb_path = Path(__file__).resolve().parent.parent / "rag" / "documents"
        _knowledge_base = VectorKnowledgeBase(documents_dir=kb_path)
        _knowledge_base.load_and_index()
    return _knowledge_base


def get_advisory_engine() -> AdvisoryEngine:
    """Returns the global Layer 5 AdvisoryEngine singleton."""
    global _advisory_engine
    if _advisory_engine is None:
        validator = GuardrailValidator(numerical_tolerance=settings.LLM.NUMERICAL_TOLERANCE_EPSILON)
        fallback = LocalTemplateSynthesizer(critical_loss_ceiling_inr=settings.LLM.CRITICAL_REVIEW_LOSS_CEILING_INR)
        provider = LocalTemplateProvider(synthesizer=fallback)
        _advisory_engine = AdvisoryEngine(
            default_provider=provider,
            guardrail_validator=validator,
            fallback_synthesizer=fallback,
        )
    return _advisory_engine


def get_operator_id(x_operator_id: Optional[str] = Header(default="OPERATOR_LOCAL")) -> str:
    """Extracts operator attribution from request header with fallback to OPERATOR_LOCAL."""
    if not x_operator_id or not x_operator_id.strip():
        return "OPERATOR_LOCAL"
    # Basic sanitization
    return x_operator_id.strip()[:64]
