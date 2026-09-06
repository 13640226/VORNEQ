# ADR 002: VORNEQ Verification and Evidence Architecture

**Status:** Proposed  
**Date:** 2026-09-06  
**Author:** VORNEQ Core Team

---

## 1. Context

ADR 001 established VORNEQ as trust infrastructure for the digital economy and defined the lifecycle:

```text
Discover → Verify → Transact → Deliver → Attest
```

The governing principle for Verify is:

> **Verification is evidence about a claim; it is not truth itself.**

Verification must preserve enough context to answer what was examined, which claim was evaluated, which method was used, who performed the verification, what outcome was reported, how confident the verifier was, what evidence supports that assertion, when the assertion was made, and what uncertainty remains.

An audit of the existing codebase showed that VORNEQ already has a substantial canonical Evidence Kernel in `apps.evidence`. This ADR is amended to make Verification an orchestration layer over that kernel rather than a second evidence system.

---

## 2. Decision

VORNEQ will model Verification as an **auditable workflow that evaluates a Claim using canonical Evidence**.

Verification does not own the canonical knowledge primitives. The following existing models remain authoritative in `apps.evidence`:

| Existing primitive | Responsibility |
| --- | --- |
| `Claim` | Canonical scoped assertion that can be evaluated. |
| `Evidence` | Canonical evidence object with integrity digest and provenance. |
| `EvidenceRelation` | Canonical relation between Claim and Evidence: supports, contradicts, contextualizes, or unclear. |
| `ProvenanceStep` | Immutable chain describing evidence origin and transformations. |
| `ReviewRecord` | Append-only review/state-transition event history. |

Verification will not create duplicate versions of these models.

The first Verification implementation therefore introduces only orchestration-specific models:

```text
VerificationMethod
VerificationRequest
VerificationResult
VerificationEvidence
```

The existing Core Reputation system remains the single reputation source of truth.

---

## 3. Verification Is Not Truth

A `VerificationResult` is a scoped assertion produced through a known method. It is not a universal `verified = true` flag and it is not a declaration of objective truth.

Different verification methods may legitimately produce different conclusions. Results may become stale, apply only to one artifact version, contain uncertainty, or conflict with other results.

Public and internal interfaces should therefore preserve and expose context such as:

- method;
- verifier;
- reported outcome;
- reported confidence;
- claim;
- evidence and evidence relations where authorized;
- timestamp;
- limitations and uncertainty.

VORNEQ must avoid unexplained labels such as "true", "trusted", or universally "verified".

---

## 4. Evidence Kernel Ownership

### Claim

`apps.evidence.models.Claim` is the canonical statement being evaluated. VerificationRequest references a Claim rather than storing a second free-form claim representation.

A Verification workflow may create a Claim through an explicit Evidence-domain service when appropriate, but the resulting Claim belongs to `apps.evidence`, not Verification.

### Evidence

`apps.evidence.models.Evidence` is the canonical evidence object.

Evidence already provides:

- UUID identity;
- integrity digest;
- observed timestamp;
- content type;
- metadata;
- creator attribution;
- immutable canonical fields.

Evidence creation must use the canonical Evidence service so digest generation and initial provenance are preserved atomically.

### EvidenceRelation

`EvidenceRelation` records the interpretation between a Claim and Evidence:

```text
supports
contradicts
contextualizes
unclear
```

A relation is not a verdict. Verification may create or reference relations through explicit Evidence-domain services, but the relation remains part of the Evidence Kernel.

### Provenance

`ProvenanceStep` remains the authoritative chain of origin and transformation for Evidence. Verification must not duplicate provenance fields that already belong to this chain.

### Review history

`ReviewRecord` is an append-only mechanism already available for auditable state-transition records. Verification services may use it where appropriate, but workflow state itself remains explicit on VerificationRequest.

---

## 5. Verification Orchestration Models

### VerificationMethod

Defines how a verification is performed.

Expected responsibilities include:

- stable identifier/name;
- human-readable description;
- manual, automated, or hybrid classification;
- optional method version;
- optional configuration metadata;
- active/inactive lifecycle.

A method describes **how a check is performed**, not whether its result should automatically be trusted.

### VerificationRequest

Represents a request to evaluate a Claim in the context of one supported artifact using one VerificationMethod.

Expected fields include:

- artifact reference;
- `claim` FK to canonical `apps.evidence.Claim`;
- `method`;
- `requested_by` using `AUTH_USER_MODEL`;
- status;
- optional instructions/context;
- timestamps.

Initial lifecycle:

```text
requested → in_progress → completed
                      ↘ failed
                      ↘ cancelled
```

State transitions must be explicit and service-controlled.

### VerificationResult

Represents one verifier's assertion for a VerificationRequest.

Expected fields include:

- request;
- verifier (`AUTH_USER_MODEL` in V1);
- outcome;
- reported confidence;
- summary;
- optional structured metadata;
- timestamps.

Initial outcome vocabulary:

```text
pass
fail
partial
inconclusive
```

A request may have multiple results in the future.

