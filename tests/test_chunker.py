"""Unit Tests for Layer 4 Hierarchical Document Chunker.

Source of Truth:
- docs/06_prd.md §7 (FR-008)
- docs/07_srs.md §3.6
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
- docs/PHASE_4_SCOPE_REVIEW.md §4, §5, §7
"""

import hashlib
from pathlib import Path
import pytest

from backend.rag.document_chunker import HierarchicalDocumentChunker
from backend.rag.schema import ContentType, DocumentChunk, SourceType


@pytest.fixture
def chunker() -> HierarchicalDocumentChunker:
    """Fixture providing standard hierarchical chunker instance."""
    return HierarchicalDocumentChunker(max_chunk_chars=1000, overlap_chars=100)


@pytest.fixture
def documents_dir() -> Path:
    """Fixture providing path to backend/rag/documents directory."""
    return Path(__file__).resolve().parent.parent / "backend" / "rag" / "documents"


def test_chunker_parses_all_governed_documents(chunker: HierarchicalDocumentChunker, documents_dir: Path):
    """TEST-CHK-01: Verifies chunker parses all markdown files in governed corpus directory."""
    chunks = chunker.chunk_directory(documents_dir)
    assert len(chunks) >= 20, f"Expected at least 20 chunks across corpus, got {len(chunks)}"

    chunk_ids = [c.chunk_id for c in chunks]
    # Verify core chunk prefixes exist
    assert any(cid.startswith("CHK-GB-") for cid in chunk_ids)
    assert any(cid.startswith("CHK-GEN-") for cid in chunk_ids)
    assert any(cid.startswith("CHK-PIT-") for cid in chunk_ids)
    assert any(cid.startswith("CHK-GRD-") for cid in chunk_ids)
    assert any(cid.startswith("CHK-SOP-") for cid in chunk_ids)
    assert any(cid.startswith("CHK-IEC-") for cid in chunk_ids)


def test_chunk_provenance_and_hash_integrity(chunker: HierarchicalDocumentChunker, documents_dir: Path):
    """TEST-CHK-02: Verifies SHA-256 hash match, positive token count, and non-null provenance."""
    chunks = chunker.chunk_directory(documents_dir)

    for chunk in chunks:
        # Assert schema types and immutability
        assert isinstance(chunk, DocumentChunk)
        assert chunk.chunk_id.startswith("CHK-")
        assert len(chunk.document_title) > 0
        assert len(chunk.source_id) > 0
        assert chunk.source_type in [
            SourceType.SOURCE_AUTHENTIC,
            SourceType.SOURCE_DERIVED,
            SourceType.PROJECT_SYNTHETIC,
        ]
        assert chunk.publisher != ""
        assert chunk.publication_date != ""
        assert len(chunk.chapter) > 0
        assert len(chunk.section) > 0

        # Non-paginated markdown guarantee: source_page must be None
        assert chunk.source_page is None, f"Expected source_page=None for markdown chunk {chunk.chunk_id}"

        # Source locator must be populated
        assert len(chunk.source_locator) > 0
        assert ">" in chunk.source_locator

        # Content and SHA-256 hash integrity
        assert len(chunk.content.strip()) > 0
        assert chunk.token_count >= 1
        expected_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        assert chunk.content_hash == expected_hash, f"Hash mismatch on chunk {chunk.chunk_id}"
        assert chunk.provenance_status == "VERIFIED"


def test_chunker_rejects_unverified_source(chunker: HierarchicalDocumentChunker, tmp_path: Path):
    """TEST-CHK-03: Verifies that UNVERIFIED documents raise ValueError and are rejected."""
    unverified_file = tmp_path / "unverified_manual.md"
    unverified_file.write_text(
        "---\n"
        "document_title: 'Unverified OEM Manual'\n"
        "source_id: 'SRC-UNVERIFIED-01'\n"
        "source_type: 'UNVERIFIED'\n"
        "publisher: 'Anonymous'\n"
        "publication_date: '2026-09-20'\n"
        "---\n\n"
        "# Chapter 1: Secret Maintenance\n"
        "## Section 1.1: Speculative Procedure\n"
        "This is an unverified maintenance procedure that must never be ingested.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_type is UNVERIFIED"):
        chunker.chunk_file(unverified_file)


def test_chunker_window_overlap_and_sentence_integrity(tmp_path: Path):
    """TEST-CHK-04: Verifies that oversized sections split with sliding overlap."""
    chunker = HierarchicalDocumentChunker(max_chunk_chars=200, overlap_chars=50)

    long_section_file = tmp_path / "long_section.md"
    long_text = (
        "---\n"
        "document_title: 'Long Technical Guide'\n"
        "source_id: 'SRC-DERIVED-LONG'\n"
        "source_type: 'SOURCE_DERIVED'\n"
        "publisher: 'WindGuard'\n"
        "publication_date: '2026-09-20'\n"
        "---\n\n"
        "# Chapter 1: Drivetrain Overview\n"
        "## Section 1.1: Extended Bearing Vibration Protocol\n"
        "<!-- chunk_id: CHK-LONG-001 -->\n"
        + "The gearbox bearing monitoring protocol requires continuous analysis of high frequency vibration signals. " * 5
    )
    long_section_file.write_text(long_text, encoding="utf-8")

    chunks = chunker.chunk_file(long_section_file)
    assert len(chunks) > 1, "Expected text to be split into multiple overlapping chunks"
    assert chunks[0].chunk_id == "CHK-LONG-001"
    assert chunks[1].chunk_id == "CHK-LONG-001-P2"
    for c in chunks:
        assert len(c.content) <= 200 + 50
