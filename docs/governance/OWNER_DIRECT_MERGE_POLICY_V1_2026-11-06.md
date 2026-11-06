# VORNEQ — Owner Direct Merge Policy V1 (Prospective Addendum)

**Decision ID:** OWNER-DEC-DIRECT-MERGE-NO-INDEPENDENT-REVIEW-01  
**Date:** 2026-11-06  
**Repository:** 13640226/VORNEQ  
**Owner:** 13640226  
**Status:** OWNER-DIRECTED / PROSPECTIVE POLICY ADDENDUM  
**Source of decision:** https://github.com/13640226/VORNEQ/issues/340#issuecomment-6682465726

## 1. Owner's decision

For ordinary future pull requests in VORNEQ, the repository owner `13640226` may merge their own eligible pull requests without a mandatory independent reviewer, second account approval, or independent-review sign-off.

Independent review is optional unless a separate, explicit and currently applicable rule is adopted for a specifically defined change. An owner-controlled or shared account must never be represented as an independent reviewer.

## 2. Supersession of prior review prerequisites

This prospective owner decision replaces the blanket independent-review prerequisite described in the historical document `docs/governance/OWNER_DEC_REVIEWER_REMOVAL_01.md` and related historical reviewer instructions **for future ordinary owner PR merges**, insofar as the owner has authority to change those policies.

The historical document remains intact as evidence of what was required or decided at the time. References in that document to a then-existing `main-protection` ruleset, mandatory PR checks, or blanket SAFE_HOLD describe the historical state; they are not current GitHub configuration evidence.

This addendum does not retroactively authorize any historical merge, resolve a disputed governance hierarchy, or claim to amend inaccessible original charters.

## 3. Technical state observed on 2026-11-06

- Repository rulesets API returned an empty list `[]`.
- Branch `main` API reported `protected=false`.
- Branch protection summary reported `enabled=false` and required status checks `off`.
- Ruleset `main-protection` (ID 22881408) was removed by the owner, not by this document.

These observations are time-bound and must be rechecked if GitHub settings change. Merge conflicts and other GitHub restrictions can still block a PR.

## 4. Separation of review policy from security evidence

- `C02`, `SC_07`, and `GOV_BREACH_01` remain historical/open findings until separately resolved with appropriate evidence.
- No owner sign-off may be described as an independent verification.
- This addendum does not change Render, production secrets, database permissions, migrations, or deployment configurations.
- This addendum is not a release-safety assessment or proof that any PR is safe to merge.

## 5. Operating convention

For an owner merge, record the PR number and exact head commit SHA in the PR or linked issue where practical. Run relevant tests and security checks for the change, but do not present these recommendations as GitHub-required approvals when no such protection is configured.

## 6. Scope of this commit

Documentation only. No GitHub ruleset, workflow, application code, production environment, database, secret, CI run, merge, or deploy is modified by this document.

**OWNER_DIRECT_MERGE_WITHOUT_INDEPENDENT_REVIEW = POLICY_ACCEPTED**  
**GITHUB_MAIN_PROTECTION = NOT_PRESENT_AT_LAST_CHECK**  
**HISTORICAL_FINDINGS = PRESERVED**  
**PRODUCTION_SECURITY_VERIFIED = NO**

## 7. Clarification — independent-review references in merge and CI governance (2026-11-06)

The owner's prospective decision applies to ordinary owner-initiated PR merges and the **human reviewer eligibility/sign-off requirement** in historical governance documents. In particular, the independent-human-signoff clause in `docs/governance/ci-security-architecture-v2.0.md` AC-CI2-09 is superseded **for future ordinary owner PR merge authorization** by the owner's own documented decision bound to the relevant PR/head SHA where a signed authorization record is required. The historical frozen CI architecture remains unchanged as evidence of its original baseline; this addendum is the prospective policy interpretation, not a claim that the frozen source text was edited.

This removes the requirement to obtain an independent human reviewer or approval as a condition of an ordinary owner merge. It does **not** waive actual source/test evidence, authorization identity, required runtime isolation, or safety controls for production credentials and databases. The existing `.github/workflows/merge-authorization.yml` is an **owner-authorization SHA check**, not an independent-review gate, and is not disabled by this policy. Its presence as a workflow does not by itself imply that GitHub requires its status for merging.

No other historical reviewer report is deleted or relabeled. Security-specific or incident-specific claims of independent verification remain unverified unless supported by genuine evidence.
