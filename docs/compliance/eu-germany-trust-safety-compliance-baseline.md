# VORNEQ Trust, Safety & Compliance Baseline (EU/Germany)

**Status:** Proposed / Legal Review Required — Architecture Ready  
**Version:** v0.2  
**Related:** User Experience Layers (Proposed), User Control Principles (Proposed), Platform Contract v0.1

---

## 1. Purpose & Status

This document establishes the compliance architecture for VORNEQ. It translates applicable EU and German legal requirements into architectural constraints, data-model decisions, and product-surface requirements that must be validated by legal counsel before production release.

**Status:** Proposed / Legal Review Required — Architecture Ready

> **Important:** This document does not claim that VORNEQ is compliant. It defines questions, boundaries, and design decisions that require legal review.

---

## 2. Compliance Matrix

| Area | VORNEQ Architectural Question | Design Status / Decision | Classification |
| --- | --- | --- | --- |
| GDPR / BDSG | What data, for what purpose, under what legal basis? | Data inventory + purpose/legal-basis mapping required | Legal Review Required |
| GDPR Art. 17 | How is deletion handled for personal data vs. reference data? | Export before deletion; content ≠ reference (tombstone) | Proposed |
| GDPR Art. 20 | What is the scope of data portability vs. product export? | Product export commitment ≠ GDPR Art. 20 right | Proposed |
| DSA / DDG | What type of intermediary service is VORNEQ? | Service classification pending | Legal Review Required |
| DSA Art. 16 | How is illegal content reported and acted upon? | Notice/action + audit trail required for hosting services | Classification-Dependent |
| DSA Art. 20 | How are complaints handled? | Internal complaint-handling system required for online platforms | Classification-Dependent |
| UrhDaG | Is VORNEQ an OCSSP under §2 UrhDaG? | Classification depends on service design | Potentially Applicable |
| EU AI Act | Where is AI used, and what is VORNEQ's role? | AI system inventory + risk/transparency classification | Potentially Applicable |
| AI Act Art. 50 | How are AI interactions and AI-generated content disclosed? | Transparency obligations apply from 2 August 2026 where Art. 50 applies | Applicable / Use-Case Dependent |
| DDG §5 | Where is legal information (Impressum) provided? | Legal/Impressum surface required when applicable | Product Requirement / Applicability Review |
| NIS2 / German implementation | What security incident management is required? | Incident-response architecture required; entity/service classification pending | Potentially Applicable |
| Data Transfers | Which processors are outside the EEA? | Processor/subprocessor registry required | Legal Review Required |
| User Control | What happens to content when a user account is deleted? | Content deletion ≠ reference deletion (tombstone) | Proposed |

### Classification Legend

- **Legal Review Required** — Must be validated by legal counsel before implementation or production reliance.
- **Classification-Dependent** — Obligation depends on service classification (for example, hosting service vs. online platform).
- **Potentially Applicable / Proposed** — Design direction exists; applicability or implementation requires validation.
- **Product Requirement** — VORNEQ product policy or launch requirement; not necessarily a standalone statutory obligation.
- **Not Yet Applicable** — Not applicable at the current stage, subject to reassessment as the service changes.

---

## 3. Key Legal Frameworks — Summary for Architects

### 3.1. GDPR — Data Protection & User Rights

#### Key Architectural Implications

- Every processing activity must have a documented purpose and applicable legal basis.
- The right to erasure under Art. 17 is not absolute and is subject to statutory conditions and exceptions.
- The right to data portability under Art. 20 is not a general right to all platform data; its statutory scope is narrower than VORNEQ's product export commitment.
- VORNEQ must distinguish product-level export promises from statutory data-subject rights.

#### Design Direction

- User-controlled data should be exportable before account deletion according to the VORNEQ product policy.
- After deletion, personal data is processed according to an applicable retention/deletion policy.
- Content deletion does not automatically imply reference deletion; any retained tombstone must itself satisfy applicable data-protection and other legal requirements.

### 3.2. DSA / DDG — Digital Services Act

The applicable DSA obligations depend on the classification of the service and, for some obligations, its size and role.

#### Key Distinction

- **Art. 16 — Notice and Action:** applies to hosting services within its scope and requires mechanisms for notices concerning allegedly illegal content.
- **Art. 20 — Internal Complaint Handling:** applies to online platforms within its scope and concerns complaints about specified platform decisions.

