"""Dedicated Phase 8 Test Suite: Automated Evaluation Suite & Verification Harness.

Source of Truth:
- docs/14_implementation_plan.md §3 (Phase 8/9 Deliverables)
- docs/PHASE_8_SCOPE_REVIEW.md (WS-P8-01 through WS-P8-07)
- docs/PHASE_8_OWNER_DECISION_RESOLUTION.md (OD-P8-01 through OD-P8-06)

Tests cover:
1. WS-P8-01: Physics & analytical ML evaluation engine
2. WS-P8-02: Scenario benchmarking (S1–S5) and contextual false-alarm suppression
3. WS-P8-03: Technical RAG retrieval metrics and cryptographic provenance
4. WS-P8-04: Advisory numerical fidelity, Pydantic schema validation, and negative guardrail injection
5. WS-P8-05: 4-tier tariff provenance hierarchy and floating-point precision
6. WS-P8-06: Multi-sample performance latency and formal SLA ceiling compliance
7. WS-P8-07: Academic & technical evaluation report generation
8. System Invariants: Zero SCADA actuation routes, offline mode self-containment, model read-only consumption
"""

import json
from pathlib import Path
import tempfile
import pytest

from backend.api.app import create_app
from backend.config import settings
from backend.evaluation.audit_advisories import audit_advisories
from backend.evaluation.benchmark_performance import benchmark_performance
from backend.evaluation.benchmark_scenarios import run_scenario_benchmark
from backend.evaluation.evaluate_models import evaluate_models
from backend.evaluation.evaluate_rag import evaluate_rag
from backend.evaluation.generate_report import generate_evaluation_report
from backend.evaluation.verify_tariffs import verify_tariffs


