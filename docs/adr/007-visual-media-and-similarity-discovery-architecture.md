# ADR 007: Visual Media and Similarity Discovery Architecture

**Status:** Proposed  
**Date:** 2026-09-06  
**Owners:** VORNEQ Core Team

## Context

VORNEQ is Trust Infrastructure for the Digital Economy. Visual and multimedia capabilities can strengthen the core lifecycle:

`Discover -> Verify -> Transact -> Deliver -> Attest`

However, visual search, media storage, similarity ranking, provenance, and authenticity are different concerns and MUST NOT be collapsed into one primitive or one score.

The platform already has canonical `Artifact`, `Identity`, Evidence/Provenance, Verification, Entitlement, and contextual Reputation primitives. ADR 006 established the pattern that a domain object remains domain-owned and binds into the canonical Artifact Registry rather than duplicating Artifact semantics.

This ADR applies the same boundary to visual media and defines how similarity discovery can be added without treating similarity as verification or truth.

## Decision

VORNEQ will introduce visual media as domain-owned models that bind to existing canonical trust primitives. Similarity discovery will remain a discovery capability. Authenticity, manipulation, origin, and source claims remain Evidence/Verification concerns.

### 1. MediaAsset is a domain model bound to Artifact

`MediaAsset` is a domain model, not a replacement for canonical `Artifact`.

A MediaAsset may own media-domain concerns such as:

- media type;
- storage reference;
- MIME type;
- byte size;
- intrinsic width/height where applicable;
- duration where applicable;
- presentation metadata;
- ingestion timestamps;
- lifecycle/availability state.

When a MediaAsset participates in trust workflows, it is explicitly registered through the existing Artifact Registry and connected using `ArtifactBinding`.

Canonical cross-domain identity remains the Artifact ID. MediaAsset remains the media-domain record.

### 2. Image and video specialization must not create parallel trust primitives

The initial implementation may use one `MediaAsset` model with a typed `media_type`, or explicit domain subclasses/models such as `ImageAsset` and `VideoAsset` if concrete behavior justifies them.

Regardless of storage shape:

- subclasses remain media-domain records;
- they do not become canonical Artifact types by themselves;
- they do not duplicate Evidence, Provenance, Verification, or Identity.

The implementation PR must choose the smallest model shape needed by current product behavior and avoid speculative inheritance.

### 3. Similarity Search is not Verification

Visual similarity search answers a discovery question such as:

> Which indexed media objects are visually similar to this query image?

A similarity score, embedding distance, perceptual-hash distance, feature match, OCR overlap, or ranking confidence MUST NOT be presented as:

- authenticity;
- truth;
- provenance;
- authorship;
- originality;
- evidence of manipulation;
- a VerificationResult;
- a Reputation score.

Similarity results are discovery signals only.

### 4. Authenticity and manipulation claims use Evidence and Verification

Claims such as:

- “this image came from source X”;
- “this media predates another copy”;
- “this image was modified”;
- “this capture is unaltered”;
- “this person or organization created/published this media”;

must be represented through the existing Claim/Evidence/Provenance and Verification architecture.

Visual Search services may surface existing public verification summaries where policy allows, but search infrastructure must not manufacture verification outcomes from similarity results.

Verification still does not mean Truth.

### 5. Source, creator, publisher, and owner roles use Identity explicitly

Media actor relationships use existing `Identity` and `ArtifactIdentityRole` records.

Examples include:

- creator;
- publisher;
- owner;
- contributor.

No trusted Identity relationship may be inferred from filenames, EXIF strings, embedded text, usernames, account handles, metadata labels, OCR results, or similarity matches.

Extracted labels may be stored as untrusted media metadata or Evidence inputs, but explicit Identity binding is required before they become canonical actor relationships.

### 6. Canonical provenance remains in the Evidence layer

The Media domain MUST NOT create a competing canonical provenance store.

MediaAsset may store operational or presentation metadata such as:

- storage checksum;
- decoder metadata;
- EXIF values as imported raw metadata;
- rendering hints;
- import job identifiers;
- thumbnail information.

Claims about origin, lineage, capture history, transformation history, attestation, or evidentiary source belong to the canonical Evidence/Provenance layer.

Imported metadata is not automatically trusted provenance.

### 7. Storage and access control are separate from trust status

Media must use Django storage abstractions rather than hard-coded filesystem paths or public storage URLs.

A MediaAsset may be public or protected depending on product policy.

Entitlement is used only when access to a media object is actually gated by a product/delivery policy. The existence of a MediaAsset does not automatically imply an Entitlement requirement.

Likewise, protected delivery does not imply verification, authenticity, or trustworthiness.

### 8. Media geometry is explicit

For images and rendered video previews, intrinsic geometry should be recorded when known so presentation can reserve layout space before media loads.

Public UI must follow the Global Experience System and existing CLS hardening principles:

- stable width/height or equivalent aspect-ratio contracts;
- responsive rendering;
- appropriate lazy loading below the fold;
- no lazy loading of critical above-the-fold media when it harms LCP;
- meaningful alt text, or empty alt text for decorative media.

### 9. Similarity indexing is derived infrastructure

Embeddings, perceptual hashes, feature vectors, OCR tokens, and other search representations are derived indexes, not canonical trust records.

