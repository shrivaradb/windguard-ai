"""WindGuard AI Layer 3 Analytical Reasoning & Contextual Loss Package.

Exports:
  - Context Engine: ContextFilterEngine, OperationalContextState, ContextResult
  - Multi-Signal Reasoner: MultiSignalReasoner, SubsystemLabel, AttributionResult
  - Tariff Registry: TariffRegistry, TariffMode, TariffProvenance
  - Loss Calculator: LossCalculator, LossEligibility, RecordLossResult, AggregatedLossSummary
  - Prioritization Engine: PrioritizationEngine, SeverityLevel, PriorityScoreBreakdown
"""

from backend.engine.context_engine import (
    ContextFilterEngine,
    ContextResult,
    OperationalContextState,
)
from backend.engine.loss_calculator import (
    AggregatedLossSummary,
    LossCalculator,
    LossEligibility,
    RecordLossResult,
)
from backend.engine.prioritization import (
    PrioritizationEngine,
    PriorityScoreBreakdown,
    SeverityLevel,
)
from backend.engine.reasoner import (
    AttributionResult,
    MultiSignalReasoner,
    SubsystemLabel,
)
from backend.engine.tariff_registry import (
    TariffMode,
    TariffProvenance,
    TariffRegistry,
)

__all__ = [
    "ContextFilterEngine",
    "OperationalContextState",
    "ContextResult",
    "MultiSignalReasoner",
    "SubsystemLabel",
    "AttributionResult",
    "TariffRegistry",
    "TariffMode",
    "TariffProvenance",
    "LossCalculator",
    "LossEligibility",
    "RecordLossResult",
    "AggregatedLossSummary",
    "PrioritizationEngine",
    "SeverityLevel",
    "PriorityScoreBreakdown",
]
