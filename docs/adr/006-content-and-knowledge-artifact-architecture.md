# ADR 006: Content and Knowledge Artifact Architecture

**Status:** Proposed  
**Date:** 2026-09-06  
**Owners:** VORNEQ Core Team

## Context

VORNEQ is a Trust Infrastructure for the Digital Economy, not a general-purpose portal. New product surfaces must strengthen the core lifecycle:

`Discover -> Verify -> Transact -> Deliver -> Attest`

The project already has canonical Evidence, Verification, Reputation, Artifact, Identity, and Entitlement primitives. It also has domain models such as `Product` and `LibraryItem` that retain their own business semantics while binding into the canonical Artifact Registry.

The next product need is richer knowledge discovery: editorial articles, research notes, explainers, and other publishable knowledge objects that can participate in search, verification, provenance, and contextual trust workflows without introducing a parallel content identity system or duplicating canonical trust primitives.

This ADR defines the boundary for a Content domain and its integration with the existing Artifact, Identity, Evidence, Verification, and Discovery layers.

## Decision

VORNEQ will introduce content as domain-owned models that bind into existing canonical trust primitives. Content models do not replace Artifact, Identity, Evidence, or Provenance.

### 1. Article is a domain model bound to Artifact

`Article` is not itself the canonical `Artifact` model and MUST NOT duplicate Artifact Registry responsibilities.

An Article owns content-domain concerns such as:

- title and slug;
- summary and body;
- publication state;
- category and tags;
- optional presentation media;
- scheduling and editorial timestamps.

When an Article must participate in trust workflows, it is registered through the existing Artifact Registry and connected using `ArtifactBinding`, following the same architecture used for Product and LibraryItem.

The Artifact remains the canonical cross-domain identifier. The Article remains the content-domain record.

### 2. Author and contributor roles use Identity

VORNEQ will not create a separate canonical `Author` actor model.

Authorship, editorship, ownership, sponsorship, or other actor relationships are represented through explicit `ArtifactIdentityRole` records pointing to existing `Identity` objects.

No author Identity may be inferred from a display name, byline string, email address, username, or other heuristic.

A presentation-only byline string may exist when source material requires it, but it must not be treated as a trusted Identity relationship unless an explicit mapping exists.

### 3. Verification and Evidence reuse the existing kernel

Article verification uses the existing Verification and Evidence architecture.

Claims about an Article may be represented by the canonical `Claim`, `Evidence`, `EvidenceRelation`, and Provenance primitives defined by ADR 002 and its amendment. Verification remains orchestration/workflow and MUST NOT create a parallel article-specific evidence model.

Verification may target the Article's canonical Artifact binding. Public verification summaries must continue to avoid leaking private evidence or internal review details.

Verification still does not mean Truth.

### 4. Canonical provenance remains in the Evidence layer

The Content domain MUST NOT introduce a second canonical provenance store such as an unrestricted `provenance_metadata` field that competes with the Evidence kernel.

Content may store presentation or editorial metadata that is not a trust assertion, for example import source labels, CMS migration identifiers, or rendering hints. Any metadata that claims source lineage, evidentiary origin, attestation history, or verification provenance belongs in the canonical Evidence/Provenance layer.

This preserves a single auditable ownership boundary for trust-relevant provenance.

### 5. Publication state is a content-domain responsibility

Article publication workflow belongs to the Content domain.

The initial model should support explicit state and timestamps rather than relying on `auto_now_add` publication semantics. At minimum:

- creation timestamp;
- update timestamp;
- publication timestamp;
- draft/published state.

Scheduling may be represented explicitly when implemented. Publication state must not be inferred solely from `published_at` being non-null unless the model contract intentionally defines that invariant.

Publication does not imply verification, and verification does not automatically publish content.

### 6. Slugs are presentation identifiers, not canonical identifiers

Article URLs may use human-readable slugs, but slugs are not canonical trust identifiers and may change under explicit editorial policy.

Canonical cross-system references use Artifact identifiers.

Slug creation must be collision-safe and tested. Implementation should avoid unbounded query loops where a deterministic uniqueness strategy can be used safely.

### 7. Discovery integration is additive

Published Articles may participate in VORNEQ discovery surfaces alongside LibraryItem, AudioItem, Product, and other eligible domain objects.

Discovery integration must preserve the domain object's own URL and presentation semantics while using Artifact bindings when trust metadata is required.

The first search implementation should prefer the project's existing PostgreSQL/Django capabilities. Elasticsearch or other external search infrastructure is not introduced until demonstrated scale or relevance requirements justify the operational cost.

### 8. Recommendation starts transparent and rule-based

Initial recommendations should be deterministic and explainable, using signals such as:

- category;
- tags;
- recency;
- explicitly recorded user preferences;
- public popularity or interaction signals when appropriate.

Recommendation ranking MUST NOT be presented as a trust or truth score. Contextual Reputation and QualitySignal semantics remain separate.

Machine-learning ranking is a later decision that requires its own privacy, explainability, data-retention, and evaluation review.

### 9. Social interaction is not evidence by default

Comments, reactions, ratings, or consensus signals may be added later, but they are interaction data unless explicitly admitted into a governed QualitySignal workflow.

Popularity, majority opinion, or comment volume MUST NOT become Truth, Verification, or Reputation automatically.

