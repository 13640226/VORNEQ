# VORNEQ Knowledge Flywheel

**Status:** Proposed  
**Version:** v0.1  
**Scope:** Strategy, not a platform contract

---

## 1. Purpose

This document describes the strategic flywheel by which VORNEQ can become more useful as people create, organize, inspect, rediscover, and reuse knowledge.

It does **not** introduce a new platform primitive, change Platform Contract v0.1, or require a closed ecosystem. It provides a strategy-level model for evaluating product and architecture priorities.

> **Core Principle:**  
> VORNEQ should compound value through inspectable knowledge relationships, provenance, context, interoperability, and reuse — **not through user lock-in**.

---

## 2. The Strategic Distinction

Integrated technology ecosystems demonstrate an important systems lesson: durable advantage can emerge when multiple parts of a product reinforce one another. VORNEQ adopts the **flywheel pattern**, not the closed-ecosystem model.

| Dimension | Closed-ecosystem flywheel | VORNEQ knowledge flywheel |
| :--- | :--- | :--- |
| Primary retention mechanism | Switching cost and ecosystem dependency | Increasing value of structured, reusable knowledge |
| Source of compounding value | Integrated devices, software, distribution, and services | Knowledge relationships, provenance, evidence, context, discovery, and composition |
| User control | Often bounded by platform-controlled formats and channels | Inspectability, portability, explicit boundaries, and user-controlled composition |
| Defensive advantage | Integration depth and cost of exit | Relationship density, trustworthy provenance, interoperability, and reusable context |
| Growth signal | More devices/services consumed | More useful knowledge created, connected, rediscovered, and reused |

The objective is therefore not to make knowledge difficult to leave VORNEQ. The objective is to make knowledge **more useful because VORNEQ preserves its relationships and context while keeping those relationships inspectable**.

---

## 3. The VORNEQ Flywheel

The proposed flywheel is:

```text
1. Create inspectable knowledge objects
        │
        ▼
2. Organize and compose knowledge in Apps / Workspace
        │
        ▼
3. Enrich value through provenance, context, evidence, and explicit verification
        │
        ▼
4. Improve rediscovery through Search and Personal Home
        │
        ▼
5. Reuse useful knowledge in new work and contexts
        │
        ▼
6. Increase the density and utility of the knowledge network
        │
        └──────────────► back to 1
```

Each stage should strengthen the next without weakening VORNEQ's architectural boundaries.

### 3.1 Create inspectable knowledge objects

Artifacts and domain-owned records provide stable references for knowledge without turning `Artifact` into a universal domain model. A domain record may expose an Artifact representation when shared identity, provenance, discovery, or referencing is useful; not every domain object must become an Artifact. Identity and provenance make origin and relationships inspectable.

### 3.2 Organize and compose knowledge

Domain Apps own their data and business rules. Workspace provides composition context without taking ownership of App data or authorization policy.

### 3.3 Enrich knowledge value

Provenance, Evidence, Verification, and contextual relationships provide material that users and systems can inspect. VORNEQ does not declare universal truth; it provides context and evidence required for examination.

### 3.4 Rediscover knowledge

Search and Personal Home reduce the cost of finding useful existing knowledge. Retrieval remains distinct from verification, and authorization must be enforced before unauthorized information can influence retrieval, ranking, pagination, or presentation.

### 3.5 Reuse knowledge

Rediscovered knowledge becomes input to new documents, notes, collections, investigations, and other domain workflows. Reuse is a stronger strategic signal than passive storage because it demonstrates continuing knowledge utility.

### 3.6 Increase network density

As knowledge is connected and reused, the platform gains more useful relationships and context. The resulting value should come from the quality and inspectability of those relationships, not from making user data artificially difficult to export or use elsewhere.

---

## 4. Current Platform Contribution

The current platform already supplies important parts of this flywheel:

