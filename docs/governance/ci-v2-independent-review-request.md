# Independent security review request — CI V2 candidate

Target: PR #490, exact reviewed HEAD must be re-pinned by the assessor.
Related frozen contract: PR #489. PRs #482, #483, #487 remain separate and unmerged.

## Reviewer eligibility gate
Reviewer must be independent of the repository owner and of implementation authors; an owner-controlled account is not independent. Verify identity, conflicts, access and signed review scope before acceptance. No independent reviewer has been appointed by this document.

## Required read-only review
1. Inspect all changed workflow and shell files against PR #490's exact HEAD; validate shell syntax without running the candidate.
2. Review Docker orchestration host privilege, image digest provenance and absence of build/pull in runtime.
3. Check disposable PostgreSQL initialization, volume lifecycle and cleanup; assess untrusted code DB privileges.
4. Verify no production secrets, inherited tokens, mounted sockets, external network or indirect endpoints reach the application.
5. Confirm that no workflow calls the candidate and no required check is spoofed or bypassed.
6. Confirm that [skip ci] is retained; no check or runtime result may be inferred from static review.
7. Record findings, evidence locations, severity, exact SHA and explicit verdict: CHANGES_REQUIRED / DOCUMENTARY_ACCEPTED / WAIT_FOR_EVIDENCE.

## Unresolved risks
- Privileged Docker daemon on orchestration host; host isolation and daemon attack surface not verified.
- Application image provenance, filesystem/UID compatibility, supply-chain integrity and Django write paths not verified.
- PostgreSQL initialization and clean removal of named volume not runtime verified.
- The declared review run ID is not an independent cryptographic authorization token.
- Runtime 0/10; CI-01 OPEN, CI-02 PARTIAL, CI-03 OPEN.

## Governance
No approval, CI execution, merge, deploy, migration or production access authorized. STOP_340 and HARD_STOP active. SC_07 independent review open. SAFE_HOLD / NO_GO.
