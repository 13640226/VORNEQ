# Architecture Scaling Principles — VORNEQ

**Status:** Proposed  
**Version:** v0.1  
**Related:** Platform Contract v0.1, User Experience Layers, User Control Principles, Trust Safety & Compliance Baseline

---

## 1. Purpose

This document defines the **scaling principles** for VORNEQ. It establishes the architectural boundaries that allow VORNEQ to grow from a modular monolith to a distributed system **only when a real need is proven**.

> **Core Principle:**  
> VORNEQ adds complexity based on proven need:  
> **first domain boundaries, then contracts, then observability, and only then physical distribution.**

---

## 2. The Stable Core (Contract-Governed)

The following components form the **stable, contract-governed core** of VORNEQ. They are not immutable; changes are versioned and require migration/ADR.

| Component | Responsibility | Status |
| :--- | :--- | :---: |
| **Identity** | User, organization, and service identity | ✅ Stable |
| **Artifact** | Digital asset with provenance and discoverability | ✅ Stable |
| **Evidence** | Verifiable evidence and supporting materials | ✅ Stable |
| **Verification** | State-machine for verification processes | ✅ Stable |
| **Contextual Reputation** | Context-bound reputation (not global trust) | ✅ Stable |
| **Registry / Manifest** | App registration and capability discovery | ✅ Stable |
| **Domain Ownership** | Each App owns its data, logic, and authorization | ✅ Stable |
| **Provenance** | Inspectable data and decision lineage | ✅ Stable |

> **Note:** These components are **stable by contract, not by immutability**. Changes are versioned, documented, and require ADR/migration.

---

## 3. Scaling Principles

### 3.1. Modular Boundaries Before Distributed Boundaries

- **Current:** Modular Monolith with hard domain boundaries (Core, Platform Shell, Apps).
- **Trigger:** Separate scalability, independent deployment, or independent team for an App.

### 3.2. Resilience Only at True Distributed Boundaries

- **Current:** No Circuit Breaker, Retry, or Bulkhead for internal calls.
- **Trigger:** When VORNEQ connects to external APIs, search clusters, remote storage, payment, or independent services.

### 3.3. CQRS Must Start Lightweight

- **Current:** Natural separation of read/write (e.g., `DocumentService` for mutation, `DocumentSearchAdapter` for read).
- **Trigger:** When a separate read model, complex reporting, or heavy queries are proven needed.

### 3.4. Event-Driven Architecture Starts with Domain Events

- **Current:** No real consumers for events.
- **Trigger:** When indexing, notification, analytics, recommendation, or any real consumer is proven needed.

### 3.5. Saga and Event Sourcing Are Not Defaults

- **Current:** `DocumentAuditLog` is an append-only audit log, not Event Sourcing.
- **Trigger for Saga:** When a business transaction spans multiple independent services and datastores.
- **Trigger for Event Sourcing:** When reconstructing state from event history is a real domain requirement.

### 3.6. Anti-Corruption Layer (ACL) for External Services

- **Current:** No external dependencies.
- **Trigger:** When VORNEQ connects to external identity providers, payment, LLM providers, third-party knowledge sources, or remote storage.

---

## 4. Target Architecture

```text
Experience (Homepage, Profile, Launcher, Workspace)
│
▼
Platform Shell (Registry, Manifest, Discovery, Capability Bus)
│
▼
Domain Apps (Documents, Notes, Marketplace)
│
▼
Core Contracts (Identity, Artifact, Entitlement, Evidence, Verification, Reputation)
│
▼
Persistence / Infrastructure (PostgreSQL, Redis, S3)  ← Implementation Choices
│
├──► Adapters / ACL ──► External Systems (future)
├──► Domain Events ──► Async Infrastructure (when needed)
└──► Observability / Audit / Security ──► cross-cutting but contract-bounded
```

---

## 5. Current Implementation Status

| Principle | Current Status | Next Action |
| :--- | :--- | :--- |
| Modular boundaries | ✅ Core, Platform Shell, Apps | Maintain domain boundaries |
| Resilience | ✅ No external dependencies | Add ACL + resilience when connecting to external services |
| CQRS lightweight | ✅ Natural read/write separation | Add separate read model if proven needed |
| Event-Driven | ❌ No real consumers | Only when proven needed |
| Saga / Event Sourcing | ❌ Not used | Only when real problem exists |
| ACL | ❌ No external dependencies | First step when connecting to external services |

---

## 6. Next Steps

| Priority | Step | Description | Status |
| :---: | :--- | :--- | :---: |
| **1** | **Workspace UI** | Documents UI + Platform registration | ✅ Done (PR #176) |
| **2** | **Personal Home Integration** | Recent Documents & Recently Viewed | 🔜 Next |
| **3** | **Retention & Deletion Policy** | Physical erase based on retention policy | 🔜 Next |
| **4** | **Domain Events (optional)** | Only if real consumer emerges | 🔜 Optional |
| **5** | **ACL for External Services** | Only when connecting to external services | 🔜 Optional |

---

## 7. References

- [Platform Contract v0.1](platform-contract.md)
- [User Experience Layers](user-experience-layers.md)
- [User Control Principles](../product/user-control-principles.md)
- [Trust, Safety & Compliance Baseline](../compliance/eu-germany-trust-safety-compliance-baseline.md)
- [Azure Architecture Center — Cloud Design Patterns](https://learn.microsoft.com/azure/architecture/patterns)

---

**Status:** Proposed  
**Next Steps:** Register as a docs-only PR from the current `main` baseline.
