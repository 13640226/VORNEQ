# ADR 008: Visual Similarity Search Architecture

**Status:** Proposed  
**Date:** 2026-09-06  
**Owners:** VORNEQ Core Team

## Context

ADR 007 established the visual-media boundary for VORNEQ: `MediaAsset` is a domain-owned record, canonical cross-domain identity remains `Artifact`, and visual similarity is a discovery concern rather than a trust claim.

The next capability is visual similarity search over registered media. VORNEQ must support similarity discovery without coupling the product to one embedding provider, one vector backend, one model family, or one external AI vendor. It must also preserve the central trust boundary:

`Similarity != Verification != Authenticity != Truth`

Similarity systems produce derived numerical representations and rankings. These may be useful for discovery, deduplication assistance, related-media browsing, and candidate generation, but they do not establish provenance, authorship, authenticity, manipulation status, or factual correctness.

## Decision

VORNEQ will implement visual similarity search as a provider-agnostic discovery subsystem over existing `MediaAsset` records. Embeddings and vector indexes are derived, rebuildable search infrastructure and are not canonical trust records.

### 1. Search remains separate from Verification

A similarity result answers only a discovery question such as:

> Which indexed MediaAssets are most similar to this query under the configured embedding/index policy?

A similarity score MUST NOT be presented as:

- proof that two assets have the same origin;
- proof that one asset is a copy of another;
- proof of authenticity;
- proof of manipulation or non-manipulation;
- Verification outcome;
- Evidence quality;
- Reputation;
- Truth.

If a product flow needs to make an authenticity, source, provenance, or manipulation claim, that claim must use the existing Evidence/Provenance and Verification architecture.

### 2. Embedding providers use an explicit adapter contract

The similarity service will depend on an internal provider interface rather than a vendor-specific SDK contract.

The contract may support capabilities such as:

- image -> embedding;
- text -> embedding, only when the configured model supports a compatible multimodal embedding space;
- provider/model identifier;
- embedding dimensionality;
- embedding policy/version identifier;
- execution metadata required for operational telemetry.

Concrete providers are adapters. No external provider is a trust authority.

Provider selection is an implementation/configuration concern and is not fixed by this ADR.

### 3. Vector storage is abstracted behind an index contract

The search service will use an internal vector-index abstraction supporting the minimum operations needed by current product behavior, such as:

- upsert an embedding for a MediaAsset;
- remove an indexed MediaAsset;
- search nearest candidates;
- rebuild or reindex derived vectors;
- report the embedding/index policy used for returned results.

This ADR does not select FAISS, pgvector, Pinecone, or any other backend.

A backend may be local, database-backed, or managed, provided it preserves the architectural boundaries defined here.

### 4. Embeddings and indexes are derived infrastructure

An embedding is a derived computational representation of a MediaAsset or query. It is not canonical Evidence or Provenance.

Stored embedding/index records should be associated with at least:

- the MediaAsset identifier;
- provider/model identifier;
- embedding policy/version;
- vector dimensionality or compatible schema identifier;
- generation timestamp;
- index namespace/version where relevant.

Embeddings MAY be deleted and rebuilt without changing canonical Artifact, Identity, Evidence, Verification, Entitlement, or Reputation state.

Model/provider changes MUST NOT silently mix incompatible vector spaces. Reindexing or explicit index version separation is required when compatibility cannot be guaranteed.

### 5. Query uploads are ephemeral by default

A user-uploaded image submitted only for similarity search is a query input, not automatically a `MediaAsset`, `Artifact`, `Evidence`, or trust record.

By default:

- the raw query image should not be persisted beyond what is operationally necessary to execute the request;
- temporary files should follow an explicit retention/deletion policy;
- no Artifact, Identity, Evidence, or Verification object is created implicitly;
- logs and telemetry must avoid retaining raw media unless explicitly required and disclosed.

If a user explicitly chooses to save/import a query image, that is a separate product action and must use the Media foundation registration flow.

### 6. Search results reference existing MediaAssets

Indexed results must resolve back to existing, active `MediaAsset` records.

