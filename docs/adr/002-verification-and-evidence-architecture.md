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

PR #50 implemented the first concrete Deliver primitive through Core Entitlement and protected Marketplace delivery. The next architectural responsibility to formalize is **Verify**.

Verification is inherently more sensitive than a delivery permission check. A verification result can influence user decisions, marketplace behavior, reputation, access, pricing, and future automated systems. If VORNEQ represents verification as an unexplained badge or an absolute declaration of truth, it creates false certainty and weakens the trust model it is intended to build.

The central question for this ADR is:

> **How should VORNEQ record and present a claim and its supporting evidence without confusing verification with truth?**

This ADR defines the semantics, data boundaries, state transitions, evidence rules, and threat assumptions for the first Verification Layer implementation.

---

## 2. Decision

VORNEQ will model verification as an **auditable assertion produced through a defined method**, not as an absolute truth claim.

A verification result must preserve enough provenance to answer:

- what artifact was examined;
- what verification method was used;
- who requested the verification;
- who performed or submitted the verification;
- what outcome was reported;
- how confident the verifier was in that outcome;
- what evidence supports the result;
- when the verification occurred;
- what limitations or uncertainty remain.

The first implementation will use four primary models:

```text
VerificationMethod
VerificationRequest
VerificationResult
Evidence
```

The existing Core Reputation system will remain the single reputation source of truth. Verification will not introduce a second Reputation model.

---

## 3. Verification Is Not Truth

VORNEQ must not collapse verification into a single universal `verified = true` state.

A VerificationResult is a scoped assertion. Its meaning depends on the method, verifier, artifact state, evidence, and time of evaluation.

For example:

- a malware scan may pass at one point in time but become outdated later;
- a human quality review may be subjective;
- an authenticity check may establish provenance without proving authorship with certainty;
- a statistical test may support one claim while saying nothing about another;
- two credible verifiers may reasonably disagree.

Therefore public and internal interfaces should use language such as:

- "verification result";
- "reported outcome";
- "evidence";
- "reported confidence";
- "method";
- "verified on <date>";

and should avoid presenting an unexplained "trusted" or "true" label.

---

## 4. Initial Domain Models

### VerificationMethod

Defines a known way in which a verification can be performed.

Expected responsibilities include:

- stable name and identifier;
- human-readable description;
- whether the method is manual, automated, or hybrid;
- optional version information;
- optional configuration or metadata needed by future implementations;
- active/inactive lifecycle.

Examples may eventually include:

- manual editorial review;
- malware scanning;
- document provenance review;
- automated schema validation;
- statistical analysis;
- reproducibility checks.

A method describes **how a check is performed**, not whether its result should automatically be trusted.

### VerificationRequest

Represents a request to verify one supported artifact using one VerificationMethod.

The initial request lifecycle is intentionally small:

```text
requested → in_progress → completed
                      ↘ failed
                      ↘ cancelled
```

Expected request data includes:

- artifact reference;
- requested_by (`AUTH_USER_MODEL`);
- method;
- state/status;
- creation and update timestamps;
- optional request context or instructions.

State transitions must be explicit and validated by service functions. Business-critical transitions should not rely on hidden Django signals.

### VerificationResult

Represents one verifier's assertion produced for a VerificationRequest.

A request may eventually have more than one result. This keeps multi-verifier verification possible without changing the request model.

Expected result data includes:

- request;
- verifier (`AUTH_USER_MODEL` in V1);
- outcome;
- reported confidence;
- summary;
- created timestamp;
- optional structured metadata.

The first outcome vocabulary should remain small and explicit, for example:

```text
pass
fail
partial
inconclusive
```

The precise values will be finalized in the data-model PR, but the model must preserve the distinction between a negative result and an inability to reach a conclusion.

### Evidence

Represents supporting material attached to a VerificationResult.

Evidence may include:

- uploaded files;
- external references or URLs;
- machine-generated reports;
- structured metadata;
- textual descriptions;
- hashes or provenance identifiers.

Evidence must be treated as potentially sensitive.

---

## 5. Artifact Boundary in V1

VORNEQ does not yet have a generalized Artifact registry.

For the initial Verification implementation, a GenericForeignKey may be used as a **temporary bridge** between VerificationRequest and supported vertical models.

V1 must support only an allowlisted set of artifact types, initially expected to be:

- Marketplace `Product`;
- `LibraryItem`.

The service layer must reject arbitrary content types even if the database representation is technically capable of referencing them.

This is intentionally transitional. Generic relations provide flexibility but weaken referential integrity and queryability compared with explicit relationships.

A future Artifact ADR must choose the long-term registry or polymorphism strategy. Verification code should therefore isolate artifact validation and resolution behind explicit service boundaries where practical.

---

## 6. Identity Boundary in V1

Verifier and requester identities will use Django's configured `AUTH_USER_MODEL` in the first implementation.

VORNEQ will **not** create a speculative universal Identity abstraction or Agent relation in this phase.