| Flywheel stage | Current VORNEQ surfaces | Strategic role |
| :--- | :--- | :--- |
| Create | Identity, Artifact and domain-owned records | Stable identity, representation, and provenance boundaries |
| Organize | Documents, Notes, Workspace | Domain work and composition |
| Enrich | Evidence, Verification, provenance and bounded audit mechanisms | Inspectable supporting context |
| Rediscover | Unified Search and Personal Home | Deterministic retrieval and resurfacing |
| Reuse | Documents, Notes, Workspace and App workflows | Bring prior knowledge into new work |
| Compound | Relationships among identities, artifacts, evidence, contexts, and domain records | Increase useful knowledge-network density |

Personal Home's first Documents integration was implemented and merged in **PR #180**. Its deterministic Recent Documents and Recently Viewed surfaces are an initial product mechanism for reducing rediscovery cost; they should not be interpreted as an ML recommendation system.

---

## 5. Strategic Guardrails

The flywheel must preserve existing architectural invariants:

1. **Knowledge value must not depend on lock-in.** Portability and inspectability are product strengths, not threats to retention.
2. **Domain ownership remains explicit.** Shared infrastructure does not acquire ownership of canonical domain data.
3. **Search is not Verification.** Retrieval or ranking must not imply truth, trust, publication, or authorization.
4. **Identity is not Authorization.** Identity provides a subject and relationships; Apps retain domain authorization policy.
5. **Artifact is not Permission.** Artifact presence does not imply publication, verification, trust, or read access.
6. **Contextual reputation is not a universal score.** Reputation remains contextual and must not silently become authorization.
7. **Workspace is composition, not domain ownership.** It must not become shared mutable App state or a path around App permissions.
8. **Complexity follows proven need.** Recommendation systems, semantic retrieval, executable cross-App capabilities, event infrastructure, and physical distribution are introduced only when real consumers and measured pressure justify them.

---

## 6. Architectural Strategy — Deep Contracts, Broad Interoperability

The flywheel should grow through four complementary principles:

### 6.1 Deep Contracts

VORNEQ should keep the set of shared contracts deliberately small, precise, and contract-governed. Identity, Artifact, Evidence, Verification, Contextual Reputation, and reviewed shared invariants are valuable because their boundaries are explicit — not because every App is forced into the same domain model.

A stable Core is not an ever-growing Core. New concepts should remain domain-owned until repeated, proven cross-platform need justifies a reviewed shared contract.

### 6.2 Broad Interoperability

Independent Apps and workflows should be able to participate in the knowledge network through reviewed shared representations and relationships without surrendering their own domain models.

Interoperability therefore means **composition across explicit boundaries**, not shared mutable domain state. Documents does not need to become Notes; Search does not become the owner of indexed data; Workspace does not become the owner of App authorization.

### 6.3 Open Extensibility

VORNEQ should be able to integrate with external systems and standard infrastructure without requiring every layer to be invented in-house. External adapters, capabilities, and integrations should use explicit contracts and anti-corruption boundaries where needed.

Open extensibility does not imply unrestricted execution or implicit trust. Capability execution, external integrations, and cross-App behavior remain subject to reviewed contracts, explicit invocation context, and domain authorization.

### 6.4 Explicit Domain Ownership

Every domain must retain clear ownership of its canonical data, business rules, and authorization policy. A shared service does not gain domain ownership merely because multiple Apps use it.

This principle applies across Search, Workspace, Personal Home, future integrations, and any future AI-assisted capability.

The combined strategy is:

> **Deep Contracts. Broad Interoperability. Open Extensibility. Explicit Domain Ownership.**

This is the architectural mechanism by which additional Apps can strengthen the flywheel without forcing the platform toward a God Model or a closed ecosystem.

---

## 7. Own the Differentiation, Reuse the Commodity

VORNEQ should concentrate engineering ownership on the concepts that create its durable differentiation: identity relationships, Artifact boundaries, provenance, Evidence, Verification, context, domain boundaries, inspectability, and the contracts that preserve them.

Commodity implementation technology should remain replaceable where practical. A database, web framework, cache, queue, object store, observability stack, or AI model may be an important implementation choice without becoming part of VORNEQ's permanent strategic identity.

Therefore:

> **Own the differentiation; reuse the commodity.**

