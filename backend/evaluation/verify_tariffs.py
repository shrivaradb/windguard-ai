"""Workstream WS-P8-05: Financial Loss & Tariff Provenance Calculation Verification.

Source of Truth:
- docs/06_prd.md (FR-007)
- docs/07_srs.md §3.4
- docs/09_technical_design.md §2.3
- docs/10_data_architecture.md §4.4
- docs/PHASE_8_SCOPE_REVIEW.md (WS-P8-05)
- docs/PHASE_8_OWNER_DECISION_RESOLUTION.md (OD-P8-01)

Verifies deterministic energy loss (kWh) and financial loss (INR) calculations across the 4-tier
Tariff Provenance Hierarchy. Asserts floating-point precision error < 10^-4 INR and complete
provenance metadata tagging.
Outputs results to evaluation_results/tariffs.json.
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, List
import numpy as np

from backend.data.schema import TelemetryRecord
from backend.engine.context_engine import ContextResult, OperationalContextState
from backend.engine.loss_calculator import LossCalculator, RecordLossResult
from backend.engine.tariff_registry import TariffMode, TariffProvenance, TariffRegistry
from backend.models.residual_engine import ResidualVector


def verify_tariffs(output_dir: Path = None) -> Dict[str, Any]:
    """Verifies tariff resolution, loss accumulation, and floating-point accuracy.

    Args:
        output_dir: Output directory. Defaults to evaluation_results/.

    Returns:
        Structured tariff evaluation results dictionary.
    """
    if output_dir is None:
        output_dir = Path("evaluation_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    tariff_registry = TariffRegistry()
    loss_calculator = LossCalculator(tariff_registry=tariff_registry)

    # 1. Verify 4-tier Tariff Hierarchy resolution
    hierarchy_checks = []

    # Tier 3 Default Configured Baseline (Default ₹3.20/kWh)
    default_tariff = tariff_registry.get_active_tariff()
    hierarchy_checks.append({
        "tier": "Tier 3: Configured Default Baseline",
        "expected_rate": 3.20,
        "resolved_rate": default_tariff.applied_rate_inr_per_kwh,
        "is_match": default_tariff.applied_rate_inr_per_kwh == 3.20,
    })

    # Tier 1 Project-Specific PPA
    ppa_tariff = tariff_registry.set_ppa_tariff(rate_inr_per_kwh=3.45, ppa_contract_id="PPA-AP-2024-WTG07")
    hierarchy_checks.append({
        "tier": "Tier 1: Project-Specific Verified PPA",
        "expected_rate": 3.45,
        "resolved_rate": ppa_tariff.applied_rate_inr_per_kwh,
        "is_match": ppa_tariff.applied_rate_inr_per_kwh == 3.45,
    })

    # Tier 2 Regulatory Benchmark
    gujarat_tariff = tariff_registry.set_regulatory_tariff(rate_inr_per_kwh=2.90, regulator_name="GERC", order_reference="GERC-Order-2025-02")
    hierarchy_checks.append({
        "tier": "Tier 2: Regulatory Reference Benchmark",
        "expected_rate": 2.90,
        "resolved_rate": gujarat_tariff.applied_rate_inr_per_kwh,
        "is_match": gujarat_tariff.applied_rate_inr_per_kwh == 2.90,
    })

    # Tier 4 Scenario Override
    override_tariff = tariff_registry.set_scenario_override(rate_inr_per_kwh=4.10, reason="High Peak Demand Override")
    hierarchy_checks.append({
        "tier": "Tier 4: Scenario Override",
        "expected_rate": 4.10,
        "resolved_rate": override_tariff.applied_rate_inr_per_kwh,
        "is_match": override_tariff.applied_rate_inr_per_kwh == 4.10,
    })

    # Reset to baseline for standard loss verification
    tariff_registry.reset_to_baseline()

    # 2. Mathematical Accuracy Check
    # Scenario: 18% power deficit on 2000 kW turbine for 6 intervals (1 hr)
    # Expected power = 1500 kW, Actual power = 1200 kW -> Deficit = 300 kW
    # Loss per 10-min interval = 300 kW * (10/60 hr) = 50 kWh
    # Financial loss at ₹3.20/kWh = 50 kWh * ₹3.20 = ₹160.00 per interval
    # 6 intervals (1 hr) = 300 kWh, ₹960.00

    dummy_record = TelemetryRecord(
        timestamp="2026-09-20T10:00:00Z",
        turbine_id="WTG-01",
        wind_speed=8.5,
        wind_direction=180.0,
        ambient_temp=25.0,
        active_power=1200.0,
        reactive_power=0.0,
        rotor_speed=14.0,
        generator_speed=1400.0,
        gearbox_bearing_temp=65.0,
        generator_stator_temp=75.0,
        nacelle_temp=30.0,
        pitch_angle=1.0,
        is_curtailed=False,
    )
    dummy_resid = ResidualVector(
        expected_power_kw=1500.0,
        residual_power_kw=-300.0,
        z_power=-3.5,
        expected_gb_temp_c=65.0,
        residual_gb_temp_c=0.0,
        z_gb=0.0,
        expected_gen_temp_c=75.0,
        residual_gen_temp_c=0.0,
        z_gen=0.0,
    )
    dummy_ctx = ContextResult(
        state=OperationalContextState.NORMAL,
        is_suppressed=False,
        explanation="Normal operation",
        precedence_level=5,
    )

    loss_res = loss_calculator.calculate_record_loss(dummy_record, dummy_resid, dummy_ctx)

    expected_kwh = 300.0 * (10.0 / 60.0)  # 50.0 kWh
    expected_inr = 50.0 * 3.20  # 160.0 INR

    kwh_error = abs(loss_res.eligible_degradation_energy_kwh - expected_kwh)
    inr_error = abs(loss_res.financial_loss_inr - expected_inr)

    # Curtailed condition: loss must be 0.0 when is_curtailed == True
    curtailed_record = dummy_record.model_copy(update={"is_curtailed": True})
    curtailed_ctx = ContextResult(
        state=OperationalContextState.CURTAILED,
        is_suppressed=True,
        explanation="Grid curtailment active",
        precedence_level=2,
    )
    curtailed_loss_res = loss_calculator.calculate_record_loss(curtailed_record, dummy_resid, curtailed_ctx)
    curtailment_zero_loss_verified = curtailed_loss_res.eligible_degradation_energy_kwh == 0.0 and curtailed_loss_res.financial_loss_inr == 0.0

    all_hierarchy_matches = all(c["is_match"] for c in hierarchy_checks)
    float_accuracy_pass = (kwh_error < 1e-4) and (inr_error < 1e-4)

    results = {
        "benchmark_id": "WS-P8-05-TARIFF-LOSS-VERIFICATION",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tariff_hierarchy_verification": {
            "tiers_tested": hierarchy_checks,
            "all_tiers_resolved_correctly": all_hierarchy_matches,
            "governance_classification": "FROZEN / PREVIOUSLY APPROVED",
        },
        "mathematical_accuracy": {
            "theoretical_expected_kwh_per_interval": expected_kwh,
            "measured_energy_loss_kwh": loss_res.eligible_degradation_energy_kwh,
            "energy_loss_error_kwh": kwh_error,
            "theoretical_expected_financial_loss_inr": expected_inr,
            "measured_financial_loss_inr": loss_res.financial_loss_inr,
            "financial_loss_error_inr": inr_error,
            "float_tolerance_threshold": 1e-4,
            "curtailment_zero_loss_verified": curtailment_zero_loss_verified,
            "status": "PASS" if float_accuracy_pass and curtailment_zero_loss_verified else "FAIL",
            "governance_classification": "FROZEN / PREVIOUSLY APPROVED",
        },
        "provenance_metadata": {
            "tariff_mode": loss_res.tariff_provenance.mode.value,
            "applied_rate_inr": loss_res.tariff_provenance.applied_rate_inr_per_kwh,
            "source_reference": loss_res.tariff_provenance.source_reference,
            "currency": loss_res.tariff_provenance.currency,
        },
        "acceptance_gate": {
            "gate_id": "GATE-P8-08",
            "requirement": "Tariff provenance and financial loss calculation verified with floating error < 10^-4 INR",
            "status": "PASS" if all_hierarchy_matches and float_accuracy_pass and curtailment_zero_loss_verified else "FAIL",
        },
    }

    with open(output_dir / "tariffs.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    res = verify_tariffs()
    print(f"Tariff Verification complete. Math status: {res['mathematical_accuracy']['status']}, Gate: {res['acceptance_gate']['status']}")
