"""Multi-Signal Residual Attribution Reasoner for WindGuard AI (Layer 3).

Source of Truth:
- docs/06_prd.md §7 (FR-005)
- docs/07_srs.md §3.4
- docs/08_system_architecture.md §3.4
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.2

Cross-correlates standardized residuals (power, gearbox temp, generator temp, rotor speed)
with operational context to deterministically isolate affected subsystems using
rule-based heuristic evidence scores.
"""

from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from backend.data.schema import TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.models.residual_engine import ResidualVector


class SubsystemLabel(str, Enum):
    """Canonical Subsystem Attribution Labels."""

    DRIVETRAIN_GEARBOX = "DRIVETRAIN_GEARBOX"
    GENERATOR_COOLING = "GENERATOR_COOLING"
    AERODYNAMIC_PITCH = "AERODYNAMIC_PITCH"
    GRID_CURTAILMENT = "GRID_CURTAILMENT"
    SENSOR_ANOMALY = "SENSOR_ANOMALY"
    NORMAL_OPERATION = "NORMAL_OPERATION"


class AttributionResult(BaseModel):
    """Deterministic Subsystem Attribution Result."""

    subsystem: SubsystemLabel = Field(..., description="Isolated subsystem classification")
    rule_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic heuristic rule evidence score (NOT a calibrated posterior probability)",
    )
    is_persistent: bool = Field(..., description="True if anomaly satisfies temporal persistence criteria")
    excursion_count: int = Field(default=0, ge=0, description="Number of excursions within persistence window")
    window_size: int = Field(default=6, ge=1, description="Sliding window size (intervals)")
    matched_rule: str = Field(..., description="Identifier of the firing attribution rule")
    explanation: str = Field(..., description="Human-readable physical attribution explanation")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Quantitative residual evidence")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class MultiSignalReasoner:
    """Deterministic Multi-Signal Subsystem Attribution Reasoner.

    Rule-based evidence attribution evaluating:
      - Power deficit residuals (R_p <= -200 kW, z_p <= -2.0)
      - Gearbox thermal residuals (R_gb > +10.0°C, z_gb >= 2.5)
      - Generator stator thermal residuals (R_gen > +12.0°C, z_gen >= 2.5)
      - Operational context precedence (Sensor dropout, grid curtailment, ambient heat)
      - Temporal sliding window persistence (>= 5/6 excursions)
    """

    def __init__(
        self,
        gb_temp_threshold_c: float = 10.0,
        gb_z_threshold: float = 2.5,
        gen_temp_threshold_c: float = 12.0,
        gen_z_threshold: float = 2.5,
        pitch_power_deficit_kw: float = -200.0,
        pitch_z_threshold: float = -2.0,
        persistence_window: int = 6,
        persistence_ratio: float = 0.80,
    ):
        self.gb_temp_threshold_c = gb_temp_threshold_c
        self.gb_z_threshold = gb_z_threshold
        self.gen_temp_threshold_c = gen_temp_threshold_c
        self.gen_z_threshold = gen_z_threshold
        self.pitch_power_deficit_kw = pitch_power_deficit_kw
        self.pitch_z_threshold = pitch_z_threshold
        self.persistence_window = persistence_window
        self.persistence_ratio = persistence_ratio

        # Internal history store per turbine for streaming evaluation: {turbine_id: {"z_gb": [...], ...}}
        self._history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    def reset_history(self, turbine_id: Optional[str] = None) -> None:
        """Resets sliding window history."""
        if turbine_id:
            self._history.pop(turbine_id, None)
        else:
            self._history.clear()

    def evaluate_record(
        self,
        telemetry: TelemetryRecord,
        residuals: ResidualVector,
        context: ContextResult,
        history_z_scores: Optional[Dict[str, List[float]]] = None,
    ) -> AttributionResult:
        """Deterministically attributes faulty subsystem for a single record.

        Args:
            telemetry: Canonical TelemetryRecord.
            residuals: Computed ResidualVector.
            context: Evaluated ContextResult from ContextFilterEngine.
            history_z_scores: Optional explicit history of z-scores for persistence evaluation.

        Returns:
            AttributionResult with subsystem, rule confidence, persistence, and evidence.
        """
        # =========================================================================
        # 1. Precedence 1: SENSOR DROPOUT / DATA QUALITY
        # =========================================================================
        if context.state == OperationalContextState.SENSOR_ANOMALY:
            return AttributionResult(
                subsystem=SubsystemLabel.SENSOR_ANOMALY,
                rule_confidence=1.00,
                is_persistent=True,
                excursion_count=1,
                window_size=self.persistence_window,
                matched_rule="RULE_SENSOR_DROPOUT",
                explanation="Sensor data quality dropout or implausible thermocouple telemetry detected.",
                evidence={"context": context.model_dump()},
            )

        # =========================================================================
        # 2. Precedence 2: GRID CURTAILMENT
        # =========================================================================
        if context.state == OperationalContextState.CURTAILED:
            return AttributionResult(
                subsystem=SubsystemLabel.GRID_CURTAILMENT,
                rule_confidence=1.00,
                is_persistent=True,
                excursion_count=1,
                window_size=self.persistence_window,
                matched_rule="RULE_GRID_CURTAILMENT",
                explanation="Active grid curtailment dispatch setpoint or deliberate aerodynamic pitch derate.",
                evidence={
                    "is_curtailed": telemetry.is_curtailed,
                    "pitch_angle": telemetry.pitch_angle,
                    "active_power": telemetry.active_power,
                    "expected_power_kw": residuals.expected_power_kw,
                },
            )

        # =========================================================================
        # 3. Benign Context Suppression (LOW_WIND_IDLE or HIGH_AMBIENT_DERATE)
        # =========================================================================
        if context.state in (OperationalContextState.LOW_WIND_IDLE, OperationalContextState.HIGH_AMBIENT_DERATE):
            # Check if there is an undeniable severe mechanical fault despite heat/low-wind
            is_severe_gb_fault = (residuals.residual_gb_temp_c >= 15.0 and residuals.z_gb >= 3.5)
            if not is_severe_gb_fault:
                return AttributionResult(
                    subsystem=SubsystemLabel.NORMAL_OPERATION,
                    rule_confidence=1.00,
                    is_persistent=False,
                    excursion_count=0,
                    window_size=self.persistence_window,
                    matched_rule="RULE_BENIGN_CONTEXT_NORMAL",
                    explanation=f"Benign operating context ({context.state.value}) suppresses equipment fault alerts.",
                    evidence={"context_state": context.state.value, "metadata": context.metadata},
                )

        # =========================================================================
        # 4. Normal Context: Physical Residual Evaluation & Persistence
        # =========================================================================
        # Retrieve or construct z-score histories
        tid = telemetry.turbine_id
        if history_z_scores:
            gb_hist = history_z_scores.get("z_gb", [residuals.z_gb])
            gen_hist = history_z_scores.get("z_gen", [residuals.z_gen])
            p_hist = history_z_scores.get("z_power", [residuals.z_power])
        else:
            self._history[tid]["z_gb"].append(residuals.z_gb)
            self._history[tid]["z_gen"].append(residuals.z_gen)
            self._history[tid]["z_power"].append(residuals.z_power)
            # Maintain sliding window cap
            if len(self._history[tid]["z_gb"]) > self.persistence_window:
                self._history[tid]["z_gb"].pop(0)
                self._history[tid]["z_gen"].pop(0)
                self._history[tid]["z_power"].pop(0)

            gb_hist = self._history[tid]["z_gb"]
            gen_hist = self._history[tid]["z_gen"]
            p_hist = self._history[tid]["z_power"]

        # Calculate persistence excursions
        gb_excursions = sum(1 for z in gb_hist if z >= self.gb_z_threshold)
        gen_excursions = sum(1 for z in gen_hist if z >= self.gen_z_threshold)
        p_excursions = sum(1 for z in p_hist if z <= self.pitch_z_threshold)

        w = max(len(gb_hist), 1)
        required_excursions = max(1, int(self.persistence_ratio * self.persistence_window))

        # Check Gearbox Thermal Fault Rule
        if residuals.residual_gb_temp_c > self.gb_temp_threshold_c and residuals.z_gb >= self.gb_z_threshold:
            is_pers = (gb_excursions >= required_excursions) or (len(gb_hist) < self.persistence_window and gb_excursions == len(gb_hist))
            return AttributionResult(
                subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
                rule_confidence=0.90,
                is_persistent=is_pers,
                excursion_count=gb_excursions,
                window_size=w,
                matched_rule="RULE_DRIVETRAIN_GEARBOX_THERMAL",
                explanation=f"Gearbox bearing thermal excursion detected (R_gb={residuals.residual_gb_temp_c:+.2f}°C > +{self.gb_temp_threshold_c}°C, z_gb={residuals.z_gb:+.2f} >= {self.gb_z_threshold}σ).",
                evidence={
                    "residual_gb_temp_c": residuals.residual_gb_temp_c,
                    "z_gb": residuals.z_gb,
                    "excursions": gb_excursions,
                    "window": w,
                },
            )

        # Check Generator Cooling Fault Rule
        if residuals.residual_gen_temp_c > self.gen_temp_threshold_c and residuals.z_gen >= self.gen_z_threshold:
            is_pers = (gen_excursions >= required_excursions) or (len(gen_hist) < self.persistence_window and gen_excursions == len(gen_hist))
            return AttributionResult(
                subsystem=SubsystemLabel.GENERATOR_COOLING,
                rule_confidence=0.85,
                is_persistent=is_pers,
                excursion_count=gen_excursions,
                window_size=w,
                matched_rule="RULE_GENERATOR_COOLING_THERMAL",
                explanation=f"Generator stator winding thermal excursion detected (R_gen={residuals.residual_gen_temp_c:+.2f}°C > +{self.gen_temp_threshold_c}°C, z_gen={residuals.z_gen:+.2f} >= {self.gen_z_threshold}σ).",
                evidence={
                    "residual_gen_temp_c": residuals.residual_gen_temp_c,
                    "z_gen": residuals.z_gen,
                    "excursions": gen_excursions,
                    "window": w,
                },
            )

        # Check Aerodynamic Pitch Deficit Rule
        if residuals.residual_power_kw <= self.pitch_power_deficit_kw and residuals.z_power <= self.pitch_z_threshold:
            is_pers = (p_excursions >= required_excursions) or (len(p_hist) < self.persistence_window and p_excursions == len(p_hist))
            return AttributionResult(
                subsystem=SubsystemLabel.AERODYNAMIC_PITCH,
                rule_confidence=0.88,
                is_persistent=is_pers,
                excursion_count=p_excursions,
                window_size=w,
                matched_rule="RULE_AERODYNAMIC_PITCH_DEFICIT",
                explanation=f"Aerodynamic pitch asymmetry power deficit detected (R_p={residuals.residual_power_kw:+.1f} kW <= {self.pitch_power_deficit_kw} kW, z_p={residuals.z_power:+.2f} <= {self.pitch_z_threshold}σ).",
                evidence={
                    "residual_power_kw": residuals.residual_power_kw,
                    "z_power": residuals.z_power,
                    "excursions": p_excursions,
                    "window": w,
                },
            )

        # Normal Nominal Baseline
        return AttributionResult(
            subsystem=SubsystemLabel.NORMAL_OPERATION,
            rule_confidence=1.00,
            is_persistent=False,
            excursion_count=0,
            window_size=w,
            matched_rule="RULE_NORMAL_OPERATION",
            explanation="Operating residuals within nominal baseline tolerances.",
            evidence={
                "z_power": residuals.z_power,
                "z_gb": residuals.z_gb,
                "z_gen": residuals.z_gen,
            },
        )

    def evaluate_batch(
        self,
        records: List[TelemetryRecord],
        residuals_list: List[ResidualVector],
        context_list: List[ContextResult],
    ) -> List[AttributionResult]:
        """Evaluates subsystem attribution for a sequence of records.

        Args:
            records: TelemetryRecord list.
            residuals_list: ResidualVector list.
            context_list: ContextResult list.

        Returns:
            List of AttributionResult objects.
        """
        results: List[AttributionResult] = []
        for rec, res, ctx in zip(records, residuals_list, context_list):
            results.append(self.evaluate_record(rec, res, ctx))
        return results

    @staticmethod
    def compute_attribution_metrics(
        predictions: List[SubsystemLabel],
        ground_truth: List[SubsystemLabel],
        scenario_ids: Optional[List[str]] = None,
        eligible_mask: Optional[List[bool]] = None,
    ) -> Dict[str, Any]:
        """Computes authoritative attribution accuracy metrics (TEST-REAS-01).

        Formulation:
            Attribution Accuracy = (correctly attributed eligible records / total eligible records) * 100%

        Returns:
            Dictionary containing overall accuracy, per-scenario accuracy, confusion matrix, and record counts.
        """
        if len(predictions) != len(ground_truth):
            raise ValueError(f"Length mismatch: {len(predictions)} predictions vs {len(ground_truth)} ground truth")

        n_total = len(predictions)
        mask = eligible_mask if eligible_mask is not None else [True] * n_total

        eligible_pred = [predictions[i] for i in range(n_total) if mask[i]]
        eligible_true = [ground_truth[i] for i in range(n_total) if mask[i]]
        eligible_scenarios = [scenario_ids[i] for i in range(n_total) if mask[i]] if scenario_ids else None

        n_eligible = len(eligible_pred)
        if n_eligible == 0:
            return {
                "overall_accuracy_pct": 100.0,
                "total_eligible_records": 0,
                "correct_classifications": 0,
                "incorrect_classifications": 0,
                "per_scenario_accuracy": {},
                "confusion_matrix": {},
            }

        correct = sum(1 for p, t in zip(eligible_pred, eligible_true) if p == t)
        incorrect = n_eligible - correct
        accuracy_pct = (correct / n_eligible) * 100.0

        # Multi-class confusion matrix
        all_labels = [label.value for label in SubsystemLabel]
        confusion_matrix: Dict[str, Dict[str, int]] = {
            true_lbl: {pred_lbl: 0 for pred_lbl in all_labels}
            for true_lbl in all_labels
        }
        for p, t in zip(eligible_pred, eligible_true):
            confusion_matrix[t.value][p.value] += 1

        # Per-scenario breakdown
        per_scenario: Dict[str, Dict[str, Any]] = {}
        if eligible_scenarios:
            scenario_groups: Dict[str, List[Tuple[SubsystemLabel, SubsystemLabel]]] = defaultdict(list)
            for p, t, s in zip(eligible_pred, eligible_true, eligible_scenarios):
                scenario_groups[s].append((p, t))

            for s_id, pairs in scenario_groups.items():
                s_correct = sum(1 for p, t in pairs if p == t)
                s_total = len(pairs)
                per_scenario[s_id] = {
                    "total_records": s_total,
                    "correct_records": s_correct,
                    "accuracy_pct": round((s_correct / s_total) * 100.0, 2),
                }

        return {
            "overall_accuracy_pct": round(accuracy_pct, 2),
            "total_eligible_records": n_eligible,
            "correct_classifications": correct,
            "incorrect_classifications": incorrect,
            "per_scenario_accuracy": per_scenario,
            "confusion_matrix": confusion_matrix,
        }
