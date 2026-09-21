"""Pydantic Schemas for Layer 4: Technical Knowledge Base & RAG Subsystem.

Source of Truth:
- docs/06_prd.md §7 (FR-008, FR-010)
- docs/07_srs.md §3.6
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
- docs/10_data_architecture.md §4.4
- docs/PHASE_4_SCOPE_REVIEW.md §7
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    """Categorical source authenticity classification."""

    SOURCE_AUTHENTIC = "SOURCE_AUTHENTIC"  # Authentic OEM manual / standard legitimacy verified
    SOURCE_DERIVED = "SOURCE_DERIVED"  # Project summary derived from identified source
    PROJECT_SYNTHETIC = "PROJECT_SYNTHETIC"  # Deliberately authored synthetic demo/test scenario content
    UNVERIFIED = "UNVERIFIED"  # Unverified origin (STRICTLY PROHIBITED from authoritative corpus)


class ContentType(str, Enum):
    """Classification of document chunk content fidelity."""

    VERBATIM_SOURCE = "VERBATIM_SOURCE"  # Direct, unedited text from an authentic source document
    DERIVED_SUMMARY = "DERIVED_SUMMARY"  # Project-authored technical synthesis citing an identified source
    PROJECT_SYNTHETIC = "PROJECT_SYNTHETIC"  # Demonstration scenario text, synthetic alarm table, or test playbook


class RetrievalMode(str, Enum):
    """Controlled vocabulary for retrieval execution engine mode."""

    HYBRID_LOCAL = "HYBRID_LOCAL"  # Dense Vector Cosine + Lexical BM25 Hybrid
    BM25_LOCAL = "BM25_LOCAL"  # BM25 Lexical-only local search
    TFIDF_LOCAL = "TFIDF_LOCAL"  # TF-IDF emergency local fallback


class DocumentChunk(BaseModel):
    """Immutable Document Chunk Schema with complete provenance tracking."""

    chunk_id: str = Field(..., description="Unique deterministic chunk ID (e.g. CHK-GB-001)")
    document_title: str = Field(..., description="Canonical document title")
    document_filename: str = Field(..., description="Source filename relative to documents directory")
    source_id: str = Field(..., description="Unique source identifier (e.g. SRC-DERIVED-GB-01)")
    source_type: SourceType = Field(..., description="Authenticity classification of source")
    publisher: str = Field(..., description="Publisher or authoring organization")
    document_version: str = Field(default="1.0", description="Version string of document")
    publication_date: str = Field(..., description="Publication date (YYYY-MM-DD)")
    chapter: str = Field(..., description="Chapter or major heading")
    section: str = Field(..., description="Specific section heading")
    source_page: Optional[int] = Field(default=None, ge=1, description="Page number if paginated; None for markdown")
    source_locator: str = Field(..., description="Deterministic location anchor (e.g. 'Sec 4.2 Bearing Inspection')")
    content: str = Field(..., description="Verbatim text content of the document chunk")
    content_type: ContentType = Field(..., description="Content fidelity classification")
    tags: List[str] = Field(default_factory=list, description="Semantic indexing tags")
    token_count: int = Field(..., ge=1, description="Word/token count of chunk")
    content_hash: str = Field(..., description="SHA-256 hash of verbatim chunk content")
    provenance_status: str = Field(default="VERIFIED", description="Provenance verification status")

    model_config = ConfigDict(populate_by_name=True, frozen=True, extra="forbid")


class RetrievalResult(BaseModel):
    """Result of hybrid RAG query execution."""

    query: str = Field(..., description="Original input search query")
    top_k: int = Field(default=3, ge=1, le=10, description="Requested top-k chunk count")
    retrieval_mode: RetrievalMode = Field(..., description="Active retrieval engine mode")
    corpus_version: str = Field(default="1.0.0", description="Version hash/string of indexed corpus")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="Ranked retrieved document chunks")
    scores: List[float] = Field(default_factory=list, description="Fused hybrid relevance scores in [0.0, 1.0]")
    query_latency_ms: float = Field(..., ge=0.0, description="Measured query execution time in milliseconds")

    model_config = ConfigDict(populate_by_name=True, frozen=True, extra="forbid")
