---
document: PHASE_4_SCOPE_REVIEW
version: 2.0
status: PROPOSED SCOPE REVIEW — NOT YET AUTHORIZED
date: 2026-09-20
author: Lead System Architect & Engineering Auditor
governance: Phase 4 Pre-Implementation Scope & Traceability Gate
depends_on:
  - docs/00_documentation_index.md
  - docs/06_prd.md
  - docs/07_srs.md
  - docs/08_system_architecture.md
  - docs/09_technical_design.md
  - docs/10_data_architecture.md
  - docs/11_ai_ml_design.md
  - docs/14_implementation_plan.md
  - docs/PHASE_1_VERIFICATION.md
  - docs/PHASE_2_FINAL_SIGNOFF_REVIEW.md
  - docs/PHASE_3_VERIFICATION.md
---

# Phase 4 Scope & Traceability Review (Hardened)
## Layer 4: Technical Knowledge Base & Local Hybrid RAG Retrieval Subsystem

---

## 1. Executive Summary & Phase Objectives

**Document Status**: **`PROPOSED SCOPE REVIEW — NOT YET AUTHORIZED`**  
**Precondition Status**: **`PHASE 3 — OWNER SIGNED OFF & FROZEN (44/44 TESTS PASSED)`**

This document establishes the hardened pre-implementation specification, mathematical formulations, corpus provenance governance, retrieval ranking algorithms, data schemas, parameter classification taxonomies, evaluation protocols, and traceability requirements for **Phase 4 (Layer 4 Technical Knowledge Base & Local Hybrid RAG Retrieval)** of **WindGuard AI**.

> [!IMPORTANT]
> **GOVERNANCE DIRECTIVE — IMPLEMENTATION LOCK**:
> Phase 4 is **NOT YET AUTHORIZED FOR IMPLEMENTATION**. This document serves exclusively as an architectural and scope review for Project Owner evaluation. Zero production code, test code, vector indexes, document corpora, or embeddings shall be created until explicit written authorization is granted.

### Core Objectives of Phase 4:
1. **Governed Technical Knowledge Corpus (FR-008)**: Establish a structured, multi-tier technical document corpus partitioned strictly by source provenance (`authoritative/`, `derived/`, `synthetic/`), completely eliminating unverified claims of OEM or IEC authorship.
2. **Deterministic Hierarchical Chunking & Provenance Tracking (FR-008)**: Implement a structure-preserving document chunker that maintains unbroken provenance (`source_id`, `source_type`, `publisher`, `document_version`, `chapter`, `section`, `source_locator`, `content_type`, `content_hash`) without inventing artificial page numbers for digital markdown documents.
3. **100% Offline Local Hybrid Retrieval Engine (FR-008, FR-010)**: Build a fully local, deterministic hybrid search engine combining dense semantic vector retrieval (local pre-packaged embedding weights / deterministic vectorizer) and lexical BM25 keyword matching with local TF-IDF emergency fallback, operating with **zero network, DNS, or cloud API calls**.
4. **Deterministic Citation & Grounding Traceability (FR-008, FR-009)**: Provide structured, immutable `DocumentChunk` and `RetrievalResult` objects enabling downstream Layer 5 LLM advisory synthesis to cite authentic document sections without hallucinating external manuals or unverified citations.
5. **Rigorous Retrieval Benchmarking (NFR-001, FR-008)**: Benchmark retrieval performance against a deterministic 15-query domain evaluation dataset targeting Precision ($P@3 \ge 85.0\%$), Mean Reciprocal Rank ($\text{MRR} \ge 0.80$), and single-query latency ($t_{\text{query}} < 50.0\,\text{ms}$).

---

## 2. Document Governance & Traceability Matrix

Every Phase 4 component traces directly to authoritative system specifications across the documentation suite:

| Component / Subsystem | Target Module Path | Authoritative Requirement ID | PRD Reference | SRS Reference | Architecture Reference | Technical Design Reference |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| **Technical Corpus Governance** | `backend/rag/documents/*` | **FR-008** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.6 | `docs/08` §3.5 | `docs/09_technical_design.md` §2.4 |
| **Document Chunking & Provenance** | `backend/rag/document_chunker.py` | **FR-008** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.6 | `docs/08` §3.5 | `docs/09_technical_design.md` §2.4 |
| **Local Hybrid Knowledge Base** | `backend/rag/knowledge_base.py` | **FR-008, FR-010** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.6 | `docs/08` §3.5 | `docs/09_technical_design.md` §2.4 |
| **RAG Schemas & Types** | `backend/rag/schema.py` | **FR-008** | `docs/06_prd.md` §7 | `docs/07_srs.md` §3.6 | `docs/08` §3.5 | `docs/10_data_architecture.md` §4.4 |

---

## 3. Systematic Parameter Classification & Traceability

To preserve scientific precision, every numeric parameter, threshold, constant, and formula weight in Phase 4 is explicitly classified according to the 6 authoritative governance categories:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             PARAMETER CLASSIFICATION TAXONOMY                                    │
├──────────────────────────────┬───────────────────────────────────────────────────────────────────┤
│ TARGET                       │ Performance goal to be verified by acceptance tests (not result)  │
│ SYSTEM CONSTRAINT            │ Hard physical or architectural boundary enforced by code/types   │
│ INITIAL DESIGN PARAMETER     │ Configurable heuristic/baseline subject to tuning/calibration    │
│ ASSUMPTION                   │ Contextual premise adopted for evaluation baseline                │
│ MEASURED RESULT              │ Empirical value obtained from verified test execution             │
│ SOURCE-DERIVED REQUIREMENT   │ Specification directly derived from OEM standard or regulation    │
└──────────────────────────────┴───────────────────────────────────────────────────────────────────┘
```

### Comprehensive Parameter Traceability Table:

| Parameter / Constant Name | Symbol / Field | Canonical Value | Classification | Technical Rationale & Scope |
| :--- | :---: | :---: | :---: | :--- |
| **Retrieval Precision at Top-$k$** | $P@3$ | $\ge 85.0\%$ | **TARGET** | Target proportion of retrieved chunks matching predefined ground-truth relevant chunk IDs. |
| **Mean Reciprocal Rank** | $\text{MRR}$ | $\ge 0.80$ | **TARGET** | Target mean reciprocal rank of the first relevant document chunk across evaluation queries. |
| **Average Query Latency** | $t_{\text{query}}$ | $< 50.0\,\text{ms}$ | **TARGET** | Measured CPU query time (20 warm-up, 100 measured runs; excluding indexing/loading). |
| **Zero Network Dependency** | — | $100\%$ Offline | **SYSTEM CONSTRAINT** | Hard architectural requirement: zero socket calls, no cloud APIs, no runtime model downloads. |
| **Valid Chunk Provenance** | — | Schema Enforced | **SYSTEM CONSTRAINT** | Every chunk must retain non-null `source_id`, `source_type`, `source_locator`, `content_hash`. |
| **Chunk Size (Characters)** | $L_{\text{chunk}}$ | $500 - 800$ chars | **INITIAL DESIGN PARAMETER** | Standard chunk length balancing semantic cohesion and focused context injection. |
| **Chunk Overlap (Characters)** | $L_{\text{overlap}}$ | $100$ chars | **INITIAL DESIGN PARAMETER** | Sliding boundary overlap preventing semantic truncation across chunk cuts. |
| **Default Retrieval Top-$k$** | $k$ | $3$ chunks | **INITIAL DESIGN PARAMETER** | Number of top ranked chunks returned for downstream advisory synthesis. |
| **Hybrid Weighting Factor** | $\alpha$ | $0.60$ | **INITIAL DESIGN PARAMETER** | Weight applied to normalized dense vector similarity ($1-\alpha=0.40$ on normalized BM25). |
| **BM25 Term Frequency Parameter** | $k_1$ | $1.5$ | **INITIAL DESIGN PARAMETER** | Standard Robertson-Spärck Jones term frequency saturation parameter. |
| **BM25 Document Length Scaling** | $b$ | $0.75$ | **INITIAL DESIGN PARAMETER** | Standard document length normalization scaling parameter. |
| **Minimum Relevance Threshold** | $S_{\min}$ | $0.15$ | **INITIAL DESIGN PARAMETER** | Score floor below which poorly matched chunks are rejected. |
| **IEC Information Model Standard** | IEC 61400-25 | IEC 61400-25 | **SOURCE-DERIVED REQUIREMENT** | International standard for wind turbine SCADA information modelling and event concepts. |

---

## 4. Source Authenticity & Corpus Governance

### 4.1 Corpus Source Taxonomy

To eliminate ambiguity regarding document origin and prevent misleading claims of OEM or IEC authorship, all documents in the RAG corpus are strictly partitioned into four explicit source categories:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               CORPUS SOURCE PROVENANCE TAXONOMY                                  │
├──────────────────────────────┬───────────────────────────────────────────────────────────────────┤
│ SOURCE_AUTHENTIC             │ Actual authoritative OEM/standard document legitimately obtained  │
│ SOURCE_DERIVED               │ Project-authored material derived from an identified source       │
│ PROJECT_SYNTHETIC            │ Deliberately authored test/demonstration scenarios & playbooks   │
│ UNVERIFIED                   │ Source cannot be verified (STRICTLY PROHIBITED FROM CORPUS)       │
└──────────────────────────────┴───────────────────────────────────────────────────────────────────┘
```

