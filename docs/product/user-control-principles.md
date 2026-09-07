# User Control & Ownership Principles

**Status:** Proposed  
**Version:** v0.1  
**Related:** User Experience Layers (Proposed), Platform Contract v0.1

---

## 1. Purpose

This document defines the principles governing user control, data ownership boundaries, portability, deletion, and algorithmic transparency in VORNEQ. It establishes reusable product and architecture rules for Documents, Notes, Profile, Reputation, Personal Home, and future capabilities.

These principles distinguish:

- data controlled by the user;
- portable preferences;
- platform-maintained metadata;
- product export commitments;
- the effect of account deletion on shared or cited Artifacts;
- the scope and limits of algorithmic transparency.

This document is **Proposed** and does not modify Platform Contract v0.1.

---

## 2. Core Principles

### 2.1. User-Controlled Data

The following categories are treated as user-controlled product data, subject to applicable law, shared-resource semantics, and platform policy:

- Artifacts created by the user, including Documents and Notes;
- personal profile information;
- preferences and workspace configuration;
- user-initiated activity data where exposed as part of the product;
- private notes and drafts.

**User-controlled data should be exportable before account deletion according to the VORNEQ product export policy. After deletion, data is processed according to the applicable retention and deletion policy.**

The exact legal meaning of ownership may vary by data category and jurisdiction; this document defines product-control boundaries rather than making a universal legal ownership claim.

### 2.2. Portable Preferences

Preferences should be portable across devices and associated with a stable user or workspace identity rather than a specific device.

Examples include:

- theme and language;
- notification settings;
- workspace layout and configuration;
- dashboard widget placement.

Portability inside the product does not by itself define the external export format. Export formats and compatibility guarantees are specified separately.

### 2.3. Platform-Maintained Metadata

The following categories may be maintained by the platform rather than treated as exclusively user-controlled content:

- aggregated usage statistics, such as view counts;
- system-generated relationships, including citations and references;
- security and audit records;
- system integrity and operational metadata.

**Platform-maintained metadata may persist after account deletion where retention is justified and lawful. Content persistence and reference persistence are separate concerns.**

### 2.4. Export Meaning & Scope

VORNEQ adopts product export as a user-control commitment. This product commitment is distinct from statutory data-portability rights such as GDPR Art. 20.

Initial product-export scope may include:

- user-created Artifacts and their product metadata;
- personal profile data;
- private Notes and drafts.

Future scope may include:

- preferences and settings;
- activity history where appropriate;
- followed items and Collections.

> **Note:** Exact export format, scope, retention behavior, and compatibility guarantees are not contracted in this document and will be defined in a future iteration.

### 2.5. Account Deletion & Shared/Cited Artifacts

When a user deletes their account, VORNEQ must distinguish between account identity, content, and graph references.

- User-controlled personal data is removed, anonymized, retained, or otherwise processed according to the applicable deletion/retention policy.
- Shared or cited Artifacts require a separate content-persistence decision:
  - content may be removed or anonymized where required by law, privacy, product policy, or a valid deletion request;
  - a minimal tombstone or persistent reference may remain where lawful and necessary to preserve citation/provenance integrity.
- Platform-maintained relationships or aggregate metadata may remain where justified and lawful.

A tombstone must not be assumed to be free of personal data or copyright concerns merely because the original content was removed. Its fields and retention policy require separate review.

> **Important:** Users should be informed of material deletion effects before account deletion is confirmed.

### 2.6. Algorithmic Transparency

VORNEQ treats algorithmic transparency as a product and trust-architecture principle.

- Ranking and recommendation systems should be able to produce an **explanation signal or metadata** appropriate to the decision.
- Users should receive meaningful explanations for automated experiences where product policy or applicable law requires them.
- Deterministic recommendations should expose understandable reasons when practical, such as recency, followed items, or explicit user filters.
- Exact explanation APIs and schemas will be defined during Search/Recommendation capability design.

This principle does not imply that every result or ranking requires the same explanation mechanism, nor that a specific machine-learning explanation technique is mandated.

---

## 3. Implementation Guidelines

### 3.1. Data Control in Code

- Artifacts should carry stable creator/ownership relationships where applicable, without inferring verified Identity from free-text author or creator fields.
- Export operations must enforce authorization and include only data within the requesting user's applicable export scope.
- Account deletion must use a defined workflow rather than ad hoc cascading deletion across applications.
- Shared/cited Artifact handling must distinguish content removal from reference removal.
- Retention decisions should be policy-driven and auditable where appropriate.

### 3.2. Transparency & Explanation

- Search and recommendation architecture should support explanation metadata without coupling UI copy directly to ranking internals.
- Explanation data must not expose secrets, sensitive information, security controls, or other users' private data.
- Complex model-specific explanation mechanisms may evolve independently from the stable product principle.

### 3.3. Shared Platform Capabilities

Documents, Notes, Profile, Marketplace, and future apps should not independently redefine export, deletion, identity, or transparency semantics. Shared platform capabilities and policies should be preferred where those concerns cross application boundaries.

---

## 4. Relation to Other Documents

- **User Experience Layers:** defines where public, personal, and workspace experiences are separated and where preferences apply.
- **Trust, Safety & Compliance Baseline:** constrains deletion, export, retention, moderation, AI transparency, and other compliance-sensitive behavior.
- **Platform Contract v0.1:** remains unchanged; stable primitives discovered through implementation may be considered for a future v0.2.

---

## 5. Next Steps

1. Validate these principles in the Knowledge/Documents Workspace design.
2. Align deletion, export, and reference-preservation flows with the EU/Germany Trust, Safety & Compliance Baseline.
3. Define shared product policies for retention and export without prematurely freezing transport formats.
4. Consider promotion of stable, reusable primitives only after implementation and validation.

---

**Refs:** User Experience Layers (Proposed), Platform Contract v0.1, #139
