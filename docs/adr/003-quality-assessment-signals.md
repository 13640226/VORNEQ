# ADR 003: Quality Assessment Signals for Verification

**Status:** Proposed  
**Date:** 2026-09-06  
**Author:** VORNEQ Core Team

---

## 1. Context

VORNEQ records Verification outcomes as scoped assertions about claims and artifacts. ADR 002 established a strict architectural boundary: **Verification is not Truth**. A verifier may report `pass`, `fail`, `partial`, or `inconclusive`, together with verifier-reported confidence, but none of those fields prove that the verifier was correct.

The new Contextual Reputation foundation records verification activity by user, domain, and method without changing a reputation score. Before any scoring policy can be introduced, VORNEQ needs an explicit model for the signals that may later be used to assess the quality of a VerificationResult.

The central problem is therefore:

> How can VORNEQ assess the quality of a verification outcome using auditable external reference signals without treating consensus, authority, or the platform itself as an owner of truth?

This ADR defines the semantics and safeguards for those signals. It does **not** define a scoring formula.

---

## 2. Decision

VORNEQ will use **Quality Assessment Signals** as explicit, attributable observations about the quality of a VerificationResult.

The platform will not create or expose a universal `ground_truth` field. Where a domain has a strong external reference, VORNEQ may record that reference as a signal with clearly stated provenance, scope, method, and limitations.

A Quality Assessment Signal is itself an assertion. It must remain inspectable and contestable.

### Core rule

```text
VerificationResult != Truth
QualityAssessmentSignal != Truth
Consensus != Truth
Authority != Truth
Reputation != Truth
```

These objects may provide evidence for decision-making, but VORNEQ must preserve the distinction between observed agreement and ontological certainty.

---

## 3. Required Properties of a Quality Signal

Any signal that may influence Contextual Reputation must be:

- **Attributable** — the human, institution, agent, or deterministic process producing it is identified.
- **Scoped** — the domain, verification method, claim, artifact, and relevant conditions are explicit.
- **Method-labelled** — the process that produced the signal is recorded.
- **Evidence-backed** — supporting evidence or provenance is available when applicable.
- **Timestamped** — the signal is anchored in time so later supersession can be represented.
- **Auditable** — the chain from VerificationResult to signal can be inspected.
- **Contestable** — disagreement or later correction can be represented without rewriting history.
- **Independent where required** — signals used together must disclose dependence or common provenance where known.

No quality signal may silently modify a verifier's reputation.

---

## 4. Signal Classes

VORNEQ recognizes several signal classes. They are not assumed to have equal strength.

### 4.1 Direct External Reference Signal

A VerificationResult is compared with an independently produced reference whose generation process is external to the verifier being assessed.

Examples:

- a security scanner result compared with a later confirmed vulnerability disclosure;
- a forecast compared with the eventually observed event;
- a structured validation result compared with an authoritative machine-readable record;
- an automated calculation compared with a reproducible deterministic computation.

An external reference may be strong, but it is still represented as a reference signal with provenance rather than as platform-owned truth.

### 4.2 Reproducibility Signal

An independent party repeats a defined method and reports whether the relevant result can be reproduced under specified conditions.

Reproducibility is particularly useful in scientific, software, security, and analytical workflows.

A failed reproduction does not automatically prove that the original verifier was wrong; environmental and methodological differences must remain visible.

### 4.3 Adjudication Signal

A qualified reviewer, panel, institution, or formal process assesses a VerificationResult after reviewing its claim and evidence.

The adjudicator's identity, mandate, method, conflicts of interest, and scope should be recordable.

Institutional authority is a source characteristic, not proof of truth.

### 4.4 Independent Corroboration Signal

One or more independently generated verification results materially agree or disagree with the assessed result.

Corroboration may increase confidence that a result is robust, but simple vote counting is insufficient. Independence and methodology matter.

### 4.5 Statistical or Proxy Signal

