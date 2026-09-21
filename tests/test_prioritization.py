"""Unit Tests for 5-Factor Prioritization Scoring Engine (Layer 3).

Source of Truth:
- docs/07_srs.md §3.4
- docs/09_technical_design.md §2.3
- docs/PHASE_3_SCOPE_REVIEW.md §4.5 & §8 (TEST-PRIO-01)
"""

import pytest
from backend.engine.prioritization import (
    PrioritizationEngine,
    PriorityScoreBreakdown,
    SeverityLevel,
)
from backend.engine.reasoner import AttributionResult, SubsystemLabel
from backend.models.residual_engine import ResidualVector


@pytest.fixture
def prioritizer() -> PrioritizationEngine:
    return PrioritizationEngine()


def test_severity_levels_enum():
    """Verifies all 4 canonical severity levels exist."""
    assert SeverityLevel.CRITICAL == "CRITICAL"
    assert SeverityLevel.HIGH == "HIGH"
    assert SeverityLevel.MEDIUM == "MEDIUM"
    assert SeverityLevel.LOW == "LOW"


def test_weights_sum_validation():
    """Verifies that engine enforces sum(weights) == 1.0."""
    valid_weights = {"w_sev": 0.25, "w_pers": 0.20, "w_conf": 0.20, "w_crit": 0.15, "w_loss": 0.20}
    engine = PrioritizationEngine(weights=valid_weights)
    assert engine is not None

    invalid_weights = {"w_sev": 0.30, "w_pers": 0.30, "w_conf": 0.30, "w_crit": 0.30, "w_loss": 0.30}
    with pytest.raises(ValueError):
        PrioritizationEngine(weights=invalid_weights)


def test_normal_operation_zero_score(prioritizer):
    """Verifies that normal operation evaluates to zero priority score and LOW severity."""
    res = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=0.0,
        z_power=0.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr = AttributionResult(
        subsystem=SubsystemLabel.NORMAL_OPERATION,
        rule_confidence=1.00,
        is_persistent=False,
        matched_rule="RULE_NORMAL_OPERATION",
        explanation="Nominal.",
    )
    score = prioritizer.compute_priority_score(res, attr)
    assert score.priority_score == 0.0
    assert score.severity == SeverityLevel.LOW
    assert score.s_sev == 0.0
    assert score.s_crit == 0.0


def test_score_bounding_0_to_100(prioritizer):
    """Verifies that Priority Score is hard-bounded in [0.0, 100.0]."""
    extreme_residuals = ResidualVector(
        expected_power_kw=2000.0,
        residual_power_kw=-1000.0,
        z_power=-50.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=50.0,
        z_gb=20.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=40.0,
        z_gen=15.0,
    )
    attr = AttributionResult(
        subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
        rule_confidence=1.00,
        is_persistent=True,
        excursion_count=6,
        window_size=6,
        matched_rule="RULE_DRIVETRAIN_GEARBOX_THERMAL",
        explanation="Extreme failure.",
    )
    score = prioritizer.compute_priority_score(
        extreme_residuals, attr, cumulative_maint_loss_inr=500000.0
    )
    assert 0.0 <= score.priority_score <= 100.0
    assert score.priority_score == 100.0
    assert score.severity == SeverityLevel.CRITICAL


def test_monotonicity_with_severity_and_loss(prioritizer):
    """Verifies monotonic score increases with higher residual excursions and higher financial loss."""
    attr = AttributionResult(
        subsystem=SubsystemLabel.AERODYNAMIC_PITCH,
        rule_confidence=0.88,
        is_persistent=True,
        excursion_count=5,
        window_size=6,
        matched_rule="RULE_AERODYNAMIC_PITCH_DEFICIT",
        explanation="Pitch derate.",
    )

    res_mild = ResidualVector(
        expected_power_kw=1800.0,
        residual_power_kw=-250.0,
        z_power=-2.5,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )

    res_severe = ResidualVector(
        expected_power_kw=1800.0,
        residual_power_kw=-600.0,
        z_power=-6.5,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )

    score_mild = prioritizer.compute_priority_score(res_mild, attr, cumulative_maint_loss_inr=5000.0)
    score_severe = prioritizer.compute_priority_score(res_severe, attr, cumulative_maint_loss_inr=35000.0)

    assert score_severe.priority_score > score_mild.priority_score
    assert score_severe.s_sev > score_mild.s_sev
    assert score_severe.s_loss > score_mild.s_loss


def test_severity_classification_thresholds(prioritizer):
    """Verifies severity tier assignments based on initial baseline thresholds (80/60/40)."""
    res = ResidualVector(
        expected_power_kw=1800.0,
        residual_power_kw=-300.0,
        z_power=-3.0,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=12.0,
        z_gb=3.5,
        expected_gen_temp_c=70.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    attr = AttributionResult(
        subsystem=SubsystemLabel.DRIVETRAIN_GEARBOX,
        rule_confidence=0.90,
        is_persistent=True,
        excursion_count=6,
        window_size=6,
        matched_rule="RULE_DRIVETRAIN_GEARBOX_THERMAL",
        explanation="Gearbox wear.",
    )

    # High loss -> CRITICAL (>= 80)
    score_crit = prioritizer.compute_priority_score(res, attr, cumulative_maint_loss_inr=45000.0)
    assert score_crit.priority_score >= 80.0
    assert score_crit.severity == SeverityLevel.CRITICAL

    # Lower persistence / loss -> HIGH or MEDIUM
    attr_med = attr.model_copy(update={"excursion_count": 2, "is_persistent": False})
    score_med = prioritizer.compute_priority_score(res, attr_med, cumulative_maint_loss_inr=2000.0)
    assert score_med.priority_score < 80.0
    assert score_med.severity in (SeverityLevel.HIGH, SeverityLevel.MEDIUM)


def test_component_criticality_hierarchy(prioritizer):
    """Verifies canonical component criticality hierarchy: GB > Gen > Pitch > Sensor > Curtailment > Normal."""
    crit = prioritizer.crit_scores
    assert crit[SubsystemLabel.DRIVETRAIN_GEARBOX] == 1.0
    assert crit[SubsystemLabel.GENERATOR_COOLING] == 0.8
    assert crit[SubsystemLabel.AERODYNAMIC_PITCH] == 0.6
    assert crit[SubsystemLabel.SENSOR_ANOMALY] == 0.3
    assert crit[SubsystemLabel.GRID_CURTAILMENT] == 0.1
    assert crit[SubsystemLabel.NORMAL_OPERATION] == 0.0
