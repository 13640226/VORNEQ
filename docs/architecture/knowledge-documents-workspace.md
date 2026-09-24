# Knowledge / Documents Workspace

**Status:** Proposed / Ready for Validation  
**Version:** v0.1  
**Related:** Platform Contract v0.1, User Experience Layers, User Control & Ownership Principles, EU/Germany Trust, Safety & Compliance Baseline

## 1. Purpose

This document defines the specification-level architecture for the Knowledge / Documents Workspace vertical in VORNEQ.

The goal of this vertical is to validate existing platform boundaries through a concrete Documents domain without modifying Platform Contract v0.1. It deliberately distinguishes current repository capabilities from implementation changes that require separate review.

The Workspace is a composition context. Documents remains the owner of document state, authorization, lifecycle, and domain behavior.

## 2. Architecture Boundaries

### 2.1. Experience Boundary

The Documents vertical follows the three-layer experience model:

- **Public Experience:** public discovery and public document representations where explicitly published.
- **Personal Home:** recent document activity and deterministic shortcuts into Documents.
- **Workspace:** deep document work, including creation, editing, organization, sharing, and review.

The public Homepage does not become a personal dashboard, and Workspace does not become the owner of Documents domain state.

### 2.2. Core Primitives Used

| Primitive | Status | Role in Documents Workspace |
| :--- | :---: | :--- |
| `Identity` | Stable | Canonical trust-actor identity; authenticated-user-to-Identity resolution is a validation boundary |
| `Artifact` | Stable | Shared representation for discovery, provenance, and reference. Adding `kind="document"` is a separately reviewed Core extension required for implementation |
| `ArtifactBinding` | Stable | Documents intends to use the stable binding pattern. Supporting `documents.Document` requires a separately reviewed extension of the current allowed-target configuration |
| `Evidence` | Stable | Supporting material for document verification where applicable |
| `Verification` | Stable | Review and verification workflows where applicable |
| `Contextual Reputation` | Stable | Contextual contributor/reviewer reputation where applicable |
| `Search` | Stable | Existing unified retrieval is a platform input. Documents first designs an authorization-safe, domain-owned retrieval adapter strategy; private Documents integration with `UnifiedSearch` is not yet decided |
| `Entitlement` | Experimental | May be consulted where applicable; it is not the Documents permission system |
| `AuditEvent` | Experimental | Current audit taxonomy is limited. Documents uses a domain audit log initially and may propose taxonomy extensions separately |
| `Capability` (v2) | Experimental | Candidate executable capabilities for narrow validation, such as document preview/search, subject to separate implementation review |

Status labels above describe the relevant Platform Contract/repository maturity and do not promote any Proposed or Experimental primitive.

## 3. Domain Model

### 3.1. Document

`Document` is a domain-specific model owned by the Documents App.

It owns document-specific state such as title, content, tags, creator/owner reference, creation/update timestamps, and active/deactivated lifecycle state.

Each Document may have a corresponding `Artifact` representation for discovery, provenance, and reference.

Adding `kind="document"` to `Artifact` and supporting `documents.Document` in `ArtifactBinding` are separate, reviewed Core changes required for implementation. This specification does not make those changes.

### 3.2. Identity Resolution

Authentication identity and canonical trust identity are distinct concerns.

The Documents vertical must validate the boundary between the authenticated Django user and canonical `Identity`, including use of the existing `UserIdentity` binding where appropriate. Domain ownership and authorization must not depend on inferring identity from free-text fields.

### 3.3. Domain Authorization

Authorization is domain-owned.

Documents implements and validates its own authorization policy. The initial conceptual roles are Owner (full read/write and sharing control), Editor (read/write access granted through a Documents-domain mechanism), and Viewer (read-only access granted through a Documents-domain mechanism). These roles describe required behavior, not a committed database schema.

`Entitlement` is not a generic permission system. It may be consulted only where an entitlement-specific use case exists.

