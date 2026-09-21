"""Transparent 5-Factor Multi-Criteria Prioritization Engine for WindGuard AI (Layer 3).

Source of Truth:
- docs/06_prd.md §7 (FR-006)
- docs/07_srs.md §3.4
- docs/08_system_architecture.md §3.4
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.5

Combines 5 normalized analytical sub-scores into a deterministic 0-100 Priority Score:
  1. S_sev  (Anomaly Severity, w=0.25)
  2. S_pers (Statistical Persistence, w=0.20)
  3. S_conf (Rule Evidence Confidence, w=0.20)
  4. S_crit (Component Criticality, w=0.15)
  5. S_loss (Financial Loss Impact, w=0.20)

Note on Parameter Classification:
  All weights, component criticality scores, the ₹50,000 loss normalization ceiling,
  and severity thresholds (80/60/40) are INITIAL DESIGN PARAMETERS.
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.engine.loss_calculator import RecordLossResult
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.models.residual_engine import ResidualVector


class SeverityLevel(str, Enum):
    """Canonical Anomaly Severity Tiers."""

    CRITICAL = "CRITICAL"  # Priority Score >= 80.0
    HIGH = "HIGH"          # 60.0 <= Priority Score < 80.0
    MEDIUM = "MEDIUM"      # 40.0 <= Priority Score < 60.0
    LOW = "LOW"            # Priority Score < 40.0


class PriorityScoreBreakdown(BaseModel):
    """Detailed mathematical breakdown of 5-factor priority score calculation."""

    s_sev: float = Field(..., ge=0.0, le=1.0, description="Normalized severity sub-score (0.0 to 1.0)")
    s_pers: float = Field(..., ge=0.0, le=1.0, description="Normalized persistence sub-score (0.0 to 1.0)")
    s_conf: float = Field(..., ge=0.0, le=1.0, description="Rule confidence sub-score (0.0 to 1.0)")
    s_crit: float = Field(..., ge=0.0, le=1.0, description="Component criticality sub-score (0.0 to 1.0)")
    s_loss: float = Field(..., ge=0.0, le=1.0, description="Financial loss impact sub-score (0.0 to 1.0)")

    w_sev: float = Field(default=0.25, description="Initial design parameter weight for severity")
    w_pers: float = Field(default=0.20, description="Initial design parameter weight for persistence")
    w_conf: float = Field(default=0.20, description="Initial design parameter weight for rule confidence")
    w_crit: float = Field(default=0.15, description="Initial design parameter weight for component criticality")
    w_loss: float = Field(default=0.20, description="Initial design parameter weight for financial loss")

    priority_score: float = Field(..., ge=0.0, le=100.0, description="Combined priority score (0.0 to 100.0)")
    severity: SeverityLevel = Field(..., description="Categorical severity tier")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class PrioritizationEngine:
    """Deterministic 5-Factor Anomaly Prioritization Scoring Engine.

    Formula:
        Score = 100 * (w1*S_sev + w2*S_pers + w3*S_conf + w4*S_crit + w5*S_loss)
    """

    # Initial Design Parameters (docs/PHASE_3_SCOPE_REVIEW.md §3 & §4.5)
    DEFAULT_WEIGHTS = {
        "w_sev": 0.25,
        "w_pers": 0.20,
        "w_conf": 0.20,
        "w_crit": 0.15,
        "w_loss": 0.20,
    }

    COMPONENT_CRITICALITY: Dict[SubsystemLabel, float] = {
        SubsystemLabel.DRIVETRAIN_GEARBOX: 1.0,
        SubsystemLabel.GENERATOR_COOLING: 0.8,
        SubsystemLabel.AERODYNAMIC_PITCH: 0.6,
        SubsystemLabel.SENSOR_ANOMALY: 0.3,
        SubsystemLabel.GRID_CURTAILMENT: 0.1,
        SubsystemLabel.NORMAL_OPERATION: 0.0,
    }

    LOSS_NORMALIZATION_CEILING_INR: float = 50000.0  # ₹50,000 reference single-shift severe loss ceiling

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        loss_norm_ceiling: Optional[float] = None,
        crit_scores: Optional[Dict[SubsystemLabel, float]] = None,
    ):
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self.loss_norm_ceiling = loss_norm_ceiling or self.LOSS_NORMALIZATION_CEILING_INR
        self.crit_scores = crit_scores or dict(self.COMPONENT_CRITICALITY)

        # Enforce weight sum validation
        w_sum = sum(self.weights.values())
        if abs(w_sum - 1.0) > 1e-4:
            raise ValueError(f"Prioritization weights must sum to 1.0 (got {w_sum:.4f})")

    def compute_priority_score(
        self,
        residuals: ResidualVector,
        attribution: AttributionResult,
        loss_result: Optional[RecordLossResult] = None,
        cumulative_maint_loss_inr: Optional[float] = None,
    ) -> PriorityScoreBreakdown:
        """Computes the 5-factor priority score for a detected operational event.

        Args:
            residuals: ResidualVector containing standardized z-scores.
            attribution: AttributionResult containing subsystem classification and rule confidence.
            loss_result: Optional single-record loss result.
            cumulative_maint_loss_inr: Optional cumulative financial loss in INR over an active anomaly episode.

        Returns:
            PriorityScoreBreakdown with sub-scores, combined 0-100 score, and severity classification.
        """
        # If normal operation, score is 0.0 with LOW severity
        if attribution.subsystem == SubsystemLabel.NORMAL_OPERATION:
            return PriorityScoreBreakdown(
                s_sev=0.0,
                s_pers=0.0,
                s_conf=0.0,
                s_crit=0.0,
                s_loss=0.0,
                w_sev=self.weights["w_sev"],
                w_pers=self.weights["w_pers"],
                w_conf=self.weights["w_conf"],
                w_crit=self.weights["w_crit"],
                w_loss=self.weights["w_loss"],
                priority_score=0.0,
                severity=SeverityLevel.LOW,
            )

        # 1. S_sev — Normalized Anomaly Severity
        # z_P normalized by 2.0; z_GB and z_Gen normalized by 2.5; scaled relative to 4.0
        z_p_norm = abs(residuals.z_power) / 2.0
        z_gb_norm = abs(residuals.z_gb) / 2.5
        z_gen_norm = abs(residuals.z_gen) / 2.5
        max_z_ratio = max(z_p_norm, z_gb_norm, z_gen_norm)
        s_sev = min(1.0, max(0.0, max_z_ratio / 4.0))

        # 2. S_pers — Statistical Persistence
        w_size = max(attribution.window_size, 1)
        s_pers = min(1.0, max(0.0, attribution.excursion_count / float(w_size)))

        # 3. S_conf — Rule Confidence Score
        s_conf = min(1.0, max(0.0, attribution.rule_confidence))

        # 4. S_crit — Component Criticality
        s_crit = self.crit_scores.get(attribution.subsystem, 0.5)

        # 5. S_loss — Financial Loss Impact
        fin_loss = (
            cumulative_maint_loss_inr
            if cumulative_maint_loss_inr is not None
            else (loss_result.financial_loss_inr if loss_result else 0.0)
        )
        s_loss = min(1.0, max(0.0, fin_loss / self.loss_norm_ceiling))

        # Combine weighted sub-scores
        raw_score = 100.0 * (
            self.weights["w_sev"] * s_sev
            + self.weights["w_pers"] * s_pers
            + self.weights["w_conf"] * s_conf
            + self.weights["w_crit"] * s_crit
            + self.weights["w_loss"] * s_loss
        )
        bounded_score = round(min(100.0, max(0.0, raw_score)), 2)

        # Classify Severity Level (Initial Baseline Thresholds)
        if bounded_score >= 80.0:
            sev_level = SeverityLevel.CRITICAL
        elif bounded_score >= 60.0:
            sev_level = SeverityLevel.HIGH
        elif bounded_score >= 40.0:
            sev_level = SeverityLevel.MEDIUM
        else:
            sev_level = SeverityLevel.LOW

        return PriorityScoreBreakdown(
            s_sev=round(s_sev, 4),
            s_pers=round(s_pers, 4),
            s_conf=round(s_conf, 4),
            s_crit=round(s_crit, 4),
            s_loss=round(s_loss, 4),
            w_sev=self.weights["w_sev"],
            w_pers=self.weights["w_pers"],
            w_conf=self.weights["w_conf"],
            w_crit=self.weights["w_crit"],
            w_loss=self.weights["w_loss"],
            priority_score=bounded_score,
            severity=sev_level,
        )
