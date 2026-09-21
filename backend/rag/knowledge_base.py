"""Layer 4 Local Hybrid RAG Search Engine & Vector Knowledge Base.

Source of Truth:
- docs/06_prd.md §7 (FR-008, FR-010)
- docs/07_srs.md §3.6
- docs/08_system_architecture.md §3.5
- docs/09_technical_design.md §2.4
- docs/PHASE_4_SCOPE_REVIEW.md §6, §7, §8

Implements 100% offline, deterministic local hybrid retrieval combining Dense Vector Cosine
Similarity with Lexical Okapi BM25 Ranking and a 3-tier local fallback hierarchy.
Zero network socket calls, zero cloud APIs, zero runtime model downloads.
"""

from collections import Counter
import math
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from nltk.stem.porter import PorterStemmer
    _STEMMER: Optional[PorterStemmer] = PorterStemmer()
except Exception:
    _STEMMER = None

from backend.rag.document_chunker import HierarchicalDocumentChunker
from backend.rag.schema import (
    DocumentChunk,
    RetrievalMode,
    RetrievalResult,
)


class LocalBM25Retriever:
    """Canonical Okapi BM25 Lexical Retriever for technical corpora."""

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        s_bm25_ref: float = 10.0,
    ):
        """Initializes the Okapi BM25 retriever.

        Args:
            k1: Term frequency saturation parameter (Initial Design Parameter: 1.5).
            b: Document length normalization scaling parameter (Initial Design Parameter: 0.75).
            s_bm25_ref: Normalization saturation reference score (Initial Design Parameter: 10.0).
        """
        self.k1 = k1
        self.b = b
        self.s_bm25_ref = s_bm25_ref
        self.token_pattern = re.compile(r"\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b")
        self.chunks: List[DocumentChunk] = []
        self.doc_len: List[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_term_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.num_docs: int = 0

    def tokenize(self, text: str) -> List[str]:
        """Domain-aware regex tokenization with case folding and optional stemming."""
        tokens = self.token_pattern.findall(text.lower())
        if _STEMMER is not None:
            return [_STEMMER.stem(t) for t in tokens]
        return tokens

    def fit(self, chunks: List[DocumentChunk]) -> "LocalBM25Retriever":
        """Indexes document chunks for BM25 retrieval."""
        self.chunks = list(chunks)
        self.num_docs = len(self.chunks)
        self.doc_len = []
        self.doc_term_freqs = []
        df_counter: Dict[str, int] = Counter()

        for chunk in self.chunks:
            # Combine title, section, tags, and content for lexical matching
            combined_text = f"{chunk.document_title} {chunk.chapter} {chunk.section} {' '.join(chunk.tags)} {chunk.content}"
            tokens = self.tokenize(combined_text)
            self.doc_len.append(len(tokens))
            term_freq = Counter(tokens)
            self.doc_term_freqs.append(term_freq)
            for t in term_freq.keys():
                df_counter[t] += 1

        self.avg_doc_len = sum(self.doc_len) / self.num_docs if self.num_docs > 0 else 1.0

        # Calculate Robertson-Spärck Jones IDF
        self.idf = {}
        for term, df in df_counter.items():
            # IDF = ln((N - n + 0.5)/(n + 0.5) + 1.0)
            self.idf[term] = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1.0)

        return self

    def score(self, query: str) -> np.ndarray:
        """Calculates raw and normalized BM25 scores for all indexed documents."""
        if self.num_docs == 0:
            return np.zeros(0, dtype=np.float64)

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return np.zeros(self.num_docs, dtype=np.float64)

        scores = np.zeros(self.num_docs, dtype=np.float64)
        for i, term_freqs in enumerate(self.doc_term_freqs):
            d_len = self.doc_len[i]
            len_norm = 1.0 - self.b + self.b * (d_len / self.avg_doc_len)
            doc_score = 0.0
            for qt in query_tokens:
                if qt in term_freqs:
                    freq = term_freqs[qt]
                    term_idf = self.idf.get(qt, 0.0)
                    numerator = freq * (self.k1 + 1.0)
                    denominator = freq + self.k1 * len_norm
                    doc_score += term_idf * (numerator / denominator)
            scores[i] = max(0.0, doc_score)

        return scores

    def normalized_score(self, query: str) -> np.ndarray:
        """Calculates BM25 scores normalized into [0.0, 1.0) via S / (S + S_ref)."""
        raw_scores = self.score(query)
        if len(raw_scores) == 0:
            return np.zeros(0, dtype=np.float64)
        return raw_scores / (raw_scores + self.s_bm25_ref)