### 4.2 Document Content Type Taxonomy

Every chunk content block is explicitly classified:
- **`VERBATIM_SOURCE`**: Direct, unedited text from an authentic source document.
- **`DERIVED_SUMMARY`**: Project-authored technical synthesis citing an identified source.
- **`PROJECT_SYNTHETIC`**: Demonstration scenario text, synthetic alarm tables, or simulated test procedures.

> [!CAUTION]
> **NO FALSE AUTHORSHIP ATTRIBUTION**:
> Project-authored summary markdown files must **NEVER** be described as "authentic OEM manuals" or "verbatim IEC specifications". The retrieval engine must preserve provenance metadata at all stages, and downstream LLM synthesis must strictly reflect whether cited text is derived or synthetic.

---

## 5. Technical Document Corpus Architecture

The Phase 4 corpus will be organized into a governed directory hierarchy reflecting document provenance:

```
backend/rag/documents/
├── authoritative/                     # Reserved for genuine, verified external source material
│   └── README.md                      # Policy and ingestion criteria for authentic sources
├── derived/                           # Project-authored technical summaries referencing known standards
│   ├── windguard_gearbox_guide.md     # Derived from high-speed stage mechanical maintenance literature
│   ├── windguard_generator_guide.md   # Derived from stator insulation & thermal management literature
│   ├── windguard_pitch_guide.md       # Derived from aerodynamic blade angle calibration procedures
│   └── windguard_indian_sop.md        # Derived from Indian wind corridor O&M best practices
└── synthetic/                         # Demonstration & testing material specifically for WindGuard AI
    ├── windguard_synthetic_playbooks.md # Diagnostic playbooks for Benchmark Scenarios S1–S5
    └── iec_61400_25_concept_guide.md    # Educational summary of IEC 61400-25 information model concepts
```

### 5.1 IEC 61400-25 Standard Representation Clarification

- **Clarification**: IEC 61400-25 defines standard information models, data classes (e.g., `WMDS` for wind turbine dynamic status, `WYAW` for yaw system), and communication protocols for wind power plants.
- **Correction**: IEC 61400-25 does **NOT** prescribe universal manufacturer-specific alarm strings such as `AL-101`, `AL-104`, `AL-201`, `AL-301`, or mandatory OEM response minutes.
- **Governance**: Synthetic alarm identifiers (`AL-104`, etc.) used in WindGuard AI demonstration scenarios are explicitly categorized as **`PROJECT_SYNTHETIC`** and will **NOT** be attributed to IEC standards.