When direct reference signals are unavailable, a measurable proxy may be recorded, such as calibration against later observations or repeatability across a benchmark set.

Proxy signals must be explicitly labelled as proxies. They must not be presented as equivalent to direct correctness assessment.

### 4.6 Contestation / Correction Signal

A later event disputes, narrows, corrects, supersedes, or invalidates a previous assessment.

Corrections are append-only events. Historical signals remain preserved rather than rewritten.

---

## 5. Consensus Policy

Consensus is not a privileged source of truth.

A majority of verifiers may share the same dependency, model family, dataset, institutional incentive, or error. Therefore a future scoring policy must not treat `N agreeing verifiers` as `N independent signals` automatically.

Where consensus is considered, VORNEQ should distinguish at least:

- number of assessments;
- number of materially independent assessment paths;
- method diversity;
- source/evidence diversity;
- known shared dependencies;
- time separation where relevant.

Consensus may be a quality signal. It is never sufficient by itself to establish truth.

---

## 6. Domain Specificity

Signal meaning varies by domain. VORNEQ must not use one universal assessment policy across all domains.

Examples:

- **Software/security:** reproducible tests, exploit confirmation, deterministic scanners, patch validation.
- **Forecasting:** later observed outcomes can provide direct resolution signals.
- **Scientific work:** reproducibility, independent replication, validated measurements, methodological review.
- **Historical/cultural claims:** provenance quality, source criticism, independent documentary corroboration, expert adjudication.
- **Legal/compliance workflows:** jurisdiction-specific authoritative records and formal review processes.
- **Religious or interpretive domains:** textual provenance and attribution may be assessable, while doctrinal truth must not be encoded as a platform verdict.

A signal that is strong in one domain may be meaningless in another.

---

## 7. Circularity and Feedback-Loop Safeguards

Contextual Reputation must not become self-validating.

The following feedback loop is prohibited:

```text
high reputation -> assessment gets high weight
assessment -> becomes reference for another verifier
agreement with that reference -> raises reputation
```

without an independent external or explicitly adjudicated signal.

Future scoring policies must therefore account for:

1. **Self-reference:** a verifier cannot assess their own result for reputation gain.
2. **Mutual reinforcement:** repeated reciprocal validation between the same actors must not create unbounded reputation.
3. **Shared-source dependence:** two verifiers using the same source are not automatically independent.
4. **Model-family dependence:** multiple AI agents derived from the same model or pipeline may represent one correlated assessment path.
5. **Institutional dependence:** multiple reviewers from one organizational decision chain may be correlated.
6. **Reputation recursion:** an actor's current score must not itself serve as the sole quality signal used to update that score.

---

## 8. Scoring Eligibility

A VerificationResult is **not automatically eligible for reputation scoring** when it is submitted or completed.

A future scoring service may update a ContextualReputation score only when all policy requirements for the relevant domain and method have been satisfied.

At minimum, eligibility should require:

- a completed VerificationResult;
- an explicit domain;
- an associated Quality Assessment Signal type accepted by the domain policy;
- a defined relationship between the signal and the assessed result;
- known provenance for the signal;
- no prohibited self-assessment loop;
- idempotent event handling;
- an auditable scoring-policy version.

`PASS`, `FAIL`, `PARTIAL`, `INCONCLUSIVE`, and `reported_confidence` are not quality signals by themselves.

---

## 9. Proposed Data Shape

A future implementation may introduce a model conceptually similar to:

```text
QualityAssessmentSignal
- verification_result
- signal_type
- assessor / source identity
- domain
- method / protocol
- observed_assessment
- strength_or_confidence (optional, method-specific)
- evidence / provenance references
- independence_metadata
- policy_metadata
- created_at
```

The final schema is intentionally deferred. It must reuse canonical Evidence/Provenance primitives from `apps.evidence` wherever possible rather than create a parallel evidence system.

Signals should be append-only or otherwise preserve a complete history of supersession and correction.

---