class LocalDenseRetriever:
    """Deterministic Local Word-Level N-Gram TF-IDF Dense Vector Retriever."""

    def __init__(
        self,
        max_features: int = 4096,
        ngram_range: Tuple[int, int] = (1, 2),
    ):
        """Initializes the local dense vectorizer.

        Args:
            max_features: Maximum vocabulary features (Initial Design Parameter: 4096).
            ngram_range: Word n-gram range (1, 2) capturing technical compounds.
        """
        self.vectorizer = TfidfVectorizer(
            token_pattern=r"(?u)\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b",
            ngram_range=ngram_range,
            norm="l2",
            max_features=max_features,
            min_df=1,
            sublinear_tf=True,
            dtype=np.float64,
        )
        self.chunks: List[DocumentChunk] = []
        self.doc_vectors: Optional[np.ndarray] = None

    def fit(self, chunks: List[DocumentChunk]) -> "LocalDenseRetriever":
        """Fits vocabulary and generates dense L2-normalized document vectors."""
        self.chunks = list(chunks)
        if not self.chunks:
            self.doc_vectors = np.zeros((0, 0), dtype=np.float64)
            return self

        corpus_texts = [
            f"{c.document_title} {c.chapter} {c.section} {' '.join(c.tags)} {c.content}"
            for c in self.chunks
        ]
        tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)
        self.doc_vectors = tfidf_matrix.toarray()
        return self

    def score(self, query: str) -> np.ndarray:
        """Computes cosine similarity between query vector and indexed document vectors in [0.0, 1.0]."""
        if self.doc_vectors is None or self.doc_vectors.shape[0] == 0:
            return np.zeros(0, dtype=np.float64)

        if not query or not query.strip():
            return np.zeros(len(self.chunks), dtype=np.float64)

        q_vec = self.vectorizer.transform([query]).toarray()[0]
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0.0:
            return np.zeros(len(self.chunks), dtype=np.float64)

        # Dot product with L2-normalized vectors yields exact cosine similarity
        sims = np.dot(self.doc_vectors, q_vec) / q_norm
        return np.maximum(0.0, sims)