---

## 6. Mathematical Formulations & Local Hybrid Retrieval

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            LAYER 4 LOCAL HYBRID RETRIEVAL PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

   Natural Language Query / SCADA Fault Signature (q)
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
  ┌──────────────┐                    ┌──────────────┐
  │ Dense Vector │                    │ Lexical BM25 │
  │  Similarity  │                    │   Matching   │
  └──────────────┘                    └──────────────┘
         │ S_vec(q, d)                       │ S_bm25(q, d)
         │ ∈ [0.0, 1.0]                      │ ∈ [0.0, ∞)
         │                                   ▼
         │                            ┌──────────────┐
         │                            │ Normalization│ -> S_bm25_norm ∈ [0.0, 1.0]
         │                            └──────────────┘
         └─────────────────┬─────────────────┘
                           ▼
            ┌─────────────────────────────┐
            │     Hybrid Score Fusion     │
            │ S = α·S_vec + (1-α)·S_bm25  │  (α = 0.60)
            └─────────────────────────────┘
                           │
                           ▼
            ┌─────────────────────────────┐
            │ Deterministic Rank & Filter │  (Score DESC, Title ASC, ID ASC)
            │ Reject if S < S_min (0.15)  │
            └─────────────────────────────┘
                           │
                           ▼
            ┌─────────────────────────────┐
            │       RetrievalResult       │  (Top-k Chunks + Full Provenance)
            └─────────────────────────────┘
```

### 6.1 Dense Semantic Vector Retriever Specification

- **Algorithm**: Dense semantic vector retrieval using cosine similarity over L2-normalized document and query embeddings.
- **Local Embedding Vectorizer**: Deterministic local sentence-embedding model (pre-packaged local weights, e.g. `all-MiniLM-L6-v2`, 384-dimensional dense vectors) or deterministic localized sub-word feature encoder.
- **Storage & Execution**: Vector index stored locally as `.npy` / `.json` arrays. Model files bundled locally in `models/embeddings/`.
- **System Constraint**: **Zero runtime downloads, zero network calls, zero external embedding API dependencies.**
- **Vector Cosine Similarity Formulation**:
  $$S_{\text{cosine}}(\mathbf{v}_q, \mathbf{v}_d) = \max\left(0.0, \, \frac{\mathbf{v}_q \cdot \mathbf{v}_d}{\|\mathbf{v}_q\|_2 \|\mathbf{v}_d\|_2}\right) \in [0.0, 1.0]$$

### 6.2 Lexical BM25 Retriever Specification

- **Algorithm**: Canonical Okapi BM25 ranking algorithm.
- **Tokenizer**: Domain-aware regex tokenizer `\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b` with case folding, preserving technical alphanumeric tokens (e.g. `AL-104`, `ISO-4406`, `IEC-61400`, `WTG-07`).
- **Stopword Policy**: Standard English stopwords filtered out, but critical domain symbols and units (`kW`, `MW`, `RPM`, `°C`) retained.
- **Stemming Policy**: Algorithmic Porter Stemmer for English technical terms.
- **BM25 Scoring Formulation**:
  $$\text{Score}_{\text{BM25}}(q, d) = \sum_{t \in q} \text{IDF}(t) \cdot \frac{f(t, d) \cdot (k_1 + 1)}{f(t, d) + k_1 \cdot \left(1 - b + b \cdot \frac{|d|}{\text{avgdl}}\right)}$$
  Where:
  $$\text{IDF}(t) = \ln\left( \frac{N - n(t) + 0.5}{n(t) + 0.5} + 1 \right), \quad k_1 = 1.5, \quad b = 0.75$$

### 6.3 BM25 Score Normalization & Hybrid Fusion

Because raw BM25 scores are unbounded $[0.0, \infty)$, they must be deterministically normalized into $[0.0, 1.0]$ before fusing with cosine similarity:

$$S_{\text{BM25, norm}}(q, d) = \frac{\text{Score}_{\text{BM25}}(q, d)}{\text{Score}_{\text{BM25}}(q, d) + \bar{S}_{\text{BM25, ref}}} \in [0.0, 1.0)$$

Where $\bar{S}_{\text{BM25, ref}}$ is a reference scaling constant (Initial Design Parameter: $10.0$) ensuring smooth saturation without artificial zero-division.

#### Final Hybrid Fusion:
$$S_{\text{hybrid}}(q, d) = \alpha \cdot S_{\text{cosine}}(\mathbf{v}_q, \mathbf{v}_d) + (1 - \alpha) \cdot S_{\text{BM25, norm}}(q, d)$$
Where $\alpha = 0.60$ (Initial Design Parameter).

### 6.4 Deterministic Ranking & Edge Case Behavior

1. **Filtering**: Any chunk with $S_{\text{hybrid}}(q, d) < S_{\min}$ ($S_{\min} = 0.15$) is excluded from results.
2. **Deterministic Tie-Breaking**: If two chunks achieve identical hybrid scores, sorting order is strictly determined by:
   $$\text{Rank Order} = (\text{Score } \downarrow, \, \text{document\_title } \uparrow, \, \text{chunk\_id } \uparrow)$$
3. **Empty / Whitespace Query**: Returns `RetrievalResult` with empty `chunks=[]`, `scores=[]`, `query_latency_ms=0.0` without raising unhandled exceptions.
4. **Zero-Match Query**: Returns empty chunk list with valid `retrieval_mode`.
5. **Requested $k > \text{Available Chunks}$**: Returns all valid above-threshold chunks without error.

---

## 7. Data Schemas (Pydantic v2 Specification)

```python
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class SourceType(str, Enum):
    """Categorical source authenticity classification."""
    SOURCE_AUTHENTIC = "SOURCE_AUTHENTIC"     # Authentic OEM manual / standard
    SOURCE_DERIVED = "SOURCE_DERIVED"         # Project summary derived from identified source
    PROJECT_SYNTHETIC = "PROJECT_SYNTHETIC"   # Synthetic demo / test scenario content
    UNVERIFIED = "UNVERIFIED"                 # Prohibited from authoritative corpus

