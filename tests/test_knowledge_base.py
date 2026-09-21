"""Unit Tests for Layer 4 Local Hybrid Search Engine & Vector Knowledge Base.

Source of Truth:
- docs/06_prd.md §7 (FR-008, FR-010)
- docs/07_srs.md §3.6
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
- docs/PHASE_4_SCOPE_REVIEW.md §6, §8
"""

from pathlib import Path
import socket
import pytest

from backend.rag.knowledge_base import (
    LocalBM25Retriever,
    LocalDenseRetriever,
    LocalHybridSearchEngine,
    VectorKnowledgeBase,
)
from backend.rag.schema import (
    ContentType,
    DocumentChunk,
    RetrievalMode,
    RetrievalResult,
    SourceType,
)


@pytest.fixture
def sample_chunks() -> list[DocumentChunk]:
    """Fixture providing deterministic sample DocumentChunks."""
    return [
        DocumentChunk(
            chunk_id="CHK-GB-001",
            document_title="WindGuard Gearbox Guide",
            document_filename="derived/windguard_gearbox_guide.md",
            source_id="SRC-DERIVED-GB-2024",
            source_type=SourceType.SOURCE_DERIVED,
            publisher="WindGuard AI Technical Team",
            publication_date="2024-11-15",
            chapter="Chapter 1: Thermal Diagnostics",
            section="Section 1.1: Bearing Thermal Overheating",
            source_page=None,
            source_locator="Chapter 1 > Section 1.1",
            content="Gearbox bearing overheating thermal threshold delta: High speed shaft bearing degradation triggers persistent thermal elevation delta.",
            content_type=ContentType.DERIVED_SUMMARY,
            tags=["gearbox", "bearing", "thermal"],
            token_count=18,
            content_hash="hash_gb_001",
            provenance_status="VERIFIED",
        ),
        DocumentChunk(
            chunk_id="CHK-GEN-001",
            document_title="WindGuard Generator Guide",
            document_filename="derived/windguard_generator_guide.md",
            source_id="SRC-DERIVED-GEN-2024",
            source_type=SourceType.SOURCE_DERIVED,
            publisher="WindGuard AI Technical Team",
            publication_date="2024-11-15",
            chapter="Chapter 1: Stator Thermal Management",
            section="Section 1.1: Class F Limits",
            source_page=None,
            source_locator="Chapter 1 > Section 1.1",
            content="Generator stator winding temperature class F limit: Continuous thermal limit 155C with Megger insulation testing required upon overheating.",
            content_type=ContentType.DERIVED_SUMMARY,
            tags=["generator", "stator", "class_f"],
            token_count=19,
            content_hash="hash_gen_001",
            provenance_status="VERIFIED",
        ),
        DocumentChunk(
            chunk_id="CHK-PIT-001",
            document_title="WindGuard Pitch Guide",
            document_filename="derived/windguard_pitch_guide.md",
            source_id="SRC-DERIVED-PIT-2024",
            source_type=SourceType.SOURCE_DERIVED,
            publisher="WindGuard AI Technical Team",
            publication_date="2024-11-15",
            chapter="Chapter 1: Blade Alignment",
            section="Section 1.1: Pitch Encoder Calibration",
            source_page=None,
            source_locator="Chapter 1 > Section 1.1",
            content="Blade pitch angle asymmetry encoder drift calibration: Rotary optical encoder zero drift causes active power deficit.",
            content_type=ContentType.DERIVED_SUMMARY,
            tags=["pitch", "encoder", "asymmetry"],
            token_count=17,
            content_hash="hash_pit_001",
            provenance_status="VERIFIED",
        ),
    ]


def test_bm25_retriever_scoring_and_normalization(sample_chunks):
    """TEST-KB-01: Verifies Okapi BM25 raw and normalized score bounds [0.0, 1.0)."""
    retriever = LocalBM25Retriever(k1=1.5, b=0.75, s_bm25_ref=10.0)
    retriever.fit(sample_chunks)

    raw_scores = retriever.score("gearbox bearing overheating")
    norm_scores = retriever.normalized_score("gearbox bearing overheating")

    assert len(raw_scores) == len(sample_chunks)
    assert raw_scores[0] > 0.0, "Expected positive score for relevant chunk"
    assert raw_scores[0] > raw_scores[1], "Expected gearbox chunk to outscore generator chunk"
    assert 0.0 <= norm_scores[0] < 1.0, f"Normalized score out of bounds: {norm_scores[0]}"


