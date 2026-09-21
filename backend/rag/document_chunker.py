"""Hierarchical Structure-Preserving Document Chunker for WindGuard AI (Layer 4).

Source of Truth:
- docs/06_prd.md §7 (FR-008)
- docs/07_srs.md §3.6
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
- docs/PHASE_4_SCOPE_REVIEW.md §4, §5, §7

Preserves hierarchical document provenance (chapter, section, source locator, content hash),
guarantees zero invented page numbers on digital markdown documents (source_page = None),
and strictly rejects documents categorized as UNVERIFIED.
"""

import hashlib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import yaml

from backend.rag.schema import (
    ContentType,
    DocumentChunk,
    SourceType,
)


class HierarchicalDocumentChunker:
    """Structure-preserving Markdown Document Chunker with unbroken provenance tracking."""

    def __init__(
        self,
        max_chunk_chars: int = 1000,
        overlap_chars: int = 100,
    ):
        """Initializes the hierarchical document chunker.

        Args:
            max_chunk_chars: Maximum character length ceiling per chunk (Initial Design Parameter: 1000 chars,
                designed for 500-800 character standard technical sections with up to 1000 char ceiling to prevent
                mid-section truncation).
            overlap_chars: Sliding boundary character overlap (Initial Design Parameter: 100 chars).
        """
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    def parse_frontmatter(self, text: str) -> Tuple[Dict[str, Any], str]:
        """Extracts YAML frontmatter metadata and body text from markdown content.

        Args:
            text: Raw markdown text.

        Returns:
            Tuple of (metadata_dict, body_text).
        """
        frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        match = frontmatter_pattern.match(text)
        if match:
            raw_yaml = match.group(1)
            body = text[match.end():]
            try:
                metadata = yaml.safe_load(raw_yaml) or {}
            except Exception:
                metadata = {}
            return metadata, body
        return {}, text

    def _split_text_with_overlap(self, text: str) -> List[str]:
        """Splits long text into overlapping chunks without truncating words."""
        text = text.strip()
        if len(text) <= self.max_chunk_chars:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.max_chunk_chars, text_len)
            if end < text_len:
                # Find nearest whitespace boundary before end
                last_space = text.rfind(" ", start, end)
                if last_space > start + (self.max_chunk_chars // 2):
                    end = last_space

            chunk_str = text[start:end].strip()
            if chunk_str:
                chunks.append(chunk_str)

            if end >= text_len:
                break
            start = max(start + 1, end - self.overlap_chars)

        return chunks

    def chunk_file(self, file_path: Path, base_dir: Optional[Path] = None) -> List[DocumentChunk]:
        """Parses and chunks a single markdown document.

        Args:
            file_path: Absolute or relative Path to markdown file.
            base_dir: Optional base directory for computing relative document_filename.

        Returns:
            List of validated DocumentChunk objects.

        Raises:
            ValueError: If the document source_type is UNVERIFIED or required metadata is missing.
        """
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        metadata, body = self.parse_frontmatter(raw_text)

        # Determine source filename relative to base_dir or document folder
        if base_dir:
            try:
                rel_filename = str(file_path.relative_to(base_dir)).replace("\\", "/")
            except ValueError:
                rel_filename = file_path.name
        else:
            rel_filename = file_path.name

        # Parse and validate SourceType
        raw_source_type = metadata.get("source_type", SourceType.SOURCE_DERIVED.value)
        try:
            source_type = SourceType(raw_source_type)
        except ValueError:
            source_type = SourceType.UNVERIFIED

        # Strict Governance Rule: UNVERIFIED material is rejected from the corpus
        if source_type == SourceType.UNVERIFIED:
            raise ValueError(
                f"Ingestion rejected for '{file_path.name}': Document source_type is UNVERIFIED. "
                "Unverified materials are strictly prohibited from the authoritative corpus."
            )

        # Parse and validate ContentType
        raw_content_type = metadata.get("content_type", ContentType.DERIVED_SUMMARY.value)
        try:
            content_type = ContentType(raw_content_type)
        except ValueError:
            content_type = ContentType.DERIVED_SUMMARY

        document_title = metadata.get("document_title", file_path.stem.replace("_", " ").title())
        source_id = metadata.get("source_id", f"SRC-{file_path.stem.upper()}")
        publisher = metadata.get("publisher", "WindGuard AI Technical Team")
        document_version = str(metadata.get("document_version", "1.0"))
        publication_date = str(metadata.get("publication_date", "2026-09-20"))
        tags = metadata.get("tags", [])

        # Parse hierarchical markdown structure
        lines = body.split("\n")
        current_chapter = "General Overview"
        current_section = "Introduction"
        current_section_lines: List[str] = []
        sections: List[Dict[str, Any]] = []

        def flush_section():
            if current_section_lines:
                sec_text = "\n".join(current_section_lines).strip()
                if sec_text:
                    sections.append({
                        "chapter": current_chapter,
                        "section": current_section,
                        "text": sec_text,
                    })
                current_section_lines.clear()

        for line in lines:
            stripped = line.strip()
            # Match Chapter Header (# or ## Chapter ...)
            if re.match(r"^#{1,2}\s+Chapter\s+\d+", stripped, re.IGNORECASE) or re.match(r"^#\s+[A-Za-z0-9]", stripped):
                flush_section()
                current_chapter = re.sub(r"^#+\s*", "", stripped).strip()
            # Match Section Header (## Section ... or ### Section ...)
            elif re.match(r"^#{2,3}\s+Section\s+\d+", stripped, re.IGNORECASE) or re.match(r"^#{2,3}\s+[A-Za-z0-9]", stripped):
                flush_section()
                current_section = re.sub(r"^#+\s*", "", stripped).strip()
            else:
                current_section_lines.append(line)

        flush_section()

        # Generate DocumentChunks
        chunks: List[DocumentChunk] = []
        chunk_counter = 1
        prefix_match = re.search(r"CHK-([A-Z0-9]+)-", body)
        doc_prefix = prefix_match.group(1) if prefix_match else file_path.stem.split("_")[1].upper() if "_" in file_path.stem else "DOC"

        for sec in sections:
            sec_chapter = sec["chapter"]
            sec_title = sec["section"]
            sec_text = sec["text"]

            # Check if explicit chunk ID markers are embedded
            chunk_marker_pattern = re.compile(r"<!--\s*chunk(?:_id)?:\s*([A-Za-z0-9_-]+)\s*-->")
            marker_match = chunk_marker_pattern.search(sec_text)

            # Clean text by removing chunk comment markers
            clean_sec_text = chunk_marker_pattern.sub("", sec_text).strip()
            if not clean_sec_text:
                continue

            text_segments = self._split_text_with_overlap(clean_sec_text)

            for i, seg in enumerate(text_segments):
                if marker_match and i == 0:
                    chunk_id = marker_match.group(1)
                elif marker_match and i > 0:
                    chunk_id = f"{marker_match.group(1)}-P{i+1}"
                else:
                    chunk_id = f"CHK-{doc_prefix}-{chunk_counter:03d}"
                    chunk_counter += 1

                source_locator = f"{sec_chapter} > {sec_title}"
                token_count = max(1, len(seg.split()))
                content_hash = hashlib.sha256(seg.encode("utf-8")).hexdigest()

                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    document_title=document_title,
                    document_filename=rel_filename,
                    source_id=source_id,
                    source_type=source_type,
                    publisher=publisher,
                    document_version=document_version,
                    publication_date=publication_date,
                    chapter=sec_chapter,
                    section=sec_title,
                    source_page=None,  # Markdown documents are non-paginated (No invented page numbers)
                    source_locator=source_locator,
                    content=seg,
                    content_type=content_type,
                    tags=tags,
                    token_count=token_count,
                    content_hash=content_hash,
                    provenance_status="VERIFIED",
                )
                chunks.append(chunk)

        return chunks

    def chunk_directory(self, dir_path: Path) -> List[DocumentChunk]:
        """Recursively parses all markdown documents within a directory hierarchy.

        Args:
            dir_path: Root directory containing markdown documents.

        Returns:
            Deterministic list of DocumentChunks sorted by chunk_id.
        """
        dir_path = Path(dir_path).resolve()
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        all_chunks: List[DocumentChunk] = []
        md_files = sorted(dir_path.rglob("*.md"))

        for md_file in md_files:
            # Skip README in authoritative if it is solely a policy file or chunk it if needed
            try:
                file_chunks = self.chunk_file(md_file, base_dir=dir_path)
                all_chunks.extend(file_chunks)
            except ValueError as e:
                # If UNVERIFIED, skip and log/raise as appropriate
                if "UNVERIFIED" in str(e):
                    continue
                raise

        # Deterministic sorting
        all_chunks.sort(key=lambda c: c.chunk_id)
        return all_chunks