Obligation levels vary by service type and size. VLOP/VLOSE designation is tied to the DSA threshold and designation process, including the 45 million average monthly active recipients threshold in the Union.

#### Architectural Approach

- DSA obligations are implemented as capabilities activated by service classification and legal applicability.
- Base concepts such as `NoticeCase`, `ModerationDecision`, and auditability should be designed generically.
- An `AppealCase` or equivalent complaint-handling capability is activated where the applicable classification and legal requirements require it.

#### Design Direction

- Before enabling public user-content hosting, determine whether the relevant VORNEQ service is a hosting service and which DSA obligations apply.
- Implement notice-and-action where required.
- Implement internal complaint handling where required for an online platform.
- Service classification must be validated with legal counsel.

### 3.3. UrhDaG — Copyright Content Sharing

The German Urheberrechts-Diensteanbieter-Gesetz implements the copyright regime for qualifying online content-sharing service providers.

Whether VORNEQ qualifies is a classification question that depends on the statutory criteria, service design, business model, and actual operation. Not every service that permits file uploads is an OCSSP.

#### Design Direction

- Determine legal classification before relying on a public-upload product model.
- If VORNEQ falls within UrhDaG, implement the obligations applicable to that classification, including licensing-related requirements where applicable.

### 3.4. EU AI Act — Artificial Intelligence

The AI Act's general application date includes 2 August 2026, subject to its phased application rules and specific provisions. Article 50 transparency requirements must be assessed for each relevant AI system and use case.

#### Architectural Implication for VORNEQ

Where VORNEQ uses AI for recommendations, ranking, knowledge extraction, content generation, or conversational interfaces, provenance and transparency should be treated as data concerns rather than UI-only concerns.

#### Design Direction

- Maintain an AI system inventory covering system purpose, role, provider/deployer relationship, and applicable classification.
- Store appropriate provenance metadata for AI-generated or AI-assisted content where relevant.
- Store transparency signals needed to support applicable disclosures.
- Validate specific AI Act obligations per use case with legal counsel.

### 3.5. DDG §5 — Legal Provider Information

Where DDG §5 applies, the required provider information must be easily, directly, and permanently accessible according to the statutory requirements.

#### Design Direction

The Legal Surface must support an Impressum/provider-information surface from launch where applicable.

### 3.6. NIS2 / German Cybersecurity Framework

Cybersecurity obligations depend on the applicable German implementation, entity category, service type, and size thresholds or other statutory criteria.

#### Design Direction

- Design incident-response capabilities before production release.
- Determine VORNEQ's entity/service classification and resulting obligations with legal counsel/security specialists.
- Keep the compliance baseline synchronized with the current German cybersecurity framework.

---

## 4. Trust, Safety & Compliance — Architectural Principles

### 4.1. Data Inventory & Purpose Mapping

Every data-processing activity should be represented in a maintained inventory containing at least:

- data/category collected or generated;
- processing purpose;
- applicable legal basis where required;
- retention policy;
- deletion or anonymization mechanism;
- relevant processors/subprocessors and transfer context where applicable.

**Status:** Legal Review Required — the inventory must be completed and reviewed before production processing that relies on it.

### 4.2. Content Deletion ≠ Reference Deletion

Deleting content and preserving knowledge-graph integrity are separate concerns.

VORNEQ should be capable of removing content where required while preserving only the minimum lawful reference/provenance structure needed to avoid unnecessary graph breakage.

This supports VORNEQ's core philosophy: preserving context and inspectability without claiming permanent ownership over data or truth.

#### Design Direction

- Separate Artifact content from reference/provenance relationships at the architectural level.
- A deletion workflow may replace content with a tombstone where retention of that reference is lawful and justified.
- Tombstones must be data-minimized and must not be assumed to be automatically free of personal data or copyright concerns; their exact fields require policy and legal review.

### 4.3. Export Commitment vs. GDPR Art. 20

- **GDPR Art. 20:** a statutory portability right with defined conditions and scope.
- **VORNEQ Product Export:** a broader product commitment that may cover user-controlled Artifacts, Notes, profile data, preferences, or other product-defined data.

#### Design Direction

- Product export is a product commitment.
- GDPR portability handling is a legal capability where its statutory conditions are met.
- They may share infrastructure but must remain conceptually and policy-wise distinct.

### 4.4. AI Transparency & Provenance as Data

**Principle:** Where AI is used, transparency should be supported by the data model rather than implemented only as UI copy.

