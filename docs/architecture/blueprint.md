# VORNEQ Architecture Blueprint v2.2

**Status:** Stable reference  
**Purpose:** Architecture and review governance for future VORNEQ changes.

## Architecture statement

VORNEQ is trust infrastructure for the digital economy. It is designed so that claims can be inspected, documented, cited, authorized, and held accountable without the platform claiming ownership of absolute truth.

The core product goal is to reduce the cost of trust in human and machine digital exchange.

Core lifecycle:

**Discover → Verify → Transact → Deliver → Attest**

Core concepts:

**Artifact, Identity, Verification, Evidence, Entitlement, Reputation**

## 1. Core trust infrastructure

### Artifact
A stable canonical identifier for a digital artifact, independent of a specific product or content surface.

### Identity
A canonical actor representing a person, organization, or agent.

### Entitlement
The authorization primitive used to decide whether an identity or user may access an artifact in the Deliver layer.

### ArtifactBinding
Connects an Artifact to an allowed domain model while keeping trust primitives decoupled from product presentation.

### ArtifactIdentityRole
Represents the role of an Identity relative to an Artifact, such as author, seller, creator, owner, or contributor.

### Core services

- **Registry:** register and resolve Artifacts and Identities.
- **Entitlement:** grant and evaluate access rights.
- **Signature:** provide cryptographic integrity and signed attribution. A signature does not by itself establish legal ownership.

## 2. Trust layers

### Verification

Verification records and manages verification activity over an Artifact or Claim.

Key rule: **Verification ≠ Truth.** A verification outcome is a documented result, not a declaration of absolute truth.

Verification reuses the canonical Evidence kernel instead of introducing parallel evidence models.

### Evidence

Evidence is the canonical evidence and provenance layer. Evidence records use integrity digests where applicable, and provenance history is append-oriented.

### Reputation

Reputation is contextual rather than global. It must remain scoped by factors such as domain, verification method, and actor role.

VORNEQ must not collapse contextual reputation into a universal trust score.

## 3. Product layers

### Content and Knowledge

Articles, categories, tags, and other knowledge content may bind into the Artifact layer while preserving their own product-level models.

### Media and Visual Discovery

Media and visual similarity are Discovery capabilities. Visual Search does not imply Verification.

### Marketplace — Discovery Hub

Marketplace is the primary discovery destination for sellable and discoverable digital artifacts, including books, software, courses, media, documents, games, and other digital products.

Library is no longer a primary navigation destination. Legacy Library detail, audio, and protected-delivery routes may remain for backward compatibility until equivalent Marketplace paths exist.

## 4. UX and interface architecture

VORNEQ uses a shared Global Experience System for navigation, cards, filters, states, and common interaction patterns.

The interface supports RTL and LTR layouts through logical CSS properties and internationalized templates.

The multi-theme system contains eight supported preferences:

- VORNEQ Default
- Dark
- Light
- Blue
- Gold
- Emerald
- Purple
- System

Primary navigation is intentionally simple, centered on **Home** and **Marketplace**.

## 5. Infrastructure

### Security

The baseline includes CSP, HSTS in production, rate limiting, brute-force protection, and dependency auditing.

### Observability

The platform uses structured logging, Prometheus-compatible metrics, and correlation IDs for request tracing.

### Reliability

Backup and restore workflows, migration preflight checks, health checks, and safer deployment sequencing form the production reliability baseline.

## Stable architecture principles

### 1. Verification ≠ Truth
Verification outcomes must never be presented as absolute truth.

### 2. Trust Context without Score
No composite Trust Score or star rating may be introduced as a proxy for trustworthiness.

### 3. Search ≠ Verification
Search is a Discovery and retrieval mechanism. Trust-aware ranking, if introduced, must be explicit and opt-in.

### 4. Reputation is Contextual
Reputation remains scoped by domain, method, actor role, and evidence context. It is never global by default.

### 5. Marketplace is the Discovery Hub
Library must not be reintroduced as a primary destination. Legacy paths may remain only for compatibility or controlled delivery needs.

### 6. No Inference
Canonical Identity must not be inferred from free-text fields such as `LibraryItem.author` or similar strings.

### 7. PostgreSQL First
Elasticsearch or other infrastructure must not be introduced without measured evidence that PostgreSQL-based approaches are insufficient.

### 8. Multi-Theme Compatibility
UI changes must use design tokens and remain compatible with the supported theme system. Avoid hard-coded product colors unless they are intentional token definitions.

### 9. Backward Compatibility
A change must not break existing URLs, API contracts, entitlement paths, or canonical data without an explicit migration, redirect, or compatibility plan.

## Architecture Check for every PR

Before merge, reviewers should verify:

1. Verification outcomes are not presented as absolute truth.
2. No composite Trust Score or star rating is introduced.
3. Search remains Discovery/retrieval rather than Verification.
4. Reputation remains contextual by domain, method, and actor role.
5. Library is not reintroduced as a primary destination.
6. Identity is not inferred from free-text fields.
7. New infrastructure is not introduced without measured need.
8. UI changes remain compatible with the multi-theme design system.
9. Existing URLs, API contracts, entitlement paths, and canonical data remain compatible or have an explicit migration/redirect plan.

Any exception to these rules must be documented in an ADR.

## Evolution roadmap

1. **Completed:** PR #122 — Performance Profiling foundation.
2. **Current:** run benchmarks on staging or production-like data to identify the actual bottleneck.
3. **Next:** optimize performance only from measured evidence.
4. **Later:** expand Playwright E2E coverage.
5. **Later:** continue observability and monitoring improvements.

## Governance

This document is an architecture blueprint, not a code snapshot. Implementation details may evolve, but changes must remain compatible with the principles above or be accompanied by an explicit architectural decision record.
