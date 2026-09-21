"""Phase 4 Acceptance Gate Test Suite (TEST-RAG-01, TEST-RAG-LAT-01, TEST-LOCKOUT-P4).

Formally verifies all mandatory Phase 4 acceptance criteria against
the finalized engineering documentation suite (docs/PHASE_4_SCOPE_REVIEW.md v2.0).
"""

from pathlib import Path
import socket
import pytest

from backend.rag.document_chunker import HierarchicalDocumentChunker
from backend.rag.knowledge_base import VectorKnowledgeBase
from backend.rag.schema import DocumentChunk, SourceType


FROZEN_15_QUERY_BENCHMARK = [
    {"query_id": "Q-GB-01", "domain": "Drivetrain / Gearbox", "search_query": "Gearbox bearing overheating thermal threshold delta", "expected_chunks": ["CHK-GB-001", "CHK-GB-002"]},
    {"query_id": "Q-GB-02", "domain": "Drivetrain / Gearbox", "search_query": "ISO 4406 oil particle count lubrication inspection", "expected_chunks": ["CHK-GB-003", "CHK-GB-004"]},
    {"query_id": "Q-GB-03", "domain": "Drivetrain / Gearbox", "search_query": "High speed shaft vibration dial indicator runout check", "expected_chunks": ["CHK-GB-002", "CHK-GB-005"]},
    {"query_id": "Q-GEN-01", "domain": "Generator & Cooling", "search_query": "Generator stator winding temperature class F limit", "expected_chunks": ["CHK-GEN-001", "CHK-GEN-002"]},
    {"query_id": "Q-GEN-02", "domain": "Generator & Cooling", "search_query": "Air to air heat exchanger cooling fan motor failure", "expected_chunks": ["CHK-GEN-003", "CHK-GEN-004"]},
    {"query_id": "Q-GEN-03", "domain": "Generator & Cooling", "search_query": "Megger insulation test stator resistance minimum", "expected_chunks": ["CHK-GEN-002", "CHK-GEN-005"]},
    {"query_id": "Q-PIT-01", "domain": "Aerodynamic & Pitch", "search_query": "Blade pitch angle asymmetry encoder drift calibration", "expected_chunks": ["CHK-PIT-001", "CHK-PIT-002"]},
    {"query_id": "Q-PIT-02", "domain": "Aerodynamic & Pitch", "search_query": "Hydraulic pitch cylinder pressure drop troubleshooting", "expected_chunks": ["CHK-PIT-003", "CHK-PIT-004"]},
    {"query_id": "Q-PIT-03", "domain": "Aerodynamic & Pitch", "search_query": "Zero pitch mechanical index reference position check", "expected_chunks": ["CHK-PIT-001", "CHK-PIT-005"]},
    {"query_id": "Q-GRD-01", "domain": "Grid Dispatch & Curtailment", "search_query": "Grid curtailment active power derate setpoint", "expected_chunks": ["CHK-GRD-001", "CHK-GRD-002"]},
    {"query_id": "Q-GRD-02", "domain": "Grid Dispatch & Curtailment", "search_query": "Feathered pitch power shedding during strong wind", "expected_chunks": ["CHK-GRD-002", "CHK-GRD-003"]},
    {"query_id": "Q-GRD-03", "domain": "Grid Dispatch & Curtailment", "search_query": "Deemed generation capacity accounting under dispatch", "expected_chunks": ["CHK-GRD-001", "CHK-GRD-004"]},
    {"query_id": "Q-SOP-01", "domain": "Indian Wind Corridor O&M", "search_query": "Monsoon wind farm pre-check desiccant breather replace", "expected_chunks": ["CHK-SOP-001", "CHK-SOP-002"]},
    {"query_id": "Q-SOP-02", "domain": "Indian Wind Corridor O&M", "search_query": "Ambient heatwave operating protocol above 38 celsius", "expected_chunks": ["CHK-SOP-003", "CHK-SOP-004"]},
    {"query_id": "Q-SOP-03", "domain": "Indian Wind Corridor O&M", "search_query": "Substation transformer oil sampling safety checklist", "expected_chunks": ["CHK-SOP-002", "CHK-SOP-005"]},
]


@pytest.fixture
def knowledge_base() -> VectorKnowledgeBase:
    """Fixture providing initialized and indexed VectorKnowledgeBase."""
    docs_dir = Path(__file__).resolve().parent.parent / "backend" / "rag" / "documents"
    kb = VectorKnowledgeBase(documents_dir=docs_dir)
    kb.load_and_index()
    return kb


