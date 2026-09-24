# VORNEQ Platform Layers

**Status:** Proposed  
**Version:** v0.1  
**Related:** Platform Contract v0.1, Architecture Scaling Principles, Search Evolution Principles

---

## 1. Purpose

This document defines the **layered architecture of VORNEQ**, separating **core contracts**, **platform shell**, **experience**, **integration**, **data/retrieval**, **security/trust/compliance**, **operations**, and **ecosystem**.

> **Core Principle:**  
> **Shared infrastructure does not imply shared domain ownership.**  
> - Search can be shared infrastructure but **is not the owner of data**.  
> - Workspace can be a composition layer but **does not own authorization**.  
> - API Gateway (if added) **does not replace domain policy**.

---

## 2. Architecture Layers

### 2.1. Core Contracts

The stable, contract‑governed primitives of VORNEQ.

| Component | Responsibility |
| :--- | :--- |
| **Identity** | User, organization, and service identity |
| **Artifact** | Digital asset with provenance and discoverability |
| **Evidence / Verification** | Verifiable evidence and state‑machine verification |
| **Contextual Reputation** | Context‑bound reputation (not global trust) |
| **Shared Contract Invariants** | Cross‑cutting rules (e.g., Search ≠ Verification, Identity ≠ Authorization) |

> **Owner:** Core Domain  
> **Boundary:** All Apps consume these contracts; none may bypass them.

---

### 2.2. Platform Shell

The infrastructure for App discovery, installation, and composition.

| Component | Responsibility |
| :--- | :--- |
| **Registry / Manifest** | App registration and discovery |
| **Discovery** | Capability discovery (descriptive strings) |
| **Launcher / Workspace Composition** | App launcher and workspace composition surface |
| **Capability Contracts** | Executable capabilities (v2) — **only as maturity justifies** |

> **Owner:** Platform Shell  
> **Boundary:** Launcher and Workspace are composition layers; they **do not** own authorization or domain data.

---

### 2.3. Experience & Access

The user‑facing layers of VORNEQ.

| Component | Responsibility |
| :--- | :--- |
| **Public Experience** | Homepage, public Artifact/Profile pages |
| **Personal Home** | User‑specific dashboard (recent activity, notifications) |
| **Workspace** | Deep work environment for Apps |

> **Owner:** Experience Layer  
> **Boundary:** Personal Home and Workspace are **presentation** layers; they **do not** own authorization or domain data.

---

### 2.4. Integration

Connecting VORNEQ to the outside world and between Apps.

| Component | Responsibility |
| :--- | :--- |
| **Public APIs** | Versioned, stable APIs for external consumers |
| **External Adapters / ACL** | Translation of external models to VORNEQ domain |
| **Webhooks** | Event delivery to external systems |
| **Domain Events / Async Delivery** | Event‑driven communication **only when justified** |

> **Owner:** Integration Layer  
> **Boundary:** Adapters/ACL prevent external models from polluting the domain.

---

### 2.5. Data & Retrieval

Storage, search, and retrieval capabilities.

| Component | Responsibility |
| :--- | :--- |
| **Domain‑owned Persistence** | PostgreSQL (current implementation) |
| **Unified Search** | Retrieval across domains (current: PostgreSQL) |
| **Object / File Storage** | S3/R2 (current implementation) |
| **Analytics / Recommendation** | **Only when justified** |

> **Owner:** Data Layer  
> **Boundary:** Search is a retrieval service; it **does not** own canonical domain data.

---

### 2.6. Security, Trust & Compliance

Identity, authorization, audit, and legal compliance.

| Component | Responsibility |
| :--- | :--- |
| **Authentication & Identity Resolution** | Resolve authenticated user to Identity |
| **Domain‑owned Authorization** | Each App owns its authorization policy |
| **Audit / Provenance** | Append‑only audit log and provenance tracking |
| **Cryptography / Key Management** | Encryption at‑rest and in‑transit |
| **Privacy / Compliance** | GDPR, DSA, AI Act, UrhDaG |

> **Owner:** Security Layer  
> **Boundary:** Authentication does **not** imply authorization; authorization remains domain‑owned.

---

### 2.7. Operations

Running, scaling, and maintaining the platform.

| Component | Responsibility |
| :--- | :--- |
| **CI/CD** | Continuous integration and deployment |
| **Backup / Recovery** | Disaster recovery and data restoration |
| **Observability** | Monitoring, logging, and tracing |
| **Scaling Infrastructure** | **Only when workload requires it** |

> **Owner:** Operations  
> **Boundary:** Infrastructure choices are implementation‑specific and not part of core contracts.

---

### 2.8. Ecosystem

Developer and partner engagement.

| Component | Responsibility |
| :--- | :--- |
| **Marketplace** | Distribution of Apps and digital products |
| **Developer APIs** | Stable APIs for third‑party developers |
| **Developer Portal** | Documentation, SDKs, and tools |
| **Partner / Third‑party Integrations** | External service connections (future) |

> **Owner:** Ecosystem  
> **Boundary:** Developer APIs follow the same contract rules as internal APIs.

---

## 3. Implementation Choices (Not Contracts)

The following are **current implementation choices**, not architectural contracts:

| Choice | Purpose |
| :--- | :--- |
| **PostgreSQL** | Primary relational database |
| **Redis** | Caching and session storage |
| **S3/R2** | Object/file storage |
| **Prometheus** | Metrics collection |
| **GitHub Actions** | CI/CD pipeline |

> **Note:** These choices may evolve over time. They are not part of the core contract.

---

## 4. Status of Key Components

| Component | Status | Notes |
| :--- | :---: | :--- |
| **Identity, Artifact, Evidence, Verification** | ✅ Stable | Core contracts |
| **Contextual Reputation** | ✅ Stable | Core contracts |
| **Registry / Manifest** | ✅ Stable | Platform Shell |
| **Launcher / Workspace** | ✅ Stable | Experience Layer |
| **Unified Search (PostgreSQL)** | ✅ Stable | Retrieval layer |
| **Capability Bus v2** | 🧪 Experimental | Only when justified |
| **Personal Home** | 🔜 Next | In development |
| **Retention & Deletion Policy** | 🔜 Next | Under design |
| **Search Measurement / Ranking** | 🔜 Future | After SLO baseline |
| **External Adapters / ACL** | 🔜 Future | Only when external services connect |
| **Kubernetes / CDN / Event Streaming** | 🔜 Future | Only when workload requires |

---

## 5. Next Steps (Ordered by Proven Need)

| Priority | Step | Description |
| :---: | :--- | :--- |
| **1** | **Personal Home Integration** | Recent Documents & Recently Viewed |
| **2** | **Retention & Deletion Policy** | Physical erase based on retention policy |
| **3** | **Search Measurement / Ranking Evolution** | SLO baseline, ranking improvements |
| **4** | **External Integration / ACL** | Only when a real external service connects |
| **5** | **Capability Bus PoC** | Only when a real consumer emerges |

---

## 6. References

- [Platform Contract v0.1](platform-contract.md)
- [Architecture Scaling Principles](scaling-principles.md)
- [Search Evolution Principles](search-evolution-principles.md)
- [User Experience Layers](user-experience-layers.md)

---

**Status:** Proposed  
**Next Steps:** Register as a docs‑only PR from current `main` (SHA to be confirmed live before branch creation).

---