**Boundary:** Search does not grant authorization. Workspace composition does not grant authorization. Artifact representation does not grant authorization.

### 3.4. Lifecycle and Deletion

Documents distinguishes lifecycle operations rather than treating all removal as the same action:

- **Deactivate:** hide a Document from active product surfaces while retaining its content according to policy.
- **Erase:** physically remove user-owned document content when the applicable deletion and retention policy permits or requires it.
- **Tombstone/reference preservation:** retain only a minimal, data-minimized reference where lawful and justified so shared citation/reference integrity can be preserved.

Content persistence and reference persistence are separate concerns. Tombstone fields, retention periods, and legal bases remain subject to the compliance baseline and policy/legal review.

## 4. Services

### 4.1. Document Service

The Documents domain requires service behavior for creating a Document and assigning its owner; retrieving/listing Documents subject to domain authorization; updating subject to write authorization; initiating deactivation and policy-governed erasure; sharing through domain-owned authorization mechanisms; and optionally creating or maintaining an Artifact representation once the required Core extensions are separately approved.

This section specifies behavior rather than repository APIs or method signatures.

### 4.2. Search Integration

Documents will design a **domain-owned, authorization-safe adapter strategy** for retrieval.

The existing `UnifiedSearch` is a public-content retrieval surface and does not by itself define private Documents authorization. Whether private Documents will be integrated directly into `UnifiedSearch` is a **separate, reviewed decision**.

Any Documents search path must preserve the boundary **Search ≠ Authorization**. A result may be returned only when the Documents-domain authorization policy permits the requesting user to discover/access it. Exact adapter APIs, filter grammar, indexing strategy, and private/public routing are implementation decisions to be validated separately.

### 4.3. Export Service

Export is produced from the **Documents domain**, not from Artifact as a substitute for domain content.

A Documents export may include domain-owned fields such as title, content, tags, and timestamps. If a corresponding Artifact representation exists, appropriate Artifact metadata and provenance may be included as supplementary information.

Export format and exact scope follow the User Control & Ownership Principles and remain separately versioned product decisions. Statutory portability obligations must not be conflated with the broader VORNEQ product export commitment.

### 4.4. Audit

Sensitive Documents operations require auditable behavior, but the existing shared `record_audit_event()` taxonomy is currently limited to approved event schemas.

Documents therefore begins with a **domain audit log** for Documents-specific sensitive operations. A shared `AuditEvent` taxonomy extension may be proposed separately after the required event names, metadata, retention classes, and privacy boundaries are validated.

The domain audit log must not silently invent shared `AuditEvent` event names.

## 5. Verification and Evidence

Documents may participate in Evidence and Verification flows when a document or a claim associated with it requires review.

Verification provides inspectable context/evidence rather than declaring intrinsic truth. Evidence and Verification remain platform/domain boundaries rather than being duplicated inside Workspace. Contextual reputation remains scoped to relevant role/domain/method rather than becoming a universal user score. Review/verification integration is validated incrementally and does not make every Document a verified Artifact by default.

## 6. Workspace UI

Workspace is a **composition context**. It does not own Documents, enforce authorization, or manage shared mutable Documents state.

- **Sidebar:** rendered by Documents App for document lists, filters, tags, and navigation.
- **Main Area:** rendered by Documents App for list, preview, and editor experiences.
- **Toolbar:** provided by Documents App for applicable actions such as search, create, delete/deactivate, and share.

Workspace-specific layout preferences belong to Workspace preferences; document state and permissions remain in Documents.

## 7. User Control, Privacy, and Compliance Boundaries

The Documents vertical is a validation target for the proposed User Control & Ownership Principles and EU/Germany Trust, Safety & Compliance baseline.

Implementation must explicitly validate ownership/export boundaries; account deletion effects on private, shared, and cited Documents; content erasure versus reference/tombstone preservation; retention and data minimization; authorization-safe discovery/sharing; auditable sensitive operations; provenance and AI/transparency metadata where an applicable automated feature is introduced; and authenticated-user-to-Identity resolution.

