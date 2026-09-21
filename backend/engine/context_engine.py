"""Operational Context Engine for WindGuard AI (Layer 3).

Source of Truth:
- docs/06_prd.md §7 (FR-004)
- docs/07_srs.md §3.3
- docs/08_system_architecture.md §3.3
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.1

Implements deterministic 5-precedence context filtering to decouple external environmental
transients (ambient heat >= 38.0°C, low-wind idling < 3.0 m/s) and grid dispatch commands
(is_curtailed == True) from physical equipment faults, achieving false-alarm suppression.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.data.schema import OperatingStatus, TelemetryRecord
from backend.models.residual_engine import ResidualVector


class OperationalContextState(str, Enum):
    """Canonical Operational Context States for WindGuard AI Layer 3."""

    NORMAL = "NORMAL"
    CURTAILED = "CURTAILED"
    HIGH_AMBIENT_DERATE = "HIGH_AMBIENT_DERATE"
    LOW_WIND_IDLE = "LOW_WIND_IDLE"
    SENSOR_ANOMALY = "SENSOR_ANOMALY"


class ContextResult(BaseModel):
    """Result of deterministic operational context evaluation."""

    state: OperationalContextState = Field(..., description="Canonical operational context state")
    is_suppressed: bool = Field(..., description="True if alarms should be suppressed due to benign/external context")
    explanation: str = Field(..., description="Human-readable technical explanation of context determination")
    precedence_level: int = Field(..., ge=1, le=5, description="Deterministic precedence tier (1=highest, 5=lowest)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual metadata (e.g. co-occurring heatwave)")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ContextFilterEngine:
    """Deterministic Operational Context Filtering Engine.

    Evaluates operating state across the 5-tier deterministic precedence hierarchy:
      Precedence 1: Sensor Quality / Dropout
      Precedence 2: Grid Curtailment (is_curtailed == True or active dispatch pitch derate)
      Precedence 3: Low-Wind Idling (< 3.0 m/s)
      Precedence 4: Ambient Heatwave (High Ambient Derate >= 38.0°C)
      Precedence 5: Normal Regime
    """

    def __init__(
        self,
        cut_in_speed_mps: float = 3.0,
        ambient_heatwave_threshold_c: float = 38.0,
        gb_thermal_rise_ceiling_c: float = 6.0,
        gb_z_ceiling: float = 2.0,
    ):
        self.cut_in_speed_mps = cut_in_speed_mps
        self.ambient_heatwave_threshold_c = ambient_heatwave_threshold_c
        self.gb_thermal_rise_ceiling_c = gb_thermal_rise_ceiling_c
        self.gb_z_ceiling = gb_z_ceiling

    def evaluate_record(
        self,
        telemetry: TelemetryRecord,
        residuals: Optional[ResidualVector] = None,
    ) -> ContextResult:
        """Evaluates operational context for a single telemetry record under deterministic precedence.

        Args:
            telemetry: Canonical TelemetryRecord.
            residuals: Optional pre-calculated ResidualVector.

        Returns:
            ContextResult with canonical state, suppression flag, explanation, and precedence.
        """
        # =========================================================================
        # Precedence 1 (Highest): SENSOR QUALITY / DROPOUT
        # =========================================================================
        is_sensor_dropout = False
        dropout_reasons = []

        if telemetry.operating_status == OperatingStatus.SENSOR_DROPOUT.value or "dropout" in telemetry.operating_status.lower():
            is_sensor_dropout = True
            dropout_reasons.append("operating_status indicates sensor dropout")

        # Thermocouple plausibility check: component temperature colder than ambient - 5°C
        if telemetry.gearbox_bearing_temp < telemetry.ambient_temp - 5.0:
            is_sensor_dropout = True
            dropout_reasons.append(
                f"gearbox_bearing_temp ({telemetry.gearbox_bearing_temp}°C) < ambient_temp ({telemetry.ambient_temp}°C) - 5°C"
            )
        if telemetry.generator_stator_temp < telemetry.ambient_temp - 5.0:
            is_sensor_dropout = True
            dropout_reasons.append(
                f"generator_stator_temp ({telemetry.generator_stator_temp}°C) < ambient_temp ({telemetry.ambient_temp}°C) - 5°C"
            )

        if telemetry.quality_flags:
            for field, flag in telemetry.quality_flags.items():
                if "dropout" in flag.lower() or "error" in flag.lower() or "unphysical" in flag.lower():
                    is_sensor_dropout = True
                    dropout_reasons.append(f"quality_flags[{field}]='{flag}'")

        if is_sensor_dropout:
            return ContextResult(
                state=OperationalContextState.SENSOR_ANOMALY,
                is_suppressed=True,
                explanation=f"Sensor data quality issue / dropout detected: {'; '.join(dropout_reasons)}.",
                precedence_level=1,
                metadata={"dropout_reasons": dropout_reasons},
            )

        # =========================================================================
        # Precedence 2: GRID CURTAILMENT (CURTAILED)
        # =========================================================================
        # S4 contains both grid curtailment and heatwave. Curtailment takes precedence.
        # Check active dispatch flag or aerodynamic pitch derate signature under strong wind
        is_curtailed = bool(telemetry.is_curtailed)
        if not is_curtailed:
            # Physical aerodynamic curtailment signature: pitch > 10° in generating wind (> 6 m/s) with power < 80% expected
            expected_p = residuals.expected_power_kw if residuals else (telemetry.wind_speed ** 3)
            if telemetry.pitch_angle > 10.0 and telemetry.wind_speed > 6.0 and telemetry.active_power < 0.8 * expected_p:
                is_curtailed = True

        if is_curtailed:
            meta: Dict[str, Any] = {"is_curtailed": True}
            if telemetry.curtailment_limit_kw is not None:
                meta["curtailment_limit_kw"] = telemetry.curtailment_limit_kw
            if telemetry.ambient_temp >= self.ambient_heatwave_threshold_c:
                meta["co_occurring_heatwave"] = True
                meta["ambient_temp_c"] = telemetry.ambient_temp

            return ContextResult(
                state=OperationalContextState.CURTAILED,
                is_suppressed=True,
                explanation="Turbine is under active grid curtailment or dispatch derating. Low power output is deliberate.",
                precedence_level=2,
                metadata=meta,
            )

        # =========================================================================
        # Precedence 3: LOW-WIND IDLING (LOW_WIND_IDLE)
        # =========================================================================
        if telemetry.wind_speed < self.cut_in_speed_mps:
            return ContextResult(
                state=OperationalContextState.LOW_WIND_IDLE,
                is_suppressed=True,
                explanation=f"Wind speed ({telemetry.wind_speed:.2f} m/s) below cut-in threshold ({self.cut_in_speed_mps:.1f} m/s). Turbine idling normally.",
                precedence_level=3,
                metadata={"wind_speed_mps": telemetry.wind_speed},
            )

        # =========================================================================
        # Precedence 4: AMBIENT HEATWAVE (HIGH_AMBIENT_DERATE)
        # =========================================================================
        if telemetry.ambient_temp >= self.ambient_heatwave_threshold_c:
            # Verify if thermal elevation is benign (within normal thermal rise over ambient)
            is_benign_ambient_rise = True
            if residuals is not None:
                # If gearbox thermal residual is high (> 6.0°C and z > 2.0), it might be an internal mechanical fault
                if residuals.residual_gb_temp_c >= self.gb_thermal_rise_ceiling_c and residuals.z_gb >= self.gb_z_ceiling:
                    is_benign_ambient_rise = False

            if is_benign_ambient_rise:
                return ContextResult(
                    state=OperationalContextState.HIGH_AMBIENT_DERATE,
                    is_suppressed=True,
                    explanation=f"Elevated component temperature is driven by severe ambient conditions (>={self.ambient_heatwave_threshold_c}°C) within expected thermal rise.",
                    precedence_level=4,
                    metadata={"ambient_temp_c": telemetry.ambient_temp},
                )

        # =========================================================================
        # Precedence 5 (Lowest): NORMAL REGIME
        # =========================================================================
        return ContextResult(
            state=OperationalContextState.NORMAL,
            is_suppressed=False,
            explanation="Standard operating regime for fault residual evaluation.",
            precedence_level=5,
            metadata={},
        )

    def evaluate_batch(
        self,
        records: List[TelemetryRecord],
        residuals_list: Optional[List[ResidualVector]] = None,
    ) -> List[ContextResult]:
        """Evaluates operational context for a list of telemetry records.

        Args:
            records: List of TelemetryRecord objects.
            residuals_list: Optional list of ResidualVector objects.

        Returns:
            List of ContextResult objects.
        """
        results: List[ContextResult] = []
        for i, rec in enumerate(records):
            res = residuals_list[i] if (residuals_list is not None and i < len(residuals_list)) else None
            results.append(self.evaluate_record(rec, res))
        return results

    def calculate_suppression_rate(
        self,
        results: List[ContextResult],
        benign_indices: Optional[List[int]] = None,
    ) -> float:
        """Calculates the proportion of benign/external context records successfully suppressed.

        Args:
            results: Evaluated ContextResult list.
            benign_indices: Optional subset of indices representing benign/curtailed/ambient periods.

        Returns:
            Suppression rate as a percentage (0.0 to 100.0).
        """
        if not results:
            return 100.0

        eval_set = [results[i] for i in benign_indices] if benign_indices is not None else results
        if not eval_set:
            return 100.0

        suppressed_count = sum(1 for r in eval_set if r.is_suppressed)
        return (suppressed_count / len(eval_set)) * 100.0