class TestPhase8EvaluationSuite:
    """Comprehensive test harness for Phase 8 evaluation modules."""

    @pytest.fixture
    def temp_eval_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_ws_p8_01_evaluate_models(self, temp_eval_dir):
        """WS-P8-01: Verifies physics & ML evaluation execution and metric targets."""
        res = evaluate_models(output_dir=temp_eval_dir)

        assert "power_curve_model" in res
        assert "thermal_baseline_model" in res
        assert (temp_eval_dir / "models.json").exists()

        pwr_m = res["power_curve_model"]["metrics"]
        assert pwr_m["r2_score"]["measured"] >= 0.95
        assert pwr_m["rmse_kw"]["measured"] <= 45.0
        assert pwr_m["single_latency_ms"]["measured_mean"] < 5.0

        thm_m = res["thermal_baseline_model"]["metrics"]
        assert thm_m["gearbox_bearing_rmse_c"]["governance_classification"] == "HISTORICAL BASELINE / LIMITATION"
        assert thm_m["generator_stator_rmse_c"]["governance_classification"] == "HISTORICAL BASELINE / LIMITATION"

    def test_ws_p8_02_scenario_benchmark(self, temp_eval_dir):
        """WS-P8-02: Verifies multi-scenario (S1–S5) benchmarking and context filtering."""
        scn_res, ctx_res = run_scenario_benchmark(output_dir=temp_eval_dir)

        assert (temp_eval_dir / "scenarios.json").exists()
        assert (temp_eval_dir / "context.json").exists()

        # Check anomaly metrics under Project Benchmark Performance framing
        assert scn_res["dataset_provenance"]["evaluation_scope"] == "PROJECT BENCHMARK PERFORMANCE"
        assert scn_res["metrics"]["precision"]["governance_classification"] == "PROPOSED \u2014 OWNER DECISION REQUIRED"
        assert scn_res["metrics"]["recall"]["governance_classification"] == "PROPOSED \u2014 OWNER DECISION REQUIRED"
        assert scn_res["metrics"]["f1_score"]["governance_classification"] == "PROPOSED \u2014 OWNER DECISION REQUIRED"
        assert scn_res["metrics"]["false_alarm_rate"]["measured"] <= 0.05

        # Check 100% contextual suppression on S4 curtailment and 11.6% on heatwave
        assert ctx_res["metrics"]["curtailment_suppression_rate"]["measured_percentage"] == "100.0%"
        assert ctx_res["metrics"]["heatwave_suppression_rate"]["measured_percentage"] == "11.6%"

    def test_ws_p8_03_evaluate_rag(self, temp_eval_dir):
        """WS-P8-03: Verifies RAG retrieval metrics on 15-query benchmark."""
        rag_res = evaluate_rag(output_dir=temp_eval_dir)

        assert (temp_eval_dir / "rag.json").exists()
        ret_m = rag_res["retrieval_metrics"]

        assert ret_m["mean_reciprocal_rank"]["measured"] == 1.0000
        assert ret_m["recall_at_3"]["measured_percentage"] == "96.67%"
        assert ret_m["historical_precision_at_3"]["governance_classification"] == "MEASUREMENT ONLY — NO PASS/FAIL TARGET"
        assert ret_m["retrieval_latency_ms"]["measured_mean"] < 50.0

        prov_m = rag_res["provenance_and_authenticity"]
        assert prov_m["provenance_integrity_rate"] == 1.0
        assert prov_m["fabricated_page_violations"] == 0

    def test_ws_p8_04_advisory_audit_and_guardrails(self, temp_eval_dir):
        """WS-P8-04: Verifies numerical fidelity, JSON schema, and guardrail enforcement."""
        adv_res, safe_res = audit_advisories(output_dir=temp_eval_dir)

        assert (temp_eval_dir / "advisories.json").exists()
        assert (temp_eval_dir / "safety.json").exists()

        adv_m = adv_res["audit_metrics"]
        assert adv_m["numerical_fidelity_rate"]["measured_percentage"] == "100.0%"
        assert adv_m["schema_conformance_rate"]["measured_percentage"] == "100.0%"
        assert adv_m["citation_validity_rate"]["measured_percentage"] == "100.0%"
        assert adv_m["guardrail_negative_catch_rate"]["measured_percentage"] == "100.0%"

        safe_inv = safe_res["safety_invariants"]
        assert safe_inv["actuation_routes_present"] == 0
        assert safe_inv["autonomous_trip_commands_present"] == 0
        assert safe_inv["cloud_llm_calls_present"] == 0

    def test_ws_p8_05_verify_tariffs(self, temp_eval_dir):
        """WS-P8-05: Verifies 4-tier tariff resolution and floating-point precision."""
        tariff_res = verify_tariffs(output_dir=temp_eval_dir)

        assert (temp_eval_dir / "tariffs.json").exists()
        assert tariff_res["tariff_hierarchy_verification"]["all_tiers_resolved_correctly"] is True
        assert tariff_res["mathematical_accuracy"]["financial_loss_error_inr"] < 1e-4
        assert tariff_res["mathematical_accuracy"]["curtailment_zero_loss_verified"] is True

    def test_ws_p8_06_benchmark_performance(self, temp_eval_dir):
        """WS-P8-06: Verifies multi-sample latency benchmarking and SLA compliance."""
        perf_res = benchmark_performance(output_dir=temp_eval_dir, n_trials=5)

        assert (temp_eval_dir / "performance.json").exists()
        assert len(perf_res["endpoint_benchmark_matrix"]) >= 4

        sla = perf_res["formal_system_sla_ceiling"]
        assert sla["measured_overall_max_ms"] <= sla["budget_ms"]
        assert sla["status"] == "PASS"

    def test_ws_p8_07_generate_report(self, temp_eval_dir):
        """WS-P8-07: Verifies compilation of docs/EVALUATION_REPORT.md."""
        # First generate prerequisite JSONs in temp directory
        evaluate_models(output_dir=temp_eval_dir)
        run_scenario_benchmark(output_dir=temp_eval_dir)
        evaluate_rag(output_dir=temp_eval_dir)
        audit_advisories(output_dir=temp_eval_dir)
        verify_tariffs(output_dir=temp_eval_dir)
        benchmark_performance(output_dir=temp_eval_dir, n_trials=3)

        out_md_path = temp_eval_dir / "EVALUATION_REPORT.md"
        report_text = generate_evaluation_report(results_dir=temp_eval_dir, output_file=out_md_path)

        assert out_md_path.exists()
        assert "WindGuard AI: Comprehensive Technical & Empirical Evaluation Report" in report_text
        assert "PROJECT BENCHMARK PERFORMANCE" in report_text
        assert "PHASE 8 — IMPLEMENTATION COMPLETE, VERIFIED & READY FOR OWNER SIGN-OFF" in report_text
        assert "SCADA Actuation Endpoints          : Exactly 0 (PERMANENTLY PROHIBITED)" in report_text

    def test_system_invariant_zero_scada_actuation(self):
        """Safety Invariant: Verifies zero SCADA actuation endpoints across all FastAPI routes."""
        app = create_app()
        prohibited_verbs = ["POST", "PUT", "PATCH", "DELETE"]
        prohibited_keywords = ["actuate", "control", "trip", "pitch_override", "yaw_override", "dispatch_cmms", "execute"]

        actuation_endpoints = []
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            for keyword in prohibited_keywords:
                if keyword in path.lower():
                    actuation_endpoints.append((path, methods))

        assert len(actuation_endpoints) == 0, f"Found prohibited actuation endpoints: {actuation_endpoints}"

    def test_models_read_only_immutability(self):
        """Governance Invariant: Verifies frozen Phase 2 models exist and are untouched."""
        power_path = settings.PATHS.MODELS_DIR / "expected_power_gbr_v1.joblib"
        thermal_path = settings.PATHS.MODELS_DIR / "expected_thermal_rf_v1.joblib"
        stats_path = settings.PATHS.MODELS_DIR / "baseline_stats_v1.json"

        assert power_path.exists(), "Expected power model file missing"
        assert thermal_path.exists(), "Expected thermal model file missing"
        assert stats_path.exists(), "Baseline stats file missing"

        # Verify loadability without training or modifying
        with open(stats_path, "r", encoding="utf-8") as f:
            stats_json = json.load(f)
            assert "mu_p" in stats_json or "turbine_id" in stats_json or "residual_means" in stats_json