Search infrastructure must not create shadow media identities. Canonical cross-domain references remain the existing MediaAsset -> Artifact binding where applicable.

Inactive or unavailable MediaAssets should not be returned as normal discovery results unless a specific administrative workflow explicitly requests them.

### 7. Text-to-image search is capability-dependent

`search_by_text()` is permitted only when the configured provider/model produces text and image embeddings in a compatible semantic space.

The service contract must not assume that every image embedding provider supports text queries.

Capability detection or explicit configuration should prevent unsupported cross-modal requests from silently producing misleading rankings.

### 8. Result semantics are explicit

A search result may include discovery-oriented fields such as:

- MediaAsset identifier;
- distance/similarity score;
- rank;
- embedding/index policy identifier;
- optional presentation metadata resolved from the MediaAsset.

The API/UI must label the score as a similarity/ranking signal, not a confidence of truth or authenticity.

Thresholds are ranking/product-policy decisions and must not be reinterpreted as Verification thresholds.

### 9. Telemetry is operational, not trust evidence

The service should capture enough telemetry to benchmark providers and backends, including where available:

- provider/model/version;
- embedding policy/index version;
- latency;
- request success/failure;
- candidate/result count;
- provider usage units;
- estimated cost when calculable;
- reindex/index operation metrics.

Operational telemetry does not become Evidence, Verification, Reputation, or a trust score merely because it is recorded.

Cost values should be treated as estimates unless reconciled against provider billing data.

### 10. Provider failures must not change trust state

Embedding-provider or vector-index failures are discovery-service failures only.

They must not:

- alter Verification outcomes;
- change Reputation;
- revoke or grant Entitlements;
- mutate canonical Evidence/Provenance;
- create trust claims implicitly.

The caller should receive an explicit search-service failure or degraded response according to product policy.

### 11. Access policy is evaluated separately from similarity

Similarity ranking does not itself grant access to media.

If a MediaAsset or its underlying file is gated by a separate access/Entitlement policy, result presentation and delivery must continue to respect that policy. Search indexing must not become a bypass around controlled delivery.

### 12. Security and privacy boundaries

Implementations must validate upload constraints before provider execution, including applicable limits for MIME type, file size, and image dimensions.

Provider adapters must make data-transfer and retention behavior configurable/documented so deployments can make informed privacy and residency choices.

Sensitive provider credentials remain infrastructure secrets and must never be stored in MediaAsset, Artifact, Evidence, or telemetry payloads.

## Consequences

### Positive

- Similarity discovery can evolve independently of Verification.
- Embedding providers and vector stores can be benchmarked or replaced without changing trust primitives.
- Reindexing is safe because vectors are explicitly treated as derived state.
- Privacy behavior for query uploads is explicit from the start.
- Future image-to-image and compatible text-to-image discovery share one architectural boundary.

### Costs / Trade-offs

- An adapter layer adds implementation work before a first provider integration.
- Provider/model upgrades require explicit compatibility and reindex policy.
- Operational telemetry and index-version management become necessary for reproducibility and cost comparison.
- Cross-modal text search cannot be guaranteed for every provider.

## Non-goals

This ADR does not define or implement:

- authenticity or manipulation Verification;
- provenance inference;
- LLM/AI Answer generation;
- automatic Claim or Evidence creation;
- a specific embedding provider;
- a specific vector database;
- a Visual Search UI;
- media ingestion UX;
- OCR as canonical Evidence;
- face recognition or identity inference;
- biometric identification;
- automatic creator/source inference;
- Entitlement policy changes.

## Implementation direction

Follow-up implementation should be split into small PRs. A recommended sequence is:

1. embedding-provider and vector-index interfaces plus local/mock test adapters;
2. indexing/reindexing service for active MediaAssets;
3. image similarity search service/API with ephemeral query handling and telemetry;
4. optional compatible text-to-image search;
5. UI in a separate PR;
6. authenticity/manipulation workflows only through a later Verification-focused design.

The first implementation PR should avoid committing the architecture to a production provider or vector backend unless current deployment requirements make that choice necessary and separately reviewable.
