"""Unit Tests for Multi-Mode Tariff Registry & Provenance (Layer 3).

Source of Truth:
- docs/07_srs.md §3.5
- docs/09_technical_design.md §2.3
- docs/10_data_architecture.md §4.2
- docs/PHASE_3_SCOPE_REVIEW.md §4.3 & §8 (TEST-TRF-01)
"""

import pytest
from pydantic import ValidationError

from backend.engine.tariff_registry import (
    TariffMode,
    TariffProvenance,
    TariffRegistry,
)


@pytest.fixture
def registry() -> TariffRegistry:
    return TariffRegistry()


def test_tariff_modes_enum():
    """Verifies all 4 canonical tariff modes exist."""
    assert TariffMode.PROJECT_PPA == "PROJECT_PPA"
    assert TariffMode.REGULATORY_BENCHMARK == "REGULATORY_BENCHMARK"
    assert TariffMode.CONFIGURED_BASELINE == "CONFIGURED_BASELINE"
    assert TariffMode.SCENARIO_OVERRIDE == "SCENARIO_OVERRIDE"


def test_default_configured_baseline_assumption(registry):
    """Verifies default demonstration baseline (₹3.20/kWh) is tagged as an assumption."""
    active = registry.get_active_tariff()
    assert active.applied_rate_inr_per_kwh == 3.20
    assert active.mode == TariffMode.CONFIGURED_BASELINE
    assert active.is_baseline_assumption is True
    assert active.currency == "INR"
    assert "Configured Baseline Assumption" in active.source_reference


def test_rate_system_constraint_bounds(registry):
    """Verifies hard validation limits: ₹0.01 <= rate <= ₹20.00/kWh."""
    # Valid boundaries
    t_min = registry.set_tariff(0.01, TariffMode.CONFIGURED_BASELINE, "Min Bound Test")
    assert t_min.applied_rate_inr_per_kwh == 0.01

    t_max = registry.set_tariff(20.00, TariffMode.CONFIGURED_BASELINE, "Max Bound Test")
    assert t_max.applied_rate_inr_per_kwh == 20.00

    # Negative / Zero rate rejection
    with pytest.raises((ValueError, ValidationError)):
        registry.set_tariff(0.0, TariffMode.CONFIGURED_BASELINE, "Zero Rate Test")

    with pytest.raises((ValueError, ValidationError)):
        registry.set_tariff(-1.50, TariffMode.CONFIGURED_BASELINE, "Negative Rate Test")

    # Upper bound violation rejection
    with pytest.raises((ValueError, ValidationError)):
        registry.set_tariff(20.01, TariffMode.CONFIGURED_BASELINE, "Excessive Rate Test")


def test_set_ppa_tariff(registry):
    """Verifies configuration of a project-specific PPA rate."""
    t_ppa = registry.set_ppa_tariff(
        rate_inr_per_kwh=3.45,
        ppa_contract_id="PPA-SECI-2024-WIND-08",
        effective_date="2026-01-01T00:00:00Z",
    )
    assert t_ppa.applied_rate_inr_per_kwh == 3.45
    assert t_ppa.mode == TariffMode.PROJECT_PPA
    assert t_ppa.is_baseline_assumption is False
    assert "PPA-SECI-2024-WIND-08" in t_ppa.source_reference


def test_set_regulatory_tariff(registry):
    """Verifies configuration of an official regulatory benchmark tariff."""
    t_reg = registry.set_regulatory_tariff(
        rate_inr_per_kwh=2.95,
        regulator_name="CERC",
        order_reference="Order No. 12/SM/2025",
    )
    assert t_reg.applied_rate_inr_per_kwh == 2.95
    assert t_reg.mode == TariffMode.REGULATORY_BENCHMARK
    assert t_reg.is_baseline_assumption is False
    assert "CERC" in t_reg.source_reference


def test_set_scenario_override_and_reset(registry):
    """Verifies operator scenario override and subsequent reset to baseline."""
    t_ovr = registry.set_scenario_override(
        rate_inr_per_kwh=5.00,
        reason="What-if peak market pricing test",
    )
    assert t_ovr.applied_rate_inr_per_kwh == 5.00
    assert t_ovr.mode == TariffMode.SCENARIO_OVERRIDE

    # Reset to baseline
    t_reset = registry.reset_to_baseline()
    assert t_reset.applied_rate_inr_per_kwh == 3.20
    assert t_reset.mode == TariffMode.CONFIGURED_BASELINE
    assert t_reset.is_baseline_assumption is True


def test_provenance_immutability(registry):
    """Verifies that TariffProvenance instances are immutable (frozen)."""
    active = registry.get_active_tariff()
    with pytest.raises(ValidationError):
        # Attempt direct mutation
        active.applied_rate_inr_per_kwh = 4.00  # type: ignore

    # Verify history tracking
    history = registry.get_history()
    assert len(history) >= 1
    assert history[0] == active