Any later conversion of social interaction into a quality signal must follow ADR 003 eligibility and audit rules.

### 10. External information domains remain conditional

Finance, weather, and similar external-information surfaces are not part of this ADR's implementation scope.

If introduced later, they should be modeled as external information with clear source attribution, freshness, and provenance. They must not be represented as verified merely because VORNEQ displays them.

Games, generic email, travel, and portal-style utility aggregation remain outside the current product thesis.

## Proposed Content domain boundary

The first implementation may introduce:

- `Article`;
- `Category`;
- `Tag`;
- admin/editorial configuration;
- services for explicit Artifact registration and Identity-role binding;
- read-only public article views;
- tests for publication state, slug behavior, registry binding, and explicit author-role mapping.

The Content app owns editorial data. Core owns canonical trust primitives.

## Service boundaries

Content services may call existing registry services to register or resolve an Article Artifact binding, but they MUST NOT duplicate registry logic.

Registration must follow the existing `register_artifact` service contract rather than inventing a second Artifact creation path.

Identity-role assignment must use explicit existing Identity objects and must not create or infer identities from article bylines.

Evidence and Verification services remain owned by their existing layers. Content services may request those workflows but do not own their primitives.

## Search and feed boundaries

Search and Home feed integration should be implemented in a later PR after the Content foundation is stable.

The integration should expose a normalized presentation record without pretending that all domain objects share one database model. A feed adapter may normalize fields such as:

- stable presentation key;
- object type;
- title;
- summary;
- URL;
- optional image;
- publication timestamp;
- optional Artifact identifier;
- optional public verification/reputation summary where policy permits.

The feed layer must not query private Evidence or internal trust records for presentation convenience.

## Media and CLS requirements

Article imagery must follow the existing Global Experience System and PR #80 hardening principles:

- rendered images should reserve intrinsic geometry with width/height or an equivalent stable aspect-ratio contract;
- below-the-fold imagery may use lazy loading;
- primary above-the-fold imagery should not be lazily loaded when that harms LCP;
- media storage must use Django storage abstractions rather than hard-coded local filesystem assumptions;
- alt text must describe meaningful content or be empty when the image is purely decorative.

## Security and trust behavior

Introducing Content must not weaken existing trust boundaries:

- publication cannot silently create a trusted Identity;
- Article creation cannot manufacture Evidence or Verification results;
- unverified content must not be labeled verified;
- social/popularity signals cannot silently affect Contextual Reputation;
- private Evidence remains private;
- Artifact and Identity mappings remain explicit and auditable.

## Implementation sequence

### PR A — ADR 006

- document Content/Artifact/Identity/Evidence boundaries;
- no runtime behavior changes.

### PR B — Content foundation

- add Content app;
- add Article, Category, and Tag models;
- add publication-state and slug tests;
- add explicit Article -> Artifact registration service;
- add explicit Article Artifact -> Identity author-role service;
- no Home/search integration yet;
- no recommendation system yet.

### PR C — Article presentation

- article list/detail views and templates;
- accessible, RTL/LTR-safe, GES-aligned presentation;
- stable image geometry;
- public verification summary integration only through existing public services.

### PR D — Unified discovery integration

- add published Articles to the existing discovery/search feed;
- normalized feed adapter;
- no speculative external search infrastructure.

### PR E — Rule-based recommendations

Only after interaction/privacy requirements are defined:

- deterministic recommendation policy;
- transparent ranking inputs;
- no trust-score conflation;
- no ML dependency by default.

## Consequences

### Positive

- VORNEQ gains a first-class knowledge publishing surface without becoming a generic portal.
- Articles can participate in verification and provenance through existing canonical primitives.
- Author relationships reuse Identity instead of creating a competing actor model.
- Search and discovery can grow across domains while preserving explicit domain boundaries.
- Trust semantics remain auditable and non-inferential.

### Costs and risks

- content-domain and Artifact records must remain synchronized through explicit services;
- publication and verification are separate state machines and may require careful UI language;
- discovery normalization adds adapter complexity;
- editorial bylines may exist without canonical Identity mapping and must be presented carefully;
- recommendation features require privacy and explainability discipline.

## Non-goals

This ADR does not:

- turn VORNEQ into a general news/entertainment portal;
- replace Product, LibraryItem, AudioItem, Artifact, Identity, Claim, Evidence, or Provenance;
- create a canonical Author model;
- infer Identity from article text, bylines, usernames, or metadata;
- define a global trust score for content or authors;
- treat publication, popularity, ratings, or consensus as Verification or Truth;
- add Games, email, travel, finance, or weather modules;
- add Elasticsearch, Redis, Celery, HTMX, GraphQL, or other infrastructure merely for architectural symmetry;
- implement recommendations in the foundation PR;
- change Entitlement or Deliver semantics.

## Decision summary

VORNEQ will add publishable knowledge through domain-specific Content models that bind explicitly to the canonical Artifact Registry. Trust actors remain canonical Identities connected through explicit Artifact roles. Verification, Evidence, Provenance, Reputation, and QualitySignal semantics are reused rather than duplicated. Discovery and recommendation capabilities may consume the Content domain later, but they must remain transparent, privacy-aware, and distinct from Truth or trust scoring.