This architecture document does not itself claim legal compliance. Applicable behavior remains subject to product policy and qualified legal review.

## 8. Platform Contract Validation Matrix

| Primitive | v0.1 Status | Validation Goal | Outcome |
| :--- | :---: | :--- | :---: |
| `Identity` | Stable | Verify authorship/ownership boundary and authenticated user → Identity resolution | Pending |
| `Artifact` | Stable | Verify domain representation boundary; adding `kind="document"` is a separate Core extension | Pending |
| `ArtifactBinding` | Stable | Verify domain → Artifact binding pattern; supporting `documents.Document` requires separate review | Pending |
| `Evidence` | Stable | Verify integration with document evidence use cases | Pending |
| `Verification` | Stable | Verify review/verification integration without implying truth | Pending |
| `Contextual Reputation` | Stable | Verify contextual contributor/reviewer reputation | Pending |
| `Search` | Stable | Verify authorization-safe retrieval; private Documents adapter strategy is a separate decision | Pending |
| `Entitlement` | Experimental | Determine whether any Documents use case actually requires it | Pending |
| `AuditEvent` | Experimental | Identify required shared taxonomy extensions; domain audit log is used initially | Pending |
| `Capability` (v2) | Experimental | Validate narrowly scoped Documents capability PoCs if justified | Pending |

**Outcome of this vertical:** if validation succeeds, selected stable and reusable patterns may be proposed for Platform Contract v0.2. Platform Contract v0.1 remains unchanged.

## 9. Implementation Decision Queue

This docs PR intentionally does not implement the following changes. Each requires separate repository review:

1. Add a Document-specific `Artifact.Kind` value if implementation demonstrates that a dedicated kind is preferable to the current fallback.
2. Extend `ArtifactBinding` allowed targets to support the concrete Documents model.
3. Define the authorization-safe retrieval/search strategy for private and public Documents.
4. Define Documents-domain authorization persistence and sharing semantics.
5. Define the Documents domain audit taxonomy and decide which events, if any, should later graduate to shared `AuditEvent` schemas.
6. Validate authenticated-user-to-`Identity` resolution behavior.
7. Define retention, erasure, tombstone, and export implementation details against product and compliance requirements.
8. Validate whether executable Documents capabilities such as preview/search provide sufficient value to justify Capability Bus v2 integration.

## 10. Validation Plan

1. Establish the Documents domain and domain-owned authorization boundary.
2. Validate user/Identity ownership resolution.
3. Validate create/read/update/deactivate behavior without requiring Artifact integration.
4. Review and implement the minimum Artifact/ArtifactBinding extensions separately.
5. Validate authorization-safe retrieval before exposing private Documents through any shared search surface.
6. Add domain audit behavior for sensitive operations.
7. Validate export, erasure, retention, and reference-preservation behavior.
8. Integrate Evidence/Verification and executable capabilities only where a concrete use case justifies them.
9. Record validation outcomes and propose only demonstrated reusable patterns for Platform Contract v0.2.

## 11. Non-Goals

This specification does not modify Platform Contract v0.1; define unreviewed Core model migrations; treat `Entitlement` as Documents ACL; treat Workspace as the Documents domain owner; expose private Documents through public search by default; invent new shared `AuditEvent` schemas; guarantee content retention through tombstones; make every Document an Artifact or every Artifact verified; or prescribe machine-learning ranking/recommendation for the initial vertical.

## 12. References

- Platform Contract v0.1
- User Experience Layers & Personalization Boundaries
- User Control & Ownership Principles
- EU/Germany Trust, Safety & Compliance Baseline
- Existing `Artifact`, `ArtifactBinding`, `Identity`, and `UserIdentity` repository implementation
- Existing `UnifiedSearch` repository implementation
- Existing `AuditEvent` and `record_audit_event()` repository implementation

---

**Last Updated:** 2026-09-07