They may be rebuilt when algorithms or index versions change.

The system should record enough operational metadata to identify the index/model/version used for a search result when needed for debugging or reproducibility, but that metadata must not be confused with ScoringPolicy or Verification policy versions.

### 10. Search ranking must be explainable at the product boundary

Initial search results should expose product-appropriate reasons such as:

- visually similar;
- same or near-duplicate image;
- matching extracted text;
- matching tags/category;

when those reasons can be determined reliably.

The UI must not label a result “verified”, “authentic”, or “original” solely because it ranked highly.

### 11. Query uploads require explicit privacy and retention rules

A user-submitted image used only as a search query is not automatically a persistent MediaAsset.

The Visual Search service must define whether query media is:

- processed ephemerally;
- temporarily retained;
- persisted as a MediaAsset only through an explicit user/product action.

Query uploads must not silently create Artifacts, Evidence, Identities, or public content.

Retention, logging, and reuse of query media require an explicit policy before production deployment.

### 12. External vision/AI providers are adapters, not trust authorities

If external image-analysis, embedding, OCR, or vision services are used later, their outputs are external computational signals.

Provider output does not become Truth or Verification merely because the provider is reputable.

Provider/model/version details may be recorded for reproducibility and audit where appropriate. Any trust claim based on such output must pass through the normal Evidence/Verification policy.

## Proposed Media domain boundary

A first foundation PR may introduce:

- a minimal `MediaAsset` domain model;
- image-relevant geometry and storage metadata;
- optional media-type-specific fields only where currently required;
- explicit Article-like registration into the Artifact Registry;
- explicit creator/source-related Identity role services using existing Identities;
- model/service tests.

The Foundation PR MUST NOT implement similarity search or authenticity verification.

## Similarity Search service boundary

A later Visual Search PR may introduce:

- query-image validation;
- derived visual index generation;
- similarity lookup;
- ranked result normalization;
- algorithm/index version metadata;
- read-only API endpoints;
- tests that demonstrate search ranking does not alter Verification, Evidence, Artifact, Identity, Entitlement, or Reputation state.

Search infrastructure should begin with the least operationally complex approach that satisfies measurable product requirements. A vector database, hosted vision API, or dedicated search cluster is not required until demonstrated scale/relevance needs justify it.

## Verification boundary

Authenticity or manipulation verification is a separate later phase.

That phase may introduce Verification methods specifically suited to media, but must reuse:

- Claim;
- Evidence;
- EvidenceRelation;
- Provenance;
- VerificationRequest/Result;
- QualitySignal where eligibility rules permit.

It MUST NOT create parallel `AuthenticityScore`, `TruthScore`, or visual-specific provenance primitives that bypass the canonical kernel.

## Security requirements

Media ingestion and search must account for:

- MIME validation and content sniffing;
- file-size limits;
- image dimension limits and decompression-bomb protections;
- safe decoder behavior;
- storage isolation;
- access authorization for protected media;
- rate limiting for expensive search/analysis operations;
- privacy of user-submitted query images;
- no exposure of private Evidence through search results.

Exact limits belong to implementation policy, not this ADR.

## Non-goals

This ADR does not:

- implement Bing-style Visual Search;
- select a vector database or external AI provider;
- define a universal authenticity detector;
- define face recognition or biometric identity matching;
- create a global image truth score;
- make similarity a QualitySignal by default;
- make every MediaAsset entitlement-protected;
- replace Artifact, Identity, Evidence, Provenance, or Verification;
- implement media editing or capture tools.

## Implementation sequence

### PR A — ADR 007

- document Media/Artifact boundaries;
- separate similarity discovery from Verification;
- define privacy/storage/provenance boundaries;
- no runtime changes.

### PR B — Media foundation

- add the minimal MediaAsset domain model needed by current requirements;
- add explicit Artifact registration support;
- add explicit existing-Identity role assignment;
- add model/service tests;
- no visual search;
- no authenticity Verification.

### PR C — Visual Similarity Search

- add query validation and derived similarity index/search service;
- add read-only API;
- keep similarity results explicitly non-verification;
- no UI yet unless required for acceptance testing.

### PR D — Visual Search UI

- accessible upload/query interface;
- stable media geometry;
- RTL/LTR support;
- clear labeling of similarity versus verification status.

### PR E — Media Authenticity Verification

- define/implement media-specific Verification methods using the existing Evidence kernel;
- expose only policy-approved public summaries;
- no global truth or authenticity score.

## Consequences

### Positive

- visual capabilities extend VORNEQ without creating parallel trust primitives;
- discovery and verification remain conceptually and operationally separate;
- media can participate in canonical Artifact/Identity workflows;
- derived search infrastructure remains replaceable and rebuildable;
- privacy and retention concerns are addressed before query-upload production use.

### Trade-offs

- a high-ranking visual match cannot be marketed as verified authenticity without separate Evidence/Verification;
- explicit Identity and provenance mapping requires more disciplined data handling than heuristic inference;
- search index/model versioning adds operational metadata and testing requirements;
- protected media access and trust status remain separate policies, which increases conceptual clarity but requires explicit product decisions.

## Status transition

This ADR remains **Proposed** until reviewed and merged. Runtime implementation begins only after the architectural boundaries above are accepted.