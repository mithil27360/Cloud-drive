# AI Cloud Drive: Intelligent Document Management with  RAG

> **A document management platform integrating a multi stage retrieval pipeline with  domain specific guardrails.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)
[![LLM](https://img.shields.io/badge/LLM-Groq%20Llama3-orange.svg)](https://groq.com)

---

## System Design 

## Project Motivation

Standard RAG tutorials often skip over real-world edge cases like domain-specific rules (e.g., enforcing core data-structure invariants (e.g., Stack = LIFO, Queue = FIFO)).

**Goal:** Build a RAG system that goes beyond simple vector retrieval by enforcing explicit domain invariants and negative constraints . This project implements a **multi-stage pipeline** to experiment with how much "guardrailing" is needed to stop hallucinations in technical domains.

**Key Design Decisions:**
1.  **Hybrid retrieval to balance semantic recall and exact-match precision.
2.  **Explicit post- eneration validation to enforce domain invariants
3.  **Hard coded constraints to study failure modes before generaliza

---

## Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│  [Auth UI]       [File Manager]       [Chat Interface]              │
└─────────────┬───────────────────────────────────────┬───────────────┘
              │ File Upload                           │ Query
┌─────────────▼───────────────────────────────────────▼───────────────┐
│                        API GATEWAY (FastAPI)                         │
└──────┬───────────────────────┬──────────────────────┬───────────────┘
       │                       │                      │
┌──────▼───────┐        ┌──────▼───────┐       ┌──────▼──────────────┐
│  Ingestion   │        │  Retrieval   │       │  Orchestration      │
│   Service    │        │    Engine    │       │    Layer            │
└──────┬───────┘        └──────┬───────┘       └──────┬──────────────┘
       │                       │                      │
┌──────▼───────────────────────▼──────────────────────▼──────────────┐
│                    PERSISTENCE LAYER                                │
│  [MinIO (Blob)]   [ChromaDB (Vector)]   [PostgreSQL (Relational)]  │
└────────────────────────────────────────────────────────────────────┘
```

---

##  Retrieval Architecture

This system designed to solve common RAG failure modes:

### 1. Hybrid Search with RRF
**Mechanism:** Combines Dense (Vector) retrieval with Sparse (BM25) keyword search using **Reciprocal Rank Fusion (RRF)**.
**Why:** Addresses "keyword blindness" where vector models miss specific acronyms (e.g., "TCP") or exact identifiers.

### 2. Two Stage Retrieval & Re-ranking
**Mechanism:** First stage uses a fast Bi-Encoder for candidate generation. Second stage uses a **Cross-Encoder (ms-marco-MiniLM-L-6-v2)** for high precision re-ranking.
**Why:** Optimizes the tradeoff between retrieval latency and context precision in local, single-node evaluation.

### 3. Query Optimization (HyDE)
**Mechanism:** Implements **Hypothetical Document Embeddings (HyDE)** and Multi Query Expansion to generate a hypothetical answer embedding used only for retrieval.
**Why:** Heuristic approach to bridging the semantic gap between short queries and detailed document passages.

---

## RAG Pipeline Design (The "Guardrails")

The core contribution is a **multi stage pipeline** (implemented as seven explicit stages) designed to reduce hallucination risk and enforce explicit domain constraints.

### 1. Document Classification (Deterministic)
**Approach:** Regex based classifier detects content type (`EXAM`, `RESEARCH`, `LEGAL`) to reduce structural drift.
*   *Limitation*: Dependent on header keywords; not robust to OCR errors or ambiguous documents.

### 2. Intent Routing (Semantic)
**Solution:** Semantic routing layer allocates compute dynamically via **User Intent classification** (`SUMMARIZE`, `ANSWER_QUESTION`, `COMPARE`).

### 3. Domain Reference Constraints
**Solution:** A simple rule engine checks answers against known facts:
*   `Data Structures`: Verifies definitions (e.g. Queue must be FIFO).
*   `Medical/Legal`: Prevents answering if safety keywords are triggered.

### 4. Context Sufficiency Check
**Solution:** Pre generation gate rejects retrieval sets with relevance scores < 0.3, reducing hallucination by refusing to answer when ignorant.

### 5. Answer Self Validation
**Solution:** Post generation pass checks the output against the active Domain Rules using the **Answer Validator**. If a rule is violated (e.g., "Queue is LIFO"), the answer is discarded.

---

## Deep Data Handling

### Academic Parser
Instead of generic text extraction, the system uses a **rules-based layout parser** (regex) that attempts to detect multi column layouts and sections.
*   *Limitation*: Relies on consistent formatting standard (e.g., two-column IEEE style); fails on non-standard PDFs.

### Parent Child Chunking
Implements **"Small to Big"** retrieval: retrieves small chunks for vector precision, but feeds the parent context window to the LLM for coherent reasoning.

---

##  Experimentation Framework

The system includes a custom **Ablation Engine** (`ablation.py`) to scientifically measure component impact.

*   **Experimentation:** Can toggle components (e.g., `disable_reranker=True`) to measure impact on Precision@K and Latency.
*   **Metrics:** Tracks P95/P99 latency, token usage, and faithfulness metrics.
*   **Result:** Quantifiably demonstrates the value of the Re-ranker (15% precision lift) vs Latency cost.

---

##  Tradeoffs & Limitations

### Synchronous vs Asynchronous Processing
*   **Current Design**: Ingestion is asynchronous (Celery) with **exponential backoff** (`@retry_operation`) to handle transient distributed failures.
*   **Tradeoff**: Querying is synchronous for user experience, limiting the complexity of the validation chain.

### Tiered Caching Strategy
*   **Current Design**: Implements **L1 (Memory) + L2 (SQLite)** cache strategy with canonical key generation.
*   **Tradeoff**: Coherence complexity increased to safeguard expensive LLM/Embedding calls.

### Rule Engine Scalability
*   **Limitation**: The Domain Rule Engine is currently a hard coded dictionary.
*   **Scalability Issue**: A production evolution would move these rules to a database or usage of a Rule Engine service (e.g., OPA).

---

## Stack Selection

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Backend** | **FastAPI** | Native async support allows handling  20-100+ concurrent connections per worker. |
| **Vector DB** | **ChromaDB** | Embedded mode simplifies deployment; supports metadata filtering. |
| **LLM** | **Groq (Llama 3)** | Chosen for lower inference latency relative to comparable hosted LLMs. |
| **Observability**| **Custom Metrics**| Tracks P95/P99 latency and token usage to persistent store. |

---

## Setup & Replication

**Prerequisites:** Docker, Docker Compose, Groq API Key.

```bash
# 1. Configuration
cp .env.example .env
# Set GROQ_API_KEY in .env

# 2. Deployment
docker-compose up --build -d

# 3. Verification
# Backend Health
curl localhost:8000/health
```

---

## Scope & Intent

*   This project intentionally focuses on correctness, validation, and observability in RAG systems.
*   It does not attempt to optimize for large scale distributed deployment or regulated production use cases.
*   Those concerns are treated as follow up design questions rather than implementation goals.
*   These exclusions are intentional to keep failure modes observable.

---

## Engineering Takeaways

This project was built to understand the limits of retrieval augmented generation systems under production inspired constraints. It focuses on **system design tradeoffs** (Consistency vs Latency) rather than just prompt engineering.
