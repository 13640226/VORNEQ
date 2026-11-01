# VORNEQ — P0 | PR #418 / Issue #340
# Independent Eligibility Assessor Selection Procedure V1.2

**Document ID:** P0_VORNEQ_PR418_CC04_INDEPENDENT_ELIGIBILITY_ASSESSOR_SELECTION_PROCEDURE_V1_2  
**Version:** 1.2  
**Date:** 2026-11-01  
**Subject:** Documentary procedure for selection of an independent assessor who may later assess a PR #418 governance reviewer  
**Status:** DOCUMENTARY_ACCEPT / OWNER_ACCEPTED (2026-11-01, **documentary scope only**)  
**Owner attestation record:** [Issue #340 — owner decision](https://github.com/13640226/VORNEQ/issues/340#issuecomment-6560513948)  
**Parent contract:** CC-04 Independent Reviewer Eligibility and Conflict-of-Interest Contract V1.1 (owner-accepted in the project conversation)  
**Related source:** [PR #418](https://github.com/13640226/VORNEQ/pull/418), [Issue #340](https://github.com/13640226/VORNEQ/issues/340)

> **Review-only and NO GO.** This document is a governance procedure, not a selection of a person, independent sign-off, migration/CI authorization, merge authorization, deployment authorization or evidence of runtime security. The Draft PR carrying this document must not be merged absent a separate explicit owner decision, and such a decision cannot silently override STOP_340 or other applicable security gates.

## 1. Scope and fixed evidence boundaries

This procedure governs the selection of an **Eligibility Assessor**, who would separately assess whether a different natural person is suitable to conduct an independent governance review of the PR #418 merge deviation. It does not itself appoint an assessor or reviewer.

The historical documentary baseline is preserved:

- PR #418 was merged on **2026-10-29 12:05:41 UTC** with merge commit **90b4fb8861b75efc7ad83d0a28faee9f249baac5**.
- The GitHub merge actor and earlier approving account were **hamidrezaasadian7-boop**. A GitHub account is not equivalent to a verified natural-person operator.
- The owner's statement that they personally performed the merge is **OWNER_REPORTED**; the human operator remains **NOT_INDEPENDENTLY_VERIFIED**.
- A qualifying pre-merge authorization is **NOT_ESTABLISHED**, not categorically proven nonexistent.
- The historically examined governance deviation is **CONFIRMED** within the previous documentary review's scope; final disposition remains **PENDING**.
- No determination of security exploitability, malicious intent or runtime safety follows from these observations.

**Separation:** NOMINATION != ELIGIBILITY != APPOINTMENT != ACCESS AUTHORIZATION != EXECUTION AUTHORIZATION. INDEPENDENT SIGN-OFF != OWNER DISPOSITION.

## 2. Roles and sequence

- **Repository Owner:** may propose an assessor candidate and separately decide any later appointment; cannot self-certify the independence of involved historical actors.
- **Assessor Candidate:** supplies appropriately authorized identity, past participation, qualification and COI information in a future process.
- **Trust Decision Authority (TDA):** accountable natural person, or institution with an identifiable authorized natural-person representative, whose own identity, authority and independence have a verifiable trust foundation.
- **Independent Verification Party:** evaluates the assessor candidate's identity/independence and conflicts against suitable evidence, subject to the TDA trust controls below.
- **Governance Record Custodian:** preserves dated provenance, decision references, versions, gaps and status; recordkeeping alone grants no approval.
- **Eligibility Assessor:** only after a valid separate appointment may assess a **different** natural-person reviewer candidate.
- **Independent Governance Reviewer:** only after separate eligibility and appointment may conduct the historical evidence review.

Required order: documentary procedure acceptance → privacy preflight → nomination → TDA trust verification → candidate natural-person/participation check → COI and qualifications → version-bound eligibility decision → exact-person/scope appointment-binding gate → separate appointment → later reviewer eligibility evaluation → independent review and sign-off → **subsequent** owner disposition → CC-08 sequence evaluation.

No one is nominated, validated or appointed by this document.

## 3. Privacy preflight — preserved ASP-SR-07

Before any *actual new collection* of identifiable candidate data, a responsible party must document **processing purpose, legal basis, controller, authorized access, approved storage, retention/deletion rules, public/private separation, security measures and data-subject request process**. If any mandatory element is missing: PRIVACY_PREFLIGHT = BLOCKED; PERSONAL_DATA_COLLECTION = NOT_AUTHORIZED.

Public GitHub issues/PRs should use minimized/pseudonymous governance attestations; do not publish raw identity documents, secrets, cookies, credentials or confidential COI records. No assertion of full GDPR compliance is made by drafting this procedure. The present document authorizes **zero** new personal-data collection.

## 4. Candidate nomination

An owner nomination merely establishes CANDIDATE = NOMINATED. It does not imply ELIGIBLE, APPOINTED or permission to receive restricted evidence. Professional titles, a second GitHub account, references or self-declared independence are insufficient alone.

## 5. §7 — Assessor Verification Trust Gate (V1.2 corrected normative section)

**Correction:** ASP-V11-RV-01. Only this section supersedes the previous §7 in procedure V1.1. The six other accepted sections remain normatively unchanged.

### 5.1 AC-T01 — Trust Decision Authority and accountability

Before a positive trust determination, identify the accountable **natural person** who decides, or the verifiably existing institution and the **named authorized natural person** acting for it. Document identity, institutional mandate if relevant, authority to act, competence for this precise assessment, separation from the candidate, historical participation, relevant conflicts, source of trust and decision accountability.

A title, organization name, different account, self-certification, automated report or owner nomination **cannot alone** establish independence. The person under assessment cannot validate their own suitability.

The verifier/TDA must have a suitably corroborated basis independent of both the candidate's own declarations and mere interested-owner assertion. An institution can supply the stopping point for the verification chain only where its existence, mandate, representative's authority, independence and material conflicts can actually be assessed. **No infinite chain of further verifiers is required**, but absence of a defensible trust anchor prevents PASS.

### 5.2 AC-T02 — Mandatory disqualification (Ausschlussgründe)

TRUST_GATE = FAIL for the relevant trust verification if the responsible natural person:

1. Performed the material PR #418 approval;
2. Performed or directly controlled the PR #418 merge;
3. Materially made the historical governance decision they would now finally judge themselves;
4. Is the assessor candidate under assessment; or
5. Has a confirmed non-manageable material COI (COI-A).

Separate accounts, role labels, institutional representation or owner risk acceptance **never** waive a confirmed direct self-review exclusion. Unknown original human-operator identity is **not** filled in by inference; independently supported candidate non-participation can still be established without resolving every historical identity, but not on the absence of an account match alone.

### 5.3 AC-T03 — Independent evidence foundation

A positive result must reference and evaluate:

- TE-01: accountable natural person's identity evidence;
- TE-02: mandate, authority and institutional representation evidence;
- TE-03: relevant historical participation / non-participation evidence;
- TE-04: self COI declaration **and** independent conflict assessment;
- TE-05: independent institutional trust anchor, where claimed;
- TE-06: contradictory evidence and its disposition;
- TE-07: inaccessible material, limitations and residual uncertainty.

For every decisive source, record its provenance, temporal relevance and independence. Multiple reports copying one declaration do **not** constitute independent corroboration. Avoid impossible absolute negative proof, but require a reasoned affirmative assessment based on appropriate accessible evidence; a material unresolved contradiction blocks PASS. Access to new restricted records is **not** granted here.

The Trust Decision Record must identify: record ID, decision authority and representative, candidate reference, identity and authority status, involvement/COI findings, trust anchor and reasons, contradictory evidence, limits, evidence manifest ID/version/cutoff, decision result, justification and residual uncertainties.

### 5.4 AC-T04 — Fail-closed decisions

Exactly three trust verdicts are permissible:

- **TRUST_GATE_PASS:** every mandatory identity, authority, separation, non-exclusion, COI, independent-evidence, manifest and valid-attestation condition has been met for the recorded scope.
- **TRUST_GATE_FAIL:** direct personal historical involvement/self-review, identical candidate and deciding person, or confirmed non-manageable COI.
- **TRUST_GATE_INSUFFICIENT_EVIDENCE:** unknown identity or authority, insufficient independent evidence/trust anchor, unresolved material COI or contradiction, absent/invalid attestation, or owner assertion only.

For TRUST_GATE != PASS, subsequent assessor eligibility is **INSUFFICIENT_EVIDENCE**, appointment binding is **BLOCKED**, and no independent reviewer assessment is authorized *by this gate*. An owner assertion cannot bypass FAIL or INSUFFICIENT_EVIDENCE.

The rules specify documentary outcomes, not executable code or automatic permission revocation.

### 5.5 AC-T05 — Version-bound attestation

A later actual decision requires all of the following fields, with real verifiable values rather than placeholders:

~~~text
ATTESTATION_ID
PROCEDURE_DOCUMENT_ID / PROCEDURE_DOCUMENT_VERSION (V1.2)
PROCEDURE_DOCUMENT_DIGEST_OR_IMMUTABLE_REF
TRUST_DECISION_RECORD_ID / VERSION / DIGEST_OR_IMMUTABLE_REF
EVIDENCE_MANIFEST_ID / VERSION / EVIDENCE_CUTOFF_UTC
ASSESSOR_CANDIDATE_REFERENCE_ID
DECISION_AUTHORITY_REFERENCE_ID
DECISION_SIGNER_NATURAL_PERSON_REFERENCE
SIGNER_IDENTITY_VERIFICATION_REFERENCE
SIGNER_AUTHORITY_VERIFICATION_REFERENCE
SIGNATURE_METHOD / SIGNATURE_TIMESTAMP_UTC
ATTESTATION_VERIFICATION_STATUS
POST_SIGNATURE_CHANGE_STATUS
~~~

Any digest must name its algorithm and exact input; no hashes, signers or timestamps are fabricated in this document. Material changes to natural-person identity, mandate, COI, documentary basis or evidence trigger reassessment and fresh attestation where affected. Until resolved: TRUST_GATE_STATUS = REASSESSMENT_PENDING and APPOINTMENT_GATE = BLOCKED.

### 5.6 Minimum negative cases

| Condition | Required result |
|---|---|
| Verifier and candidate are the same natural person | FAIL |
| Verifier personally approved or merged PR #418 | FAIL |
| Verifier directly reviews own material governance decision | FAIL |
| Institution or its signer cannot be independently identified/authorized | INSUFFICIENT_EVIDENCE |
| Owner alone declares verifier independent | INSUFFICIENT_EVIDENCE |
| Material COI unresolved; independent trust evidence absent | INSUFFICIENT_EVIDENCE |
| Attestation does not match the decision/evidence version | INSUFFICIENT_EVIDENCE |
| Material change after attestation without reassessment | REASSESSMENT_PENDING |
| All mandatory controls verified and attested | PASS MAY BE GRANTED |

## 6. Personal non-participation — preserved ASP-SR-03

The assessor candidate's non-participation assessment must distinguish: a dated self-declaration, independent corroboration, contrary evidence, unverifiable areas and reasoned conclusions. Review natural-person identity and multi-account/delegation risks. Mere absence of their name in GitHub activity is not proof. Substantive unresolved contradictions result in NON_PARTICIPATION_NOT_ESTABLISHED and prevent positive eligibility. No passwords, session cookies, SSH private keys or 2FA secrets may be demanded.

## 7. COI and COI-B effectiveness — preserved ASP-SR-04

- **COI-A:** non-manageable direct self-review or a materially outcome-dependent interest → INELIGIBLE; no owner waiver.
- **COI-B:** potentially manageable relationship → document exact relationship, why it is not COI-A, proposed safeguards, independent effectiveness assessment by a suitably independent party, accountable evaluator, conditions, recheck triggers and residual uncertainties. Without credible independent effectiveness verification: INSUFFICIENT_EVIDENCE.
- **COI-C:** no material conflict identified only after adequate disclosure and reasonable checks; never equate missing information with COI-C.
- **UNDETERMINED:** insufficient or contradictory disclosure → INSUFFICIENT_EVIDENCE.

## 8. Professional qualifications

Evaluate relevant evidence of GitHub PR/review/merge provenance, governance authorization boundaries, distinction among fact/claim/inference, COI analysis, documentary reporting and information security limits. Actual role-related experience or work samples may be appropriate; title or certificate alone is not dispositive. Each material competence is SUFFICIENT / INSUFFICIENT / NOT_ESTABLISHED.

## 9. Eligibility decision and attestation — preserved ASP-SR-05

A positive assessor decision requires PASS for privacy preflight, TDA trust, identity, non-participation and relevant COI checks; all essential qualifications must be sufficient and the final attestation valid for its specific natural person, role, scope and evidence version. Results: ELIGIBLE / INELIGIBLE / INSUFFICIENT_EVIDENCE. UNKNOWN != PASS.

In addition to §5.5's Trust Attestation, a later eligibility decision must reference a versioned eligibility decision document and digest or immutable reference; evidence manifest ID/version/cutoff; signer's identity, method and timestamp; verified attestation status. A valid Trust Attestation does not by itself constitute the assessor's final eligibility assessment.

## 10. Appointment Binding Gate — preserved ASP-SR-02

A later appointment requires the **identical verified natural person**, scope consistent with the approved eligibility assessment, a current and verified attestation, no unresolved material COI change, and a recorded separate owner appointment decision. Required outcome: APPOINTMENT_BINDING = PASS / BLOCKED. Any mismatch blocks appointment; owner approval alone does not override the mismatch. Record candidate ID, eligibility decision reference, sign-off reference, verified scope, decision maker, timestamp and gate result.

**Appointment never confers** GitHub write/merge rights, CI permissions, DB connections, migrations, secrets access or Render/deployment authority.

## 11. Suspension and reassessment — preserved ASP-SR-06

New substantive involvement, material COI, disputed identity, changed scope/person, invalidated attestation, failed COI-B safeguard or newly contradictory evidence triggers REASSESSMENT_PENDING. During reassessment: APPOINTMENT_VALIDITY = SUSPENDED_FOR_REVIEW; NEW_REVIEW_ACTIVITY = BLOCKED_WITHIN_CC04_PROCESS; FINAL_SIGN_OFF = BLOCKED. If a confirmed disqualifying conflict emerges: INELIGIBLE / NOT_VALID_FOR_CONTINUATION. Preserve original documentary history under applicable privacy controls. These status rules do not themselves technically revoke access.

## 12. Evidence, sign-off and closure boundaries

Following a separately appointed eligible assessor, a **different** natural-person reviewer candidate may be assessed. Any eligible reviewer requires separate appointment and independent historical review; subsequent signature and owner disposition remain distinct. No stage retrospectively authorizes the PR #418 merge or closes Issue #340.

No actual reviewer, assessor or TDA has been established in this record. The actual privacy preflight, personal-data collection, identity verification, COI check, signature, manifest verification, independent historical review and CC-08 final sign-off are all NOT PERFORMED.

## 13. Owner decision provenance and limits

The owner expressly accepted the CC-04 contract V1.1 and the Assessor Selection Procedure V1.2 in the project conversation on **2026-11-01**. The decision is also memorialized in [Issue #340 comment 6560513948](https://github.com/13640226/VORNEQ/issues/340#issuecomment-6560513948).

This **documentation-only Draft PR** provides a proposed repository file for formal review and must remain **unmerged**. A GitHub PR review of this document is not the independent historical PR #418 review and cannot satisfy CC-04 or CC-08 merely by marking APPROVED.

## 14. Preserved controls and NO-GO state

~~~text
PROJECT = VORNEQ
PRIORITY = P0

CC04_CONTRACT_V1_1 = OWNER_ACCEPTED
ASSESSOR_SELECTION_PROCEDURE_V1_2 = OWNER_ACCEPTED_DOCUMENTARY_ONLY
V1_2_GITHUB_DOCUMENT = DRAFT_PR_PENDING_REVIEW

TRUST_DECISION_AUTHORITY = NOT_ESTABLISHED
TRUST_GATE_ACTUAL_VERIFICATION = NOT_PERFORMED
ASSESSOR_CANDIDATE = NOT_NOMINATED
ASSESSOR_ELIGIBILITY = NOT_ESTABLISHED
ASSESSOR_APPOINTMENT = NONE
REVIEWER_ELIGIBILITY = NOT_ESTABLISHED
REVIEWER_APPOINTMENT = NONE
CC04_INDEPENDENT_REVIEW = NOT_PERFORMED
CC08_INDEPENDENT_SIGN_OFF = NOT_PERFORMED
OWNER_FINAL_DISPOSITION = PENDING
ISSUE340_FINAL_CLOSURE = BLOCKED

PR418_GOVERNANCE_DEVIATION = CONFIRMED
PRE_MERGE_AUTHORIZATION = NOT_ESTABLISHED
HUMAN_OPERATOR = NOT_INDEPENDENTLY_VERIFIED

STOP_340 = ACTIVE
HARD_STOP = ACTIVE
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
DATABASE_GO = NO
MIGRATION_GO = NO
WORKFLOW_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
NEW_SOURCE_ACCESS = NONE
NEW_PERSONAL_DATA_COLLECTION = NONE
NEW_EXECUTION_AUTHORIZATION = NONE

FINAL_STATE = SAFE_HOLD / NO_GO
~~~

**PROPOSAL ≠ APPROVAL ≠ EXECUTION_AUTHORIZATION ≠ VERIFIED_EVIDENCE.**
