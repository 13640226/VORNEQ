# VORNEQ — C02 Runtime Database Identity Verification Contract V1.2

Document ID: VORNEQ_C02_RUNTIME_DB_IDENTITY_VERIFICATION_CONTRACT_V1_2
Incident: GOV-BREACH-01
Scope: DOCUMENTARY_ONLY
Owner acceptance: REPORTED_IN_CONVERSATION; independent attestation NOT_VERIFIED
Baseline: proposed owner-frozen documentary baseline
Status: DOCUMENTARY_DRAFT / OWNER_REPORTED_ACCEPTANCE
Implementation: NOT_AUTHORIZED

## Purpose and evidence baseline
Prove separately (a) configured database target, (b) current runtime connection identity, (c) historical runtime connection identity at incident time, and (d) production/staging isolation. No one claim implies another. Render resource existence and presence of DATABASE_URL were observed, but the actual binding and runtime identities remain UNKNOWN. No SQL statement, absence of writes, or migration absence is proven by available logs.

Expected inventory (documentary identifiers only):
- Production web service: srv-dadn07eq1p3s73eccau0
- Staging web service: srv-dadm6fv40ujc73c2dik0
- Production DB resource: dpg-dagru1h42hec73eqr960-a
- Staging DB resource: dpg-dbd7tqom7kps73c4dolg-a
- Incident merge commit: 8e1bbe97966b6f9ea137d5aa5a6a30a5cf8fdd4a

## Non-equivalence and authority
PROPOSAL != APPROVAL != EXECUTION_AUTHORIZATION != VERIFIED_EVIDENCE.
CONFIGURATION_MATCH != RUNTIME_PROOF.
CURRENT_RUNTIME_PROOF != HISTORICAL_PROOF.
DATABASE_CONNECTION != DATABASE_WRITE.
DOCUMENTARY_ACCEPT != MERGE_GO or DEPLOY_GO.
UNKNOWN is never converted into PASS. A PASS never automatically authorizes a write, migration, merge, restart, or deploy.

## Trust boundaries (SR-01 / AC-13)
TB-01 GitHub source: content at pinned commit only.
TB-02 Render control plane: observed service/configuration/deploy metadata only.
TB-03 Django runtime: identity of a specific live process/instance, not self-attested as independent proof.
TB-04 PostgreSQL runtime: database-side identity evidence requiring independent mapping to Render resource ID.
TB-05 Independent verifier: separately appointed, qualified, conflict-screened reviewer.
Evidence crossing boundaries requires independently verifiable linkage.

## Secret handling (SR-02 / AC-14)
SECRET_ACCESS, SECRET_PROCESSING, SECRET_DISPLAY, SECRET_EXPORT, DATABASE_URL_EXTRACTION = PROHIBITED under current authorization.
Even hidden-value comparison processes a secret and requires a separately approved scope. No secret in logs, exceptions, CI artifacts, PRs, screenshots, or public evidence. Any future verifier requires a reviewed threat model, minimum privilege, and explicit separate authorization. This document does not prescribe executing such a verifier.

## Attribution contract (DR-F01; AT-01..AT-08; AC-16/17)
AT-01 authoritative Render service ID; AT-02 active deploy ID at observed time; AT-03 full commit SHA mapped to deploy; AT-04 runtime instance/process identity; AT-05 independent instance-to-connection linkage; AT-06 independent connection-to-database-resource mapping; AT-07 UTC observation and collection timestamps; AT-08 integrity and completeness of every link.
PASS iff all eight pass with valid source evidence. Missing evidence => UNKNOWN. Verified mismatch => FAIL; incompatible trustworthy evidence => CONFLICT. Time proximity alone, app=[unknown], or a database name reported by Django alone cannot establish attribution.

## Verification protocol (DR-F02; VP-01..VP-08; AC-15)
Logical non-secret inputs: target service ID, expected database resource ID, target deploy ID, full commit SHA, observation window, explicit authorization scope, verifier ID.
Permitted output fields: verification ID, service/deploy/commit, expected and observed DB resource identities (only when independently mapped), observation UTC, CONFIGURATION/RUNTIME/ATTRIBUTION verdicts, evidence manifest ID, independent review status.
Forbidden output: DATABASE_URL, credentials, tokens, unredacted connection strings.
VP-01 inputs constrained; VP-02 no secret outputs; VP-03 independent identity source; VP-04 reproducible attribution test; VP-05 mismatch => FAIL; VP-06 missing evidence => UNKNOWN; VP-07 deploy/time binding; VP-08 separately authorized reviewer and collection.
A Render resource ID and PostgreSQL-native identity are different namespaces: a documented, independently validated mapping is mandatory. Implementation and runtime verification remain NOT_AUTHORIZED.

