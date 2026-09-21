"""Eligible Energy and Financial Loss Calculation Engine for WindGuard AI (Layer 3).

Source of Truth:
- docs/06_prd.md §7 (FR-007)
- docs/07_srs.md §3.5
- docs/08_system_architecture.md §3.4
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.4

Deterministically calculates power deficit, 10-minute integrated energy loss (kWh),
and financial impact (INR) under strict eligibility boundaries:
  - S3 Aerodynamic Pitch Degradation: Included in maintenance financial loss when eligible.
  - S4 Grid Curtailment: Tracked separately as Deemed Curtailed Generation; EXCLUDED from maintenance loss.
  - Low-Wind Idling: EXCLUDED (no harvestable energy available).
  - S5 Sensor Dropout: EXCLUDED from loss calculations.
  - Overperformance / Negative Deficit: Clamped to 0.0 kW.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.engine.tariff_registry import TariffProvenance, TariffRegistry
from backend.models.residual_engine import ResidualVector


class LossEligibility(str, Enum):
    """Canonical Loss Eligibility Categories."""

    ELIGIBLE_DEGRADATION = "ELIGIBLE_DEGRADATION"  # Included in maintenance financial loss (equipment wear/derate)
    CURTAILED_CAPACITY = "CURTAILED_CAPACITY"      # Excluded from maintenance loss; tracked as deemed generation
    LOW_WIND_IDLE = "LOW_WIND_IDLE"                # Excluded (wind speed below cut-in threshold)
    EXCLUDED_SENSOR_ERROR = "EXCLUDED_SENSOR_ERROR" # Excluded (unreliable/corrupted telemetry)
    NOMINAL_NO_DEFICIT = "NOMINAL_NO_DEFICIT"      # Excluded (normal operation or overperformance)


class RecordLossResult(BaseModel):
    """Loss calculation breakdown for a single 10-minute telemetry record."""

    power_expected_kw: float = Field(..., description="Expected healthy power output in kW")
    power_actual_kw: float = Field(..., description="Actual measured power output in kW")
    power_deficit_kw: float = Field(..., ge=0.0, description="Clamped non-negative power deficit in kW")
    interval_minutes: float = Field(default=10.0, description="Telemetry integration interval in minutes")
    energy_deficit_kwh: float = Field(..., ge=0.0, description="Raw energy deficit in kWh (P_deficit * dt / 60)")
    eligibility: LossEligibility = Field(..., description="Classification category for loss eligibility")
    eligible_degradation_energy_kwh: float = Field(
        ...,
        ge=0.0,
        description="Degradation energy loss eligible for maintenance financial impact (kWh)",
    )
    curtailed_capacity_kwh: float = Field(
        ...,
        ge=0.0,
        description="Grid curtailed generation capacity tracked separately from maintenance (kWh)",
    )
    applied_tariff_inr_per_kwh: float = Field(..., ge=0.01, le=20.0, description="Active tariff rate applied")
    financial_loss_inr: float = Field(
        ...,
        ge=0.0,
        description="Eligible maintenance financial loss in INR (E_deg * Tariff)",
    )
    tariff_provenance: TariffProvenance = Field(..., description="Immutable provenance record of applied tariff")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class AggregatedLossSummary(BaseModel):
    """Aggregated financial and energy loss summary over an evaluation period."""

    total_records: int = Field(..., ge=0, description="Total number of evaluated telemetry intervals")
    total_raw_deficit_kwh: float = Field(..., ge=0.0, description="Sum of all raw unconstrained energy deficits (kWh)")
    eligible_degradation_energy_kwh: float = Field(
        ...,
        ge=0.0,
        description="Total eligible aerodynamic/mechanical degradation lost energy (kWh)",
    )
    curtailed_capacity_kwh: float = Field(
        ...,
        ge=0.0,
        description="Total deemed grid-curtailed generation capacity (kWh)",
    )
    excluded_sensor_records: int = Field(..., ge=0, description="Number of intervals excluded due to sensor errors")
    excluded_low_wind_records: int = Field(..., ge=0, description="Number of intervals excluded due to low wind")
    maintenance_financial_loss_inr: float = Field(
        ...,
        ge=0.0,
        description="Total eligible maintenance financial loss in INR",
    )
    deemed_curtailment_revenue_impact_inr: float = Field(
        ...,
        ge=0.0,
        description="Financial value of curtailed capacity in INR (tracked separately)",
    )
    applied_tariff_inr_per_kwh: float = Field(..., ge=0.01, le=20.0, description="Active tariff rate applied")
    tariff_provenance: TariffProvenance = Field(..., description="Immutable provenance record of applied tariff")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class LossCalculator:
    """Deterministic Energy and Financial Loss Calculation Engine.

    Calculates 10-minute integrated energy losses and enforces strict eligibility rules:
      - Clamps negative power deficits to 0.0 (preventing unphysical negative losses).
      - Isolates true maintenance-eligible aerodynamic derating from grid curtailment and sensor dropouts.
      - Retains full tariff provenance for every calculation.
    """

    def __init__(
        self,
        tariff_registry: Optional[TariffRegistry] = None,
        default_interval_min: float = 10.0,
    ):
        self.tariff_registry = tariff_registry or TariffRegistry()
        self.default_interval_min = default_interval_min

    def calculate_record_loss(
        self,
        telemetry: TelemetryRecord,
        residuals: ResidualVector,
        context: ContextResult,
        attribution: Optional[AttributionResult] = None,
        tariff: Optional[TariffProvenance] = None,
    ) -> RecordLossResult:
        """Calculates loss metrics for a single 10-minute telemetry record.

        Args:
            telemetry: Canonical TelemetryRecord.
            residuals: Computed ResidualVector.
            context: Evaluated ContextResult.
            attribution: Optional AttributionResult from MultiSignalReasoner.
            tariff: Optional specific TariffProvenance (uses active tariff if omitted).

        Returns:
            RecordLossResult with partitioned energy, eligibility classification, and financial impact.
        """
        active_tariff = tariff or self.tariff_registry.get_active_tariff()
        rate = active_tariff.applied_rate_inr_per_kwh

        # 1. Non-negativity clamped power deficit: P_deficit = max(0.0, P_expected - P_actual)
        p_exp = residuals.expected_power_kw
        p_act = telemetry.active_power
        p_deficit = max(0.0, round(p_exp - p_act, 2))

        dt = self.default_interval_min
        e_raw_kwh = round(p_deficit * (dt / 60.0), 4)

        # 2. Evaluate Loss Eligibility
        # Condition A: Sensor Quality / Dropout -> EXCLUDED
        if (
            context.state == OperationalContextState.SENSOR_ANOMALY
            or telemetry.operating_status == OperatingStatus.SENSOR_DROPOUT.value
            or (attribution is not None and attribution.subsystem == SubsystemLabel.SENSOR_ANOMALY)
        ):
            return RecordLossResult(
                power_expected_kw=p_exp,
                power_actual_kw=p_act,
                power_deficit_kw=p_deficit,
                interval_minutes=dt,
                energy_deficit_kwh=e_raw_kwh,
                eligibility=LossEligibility.EXCLUDED_SENSOR_ERROR,
                eligible_degradation_energy_kwh=0.0,
                curtailed_capacity_kwh=0.0,
                applied_tariff_inr_per_kwh=rate,
                financial_loss_inr=0.0,
                tariff_provenance=active_tariff,
            )

        # Condition B: Low-Wind Idling -> EXCLUDED (no wind energy available to harvest)
        if context.state == OperationalContextState.LOW_WIND_IDLE or telemetry.wind_speed < 3.0:
            return RecordLossResult(
                power_expected_kw=p_exp,
                power_actual_kw=p_act,
                power_deficit_kw=0.0,
                interval_minutes=dt,
                energy_deficit_kwh=0.0,
                eligibility=LossEligibility.LOW_WIND_IDLE,
                eligible_degradation_energy_kwh=0.0,
                curtailed_capacity_kwh=0.0,
                applied_tariff_inr_per_kwh=rate,
                financial_loss_inr=0.0,
                tariff_provenance=active_tariff,
            )

        # Condition C: Grid Curtailment -> Curtailed Capacity (Excluded from Maintenance Loss)
        if (
            context.state == OperationalContextState.CURTAILED
            or telemetry.is_curtailed
            or (attribution is not None and attribution.subsystem == SubsystemLabel.GRID_CURTAILMENT)
        ):
            return RecordLossResult(
                power_expected_kw=p_exp,
                power_actual_kw=p_act,
                power_deficit_kw=p_deficit,
                interval_minutes=dt,
                energy_deficit_kwh=e_raw_kwh,
                eligibility=LossEligibility.CURTAILED_CAPACITY,
                eligible_degradation_energy_kwh=0.0,
                curtailed_capacity_kwh=e_raw_kwh,
                applied_tariff_inr_per_kwh=rate,
                financial_loss_inr=0.0,
                tariff_provenance=active_tariff,
            )

        # Condition D: True Aerodynamic / Mechanical Power Degradation in Normal Context
        is_degradation_fault = False
        if context.state == OperationalContextState.NORMAL:
            if attribution is not None:
                if attribution.subsystem == SubsystemLabel.AERODYNAMIC_PITCH and attribution.is_persistent:
                    is_degradation_fault = True
            else:
                # Fallback to direct residual criteria if attribution object is omitted
                if residuals.residual_power_kw <= -200.0 and residuals.z_power <= -2.0:
                    is_degradation_fault = True

        if is_degradation_fault and e_raw_kwh > 0.0:
            fin_loss = round(e_raw_kwh * rate, 2)
            return RecordLossResult(
                power_expected_kw=p_exp,
                power_actual_kw=p_act,
                power_deficit_kw=p_deficit,
                interval_minutes=dt,
                energy_deficit_kwh=e_raw_kwh,
                eligibility=LossEligibility.ELIGIBLE_DEGRADATION,
                eligible_degradation_energy_kwh=e_raw_kwh,
                curtailed_capacity_kwh=0.0,
                applied_tariff_inr_per_kwh=rate,
                financial_loss_inr=fin_loss,
                tariff_provenance=active_tariff,
            )

        # Condition E: Nominal Operation / No Eligible Deficit
        return RecordLossResult(
            power_expected_kw=p_exp,
            power_actual_kw=p_act,
            power_deficit_kw=p_deficit,
            interval_minutes=dt,
            energy_deficit_kwh=e_raw_kwh,
            eligibility=LossEligibility.NOMINAL_NO_DEFICIT,
            eligible_degradation_energy_kwh=0.0,
            curtailed_capacity_kwh=0.0,
            applied_tariff_inr_per_kwh=rate,
            financial_loss_inr=0.0,
            tariff_provenance=active_tariff,
        )

    def calculate_batch_losses(
        self,
        records: List[TelemetryRecord],
        residuals_list: List[ResidualVector],
        context_list: List[ContextResult],
        attribution_list: Optional[List[AttributionResult]] = None,
        tariff: Optional[TariffProvenance] = None,
    ) -> AggregatedLossSummary:
        """Calculates and aggregates losses across a batch of telemetry records.

        Args:
            records: TelemetryRecord list.
            residuals_list: ResidualVector list.
            context_list: ContextResult list.
            attribution_list: Optional list of AttributionResult objects.
            tariff: Optional TariffProvenance to apply across the batch.

        Returns:
            AggregatedLossSummary with cumulative energy, deemed curtailment, and financial losses.
        """
        active_tariff = tariff or self.tariff_registry.get_active_tariff()
        rate = active_tariff.applied_rate_inr_per_kwh

        total_raw_kwh = 0.0
        eligible_deg_kwh = 0.0
        curtailed_kwh = 0.0
        maint_loss_inr = 0.0
        sensor_excluded_count = 0
        low_wind_excluded_count = 0

        for i, rec in enumerate(records):
            res = residuals_list[i]
            ctx = context_list[i]
            attr = attribution_list[i] if (attribution_list is not None and i < len(attribution_list)) else None

            rec_loss = self.calculate_record_loss(rec, res, ctx, attr, active_tariff)

            total_raw_kwh += rec_loss.energy_deficit_kwh
            eligible_deg_kwh += rec_loss.eligible_degradation_energy_kwh
            curtailed_kwh += rec_loss.curtailed_capacity_kwh
            maint_loss_inr += rec_loss.financial_loss_inr

            if rec_loss.eligibility == LossEligibility.EXCLUDED_SENSOR_ERROR:
                sensor_excluded_count += 1
            elif rec_loss.eligibility == LossEligibility.LOW_WIND_IDLE:
                low_wind_excluded_count += 1

        deemed_curt_impact = round(curtailed_kwh * rate, 2)

        return AggregatedLossSummary(
            total_records=len(records),
            total_raw_deficit_kwh=round(total_raw_kwh, 2),
            eligible_degradation_energy_kwh=round(eligible_deg_kwh, 2),
            curtailed_capacity_kwh=round(curtailed_kwh, 2),
            excluded_sensor_records=sensor_excluded_count,
            excluded_low_wind_records=low_wind_excluded_count,
            maintenance_financial_loss_inr=round(maint_loss_inr, 2),
            deemed_curtailment_revenue_impact_inr=deemed_curt_impact,
            applied_tariff_inr_per_kwh=rate,
            tariff_provenance=active_tariff,
        )