AI Agents are part of the long-term architecture but are not yet a stable runtime entity in the codebase. When Agent participation becomes concrete, Identity generalization must be evaluated separately so that human and machine identity semantics are not conflated prematurely.

---

## 7. Confidence Semantics

Confidence is separated into distinct concepts.

### Outcome

The verifier's reported result of the verification process.

Example:

```text
pass / fail / partial / inconclusive
```

### Reported Confidence

The verifier's stated confidence in its own result.

This value describes the verifier's assessment. It is **not** the platform's universal trust score.

The storage format may use a constrained numeric scale such as `0.0–1.0` or `0–100`, to be finalized in the data-model PR. Validation must enforce the declared range.

### Aggregate Confidence

A future VORNEQ-generated assessment combining multiple results, methods, verifier reputation, recency, evidence quality, or other factors.

**Aggregate confidence is explicitly out of scope for the first Verification model and service PRs.**

No algorithm should be treated as an official trust score until its semantics, abuse resistance, calibration, and explainability have been separately designed and reviewed.

---

## 8. Evidence Visibility and Access

Evidence is **private by default**.

This is required because evidence may contain:

- personal information;
- copyrighted material;
- private customer data;
- vulnerability or security details;
- scanner output that exposes implementation information;
- proprietary reports;
- data unsuitable for public redistribution.

The initial Evidence visibility model should support at least:

```text
private
verifier
public
```

The exact meaning must be enforced at the service/query level.

A working interpretation is:

| Visibility | Intended access |
| --- | --- |
| `private` | restricted to authorized platform/admin workflows and explicitly authorized participants |
| `verifier` | available to the relevant verification participants and authorized staff |
| `public` | explicitly approved for public presentation |

A public verification summary must never automatically expose non-public evidence.

Changing evidence visibility should be an explicit action. Uploading evidence must not imply permission to publish it.

---

## 9. Service Boundaries

Verification business rules should be expressed through explicit services rather than scattered model mutations or hidden signals.

Expected services include concepts such as:

```python
request_verification(...)
start_verification(...)
submit_verification_result(...)
cancel_verification(...)
fail_verification(...)
get_artifact_verification_summary(...)
```

The service layer will be responsible for:

- artifact allowlist validation;
- method validation;
- state transitions;
- requester/verifier authorization;
- confidence validation;
- evidence handling policies;
- transaction boundaries where multiple records change together.

The final API names may differ, but explicit transition-oriented services are required.

---

## 10. State Transition Rules

The request state machine should reject invalid transitions.

Initial intended transitions:

```text
requested   → in_progress
requested   → cancelled
requested   → failed
in_progress → completed
in_progress → failed
in_progress → cancelled
```

Completed, failed, and cancelled requests are terminal in V1.

Direct transitions such as:

```text
completed → in_progress
cancelled → completed
failed    → completed
```

must be rejected unless a future ADR introduces an explicit reopen/retry concept.

Result submission that completes a request should occur atomically where possible so the system cannot persist a completed request without its corresponding result.

---

## 11. Threat Model

The Verification Layer is a trust-sensitive system and must be designed under adversarial assumptions.

### Sybil and reputation manipulation

An attacker may create multiple identities to submit favorable verification outcomes or manufacture reputation.

Initial mitigation:

- verifier eligibility is restricted rather than open to all accounts;
- verification events do not automatically modify reputation in the first implementation;
- reputation integration is deferred to a dedicated PR and policy review.

### Biased or conflicted verifiers

A creator may verify their own artifact or coordinate with related accounts.

Initial mitigation:

- authorization policy must be explicit;
- self-verification should be disallowed by default unless a method specifically represents self-attestation;
- future conflict-of-interest metadata may be added if required.

### Evidence poisoning

Evidence may be misleading, malicious, oversized, unsafe, or intentionally crafted to exploit downstream tools.

Mitigation requirements:

- reuse or extend safe upload validation;
- evidence is not executed merely because it is uploaded;
- automated analysis must run in appropriately isolated environments when introduced;
- file type and size policies must be explicit.

### Sensitive evidence disclosure

Private evidence could be exposed through templates, APIs, storage URLs, logs, or object serialization.

Mitigation requirements:

- private-by-default visibility;
- public serializers/templates include only explicitly public evidence;
- protected evidence delivery must use controlled authorization rather than direct file URLs;
- regression tests must cover unauthorized access and URL disclosure.

### False certainty and misleading UI

Users may interpret a confidence number or badge as a guarantee.

Mitigation requirements:

- preserve method, date, verifier, outcome, and limitations;
- avoid universal "verified = true" semantics;
- do not introduce aggregate trust scores before their meaning is documented;
- public UI should communicate scope and uncertainty.

### Stale verification

An artifact may change after verification or a verification may become outdated.

Initial design requirement:

- verification records must preserve timestamps;
- future model work should retain enough artifact/version context to determine whether a result applies to the current artifact state;
- verification should not be silently transferred to materially changed artifacts.