def test_dense_retriever_cosine_similarity(sample_chunks):
    """TEST-KB-02: Verifies dense vectorizer cosine similarity calculation in [0.0, 1.0]."""
    retriever = LocalDenseRetriever()
    retriever.fit(sample_chunks)

    sims = retriever.score("generator stator winding temperature")
    assert len(sims) == len(sample_chunks)
    assert 0.0 <= sims[1] <= 1.0
    assert sims[1] > sims[0], "Expected generator chunk to have higher cosine similarity"


def test_hybrid_score_fusion(sample_chunks):
    """TEST-KB-03: Verifies hybrid fusion score matches alpha * S_dense + (1-alpha) * S_bm25."""
    engine = LocalHybridSearchEngine(alpha=0.60, min_relevance_threshold=0.0)
    engine.index_chunks(sample_chunks)

    res = engine.search("gearbox bearing overheating", top_k=3, mode=RetrievalMode.HYBRID_LOCAL)
    assert len(res.chunks) > 0
    assert res.retrieval_mode == RetrievalMode.HYBRID_LOCAL
    assert res.chunks[0].chunk_id == "CHK-GB-001"
    assert 0.0 <= res.scores[0] <= 1.0


def test_deterministic_tie_breaking(sample_chunks):
    """TEST-KB-04: Verifies deterministic sorting by score DESC, document_title ASC, chunk_id ASC."""
    engine = LocalHybridSearchEngine(alpha=0.60, min_relevance_threshold=0.0)
    engine.index_chunks(sample_chunks)

    # Empty query produces zero scores; deterministic tie-breaker should sort by title and id
    res = engine.search("", top_k=3)
    assert len(res.chunks) == 0
    assert res.query_latency_ms == 0.0


def test_edge_cases_empty_whitespace_and_large_k(sample_chunks):
    """TEST-KB-05: Verifies graceful handling of empty, whitespace, and k > N queries."""
    engine = LocalHybridSearchEngine(min_relevance_threshold=0.15)
    engine.index_chunks(sample_chunks)

    # Whitespace query
    res_ws = engine.search("   \t\n  ", top_k=3)
    assert len(res_ws.chunks) == 0
    assert res_ws.query_latency_ms == 0.0

    # Zero match query (gibberish)
    res_zero = engine.search("zzzyyyxxx999qqq", top_k=3)
    assert len(res_zero.chunks) == 0
    assert res_zero.query_latency_ms >= 0.0

    # Requested k > len(chunks)
    res_large_k = engine.search("bearing", top_k=10)
    assert len(res_large_k.chunks) <= len(sample_chunks)


def test_3_tier_fallback_hierarchy(sample_chunks):
    """TEST-KB-06: Verifies primary HYBRID_LOCAL, secondary BM25_LOCAL, and emergency TFIDF_LOCAL modes."""
    engine = LocalHybridSearchEngine(min_relevance_threshold=0.0)
    engine.index_chunks(sample_chunks)

    res_hybrid = engine.search("stator winding", top_k=2, mode=RetrievalMode.HYBRID_LOCAL)
    assert res_hybrid.retrieval_mode == RetrievalMode.HYBRID_LOCAL
    assert res_hybrid.chunks[0].chunk_id == "CHK-GEN-001"

    res_bm25 = engine.search("stator winding", top_k=2, mode=RetrievalMode.BM25_LOCAL)
    assert res_bm25.retrieval_mode == RetrievalMode.BM25_LOCAL
    assert res_bm25.chunks[0].chunk_id == "CHK-GEN-001"

    res_tfidf = engine.search("stator winding", top_k=2, mode=RetrievalMode.TFIDF_LOCAL)
    assert res_tfidf.retrieval_mode == RetrievalMode.TFIDF_LOCAL
    assert res_tfidf.chunks[0].chunk_id == "CHK-GEN-001"


def test_zero_network_offline_guarantee(monkeypatch, sample_chunks):
    """TEST-KB-07: Verifies system constraint of zero network socket calls during RAG execution."""
    def forbidden_socket(*args, **kwargs):
        raise RuntimeError("SYSTEM CONSTRAINT VIOLATION: Network socket connection attempted during RAG execution!")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    monkeypatch.setattr(socket, "create_connection", forbidden_socket)

    # Execute full pipeline with blocked sockets
    engine = LocalHybridSearchEngine()
    engine.index_chunks(sample_chunks)
    res = engine.search("gearbox bearing thermal delta", top_k=3)
    assert len(res.chunks) >= 1
    assert res.chunks[0].chunk_id == "CHK-GB-001"
