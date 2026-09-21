"""Acceptance and Unit Tests for Layer 4 Technical Knowledge (RAG) API Routes (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_rag_query_gearbox_bearing(client: TestClient):
    """Verifies that POST /api/rag/query retrieves relevant chunks and valid citation metadata."""
    payload = {
        "query": "gearbox high speed shaft bearing overheating lubrication",
        "top_k": 3,
        "mode": "HYBRID_LOCAL",
    }
    response = client.post("/api/rag/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert data["top_k"] == 3
    assert len(data["chunks"]) > 0
    assert len(data["scores"]) == len(data["chunks"])
    assert data["query_latency_ms"] >= 0.0

    # Verify first chunk metadata
    first_chunk = data["chunks"][0]
    assert "chunk_id" in first_chunk
    assert "document_title" in first_chunk
    assert "content" in first_chunk
    assert "content_hash" in first_chunk
    assert len(first_chunk["content_hash"]) == 64  # Valid SHA-256


def test_rag_query_empty_string_rejected(client: TestClient):
    """Verifies that empty RAG queries are rejected with 400 or 422."""
    response = client.post("/api/rag/query", json={"query": "   ", "top_k": 3})
    assert response.status_code in (400, 422)


def test_rag_query_top_k_bounds(client: TestClient):
    """Verifies that top_k > 10 is rejected by schema validator."""
    response = client.post("/api/rag/query", json={"query": "bearing", "top_k": 50})
    assert response.status_code == 422