This principle complements the Scaling Principles: complexity and infrastructure specialization should follow demonstrated requirements rather than architecture fashion or a desire for platform completeness.

---

## 8. AI as a Cross-cutting Capability

AI may eventually assist Search, Documents, Evidence workflows, Workspace, Personal Home, or other Apps. That does not make AI a new domain owner or an automatic Platform primitive.

The strategic guardrails are explicit:

```text
AI = cross-cutting capability
AI ≠ Domain Owner
AI ≠ Authorization
AI ≠ Verification
AI output ≠ Evidence
AI inference ≠ Identity
AI ranking ≠ Truth
```

An AI-produced statement may become material that a domain workflow stores or examines, but its origin must remain inspectable and it must not acquire Evidence or Verification semantics merely because a model produced it.

Likewise, recommendation and personalization should not become shared platform primitives before deterministic product behavior, measurement, real consumers, and demonstrated need justify that promotion.

---

## 9. What to Measure

A flywheel becomes useful as a strategy only when its movement can be observed. Future measurement should prefer signals of knowledge utility over vanity growth metrics.

Candidate signals include:

- percentage of created knowledge that is later rediscovered;
- percentage of rediscovered knowledge that is reused in another workflow;
- time required to return to a previously useful item;
- growth in meaningful, user-visible relationships per active knowledge object;
- proportion of important objects with inspectable provenance/context;
- successful cross-App reuse without authorization-boundary violations;
- export/portability success as evidence that retention is value-driven rather than lock-in-driven.

These are strategic measurement directions, not current SLOs or contractual requirements. Baselines and targets should be introduced only after instrumentation exists and real usage can be measured.

---

## 10. Product Priorities Through the Flywheel

The flywheel provides a filter for roadmap decisions:

- **Retention & Deletion Policy** strengthens trustworthy lifecycle management and user control.
- **Search measurement and ranking evolution** can strengthen rediscovery once baseline workload and quality signals exist.
- **External adapters / ACL** can increase useful knowledge inflow and outflow when a real external integration exists.
- **Executable Capability Bus work** is justified only when a real cross-App consumer requires it.
- **Recommendation or ML personalization** should follow deterministic product learning and measurable need, not precede them.

The question for a new platform initiative should therefore be:

> Does this measurably improve creation, enrichment, rediscovery, reuse, or inspectable relationships while preserving domain ownership and user control?

If not, it should not be justified merely as "platform completeness."

---

## 11. Relationship to Architecture

This document is intentionally downstream of the architecture contract.

- **Platform Contract v0.1** remains authoritative for shared primitives, maturity, and invariants.
- **Architecture Scaling Principles** governs when architectural complexity is justified.
- **Platform Layers** describes responsibility and ownership boundaries across the system.
- **Search Evolution Principles** is a proposed search-specific framework in PR #178 at the time this document is authored; it is **not yet part of `main`** and is therefore not treated here as a merged dependency.

This strategy must adapt to reviewed architectural contracts, not override them.

---

## 12. Summary

VORNEQ's durable advantage should not be a closed ecosystem. It should be a compounding knowledge system in which:

**inspectable knowledge → organization → provenance/context/evidence → rediscovery → reuse → denser useful relationships → more valuable knowledge**.

Its architectural strategy for sustaining that loop is:

> **Deep Contracts. Broad Interoperability. Open Extensibility. Explicit Domain Ownership.**

VORNEQ should own the concepts that create its differentiation, reuse commodity infrastructure where appropriate, and treat AI as a bounded cross-cutting capability rather than a new source of truth or ownership.

The stronger this loop becomes, the more valuable VORNEQ can become without relying on artificial switching costs.

---

## References

- [Platform Contract v0.1](../architecture/platform-contract.md)
- [Architecture Scaling Principles](../architecture/scaling-principles.md)
- [Platform Layers](../architecture/platform-layers.md)
- [PR #180 — Documents Personal Home integration](https://github.com/13640226/VORNEQ/pull/180)
- [PR #178 — Search Evolution Principles (open at authoring time)](https://github.com/13640226/VORNEQ/pull/178)