class ContentType(str, Enum):
    """Classification of text fidelity."""
    VERBATIM_SOURCE = "VERBATIM_SOURCE"       # Exact verbatim text from source document
    DERIVED_SUMMARY = "DERIVED_SUMMARY"       # Project-authored technical summary
    PROJECT_SYNTHETIC = "PROJECT_SYNTHETIC"   # Synthetic demonstration procedure

class RetrievalMode(str, Enum):
    """Controlled vocabulary for retrieval execution mode."""
    HYBRID_LOCAL = "HYBRID_LOCAL"             # Dense Vector + BM25 Hybrid
    BM25_LOCAL = "BM25_LOCAL"                 # BM25 Lexical-only local search
    TFIDF_LOCAL = "TFIDF_LOCAL"               # TF-IDF emergency local fallback

class DocumentChunk(BaseModel):
    """Immutable Document Chunk Schema with complete provenance tracking."""
    chunk_id: str = Field(..., description="Unique deterministic chunk ID (e.g. CHK-GB-001)")
    document_title: str = Field(..., description="Canonical document title")
    document_filename: str = Field(..., description="Source filename relative to documents directory")
    source_id: str = Field(..., description="Unique source identifier (e.g. SRC-OEM-GB-2024)")
    source_type: SourceType = Field(..., description="Authenticity classification of source")
    publisher: str = Field(..., description="Publisher or authoring organization")
    document_version: str = Field(default="1.0", description="Version string of document")
    publication_date: str = Field(..., description="Publication date (YYYY-MM-DD)")
    chapter: str = Field(..., description="Chapter or major heading")
    section: str = Field(..., description="Specific section heading")
    source_page: Optional[int] = Field(default=None, ge=1, description="Page number if paginated; None for markdown")
    source_locator: str = Field(..., description="Deterministic location anchor (e.g. 'Sec 4.2 Bearing Inspection')")
    content: str = Field(..., description="Text content of the document chunk")
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
```

---

## 8. Deterministic Local Fallback Hierarchy

To guarantee continuous operational availability in air-gapped substation environments without external dependencies, Phase 4 implements a 3-tier local fallback hierarchy:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             LOCAL RAG FALLBACK HIERARCHY                                         │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

   [ Primary Mode ] ────────────► HYBRID_LOCAL (Dense Vector Cosine + BM25 Lexical)
                                  Executes full hybrid score fusion.
                                  Zero network / 100% local CPU.
                                           │
                                           ▼ (If dense model weights unavailable)
   [ Secondary Mode ] ──────────► BM25_LOCAL (BM25 Lexical-Only)
                                  Executes Okapi BM25 keyword matching over token inverted index.
                                  RetrievalMode = "BM25_LOCAL".
                                           │
                                           ▼ (If BM25 index unavailable)
   [ Emergency Fallback ] ──────► TFIDF_LOCAL (Pure Scikit-Learn / Pure Python TF-IDF)
                                  Executes term-frequency inverse-document-frequency cosine match.
                                  RetrievalMode = "TFIDF_LOCAL".
```