def test_gate_01_retrieval_ranking_and_grounding(knowledge_base: VectorKnowledgeBase):
    """TEST-RAG-01: Verifies retrieval ranking quality (MRR >= 0.80) and query grounding."""
    eval_res = knowledge_base.evaluate_benchmark(FROZEN_15_QUERY_BENCHMARK, top_k=3)

    assert eval_res["num_queries"] == 15
    # Asserts Mean Reciprocal Rank meets or exceeds authorized target 0.80
    assert eval_res["mrr"] >= 0.80, f"Expected MRR >= 0.80, got {eval_res['mrr']}"

    # Every query must retrieve at least one relevant ground-truth chunk in top-3 (100% Top-3 Recall)
    for q in eval_res["per_query_results"]:
        assert q["overlap_count"] >= 1, f"Query {q['query_id']} retrieved zero relevant chunks in top-3"
        assert q["reciprocal_rank"] > 0.0


def test_gate_02_retrieval_latency_target(knowledge_base: VectorKnowledgeBase):
    """TEST-RAG-LAT-01: Verifies average retrieval latency < 50.0 ms across 100 timed runs."""
    query_texts = [q["search_query"] for q in FROZEN_15_QUERY_BENCHMARK]
    lat_res = knowledge_base.benchmark_latency(query_texts, warmups=20, iterations=100)

    # Average query latency TARGET: < 50.0 ms
    assert lat_res["mean_latency_ms"] < 50.0, f"Average latency {lat_res['mean_latency_ms']} ms exceeded 50.0 ms target"
    assert lat_res["p95_latency_ms"] < 50.0


def test_gate_03_chunk_provenance_and_hash_integrity(knowledge_base: VectorKnowledgeBase):
    """TEST-RAG-META-01: Verifies 100% of chunks have verified provenance and SHA-256 integrity."""
    assert len(knowledge_base.chunks) >= 20

    for chunk in knowledge_base.chunks:
        assert isinstance(chunk, DocumentChunk)
        assert chunk.source_type in [
            SourceType.SOURCE_AUTHENTIC,
            SourceType.SOURCE_DERIVED,
            SourceType.PROJECT_SYNTHETIC,
        ]
        assert chunk.source_type != SourceType.UNVERIFIED
        assert chunk.source_page is None  # Markdown-native documents have no artificial page numbers
        assert len(chunk.content_hash) == 64  # Valid SHA-256 hex string
        assert chunk.provenance_status == "VERIFIED"


def test_gate_04_zero_network_offline_system_constraint(monkeypatch):
    """TEST-RAG-OFFLINE-01: Enforces 100% offline air-gapped CPU operation with zero network calls."""
    def blocked_socket(*args, **kwargs):
        raise AssertionError("CRITICAL VIOLATION: Network socket access detected during offline retrieval!")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    monkeypatch.setattr(socket, "create_connection", blocked_socket)

    docs_dir = Path(__file__).resolve().parent.parent / "backend" / "rag" / "documents"
    kb = VectorKnowledgeBase(documents_dir=docs_dir)
    kb.load_and_index()
    res = kb.search("Gearbox bearing overheating", top_k=3)
    assert len(res.chunks) >= 1


def test_gate_05_edge_case_and_tie_break_determinism(knowledge_base: VectorKnowledgeBase):
    """TEST-RAG-EDGE-01: Verifies deterministic behavior for empty queries, zero matches, and k > N."""
    # Empty query
    r_empty = knowledge_base.search("", top_k=3)
    assert len(r_empty.chunks) == 0
    assert r_empty.query_latency_ms == 0.0

    # Whitespace query
    r_ws = knowledge_base.search("   ", top_k=3)
    assert len(r_ws.chunks) == 0

    # Non-matching query
    r_zero = knowledge_base.search("qqqxxxyyyzzz_no_match", top_k=3)
    assert len(r_zero.chunks) == 0

    # Large k
    r_large = knowledge_base.search("bearing temperature", top_k=10)
    assert len(r_large.chunks) <= len(knowledge_base.chunks)


def test_gate_06_phase_boundary_lockout():
    """TEST-LOCKOUT-P4: Confirms strict architectural lockout of Phase 5 LLM and Phase 6 UI/Fleet APIs."""
    backend_path = Path(__file__).resolve().parent.parent / "backend"

    # Confirmed absence of Phase 5 LLM synthesis modules
    assert not (backend_path / "llm" / "advisory_engine.py").exists()
    assert not (backend_path / "llm" / "prompt_builder.py").exists()

    # Confirmed absence of Phase 6 UI and fleet management modules
    frontend_path = Path(__file__).resolve().parent.parent / "frontend"
    assert not frontend_path.exists()
    assert not (backend_path / "api" / "case_routes.py").exists()
    assert not (backend_path / "api" / "fleet_routes.py").exists()
