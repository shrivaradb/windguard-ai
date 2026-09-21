"""Multi-Mode Tariff Registry with Provenance Tracking for WindGuard AI (Layer 3).

Source of Truth:
- docs/06_prd.md §7 (FR-007)
- docs/07_srs.md §3.5
- docs/08_system_architecture.md §3.4
- docs/09_technical_design.md §2.3
- docs/10_data_architecture.md §4.2
- docs/PHASE_3_SCOPE_REVIEW.md §4.3

Manages multi-mode electricity tariffs supporting Project PPA, Regulatory Benchmark,
Configured Baseline Assumption (₹3.20/kWh baseline assumption), and Scenario Override
with system constraint rate validation bounds (₹0.01 - ₹20.00/kWh) and complete provenance tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TariffMode(str, Enum):
    """Canonical Tariff Operating Modes."""

    PROJECT_PPA = "PROJECT_PPA"                   # Long-term negotiated utility PPA contract rate
    REGULATORY_BENCHMARK = "REGULATORY_BENCHMARK" # State/Central regulatory benchmark (e.g. CERC/SERC order)
    CONFIGURED_BASELINE = "CONFIGURED_BASELINE"   # Configured baseline assumption for demo (₹3.20/kWh)
    SCENARIO_OVERRIDE = "SCENARIO_OVERRIDE"       # Operator simulation / what-if test override


class TariffProvenance(BaseModel):
    """Immutable Tariff Provenance Record.

    Ensures every financial calculation retains complete audit traceability back
    to the underlying contract, regulatory benchmark, or baseline assumption.
    """

    applied_rate_inr_per_kwh: float = Field(
        ...,
        ge=0.01,
        le=20.0,
        description="Electricity tariff rate in INR per kWh (Bounded: ₹0.01 - ₹20.00/kWh)",
    )
    mode: TariffMode = Field(..., description="Active tariff classification mode")
    source_reference: str = Field(..., description="Documented reference, order ID, or contract number")
    effective_date: str = Field(..., description="ISO-8601 effective date string")
    currency: str = Field(default="INR", description="Currency denomination (default: INR)")
    is_baseline_assumption: bool = Field(
        ...,
        description="True if rate is a configured baseline assumption rather than an authoritative contract/order",
    )
    notes: Optional[str] = Field(default=None, description="Optional engineering/operational notes")

    model_config = ConfigDict(populate_by_name=True, frozen=True, extra="forbid")

    @field_validator("applied_rate_inr_per_kwh")
    @classmethod
    def validate_rate_bounds(cls, v: float) -> float:
        """Enforces hard system constraint bounds on tariff rate."""
        if v < 0.01:
            raise ValueError(f"Tariff rate ₹{v:.4f}/kWh violates lower bound (min ₹0.01/kWh)")
        if v > 20.0:
            raise ValueError(f"Tariff rate ₹{v:.4f}/kWh violates upper bound (max ₹20.00/kWh)")
        return round(v, 4)


class TariffRegistry:
    """Multi-Mode Tariff Registry with Provenance Management.

    Maintains active tariff state, enforces ₹0.01 - ₹20.00/kWh validation,
    and logs immutable provenance records for all rate mutations.
    """

    # Baseline Demonstration Assumption (Configured Baseline, not universal default)
    DEFAULT_BASELINE_RATE_INR: float = 3.20
    DEFAULT_SOURCE_REF: str = "Configured Baseline Assumption (docs/10_data_architecture.md §4.2)"
    DEFAULT_EFFECTIVE_DATE: str = "2026-09-20T00:00:00Z"

    def __init__(
        self,
        initial_rate_inr: float = DEFAULT_BASELINE_RATE_INR,
        initial_mode: TariffMode = TariffMode.CONFIGURED_BASELINE,
        initial_source: str = DEFAULT_SOURCE_REF,
        initial_effective_date: str = DEFAULT_EFFECTIVE_DATE,
    ):
        self._history: List[TariffProvenance] = []
        self._active_tariff: TariffProvenance = self._create_provenance(
            rate=initial_rate_inr,
            mode=initial_mode,
            source=initial_source,
            effective_date=initial_effective_date,
            is_baseline=(initial_mode == TariffMode.CONFIGURED_BASELINE),
            notes="Initial default demonstration tariff registry configuration.",
        )
        self._history.append(self._active_tariff)

    def _create_provenance(
        self,
        rate: float,
        mode: TariffMode,
        source: str,
        effective_date: Optional[str] = None,
        is_baseline: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> TariffProvenance:
        """Helper to create and validate an immutable TariffProvenance instance."""
        eff_date = effective_date or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        is_base = is_baseline if is_baseline is not None else (mode == TariffMode.CONFIGURED_BASELINE)

        return TariffProvenance(
            applied_rate_inr_per_kwh=rate,
            mode=mode,
            source_reference=source,
            effective_date=eff_date,
            currency="INR",
            is_baseline_assumption=is_base,
            notes=notes,
        )

    def get_active_tariff(self) -> TariffProvenance:
        """Returns current active tariff with full provenance metadata."""
        return self._active_tariff

    def get_history(self) -> List[TariffProvenance]:
        """Returns full historical log of configured tariffs."""
        return list(self._history)

    def set_tariff(
        self,
        rate_inr_per_kwh: float,
        mode: TariffMode,
        source_reference: str,
        effective_date: Optional[str] = None,
        is_baseline_assumption: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> TariffProvenance:
        """Configures active tariff with arbitrary mode and explicit provenance."""
        provenance = self._create_provenance(
            rate=rate_inr_per_kwh,
            mode=mode,
            source=source_reference,
            effective_date=effective_date,
            is_baseline=is_baseline_assumption,
            notes=notes,
        )
        self._active_tariff = provenance
        self._history.append(provenance)
        return self._active_tariff

    def set_ppa_tariff(
        self,
        rate_inr_per_kwh: float,
        ppa_contract_id: str,
        effective_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> TariffProvenance:
        """Configures a project-specific negotiated Power Purchase Agreement (PPA) rate."""
        return self.set_tariff(
            rate_inr_per_kwh=rate_inr_per_kwh,
            mode=TariffMode.PROJECT_PPA,
            source_reference=f"PPA Contract ID: {ppa_contract_id}",
            effective_date=effective_date,
            is_baseline_assumption=False,
            notes=notes or f"Project-specific utility PPA rate: {ppa_contract_id}",
        )

    def set_regulatory_tariff(
        self,
        rate_inr_per_kwh: float,
        regulator_name: str,
        order_reference: str,
        effective_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> TariffProvenance:
        """Configures an official regulatory benchmark tariff (e.g. CERC or SERC feed-in order)."""
        return self.set_tariff(
            rate_inr_per_kwh=rate_inr_per_kwh,
            mode=TariffMode.REGULATORY_BENCHMARK,
            source_reference=f"{regulator_name} Order: {order_reference}",
            effective_date=effective_date,
            is_baseline_assumption=False,
            notes=notes or f"Official regulatory benchmark tariff from {regulator_name}",
        )

    def set_scenario_override(
        self,
        rate_inr_per_kwh: float,
        reason: str,
        effective_date: Optional[str] = None,
    ) -> TariffProvenance:
        """Applies a temporary what-if simulation or operator scenario override rate."""
        return self.set_tariff(
            rate_inr_per_kwh=rate_inr_per_kwh,
            mode=TariffMode.SCENARIO_OVERRIDE,
            source_reference=f"Operator Scenario Override: {reason}",
            effective_date=effective_date,
            is_baseline_assumption=False,
            notes=f"Scenario override: {reason}",
        )

    def reset_to_baseline(self) -> TariffProvenance:
        """Resets active tariff to default configured demonstration baseline (₹3.20/kWh)."""
        return self.set_tariff(
            rate_inr_per_kwh=self.DEFAULT_BASELINE_RATE_INR,
            mode=TariffMode.CONFIGURED_BASELINE,
            source_reference=self.DEFAULT_SOURCE_REF,
            effective_date=self.DEFAULT_EFFECTIVE_DATE,
            is_baseline_assumption=True,
            notes="Reset to configured demonstration baseline assumption.",
        )