- **Lockout Rule**: No fallback tier may make external network calls or cloud API requests.

---

## 9. Standardized 15-Query Evaluation Dataset Specification

Retrieval precision ($P@3$) and ranking quality ($\text{MRR}$) will be evaluated against a standardized 15-query domain evaluation dataset covering all 5 core operational domains:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           STANDARDIZED 15-QUERY EVALUATION BENCHMARK                             │
├──────────┬──────────────────────────────┬──────────────────────────────┬─────────────────────────┤
│ Query ID │ Operational Domain           │ Search Query Text            │ Expected Target Chunks  │
├──────────┼──────────────────────────────┼──────────────────────────────┼─────────────────────────┤
│ Q-GB-01  │ Drivetrain / Gearbox         │ "Gearbox bearing overheating │ CHK-GB-001, CHK-GB-002  │
│          │                              │ thermal threshold delta"     │                         │
│ Q-GB-02  │ Drivetrain / Gearbox         │ "ISO 4406 oil particle count │ CHK-GB-003, CHK-GB-004  │
│          │                              │ lubrication inspection"      │                         │
│ Q-GB-03  │ Drivetrain / Gearbox         │ "High speed shaft vibration  │ CHK-GB-002, CHK-GB-005  │
│          │                              │ dial indicator runout check" │                         │
│ Q-GEN-01 │ Generator & Cooling          │ "Generator stator winding    │ CHK-GEN-001, CHK-GEN-002│
│          │                              │ temperature class F limit"   │                         │
│ Q-GEN-02 │ Generator & Cooling          │ "Air to air heat exchanger   │ CHK-GEN-003, CHK-GEN-004│
│          │                              │ cooling fan motor failure"   │                         │
│ Q-GEN-03 │ Generator & Cooling          │ "Megger insulation test      │ CHK-GEN-002, CHK-GEN-005│
│          │                              │ stator resistance minimum"   │                         │
│ Q-PIT-01 │ Aerodynamic & Pitch          │ "Blade pitch angle asymmetry │ CHK-PIT-001, CHK-PIT-002│
│          │                              │ encoder drift calibration"   │                         │
│ Q-PIT-02 │ Aerodynamic & Pitch          │ "Hydraulic pitch cylinder    │ CHK-PIT-003, CHK-PIT-004│
│          │                              │ pressure drop troubleshooting│                         │
│ Q-PIT-03 │ Aerodynamic & Pitch          │ "Zero pitch mechanical index │ CHK-PIT-001, CHK-PIT-005│
│          │                              │ reference position check"    │                         │
│ Q-GRD-01 │ Grid Dispatch & Curtailment  │ "Grid curtailment active     │ CHK-GRD-001, CHK-GRD-002│
│          │                              │ power derate setpoint"       │                         │
│ Q-GRD-02 │ Grid Dispatch & Curtailment  │ "Feathered pitch power       │ CHK-GRD-002, CHK-GRD-003│
│          │                              │ shedding during strong wind" │                         │
│ Q-GRD-03 │ Grid Dispatch & Curtailment  │ "Deemed generation capacity  │ CHK-GRD-001, CHK-GRD-004│
│          │                              │ accounting under dispatch"   │                         │
│ Q-SOP-01 │ Indian Wind Corridor O&M     │ "Monsoon wind farm pre-check │ CHK-SOP-001, CHK-SOP-002│
│          │                              │ desiccant breather replace"  │                         │
│ Q-SOP-02 │ Indian Wind Corridor O&M     │ "Ambient heatwave operating  │ CHK-SOP-003, CHK-SOP-004│
│          │                              │ protocol above 38 celsius"   │                         │
│ Q-SOP-03 │ Indian Wind Corridor O&M     │ "Substation transformer oil  │ CHK-SOP-002, CHK-SOP-005│
│          │                              │ sampling safety checklist"   │                         │
└──────────┴──────────────────────────────┴──────────────────────────────┴─────────────────────────┘
```

### Evaluation Metric Formulations:
1. **Precision at 3 ($P@3$)**:
   $$P@3 = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{|\text{Retrieved Chunks}_{i, 1..3} \cap \text{Expected Chunks}_i|}{3} \times 100\% \quad [\text{TARGET: } \ge 85.0\%]$$
2. **Mean Reciprocal Rank ($\text{MRR}$)**:
   $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \text{RR}_i \quad [\text{TARGET: } \ge 0.80]$$
   Where $\text{RR}_i = \frac{1}{\text{rank}_i}$ for the first relevant chunk in the ranking. If no relevant chunk appears in top-$k$, $\text{RR}_i = 0.0$.

---

## 10. Benchmark Latency Measurement Protocol

To ensure reproducible, un-fabricated latency benchmarking:
- **Environment Recording**: Verified CPU hardware, OS version, and Python runtime.
- **Warm-Up Runs**: Exactly **20 warm-up queries** executed prior to measurement.
- **Measured Runs**: Exactly **100 timed query executions** using `time.perf_counter()`.
- **Exclusions**: Model initialization, tokenization dictionary compilation, and disk index loading are strictly excluded from query latency measurements.
- **Reported Metrics**: Mean Query Latency ($\text{ms}$) and 95th-percentile (p95) Latency ($\text{ms}$).
- **Target**: Average query latency $t_{\text{query}} < 50.0\,\text{ms}$ (classified strictly as **TARGET**).

---

## 11. Phase 4 Deliverables & File Structure Plan

```
backend/
├── rag/
│   ├── __init__.py                # Package exports for Layer 4 RAG components
│   ├── schema.py                  # Pydantic v2 schemas (DocumentChunk, RetrievalResult, Enums)
│   ├── document_chunker.py        # Structure-preserving markdown chunker & metadata extractor
│   ├── knowledge_base.py          # VectorKnowledgeBase & LocalHybridSearchEngine
│   └── documents/                 # Governed technical corpus
│       ├── authoritative/         # Verified external source material
│       │   └── README.md
│       ├── derived/               # Project-authored technical summaries
│       │   ├── windguard_gearbox_guide.md
│       │   ├── windguard_generator_guide.md
│       │   ├── windguard_pitch_guide.md
│       │   └── windguard_indian_sop.md
│       └── synthetic/             # Demonstration & test material
│           ├── windguard_synthetic_playbooks.md
│           └── iec_61400_25_concept_guide.md

