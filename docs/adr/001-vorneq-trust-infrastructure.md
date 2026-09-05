# ADR 001: VORNEQ Trust Infrastructure Architecture

**Status:** Accepted  
**Date:** 2026-09-06  
**Author:** VORNEQ Core Team

---

## 1. Context

VORNEQ began as a digital knowledge platform for books, articles, audio, and digital products. The broader problem VORNEQ is designed to address, however, is not a shortage of information. It is the cost and difficulty of establishing **trust** in digital artifacts, services, transactions, and AI-generated outputs.

As humans and AI agents produce and exchange increasing volumes of digital work, participants need to assess whether an artifact or service is:

- authentic or traceable to a credible origin;
- secure enough for its intended use;
- authorized for access or reuse;
- supported by relevant evidence;
- suitable for a particular use case.

VORNEQ's long-term mission is therefore to **reduce the cost of trust in the digital economy**.

This requires an architecture that can support multiple product verticals without rebuilding identity, verification, access, delivery, and reputation logic independently for each one.

---

## 2. Decision

**VORNEQ is trust infrastructure for the digital economy. Trust is the core product; a marketplace is one application of that infrastructure.**

The architectural direction is organized around the following lifecycle:

```text
Discover → Verify → Transact → Deliver → Attest
```

The lifecycle is not required to be strictly synchronous or linear for every use case. It defines the major trust responsibilities that VORNEQ must support.

### Core concepts

VORNEQ will evolve around five primary concepts:

| Concept | Meaning |
| --- | --- |
| **Artifact** | A digital object or output that carries information or value, such as a PDF, report, dataset, code package, model output, or attestation. |
| **Identity** | A human, organization, or AI agent that creates, verifies, transacts with, or consumes artifacts. |
| **Verification** | A scoped claim about an artifact or identity, supported by a method, evidence, timestamp, and where appropriate a confidence or risk assessment. |
| **Entitlement** | A record proving that an identity currently has a right to access or use a protected resource. |
| **Reputation** | Historical trust information derived from behavior, verification outcomes, transaction outcomes, and other auditable events. |

These concepts are architectural primitives, not a statement that every corresponding generalized model already exists today.

### Trust must remain explainable

VORNEQ must not represent verification as an unexplained or absolute declaration of truth. Verification should answer questions such as:

- what claim was checked;
- who or what performed the check;
- which method was used;
- what evidence supports the result;
- when the result was produced;
- what limitations, confidence, or risk remain.

Trust in VORNEQ should therefore be **evidence-based and auditable**, rather than reduced to a single opaque "verified" flag.

---

## 3. Architectural Boundaries

### Core

`apps/core` owns reusable trust primitives and services that should not be specific to one product vertical.

Today, this includes core reputation models and the Entitlement primitive introduced by PR #50. Future generalized concepts such as Artifact and broader Identity/Verification abstractions should be introduced here only when their boundaries are sufficiently understood.

### Verticals

Existing product experiences such as `library` and `marketplace`, and future experiences such as Agents, Verify, Attestation, and Bounties, remain vertical-specific layers.

Verticals may adapt existing domain models to core primitives, but should avoid duplicating trust logic that belongs in Core.

### Delivery

Controlled delivery is currently implemented by the Marketplace vertical in `marketplace/delivery.py`, backed by the Core Entitlement primitive.

This is intentional. A generalized delivery application or service should only be extracted when multiple verticals require the same delivery behavior and a stable cross-vertical interface is clear.

This ADR therefore establishes **Deliver as an architectural responsibility**, not a requirement that an `apps/delivery` package exist immediately.

---

## 4. Concrete Implementation: Entitlement and Controlled Delivery

PR #50 introduced the first explicit implementation of the Deliver responsibility.

### Entitlement

`Entitlement` is defined in `apps/core/models.py` and currently relates a Django user to a Marketplace `Product`.

It supports:

- activation and revocation;
- optional expiration;
- metadata for future grant context;
- uniqueness of the user/product entitlement pair;
- indexes supporting entitlement checks.

The current Product relationship is a deliberate transitional boundary. Entitlement must not be prematurely generalized through polymorphism before Artifact semantics are defined.

### Entitlement services

`apps/core/services/entitlement.py` exposes explicit operations:

- `grant_entitlement(...)`
- `revoke_entitlement(...)`
- `has_valid_entitlement(...)`

Entitlements are not automatically granted by hidden signals. Payment completion, administrative grants, subscriptions, and future trust workflows should call explicit service boundaries.

### Protected delivery

`marketplace/delivery.py` provides the current protected digital delivery endpoint.

Delivery requires:

1. an authenticated user;
2. an approved and published product;
3. a digital file associated with that product;
4. a valid, active, non-expired Entitlement;
5. an available file in the configured Django storage backend.

Unauthorized or unavailable delivery targets return `404` to avoid exposing protected-resource availability.