class LocalHybridSearchEngine:
    """Deterministic 100% Offline Hybrid Search Engine with 3-tier local fallback."""

    def __init__(
        self,
        alpha: float = 0.60,
        min_relevance_threshold: float = 0.15,
        corpus_version: str = "1.0.0",
    ):
        """Initializes the hybrid search engine.

        Args:
            alpha: Hybrid weighting factor for dense similarity (Initial Design Parameter: 0.60).
            min_relevance_threshold: Relevance score cutoff (Initial Design Parameter: 0.15).
            corpus_version: Corpus tracking version string.
        """
        self.alpha = alpha
        self.min_relevance_threshold = min_relevance_threshold
        self.corpus_version = corpus_version
        self.chunks: List[DocumentChunk] = []
        self.dense_retriever = LocalDenseRetriever()
        self.bm25_retriever = LocalBM25Retriever()

    def index_chunks(self, chunks: List[DocumentChunk]) -> "LocalHybridSearchEngine":
        """Indexes chunks across dense and BM25 search engines."""
        self.chunks = list(chunks)
        self.dense_retriever.fit(self.chunks)
        self.bm25_retriever.fit(self.chunks)
        return self

    def search(
        self,
        query: str,
        top_k: int = 3,
        mode: RetrievalMode = RetrievalMode.HYBRID_LOCAL,
    ) -> RetrievalResult:
        """Executes search under the specified retrieval mode with deterministic fallback.

        Args:
            query: Input natural language or SCADA signature query.
            top_k: Number of ranked chunks to return (1 <= top_k <= 10).
            mode: Requested RetrievalMode.

        Returns:
            Immutable RetrievalResult object.
        """
        t0 = time.perf_counter()
        top_k_clamped = max(1, min(10, top_k))

        # Handle empty or whitespace-only query
        if not query or not query.strip():
            return RetrievalResult(
                query=query,
                top_k=top_k_clamped,
                retrieval_mode=mode,
                corpus_version=self.corpus_version,
                chunks=[],
                scores=[],
                query_latency_ms=0.0,
            )

        if not self.chunks:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return RetrievalResult(
                query=query,
                top_k=top_k_clamped,
                retrieval_mode=mode,
                corpus_version=self.corpus_version,
                chunks=[],
                scores=[],
                query_latency_ms=latency_ms,
            )

        active_mode = mode
        fused_scores = np.zeros(len(self.chunks), dtype=np.float64)

        # 3-Tier Local Fallback Execution
        if active_mode == RetrievalMode.HYBRID_LOCAL:
            try:
                dense_scores = self.dense_retriever.score(query)
                bm25_scores = self.bm25_retriever.normalized_score(query)
                fused_scores = self.alpha * dense_scores + (1.0 - self.alpha) * bm25_scores
            except Exception:
                # Fallback Tier 2: BM25_LOCAL
                active_mode = RetrievalMode.BM25_LOCAL
                fused_scores = self.bm25_retriever.normalized_score(query)

        if active_mode == RetrievalMode.BM25_LOCAL:
            try:
                fused_scores = self.bm25_retriever.normalized_score(query)
            except Exception:
                # Fallback Tier 3: TFIDF_LOCAL
                active_mode = RetrievalMode.TFIDF_LOCAL
                fused_scores = self.dense_retriever.score(query)

        if active_mode == RetrievalMode.TFIDF_LOCAL:
            fused_scores = self.dense_retriever.score(query)

        # Deterministic Ranking & Tie-Breaking: (-score, document_title, chunk_id)
        candidates = []
        for i, chunk in enumerate(self.chunks):
            score = float(fused_scores[i])
            if score >= self.min_relevance_threshold:
                candidates.append((score, chunk))

        # Sort: descending score, ascending document_title, ascending chunk_id
        candidates.sort(key=lambda item: (-item[0], item[1].document_title, item[1].chunk_id))

        selected = candidates[:top_k_clamped]
        ranked_chunks = [item[1] for item in selected]
        ranked_scores = [round(float(item[0]), 6) for item in selected]

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return RetrievalResult(
            query=query,
            top_k=top_k_clamped,
            retrieval_mode=active_mode,
            corpus_version=self.corpus_version,
            chunks=ranked_chunks,
            scores=ranked_scores,
            query_latency_ms=latency_ms,
        )