tests/
├── test_chunker.py                # Unit tests for chunking, hash generation, and metadata preservation
├── test_knowledge_base.py         # Unit tests for BM25, dense similarity, hybrid fusion, and tie-breaking
└── test_acceptance_phase4.py      # Acceptance gate tests (TEST-RAG-01, TEST-RAG-LAT-01, Lockout, Regression)
```

---

## 12. Strict Phase Boundaries & Lockout Confirmation

To maintain modular architectural isolation, the following subsystems remain **100% LOCKED OUT**:

| Subsystem / Capability | Phase 4 Status | Scheduled Phase |
| :--- | :---: | :---: |
| **Technical Corpus & Hierarchical Chunking** | **IN SCOPE** | **Phase 4** |
| **Local Hybrid Vector + BM25 Retrieval Engine** | **IN SCOPE** | **Phase 4** |
| **Citation Metadata & Provenance Tracking** | **IN SCOPE** | **Phase 4** |
| **Retrieval Precision & Latency Verification** | **IN SCOPE** | **Phase 4** |
| **LLM Advisory Synthesis (`backend/llm/*`)** | **STRICTLY LOCKED OUT** | Phase 5 |
| **Prompt Bounding & Guardrail Validation** | **STRICTLY LOCKED OUT** | Phase 5 |
| **Web UI / Operator Dashboard (`frontend/*`)** | **STRICTLY LOCKED OUT** | Phase 6 |
| **Fleet REST API Endpoints (`/api/cases`, `/api/fleet/*`)** | **STRICTLY LOCKED OUT** | Phase 6 |
| **SCADA Actuation / Control Commands** | **PERMANENTLY LOCKED OUT** | Never |

---

## 13. Phase 4 Acceptance Criteria & Test Plan

1. **`TEST-RAG-01` (Retrieval Precision & Grounding)**:
   - Evaluates the 15-query benchmark against ground-truth relevant chunk mappings.
   - *Target*: Top-3 Retrieval Precision $P@3 \ge 85.0\%$ and $\text{MRR} \ge 0.80$.
2. **`TEST-RAG-LAT-01` (Retrieval Latency Performance)**:
   - Executes 20 warm-up + 100 timed query runs on local CPU.
   - *Target*: Average query latency $< 50.0\,\text{ms}$.
3. **`TEST-RAG-META-01` (Chunk Provenance & Hash Integrity)**:
   - Asserts $100\%$ of chunks have valid `source_id`, `source_type`, `source_locator`, `content_hash` (SHA-256), and positive `token_count`.
   - Asserts no artificial page numbers exist on markdown-native derived documents (`source_page is None`).
4. **`TEST-RAG-OFFLINE-01` (100% Offline System Constraint)**:
   - Mocks network socket calls and verifies that index initialization, chunking, vectorization, and search execute with zero network calls.
5. **`TEST-RAG-EDGE-01` (Edge Case Query Behavior)**:
   - Verifies deterministic, graceful handling of empty queries, whitespace, zero-match queries, tied scores, and $k > N$.
6. **`TEST-REGRESS-P1-P2-P3` (Phase 1–3 Regression Protection)**:
   - Verifies that all Phase 1, Phase 2, and Phase 3 functionality remains intact without regression.
7. **`TEST-LOCKOUT-P4` (Phase Boundary Lockout)**:
   - Asserts zero existence of `backend/llm/`, `frontend/`, `/api/cases`, `/api/fleet/*`, or turbine control actuation endpoints.

---

## 14. Current Governance Status & Next Gate

```
====================================================================================================
                             PHASE 4 PRE-IMPLEMENTATION GOVERNANCE GATE
====================================================================================================
Phase 1 Status                      : VERIFIED & FROZEN
Phase 2 Status                      : OWNER SIGNED OFF & FROZEN
Phase 3 Status                      : OWNER SIGNED OFF & FROZEN (44/44 PASS)
Phase 4 Scope Status                : PROPOSED SCOPE REVIEW — NOT YET AUTHORIZED
Phase 4 Implementation Code         : ZERO CODE WRITTEN (FROZEN)
====================================================================================================
```

### Next Gate:
**`PHASE 4 — READY FOR OWNER REVIEW & AUTHORIZATION`**

*(Awaiting explicit Project Owner review and authorization of `docs/PHASE_4_SCOPE_REVIEW.md` v2.0 before any implementation work begins).*