VORNEQ adopts explanation metadata for ranking and recommendations as a product and trust-architecture principle. Specific legal transparency obligations depend on the AI system, use case, provider/deployer role, and applicable AI Act provision.

#### Design Direction

- Search/recommendation architecture should be able to produce explanation signals or metadata where appropriate.
- Maintain an AI system inventory.
- Determine legal risk and transparency classification per use case.
- Avoid treating every ranking or recommendation explanation as a direct requirement of AI Act Art. 50.

### 4.5. Notice-and-Action System

Where DSA Art. 16 applies, VORNEQ must support the legally required notice-and-action workflow.

#### Design Direction

- Provide an electronic reporting mechanism where required.
- Record moderation decisions and required communications.
- Produce auditable events for moderation actions.
- Activate internal complaint handling where DSA Art. 20 applies to the service.

### 4.6. Compliance by Design

**Principle:** Legal and trust requirements should be represented as explicit system capabilities and policies rather than scattered conditional logic across applications.

Documents, Notes, Profile, Marketplace, and future apps should consume shared compliance capabilities instead of independently implementing deletion, moderation, export, or transparency behavior.

#### Conceptual Primitives

These are **Proposed** concepts and are not additions to Platform Contract v0.1:

```text
Artifact
   ├── Provenance
   ├── RetentionPolicy
   ├── ModerationCase
   ├── Tombstone
   └── ExportDescriptor

Identity
   ├── ConsentRecord
   ├── DataSubjectRequest
   └── AccountDeletionRequest

AI Operation
   ├── Provenance
   ├── TransparencySignal
   └── ExplanationMetadata
```

#### AuditEvent as Spine

The existing VORNEQ `AuditEvent` concept should serve as the audit backbone for this layer rather than introducing a separate compliance logging system. Moderation, export, deletion, consent, and other sensitive changes can produce audit events according to applicable policy.

Retention, access control, integrity, and deletion rules for audit data require their own policy and legal review.

---

## 5. Legal Surface Requirements

| Component | Basis | Status |
| --- | --- | --- |
| Impressum / Provider Information | DDG §5 | Required if applicable |
| Privacy Information | GDPR Arts. 13–14 | Required when applicable processing occurs |
| Terms / Contract Information | BGB / EGBGB | Contract-model dependent |
| Consent / Device Storage | TDDDG §25 + GDPR | Required where applicable |
| Data Subject Request Capability | GDPR | Legal requirement where applicable |
| Self-service Account Deletion | VORNEQ product policy | Product requirement |
| Product Data Export | VORNEQ product policy | Product requirement |
| GDPR Portability Handling | GDPR Art. 20 | Legal requirement where conditions are met |
| Notice-and-Action | DSA Art. 16 | Classification-dependent |
| Complaint Handling | DSA Art. 20 | Classification-dependent |

---

## 6. Next Steps

| Step | Action | Owner |
| --- | --- | --- |
| 1 | Complete data inventory and purpose/legal-basis mapping | Engineering + Legal |
| 2 | Determine DSA service classification and applicable obligations | Legal |
| 3 | Determine UrhDaG classification | Legal |
| 4 | Design notice-and-action capability if applicable | Engineering |
| 5 | Design internal complaint-handling capability if applicable | Engineering |
| 6 | Design AI system inventory and provenance/transparency data model | Engineering |
| 7 | Define retention/deletion and data-subject-request policies | Engineering + Legal |
| 8 | Draft/review Privacy Information, contractual information, and Impressum as applicable | Legal |
| 9 | Validate architecture and product decisions with qualified legal counsel | Legal |

---

## 7. References

Primary legal texts should be used for legal review and kept current:

- GDPR — Regulation (EU) 2016/679
- DSA — Regulation (EU) 2022/2065
- DDG — Digitale-Dienste-Gesetz (Germany)
- TDDDG — Telekommunikation-Digitale-Dienste-Datenschutz-Gesetz (Germany)
- UrhDaG — Urheberrechts-Diensteanbieter-Gesetz (Germany)
- EU AI Act — Regulation (EU) 2024/1689
- NIS2 — Directive (EU) 2022/2555 and applicable German implementing legislation
- BGB / EGBGB — applicable German contract and consumer-information provisions

---

**Status:** Proposed / Legal Review Required — Architecture Ready  
**Last Updated:** 2026-09-07