## Reviewer independence (DR-F03; IR-01..IR-08; AC-22)
IR-01 explicit owner appointment; IR-02 reviewer not implementer of assessed control; IR-03 conflict-of-interest disclosure; IR-04 relevant technical qualifications; IR-05 reviewable primary evidence; IR-06 power to reject; IR-07 bounded written scope/limitations; IR-08 appointment does not grant access. Acceptance requires verified appointment, independence, qualifications, scope and evidence review. No independent reviewer is verified as appointed by this document.

## Runtime instance coverage (DR-F04; IC-01..IC-06)
IC-01 authoritative inventory of in-scope active instances; IC-02 instance identifiers; IC-03 explicit unverified inventory; IC-04 account for scaling/rollover; IC-05 individual instance verdicts; IC-06 service verdict only when every in-scope instance verified.
Coverage = verified instances / independently established in-scope instances; service-wide PASS requires 100% of a complete inventory within a bounded observation window. Unknown inventory or any unverified instance => UNKNOWN; verified wrong target => FAIL. Point-in-time coverage cannot prove historical continuity.

## Evidence custody (DR-F05; EC-01..EC-08; AC-20/21)
EC-01 named evidence owner; EC-02 approved storage location; EC-03 role-scoped access; EC-04 integrity verification; EC-05 original vs redacted derivative tracked; EC-06 approved retention policy; EC-07 auditable transfers/deletion; EC-08 no secrets in public repository.
Manifest fields: EVIDENCE_ID, INCIDENT_ID, SOURCE_SYSTEM, SOURCE_RESOURCE_ID, EVIDENCE_TYPE, COLLECTION_METHOD, OBSERVED_AT_UTC, COLLECTED_AT_UTC, SERVICE_ID, DEPLOY_ID, COMMIT_SHA, RUNTIME_INSTANCE_ID, DATABASE_RESOURCE_ID, CONTENT_DIGEST, DIGEST_ALGORITHM, REDACTION_STATUS, CHAIN_OF_CUSTODY_STATUS, INDEPENDENT_VERIFICATION_STATUS.
Digest alone does not establish provenance. Custodian, storage, and retention decisions remain pending owner authorization.

## Identity time classes (SR-05 / AC-18)
Configured identity, current runtime identity, historical incident identity are distinct. Current PASS cannot close historical incident analysis. Historical attribution needs service, deploy, DB identity, valid event timestamp and evidence integrity. Missing historical evidence => UNKNOWN.

## Fail-closed (SR-06/07 / AC-19)
Possible verdicts: PASS, FAIL, UNKNOWN, CONFLICT, SECURITY_STOP.
FAIL => stop/escalate; UNKNOWN => stop/wait; CONFLICT => stop/reconcile; SECURITY_STOP => halt collection and assess impact. PASS => record evidence only, not GO. Structural pass counts do not override missing configuration/runtime/independent gates.

## Acceptance mapping
AC-13 trust boundaries; AC-14 secret distinctions; AC-15 runtime proof; AC-16 service/deploy attribution; AC-17 commit/time binding; AC-18 historical/current separation; AC-19 fail-closed; AC-20 evidence integrity; AC-21 custody/retention; AC-22 independent review.
V12-AC-01 attribution testability; V12-AC-02 bounded verification protocol; V12-AC-03 reviewer independence; V12-AC-04 measurable instance coverage; V12-AC-05 evidence custody.
These are DEFINED only, not IMPLEMENTED or VERIFIED.

## Closure gates
C02-CLOSE-01/02 configured production/staging identities; -03/04 actual production/staging runtime identities; -05 isolation; -06 historical incident impact; -07 independent review; -08 explicit authorized closure decision. No automatic closure.

## Frozen safety state
C02=OPEN_CRITICAL; SC_07=OPEN_CRITICAL; STOP_340=ACTIVE; HARD_STOP=ACTIVE.
DATABASE_GO=NO; MIGRATION_GO=NO; MERGE_GO=NO; DEPLOY_GO=NO.
CONFIGURED_DATABASE_IDENTITY=UNKNOWN; CURRENT_RUNTIME_DATABASE_IDENTITY=UNKNOWN; HISTORICAL_RUNTIME_DATABASE_IDENTITY=UNKNOWN; PRODUCTION_STAGING_ISOLATION=NOT_VERIFIED; DATABASE_WRITE_IMPACT=UNKNOWN.
FINAL_STATE=SAFE_HOLD / INCIDENT_INVESTIGATION_ACTIVE.

This is a documentary contract. No runtime evidence was collected and no independent security attestation is implied.
