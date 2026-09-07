# Search Evolution Principles — VORNEQ

**Status:** Proposed  
**Version:** v0.1  
**Related:** Architecture Scaling Principles, Platform Contract v0.1

---

## 1. Purpose

This document defines the **decision framework** for evolving search capabilities in VORNEQ. It is not a migration roadmap for any specific technology.

> **Core Principle:**  
> Search infrastructure evolves only when **real workload pressure** (measured SLO violations, corpus/query growth, proven ranking needs, or consumer demand) justifies it.

---

## 2. Evolution Stages

Search evolves through the following stages. Each stage is a **decision point**, not a mandatory step.

```
Domain‑safe Retrieval
│
▼
Unified Search Contract
│
▼
Measured Ranking
│
▼
Hybrid / Semantic Retrieval
│
▼
Context‑aware Ranking
│
▼
Recommendation / Personalization
│
▼
Independent Search Infrastructure
(only if operational pressure justifies it)
```

> **Important:** Semantic Search does **not** necessarily imply a separate Search Cluster. Recommendation does **not** necessarily belong inside Search. Each can become an independent capability or bounded component only when proven needed.

---

## 3. Decision Triggers

Each evolution stage is triggered by **measurable, workload‑dependent conditions**:

| Stage | Trigger |
| :--- | :--- |
| **Domain‑safe Retrieval** | ✅ Default for VORNEQ (current state) |
| **Unified Search Contract** | Need for a stable, versioned search interface across multiple Apps |
| **Measured Ranking** | Proven need for ranking beyond simple relevance (e.g., recency, popularity) |
| **Hybrid / Semantic Retrieval** | Relational retrieval becomes insufficient for query understanding |
| **Context‑aware Ranking** | Need to personalize results based on user Identity, role, or historical behavior |
| **Recommendation / Personalization** | Real consumer demand for personalized discovery |
| **Independent Search Infrastructure** | **Persistent violation of SLOs** (latency, throughput) or **corpus/query growth** that exceeds current capacity |

---

## 4. Invariants (Must Preserve)

Throughout all stages, the following invariants must be preserved:

- **Search ≠ Verification** — Search results are discovery, not endorsement.
- **Authorization before Retrieval** — Private retrieval must be limited before ranking and pagination.
- **Artifact Presence ≠ Permission** — Existence of an Artifact does not imply publication or read permission.
- **Search Engine ≠ Domain Data Owner** — The search engine must not become the canonical owner of domain data.
- **Search Contract Stability** — The Unified Search Contract must remain stable across implementations.

---

## 5. Architecture Relationship

| Layer | Responsibility |
| :--- | :--- |
| **Domain Apps** | Own data, authorization, and business logic |
| **Unified Search Contract** | Stable interface for retrieval |
| **Search Implementation** | PostgreSQL (current), future Search Platform (if justified) |
| **Infrastructure** | Observability, monitoring, and SLO tracking |

> **Note:** PostgreSQL is the **current implementation choice**. A future Search Platform (e.g., Vespa, Elasticsearch) is an **option**, not a requirement.

---

## 6. What This Is Not

- **Not a roadmap for Vespa or Elasticsearch.**
- **Not a commitment to distributed search infrastructure.**
- **Not a requirement for semantic retrieval or recommendation at launch.**
- **Not a replacement for domain‑owned authorization.**

---

## 7. References

- [Architecture Scaling Principles](scaling-principles.md)
- [Platform Contract v0.1](platform-contract.md)
- [UnifiedSearch Implementation](../../apps/search/services.py)

---

**Status:** Proposed  
**Next Steps:** Register as a docs‑only PR from current `main` (SHA to be confirmed live before branch creation).