## 10. Relationship to Contextual Reputation

`ContextualReputation` remains a projection/cache over auditable events, not the canonical record of why an actor is considered reliable.

The canonical chain should remain inspectable:

```text
VerificationResult
    -> Quality Assessment Signal(s)
        -> Scoring Policy Version
            -> Contextual Reputation Event
                -> Contextual Reputation projection
```

A public reputation value, if introduced later, must be accompanied by enough context to understand at least domain, method, sample size, recency, and methodology.

No single cross-domain `trust score` is introduced by this ADR.

---

## 11. Time Sensitivity and Supersession

Quality assessments can become stale.

A later software version, new scientific evidence, corrected dataset, changed regulatory framework, or discovered conflict of interest may reduce the relevance of an older signal.

Future scoring policies may use recency or temporal validity, but must not erase historical events. Corrections and superseding assessments are appended and linked to earlier signals.

---

## 12. Threat Model

The Quality Assessment layer must anticipate:

- Sybil verifier clusters designed to manufacture agreement;
- collusive reciprocal verification;
- compromised or captured adjudicators;
- benchmark gaming;
- selective publication of favorable assessment signals;
- adversarial Evidence or provenance manipulation;
- correlated AI systems presented as independent verifiers;
- malicious domain labelling to obtain a more favorable reputation context;
- stale external references;
- authority laundering, where institutional status is presented as proof of correctness.

Mitigations will include provenance, explicit dependency metadata, idempotent event logs, policy versioning, domain-specific requirements, and auditability.

---

## 13. Privacy and Disclosure

Quality signals may depend on sensitive evidence. Public reputation computation must not imply that all supporting material is public.

Signal visibility and Evidence visibility remain separate concerns. A scoring policy may consume authorized private evidence without disclosing that evidence publicly, provided the existence and methodology of the assessment can be represented honestly.

No private Evidence content becomes public merely because it contributed to a reputation event.

---

## 14. Consequences

### Positive

- Prevents `PASS/FAIL` from being mistaken for correctness.
- Preserves VORNEQ's neutrality: the platform records assessments rather than owning truth.
- Makes future reputation scoring explainable and auditable.
- Supports domain-specific quality standards.
- Reduces circular reputation and consensus-manipulation risk.
- Allows strong external references where they exist without forcing that model onto interpretive domains.

### Negative

- Reputation scoring becomes deliberately slower to implement.
- Some domains may not support meaningful numerical scores at all.
- Independence and provenance analysis add complexity.
- A single simple global leaderboard becomes architecturally inappropriate.

These costs are accepted because false precision would undermine the Trust Infrastructure itself.

---

## 15. Implementation Sequence

1. Merge the Contextual Reputation foundation.
2. Accept this ADR.
3. Design a minimal `QualityAssessmentSignal` schema that reuses Evidence Kernel primitives.
4. Implement signal recording without reputation scoring.
5. Define one narrow, defensible domain-specific scoring policy with versioning and tests.
6. Only then allow that policy to update `ContextualReputation.score`.
7. Evaluate behavior before adding policies for other domains.

The first scoring policy should be chosen where a high-quality external outcome exists, rather than where assessment is primarily interpretive.

---

## 16. Non-Goals

This ADR does not:

- define a universal ground truth;
- define a global trust score;
- make majority consensus authoritative;
- score a verifier because they submitted a verification;
- infer accuracy from `reported_confidence`;
- expose private Evidence;
- define the final scoring formula;
- define Artifact Registry architecture.

---

## 17. Conclusion

VORNEQ will evaluate verification quality through explicit, auditable **Quality Assessment Signals**, not through platform-owned truth claims.

External references, reproducibility, adjudication, independent corroboration, and statistical proxies may all contribute useful information, but their semantics and limitations must remain visible.

This preserves the core principle of the VORNEQ Trust Infrastructure:

> Make claims, evidence, assessments, and accountability inspectable without pretending to own truth.