`VerificationResult` does **not** own Evidence and does not replace `EvidenceRelation`.

### VerificationEvidence

`VerificationEvidence` is a context-specific link/policy object between a VerificationResult and canonical Evidence.

Expected responsibilities:

- result FK;
- evidence FK to `apps.evidence.Evidence`;
- context-specific visibility;
- optional note or role describing how the evidence is used in that verification context.

This model exists because Evidence itself should not carry a single universal visibility classification. The same canonical Evidence may participate in multiple contexts with different access policies.

---

## 6. Evidence Visibility

Evidence access is **private by default in Verification contexts**.

Visibility belongs on `VerificationEvidence`, not canonical `Evidence`.

Initial visibility levels should support at least:

```text
private
participants
public
```

Working interpretation:

| Visibility | Intended access |
| --- | --- |
| `private` | Authorized platform/admin workflows only unless explicitly granted. |
| `participants` | Relevant requester/verifier participants and authorized staff. |
| `public` | Explicitly approved for public presentation. |

A public verification summary must never expose Evidence merely because that Evidence exists. Publication requires an explicit public VerificationEvidence policy.

Changing visibility is an explicit policy action and must not mutate canonical Evidence content or provenance.

---

## 7. Artifact Boundary in V1

VORNEQ does not yet have a generalized Artifact registry.

VerificationRequest may use a GenericForeignKey as a **temporary bridge**, but the service layer must allow only explicitly supported targets.

V1 target allowlist:

```text
marketplace.Product
library.LibraryItem
```

The validation must compare stable app/model identifiers rather than human class names.

Generic relations are transitional because they weaken database referential integrity and queryability. Artifact Registry design remains a future architecture decision after concrete Verification usage is established.

---

## 8. Identity Boundary in V1

Requester and verifier identities use Django's configured `AUTH_USER_MODEL`.

V1 does not introduce a speculative universal Identity or Agent abstraction. Human/Agent identity generalization will be addressed only after Agents become a concrete runtime entity.

Self-verification is denied by default unless a future method explicitly represents self-attestation.

---

## 9. Confidence Semantics

Three concepts remain separate.

### Outcome

The verifier's reported result:

```text
pass / fail / partial / inconclusive
```

### Reported confidence

The verifier's stated confidence in their own result. V1 may use a validated `0–100` scale.

This is **not** VORNEQ's universal trust score.

### Aggregate confidence

Any future platform-derived score combining multiple results, methods, recency, reputation, or evidence quality.

Aggregate confidence is explicitly out of scope for the initial Verification model and service PRs and requires a separately reviewed, explainable design.

---

## 10. Canonical Write Boundaries

Verification must respect existing Evidence-domain write paths.

Rules:

1. New Evidence must be created through the canonical Evidence service that generates integrity digests and initial Provenance atomically.
2. Evidence canonical fields must not be mutated by Verification.
3. EvidenceRelation creation/retirement should use Evidence-domain services rather than ad-hoc model mutation.
4. VerificationEvidence controls contextual access only; it does not alter canonical Evidence.
5. Verification orchestration services may coordinate transactions across Verification and Evidence domains when necessary, but ownership boundaries remain explicit.

---

## 11. Verification Service Boundaries

Business rules belong in explicit services rather than hidden signals.

Expected orchestration services include concepts such as:

```python
request_verification(...)
start_verification(...)
submit_verification_result(...)
attach_verification_evidence(...)
cancel_verification(...)
fail_verification(...)
get_artifact_verification_summary(...)
```

Services are responsible for:

- target allowlist validation;
- Claim association;
- method validation;
- requester/verifier authorization;
- state transitions;
- confidence validation;
- VerificationEvidence visibility policy;
- coordination with canonical Evidence/EvidenceRelation services;
- transaction boundaries where multiple records must remain consistent.

---

## 12. State Transition Rules

Initial allowed transitions:

```text
requested   → in_progress
requested   → cancelled
requested   → failed
in_progress → completed
in_progress → failed
in_progress → cancelled
```

Completed, failed, and cancelled are terminal in V1.

Invalid reverse transitions must be rejected unless a future design introduces explicit retry/reopen semantics.

Result submission that completes a request should be atomic with the corresponding workflow changes.

---

## 13. Threat Model

### False certainty

A result or confidence number may be interpreted as guaranteed truth.

Mitigation:

- preserve Claim, method, verifier, date, evidence context, and limitations;
- avoid universal trust badges;
- keep aggregate scoring out of scope until separately designed.

### Sybil and coordinated verification

Multiple accounts may collude to manufacture favorable results.

Mitigation:

- conservative verifier authorization;
- no automatic Reputation mutation in the initial implementation;
- later contextual Reputation policy.

### Conflicted verifiers

Creators or related accounts may verify their own artifacts.

Mitigation:

- explicit authorization checks;
- self-verification denied by default.

### Evidence poisoning

Evidence may be malicious, misleading, oversized, or unsafe for downstream tools.

Mitigation:

- canonical creation path;
- upload/content policies;
- no execution merely because Evidence is stored;
- sandboxing for future automated analysis.

### Sensitive evidence disclosure

Evidence may contain private, copyrighted, proprietary, or security-sensitive information.

Mitigation:

- context visibility is private by default;
- public output uses only explicitly public VerificationEvidence links;
- protected delivery rather than direct storage URLs;
- regression tests for unauthorized access and disclosure.

### Evidence tampering

Stored evidence may be altered after a verification result.

Mitigation:

- canonical Evidence immutability;
- integrity digest verification;
- immutable provenance.

### Stale verification

An artifact may change after verification.

Mitigation direction:

- preserve timestamps and sufficient artifact/version context;
- do not silently transfer a result to a materially changed artifact;
- defer the complete artifact-version binding strategy until Artifact Registry design.

---

## 14. Reputation Integration

Existing `apps/core` Reputation and ReputationHistory remain authoritative.

Verification introduces no new Reputation table and initial Verification outcomes do not automatically mutate Reputation.

Future Reputation integration must be contextual rather than a universal score. Policy must consider domain, method, recency, evidence, disputes, reversals, and conflicts before any automated update is accepted.

---

## 15. Public Presentation

Public presentation is deferred until models and services are stable.

Future public summaries may show:

- Claim;
- method;
- reported outcome;
- verification timestamp;
- appropriate verifier representation;
- reported confidence when meaningful;
- summary;
- only Evidence connected through explicitly public VerificationEvidence policies.

They must not expose:

- private/participants-only Evidence;
- direct protected storage URLs;
- internal notes or security metadata;
- an unexplained aggregate trust score.

---

## 16. Consequences

### Positive

- Reuses the mature Evidence Kernel rather than creating a parallel source of truth.
- Preserves canonical Evidence integrity, provenance, and Claim semantics.
- Keeps Verification focused on workflow and authorization.
- Allows context-specific evidence visibility without contaminating canonical Evidence.
- Maintains compatibility with future multi-verifier workflows.
- Reduces migration and long-term conceptual debt.

### Costs and risks

- Verification services must coordinate cleanly across app boundaries.
- GenericForeignKey remains a transitional compromise for artifacts.
- Access policy for shared Evidence requires careful query/service design.
- Existing Evidence primitives are sophisticated enough that new Verification code must respect their invariants.

---

## 17. Implementation Sequence

The amended sequence is:

| PR | Scope |
| --- | --- |
| **#52** | ADR 002 initial design |
| **ADR 002 amendment** | Record Evidence Kernel reuse and Verification-as-orchestration boundary |
| **#53** | `VerificationMethod`, `VerificationRequest`, `VerificationResult`, `VerificationEvidence`, migrations, admin, and model validation |
| **#54** | Verification orchestration services, authorization, Evidence/EvidenceRelation integration, and state-transition tests |
| **#55** | Read-only public verification summary and limited API surface |
| **Future ADR** | Artifact Registry and Contextual Trust Architecture after real Verification usage is observed |
| **#56 or later** | Explicit contextual Reputation integration |

Aggregate confidence remains outside this sequence until separately designed.

---

## 18. Decision Rules

Future Verification work must follow these rules:

1. **Verification records scoped assertions, not truth.**
2. **`apps.evidence` owns canonical Claim, Evidence, EvidenceRelation, Provenance, and Evidence review history.**
3. **Verification is an orchestration/workflow layer and must not duplicate Evidence Kernel models.**
4. **VerificationRequest references a canonical Claim.**
5. **VerificationEvidence links a result to canonical Evidence and owns context-specific visibility only.**
6. **Evidence remains immutable and is created through its canonical service path.**
7. **EvidenceRelation remains the canonical interpretation between Claim and Evidence.**
8. **Reported confidence is the verifier's assessment, not VORNEQ's aggregate trust score.**
9. **Aggregate confidence requires separate explainable design.**
10. **The existing Reputation system remains authoritative and is not automatically mutated in initial Verification work.**
11. **V1 identities are Django users; Agent identity is deferred.**
12. **V1 targets are allowlisted Product and LibraryItem references through a temporary generic bridge.**
13. **State changes and authorization belong in explicit services.**
14. **Private evidence must never be exposed through public templates, APIs, logs, or direct storage URLs.**
15. **Artifact Registry generalization is deferred until real integration patterns justify it.**

---

## 19. Conclusion

VORNEQ's Verification Layer is an orchestration system built on an existing canonical Evidence Kernel.

The architecture is therefore:

```text
Artifact context
      ↓
VerificationRequest ───→ Claim
      ↓                  ↓
VerificationResult   EvidenceRelation
      ↓                  ↑
VerificationEvidence ─→ Evidence
                         ↓
                    Provenance
```

The governing principle remains:

> **Verification is evidence about a claim; it is not truth itself.**

The amendment prevents a second Evidence system from emerging and establishes a clearer ownership boundary: Evidence Kernel records canonical knowledge and provenance; Verification organizes controlled workflows that evaluate claims against that evidence.