class VectorKnowledgeBase:
    """Top-Level Knowledge Base Manager for Layer 4 RAG Subsystem."""

    def __init__(
        self,
        documents_dir: Optional[Path] = None,
        alpha: float = 0.60,
        min_relevance_threshold: float = 0.15,
        corpus_version: str = "1.0.0",
    ):
        """Initializes the Vector Knowledge Base.

        Args:
            documents_dir: Path to backend/rag/documents directory.
            alpha: Hybrid weighting factor for dense similarity.
            min_relevance_threshold: Relevance score cutoff.
            corpus_version: Corpus tracking version.
        """
        self.documents_dir = Path(documents_dir).resolve() if documents_dir else Path(__file__).resolve().parent / "documents"
        self.chunker = HierarchicalDocumentChunker(max_chunk_chars=1000, overlap_chars=100)
        self.search_engine = LocalHybridSearchEngine(
            alpha=alpha,
            min_relevance_threshold=min_relevance_threshold,
            corpus_version=corpus_version,
        )
        self.chunks: List[DocumentChunk] = []

    def load_and_index(self) -> int:
        """Loads and indexes all governed documents from the documents directory.

        Returns:
            Number of indexed chunks.
        """
        if not self.documents_dir.exists():
            raise FileNotFoundError(f"Documents directory not found: {self.documents_dir}")

        self.chunks = self.chunker.chunk_directory(self.documents_dir)
        self.search_engine.index_chunks(self.chunks)
        return len(self.chunks)

    def search(
        self,
        query: str,
        top_k: int = 3,
        mode: RetrievalMode = RetrievalMode.HYBRID_LOCAL,
    ) -> RetrievalResult:
        """Executes retrieval query against the indexed knowledge base."""
        return self.search_engine.search(query=query, top_k=top_k, mode=mode)

    def evaluate_benchmark(self, benchmark_set: List[Dict[str, Any]], top_k: int = 3) -> Dict[str, Any]:
        """Evaluates the knowledge base against a standardized ground-truth query set.

        Args:
            benchmark_set: List of dicts with query_id, query_text, expected_chunks.
            top_k: Top-k ranking window (default 3).

        Returns:
            Dict with precision_at_k, mrr, per_query_results.
        """
        p_at_k_sum = 0.0
        rr_sum = 0.0
        query_results = []

        for item in benchmark_set:
            qid = item["query_id"]
            qtext = item["search_query"]
            expected = set(item["expected_chunks"])

            res = self.search(qtext, top_k=top_k)
            retrieved_ids = [c.chunk_id for c in res.chunks]

            # Precision at k: |Retrieved ∩ Expected| / k
            overlap = len(set(retrieved_ids).intersection(expected))
            p_k = (overlap / top_k) * 100.0
            p_at_k_sum += p_k

            # Reciprocal Rank: 1 / rank of first relevant chunk
            rr = 0.0
            for rank, cid in enumerate(retrieved_ids, start=1):
                if cid in expected:
                    rr = 1.0 / rank
                    break
            rr_sum += rr

            query_results.append({
                "query_id": qid,
                "query_text": qtext,
                "expected": list(expected),
                "retrieved": retrieved_ids,
                "overlap_count": overlap,
                "p_at_k": p_k,
                "reciprocal_rank": rr,
                "scores": res.scores,
                "latency_ms": res.query_latency_ms,
            })

        num_q = len(benchmark_set) if benchmark_set else 1
        mean_p_at_k = p_at_k_sum / num_q
        mean_mrr = rr_sum / num_q

        return {
            "num_queries": len(benchmark_set),
            "precision_at_3": round(mean_p_at_k, 2),
            "mrr": round(mean_mrr, 4),
            "per_query_results": query_results,
        }

    def benchmark_latency(
        self,
        queries: List[str],
        warmups: int = 20,
        iterations: int = 100,
    ) -> Dict[str, float]:
        """Measures CPU query latency across warm-up and timed iterations."""
        if not queries:
            return {"mean_latency_ms": 0.0, "p95_latency_ms": 0.0, "min_latency_ms": 0.0, "max_latency_ms": 0.0}

        # Warm-up runs (not timed for measurement)
        for i in range(warmups):
            q = queries[i % len(queries)]
            _ = self.search(q, top_k=3)

        # Timed measurement runs
        durations_ms: List[float] = []
        for i in range(iterations):
            q = queries[i % len(queries)]
            t0 = time.perf_counter()
            _ = self.search(q, top_k=3)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            durations_ms.append(dt_ms)

        durations_arr = np.array(durations_ms)
        return {
            "mean_latency_ms": round(float(np.mean(durations_arr)), 4),
            "p95_latency_ms": round(float(np.percentile(durations_arr, 95)), 4),
            "p99_latency_ms": round(float(np.percentile(durations_arr, 99)), 4),
            "min_latency_ms": round(float(np.min(durations_arr)), 4),
            "max_latency_ms": round(float(np.max(durations_arr)), 4),
        }
