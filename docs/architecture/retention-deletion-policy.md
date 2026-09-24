# Retention & Deletion Policy — VORNEQ

**Status:** Proposed  
**Version:** v0.1  
**Related:** User Control Principles, Trust Safety & Compliance Baseline, Platform Contract v0.1

---

## 1. Purpose

This document defines the **data lifecycle semantics** for VORNEQ, including deactivation, retention, legal holds, deletion, and erasure. It is a **policy-level proposal** and does not introduce immediate code changes.

> **Core Principle:**  
> **Content Deletion ≠ Reference Deletion.**  
> The system must be able to remove content when legally required, while preserving reference/provenance structure only where lawful and justified.

---

## 2. Lifecycle States

The lifecycle of a Document (and, by extension, other domain objects) is defined by the following states:

| State | Description | Visibility |
| :--- | :--- | :--- |
| **ACTIVE** | Normal operation. Visible in UI, Search, Workspace. | ✅ Visible |
| **DEACTIVATED** | Soft-deactivated. Hidden from UI/Search. Content remains in database. | ❌ Hidden |
| **PENDING_DELETION** | Accepted deletion/erasure request awaiting policy conditions (e.g., retention period, hold). | ❌ Hidden |
| **ERASED** | Physically erased from database. Only a minimal tombstone remains (where lawful and justified). | ❌ Hidden (reference only) |

> **Important:** `ERASED` is an **outcome**, not a stored state on the Document record. After erasure, the Document record itself no longer exists.

---

## 3. Retention & Holds

### 3.1. Retention Period

- Each domain object has a **retention period** (e.g., 30 days for illustrative purposes, but **not hard-coded** in v0.1).
- The retention period is **policy-driven** and subject to legal/regulatory review.
- The policy determines the time between `DEACTIVATED` / `PENDING_DELETION` and `ERASED`.

### 3.2. Legal / Security Hold

- A **Hold** is a mechanism to temporarily prevent erasure for legal, security, or investigative reasons.
- Hold is **independent** of lifecycle state:
  - A Document can be `PENDING_DELETION` and simultaneously under Hold.
  - Hold does not change the lifecycle state; it only blocks the erasure workflow.
- Hold must include:
  - `reason` (legal/security/investigation)
  - `scope` (which objects are affected)
  - `placed_at` (timestamp)
  - `released_at` (timestamp when lifted)
  - `actor` / `authority` (who placed the hold)

---

## 4. Erasure Workflow (Conceptual)

```text
1. Authorization check → authorized actor according to domain policy and applicable legal process
2. Policy check → retention period expired? Hold active?
3. Content removal → erase domain-owned data
4. Anonymization / Pseudonymization → remove personal identifiers
5. Artifact handling → deactivate or tombstone based on policy
6. Tombstone creation → minimal reference (only if lawful and justified)
7. Audit correlation → preserve reference without personal data
```

**Key Invariants:**
- Erasure should preserve graph/reference integrity only to the minimum extent lawfully justified.
- Platform-maintained metadata may remain only where its retention is independently justified, lawful, and data-minimized.
- Erasure must be **auditable** and **logged** (even for the erased object).

---

## 5. Audit & Provenance Implications

### 5.1. DocumentAuditLog (Current State — Confirmed by Live Review)

- `DocumentAuditLog.document` → currently `PROTECT`. To enable erasure, a migration to `SET_NULL` + a stable, non-sensitive correlation identifier will be required.
- `actor_identity` → `SET_NULL` + pseudonymization of metadata (e.g., `target_identity` in share/revoke events).
- **Append-only does not mean retain forever.** Immutability during retention must be distinguished from eventual lawful deletion/anonymization.

### 5.2. Shared AuditEvent (Core)

- Currently Experimental and limited to `verification.*` events.
- This policy **does not** propose to replace `DocumentAuditLog` with `AuditEvent` immediately.
- A future direction may align domain audit with Core AuditEvent, but only when the Core AuditEvent schema and taxonomy are stabilized.

---

## 6. Cross-Domain Implications

The policy defined here applies to **all domain objects** (Documents, Notes, Evidence, Verification, Reputation), not only Documents.

| Model | Current Status | Proposed Direction |
| :--- | :--- | :--- |
| **Documents** (confirmed) | `DocumentAuditLog.document` = `PROTECT`; `DocumentAccess.document` = `CASCADE`; Document itself soft-delete only | Erasure workflow + tombstone; audit FK → `SET_NULL` + correlation ID |
| **Other domains (Evidence, Verification, ArtifactBinding, Identity, etc.)** | Not yet reviewed in detail | **Requires domain-specific retention review** before any migration or implementation |

> **Important:** Core has multiple immutable/append-only models and `PROTECT` relationships. A single erasure policy should not impose uniform semantics across all domains without domain-specific review.

---

## 7. Export-Before-Deletion

- **Product Export Commitment:** Users can export their data before deletion.
- **Legal Right to Erasure:** GDPR Art. 17 provides a right to erasure, but **not absolute**.
- **Distinction:** Product export is a **product promise**, not a legal precondition for deletion.

---

## 8. Next Steps

| Phase | Action |
| :--- | :--- |
| **1** | Accept this policy (Proposed → Reviewed) |
| **2** | Legal review of retention period and tombstone rules |
| **3** | Domain-specific retention review for Evidence, Verification, ArtifactBinding, Identity |
| **4** | Design migration plan (FK changes, tombstone model) |
| **5** | Implement erasure workflow (no code changes yet) |
| **6** | Validate with Documents domain first |
| **7** | Extend to other domains after domain-specific review |

---

## 9. References

- [User Control Principles](../product/user-control-principles.md)
- [Trust Safety & Compliance Baseline](../compliance/eu-germany-trust-safety-compliance-baseline.md)
- [Platform Contract v0.1](platform-contract.md)

---

**Status:** Proposed  
**Next Steps:** Legal review, domain-specific retention review, then migration/implementation planning.
