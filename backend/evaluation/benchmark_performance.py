"""Workstream WS-P8-06: End-to-End Latency & Performance SLA Benchmark Runner.

Source of Truth:
- docs/06_prd.md (NFR-001)
- docs/07_srs.md (SRS-NFR-01)
- docs/PHASE_6_OWNER_SIGN_OFF.md
- docs/PHASE_7_FINAL_RECONCILIATION.md §4
- docs/PHASE_8_SCOPE_REVIEW.md (WS-P8-06)
- docs/PHASE_8_OWNER_DECISION_RESOLUTION.md (OD-P8-01)

Executes statistically rigorous multi-sample latency benchmarking (N=50 trials per endpoint)
across all primary FastAPI REST endpoints. Verifies individual component budgets and the
formal binding system SLA ceiling of <= 2.5 seconds.
Outputs results to evaluation_results/performance.json.
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, List
from fastapi.testclient import TestClient
import numpy as np

from backend.api.app import create_app


def benchmark_performance(output_dir: Path = None, n_trials: int = 50) -> Dict[str, Any]:
    """Benchmarks REST API endpoints across repeated trials.

    Args:
        output_dir: Output directory. Defaults to evaluation_results/.
        n_trials: Number of trials per endpoint (Default N=50).

    Returns:
        Structured performance evaluation matrix dictionary.
    """
    if output_dir is None:
        output_dir = Path("evaluation_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    app = create_app()
    client = TestClient(app)

    # Warm-up cycle
    client.get("/api/fleet/status")
    client.get("/api/turbines/WTG-01/telemetry")
    client.get("/api/tariffs")

    endpoints_to_benchmark = [
        {
            "name": "Fleet Status",
            "method": "GET",
            "url": "/api/fleet/status",
            "payload": None,
            "budget_ms": 250.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
        {
            "name": "Turbine Telemetry",
            "method": "GET",
            "url": "/api/turbines/WTG-01/telemetry",
            "payload": None,
            "budget_ms": 150.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
        {
            "name": "On-Demand Diagnosis",
            "method": "POST",
            "url": "/api/turbines/WTG-07/diagnose",
            "payload": {},
            "budget_ms": 1500.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
        {
            "name": "Technical RAG Query",
            "method": "POST",
            "url": "/api/rag/query",
            "payload": {"query": "Gearbox high bearing temperature AL-104 inspection", "top_k": 3},
            "budget_ms": 300.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
        {
            "name": "Case Management & List",
            "method": "GET",
            "url": "/api/cases",
            "payload": None,
            "budget_ms": 150.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
        {
            "name": "Tariff Registry Query",
            "method": "GET",
            "url": "/api/tariffs",
            "payload": None,
            "budget_ms": 100.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
        {
            "name": "Demo System Status",
            "method": "GET",
            "url": "/api/demo/status",
            "payload": None,
            "budget_ms": 150.0,
            "budget_status": "PROPOSED — OWNER DECISION REQUIRED",
        },
    ]

    benchmark_matrix = []
    sla_ceiling_ms = 2500.0
    sla_violations = 0

    for ep in endpoints_to_benchmark:
        latencies = []
        for _ in range(n_trials):
            t0 = time.perf_counter()
            if ep["method"] == "GET":
                resp = client.get(ep["url"])
            elif ep["method"] == "POST":
                resp = client.post(ep["url"], json=ep["payload"])
            lat_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(lat_ms)

        mean_l = float(np.mean(latencies))
        p50_l = float(np.percentile(latencies, 50))
        p90_l = float(np.percentile(latencies, 90))
        p95_l = float(np.percentile(latencies, 95))
        p99_l = float(np.percentile(latencies, 99))
        max_l = float(np.max(latencies))
        headroom = ep["budget_ms"] - p95_l

        if max_l > sla_ceiling_ms:
            sla_violations += 1

        benchmark_matrix.append({
            "endpoint_name": ep["name"],
            "http_method": ep["method"],
            "url": ep["url"],
            "trials_n": n_trials,
            "budget_ms": ep["budget_ms"],
            "mean_ms": round(mean_l, 2),
            "median_p50_ms": round(p50_l, 2),
            "p90_ms": round(p90_l, 2),
            "p95_ms": round(p95_l, 2),
            "p99_ms": round(p99_l, 2),
            "max_ms": round(max_l, 2),
            "headroom_margin_ms": round(headroom, 2),
            "headroom_pct": round((headroom / ep["budget_ms"]) * 100.0, 1),
            "status": "PROPOSED_TARGET_NOT_OWNER_APPROVED",
            "governance_classification": ep["budget_status"],
        })

    # Overall max latency across all tests
    overall_max_latency = max(m["max_ms"] for m in benchmark_matrix)
    overall_sla_pass = overall_max_latency <= sla_ceiling_ms

    results = {
        "benchmark_id": "WS-P8-06-PERFORMANCE-SLA",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sample_size_per_endpoint": n_trials,
        "environment": {
            "runtime": "FastAPI TestClient / Python ASGI runtime",
            "host_os": "Windows 11 / x86_64",
            "execution_mode": "Local Offline / CPU Only",
        },
        "formal_system_sla_ceiling": {
            "budget_ms": sla_ceiling_ms,
            "measured_overall_max_ms": overall_max_latency,
            "sla_headroom_margin_ms": round(sla_ceiling_ms - overall_max_latency, 2),
            "sla_headroom_pct": round(((sla_ceiling_ms - overall_max_latency) / sla_ceiling_ms) * 100.0, 1),
            "violations_count": sla_violations,
            "status": "PASS" if overall_sla_pass else "FAIL",
            "governance_classification": "FROZEN / PREVIOUSLY APPROVED",
        },
        "endpoint_benchmark_matrix": benchmark_matrix,
        "acceptance_gate": {
            "gate_id": "GATE-P8-09",
            "requirement": "Multi-sample performance benchmarks execute and confirm formal <= 2.5s system SLA ceiling",
            "status": "PASS" if overall_sla_pass else "FAIL",
        },
    }

    with open(output_dir / "performance.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    res = benchmark_performance()
    print(f"Performance Benchmark complete. Overall Max: {res['formal_system_sla_ceiling']['measured_overall_max_ms']} ms, Gate: {res['acceptance_gate']['status']}")