A full artifact-version binding strategy is deferred until Product/Library version semantics are audited.

---

## 12. Reputation Integration

The existing `apps/core` Reputation and ReputationHistory models remain authoritative.

The Verification Layer will not create a new reputation table.

Verification outcomes also will **not** immediately mutate reputation in the initial model/services PRs.

Reputation integration requires a later explicit policy defining:

- which events affect which reputation dimensions;
- how outcomes are judged correct or incorrect over time;
- whether a verifier can lose reputation;
- how disputes, reversals, stale results, and conflicting verifications are handled;
- how to prevent circular logic in which reputation determines confidence and confidence immediately determines reputation.

This work is planned as a separate PR after the basic Verification Layer is proven.

---

## 13. Authorization Direction

The first implementation should not allow every authenticated user to act as a verifier by default.

V1 verifier authorization should use a conservative policy such as staff permission or an explicit Django permission/group.

The exact permission name belongs in the implementation PR, but authorization must be independently testable and must not rely solely on UI visibility.

Automated verifiers and Agents are out of scope for V1.

---

## 14. Public Presentation

Public verification presentation is deferred until the model and services are stable.

When added, the public summary should be read-only and should expose only information appropriate for public trust decisions, such as:

- method;
- reported outcome;
- verification timestamp;
- verifier identity or an appropriately public verifier representation;
- reported confidence when meaningful;
- summary;
- explicitly public evidence.

It must not expose:

- private/verifier-only evidence;
- internal security metadata;
- arbitrary storage URLs;
- hidden reviewer notes;
- a platform aggregate confidence score before such a score has a separately accepted design.

---

## 15. Consequences

### Positive

- Verification remains auditable and explainable rather than badge-driven.
- Evidence privacy is protected by default.
- Existing Reputation remains the single source of truth.
- The first implementation can support Product and LibraryItem without prematurely committing to a universal Artifact model.
- Multi-verifier workflows remain possible because Request and Result are separate concepts.
- Explicit state transitions make business rules testable and resistant to accidental mutation.

### Costs and risks

- GenericForeignKey is a transitional compromise with weaker referential integrity.
- Supporting private evidence requires careful access control and storage practices.
- Verification UI must communicate uncertainty clearly, which is more complex than a simple badge.
- A conservative verifier policy may limit early marketplace scale.
- Aggregate confidence and reputation integration require additional design work before they can be safely automated.

---

## 16. Implementation Sequence

The Verification Layer should be introduced incrementally:

| PR | Scope |
| --- | --- |
| **#52** | ADR 002: Verification and Evidence Architecture — design only |
| **#53** | Verification data models, migrations, model validation, and admin |
| **#54** | Verification services, authorization, evidence handling, and state-transition tests |
| **#55** | Read-only public verification summary for supported artifacts and limited API surface |
| **#56** | Explicit integration with the existing Reputation/ReputationHistory system |

Aggregate confidence scoring is not implied by PR #56 and may require its own ADR or PR.

---

## 17. Evolution Toward Artifact Registry

The GenericForeignKey bridge is not the long-term Artifact architecture.

When multiple trust primitives require stable cross-vertical artifact identity, VORNEQ should introduce a separate Artifact architecture decision that evaluates:

- explicit registry records;
- vertical-to-artifact relationships;
- artifact versions and immutable fingerprints;
- ownership and provenance;
- query and referential-integrity requirements;
- migration from existing Product and LibraryItem records.

Verification services should minimize assumptions that would make this future migration unnecessarily difficult.

---

## 18. Decision Rules for Verification Work

Future Verification work must follow these rules:

1. **Verification records assertions, not absolute truth.**
2. **Every result must retain provenance: method, verifier, time, outcome, and supporting context.**
3. **Evidence is private unless explicitly made public.**
4. **Reported confidence is the verifier's assessment, not VORNEQ's aggregate trust score.**
5. **Aggregate confidence requires a separate, explainable design.**
6. **The existing Reputation system remains authoritative.**
7. **Verification must not automatically modify Reputation until a dedicated policy is accepted.**
8. **V1 identities are Django users; Agent identity is deferred.**
9. **V1 artifacts are allowlisted Product and LibraryItem references through a temporary generic bridge.**
10. **State changes and authorization belong in explicit services and must be regression-tested.**
11. **Public interfaces must never expose private evidence or direct protected file URLs.**
12. **Self-verification is denied by default unless a method explicitly represents self-attestation.**

---

## 19. Conclusion

VORNEQ's Verification Layer will be built as an evidence-based, auditable system for recording scoped assertions.

The governing principle is:

> **Verification is evidence about a claim; it is not truth itself.**

The initial architecture deliberately favors explicit provenance, conservative access, private evidence, constrained identities, and incremental generalization.

This creates a foundation on which later capabilities — multi-verifier analysis, public summaries, Reputation integration, automated Agents, Attestation, and eventually aggregate trust assessments — can be built without turning an early heuristic into an opaque universal trust score.