The implementation accesses the file through the storage abstraction attached to the file field (`product.digital_file.storage`) rather than relying on a local filesystem `.path`. This preserves compatibility with future object-storage backends.

The public product template does not expose `digital_file.url`; entitled users receive a link only to the protected application endpoint.

### Security regression coverage

Current tests cover:

- anonymous download requests being redirected to authentication;
- authenticated users without entitlement receiving `404`;
- inactive and expired entitlements receiving `404`;
- products without files receiving `404`;
- valid entitlement delivery succeeding;
- direct protected file URLs not appearing in public product HTML;
- protected download links being hidden until entitlement is valid.

---

## 5. Consequences

### Positive

- **Reusable trust foundations:** future verticals can share core trust capabilities rather than reimplementing them.
- **Controlled access:** entitlement and delivery are separated from public discovery and presentation.
- **Storage portability:** protected delivery does not assume a local filesystem.
- **Incremental migration:** existing Product and Library models can remain stable while core abstractions mature.
- **Reduced long-term coupling:** trust rules have an explicit architectural home.

### Costs and risks

- **Greater architectural discipline is required:** it will sometimes be faster locally to add vertical-specific logic, but doing so can fragment the trust model.
- **Generalization has migration cost:** existing domain models may eventually need explicit relationships to Artifact and Identity abstractions.
- **Premature abstraction is also a risk:** generic relations or universal object models introduced before the use cases are understood may produce a weak and hard-to-query data model.
- **Trust decisions carry product responsibility:** verification and reputation systems must preserve provenance, evidence, and limitations rather than creating unjustified certainty.

---

## 6. Migration Strategy

Existing models such as `Product` and `LibraryItem` will **not** be renamed or replaced merely to conform to this ADR.

The migration strategy is incremental:

1. keep existing vertical models operational;
2. introduce a Core primitive only when at least one concrete responsibility is understood and testable;
3. connect existing vertical models to the primitive through explicit relationships or adapters;
4. preserve backwards compatibility and data integrity;
5. generalize only after multiple use cases demonstrate a stable shared boundary.

For Artifact specifically, a future ADR or implementation PR must evaluate alternatives such as:

- an explicit Artifact registry with one-to-one or foreign-key relationships;
- typed artifact subclasses;
- service-level adapters;
- generic relations only if their flexibility clearly outweighs referential-integrity and queryability costs.

This ADR does **not** choose a polymorphism strategy for Artifact.

---

## 7. Roadmap

| Phase | Focus | Status |
| --- | --- | --- |
| **Phase 1** | VORNEQ Knowledge: discovery, Marketplace, Entitlement, and Controlled Delivery; transaction/payment lifecycle still to be completed | 🟡 In progress |
| **Phase 2** | General Verification layer: scoped claims, evidence, verifier identity, methods, confidence/risk representation | 🔜 Next architecture phase |
| **Phase 3** | Agent participation and Agent Marketplace, including controlled execution/sandbox requirements | Planned |
| **Phase 4** | Attestation and Micro-Bounty workflows built on shared trust primitives | Planned |

The roadmap is directional. Security, legal, operational, and product validation gates may change implementation order.

---

## 8. Brand and Product Positioning

The architectural distinction is reflected in the brand hierarchy:

- **Company / platform:** *VORNEQ is trust infrastructure for the digital economy.*
- **First product vertical:** *VORNEQ Knowledge*
- **Knowledge tagline:** *Discover Knowledge.*

Future vertical names such as VORNEQ Verify or VORNEQ Agents may use the same trust infrastructure without changing the platform's core identity.

---

## 9. Decision Rules for Future Work

Future architectural work should follow these rules:

1. **Trust belongs in Core when it is reusable across verticals.**
2. **Vertical-specific user experience stays in the vertical until a stable shared interface exists.**
3. **Access to a protected artifact must be based on an explicit entitlement or equivalent policy decision.**
4. **Verification must retain provenance, method, evidence, time, and limitations.**
5. **Do not generalize Product, LibraryItem, or other domain models prematurely.**
6. **Prefer explicit services and auditable state transitions over hidden signal-driven business logic.**
7. **New trust primitives require tests for unauthorized, expired, revoked, or otherwise invalid states.**

---

## 10. Conclusion

This ADR formalizes VORNEQ's transition from a content-centric platform toward a reusable trust infrastructure.

The governing product decision is:

> **Trust is the core product. Marketplace is one of its applications.**

The lifecycle:

```text
Discover → Verify → Transact → Deliver → Attest
```

and the architectural concepts of Artifact, Identity, Verification, Entitlement, and Reputation will guide future development, while implementation remains incremental and grounded in concrete use cases.

PR #50 provides the first production-oriented proof of this direction through Entitlement-backed controlled delivery. Future ADRs should refine Artifact, Verification, Identity, transaction, and attestation boundaries as those systems move from philosophy into concrete implementation.
