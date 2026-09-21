"""Technical Knowledge Base (RAG) Query REST API Routes for WindGuard AI (Layer 6).

Source:
- docs/07_srs.md §4.1
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_knowledge_base
from backend.api.schemas import RAGQueryRequest, RAGQueryResponse
from backend.rag.knowledge_base import VectorKnowledgeBase

router = APIRouter(prefix="/rag", tags=["Technical Knowledge Base (RAG)"])


@router.post("/query", response_model=RAGQueryResponse, status_code=status.HTTP_200_OK)
def query_knowledge_base(
    payload: RAGQueryRequest,
    kb: VectorKnowledgeBase = Depends(get_knowledge_base),
) -> RAGQueryResponse:
    """Performs hybrid dense vector and lexical BM25 search over OEM manuals and SOPs."""
    if not payload.query or not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    result = kb.search(
        query=payload.query,
        top_k=payload.top_k,
        mode=payload.mode,
    )

    return RAGQueryResponse(
        query=result.query,
        top_k=result.top_k,
        retrieval_mode=result.retrieval_mode,
        corpus_version=result.corpus_version,
        chunks=result.chunks,
        scores=result.scores,
        query_latency_ms=result.query_latency_ms,
    )
