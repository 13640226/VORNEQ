# C02 runtime identity — documentary review and incident evidence ledger

Incident: GOV-BREACH-01. Documentary record only; no new execution or runtime verification.

## Governance incident baseline
PR #467 merged without separate merge authorization despite review approval. Merge commit 8e1bbe97966b6f9ea137d5aa5a6a30a5cf8fdd4a (2026-10-31 16:56:50 UTC). Both web services were observed Live on this commit: staging 17:00:11 UTC, VORNEQ 17:00:43 UTC. Render web logs in 16:55–17:08 UTC did not explicitly show manage.py migrate, but absence of migration or writes is NOT proven. Production DB logs contained connections around deployment, with app=[unknown] and no independently proven web-service attribution. Do not infer correct DB binding from environment grouping or presence of DATABASE_URL.

## V1 — three-layer design
L1 structural metadata, L2 configured destination, L3 actual runtime identity. Review: CORRECTION_REQUIRED.
SR-01 CRITICAL trust boundaries; SR-02 CRITICAL secret-processing ambiguity; SR-03 CRITICAL runtime proof mechanism; SR-04 HIGH evidence provenance; SR-05 HIGH time/deploy linkage; SR-06 HIGH stop behavior; SR-07 MEDIUM weighted acceptance; SR-08 MEDIUM custody. All findings remain OPEN operationally.

## V1.1 — corrections
Documented TB-01..TB-05, secret-access vs processing, runtime evidence requirements, manifest, historical/current distinction, fail-closed decisions, grouped acceptance, custody principles. AC-13..AC-22 DEFINED only. Final documentary review verdict CORRECTION_REQUIRED, with DR-F01 CRITICAL attribution chain; DR-F02 CRITICAL verifier protocol; DR-F03 HIGH reviewer independence; DR-F04 HIGH instance coverage; DR-F05 MEDIUM evidence custody.

## V1.2 — corrected contracts
DR-F01 Attribution: AT-01..AT-08.
DR-F02 Verification protocol: VP-01..VP-08.
DR-F03 Reviewer independence: IR-01..IR-08.
DR-F04 Instance coverage: IC-01..IC-06.
DR-F05 Evidence custody: EC-01..EC-08.
All five are DOCUMENTARY_ADDRESSED, not independently verified or operationally closed. V12-AC-01..05 documented.
Owner subsequently reported DOCUMENTARY_ACCEPT and FROZEN baseline, but independent reviewer appointment, independent attestation and actual repository governance record were not demonstrated by that report. Treat as OWNER_REPORTED_ACCEPTANCE, not ATTESTED_VERIFIED runtime evidence. This PR records documentary content only; it does not ratify the historical unauthorized merge.

## Open questions
Configured production and staging destinations UNKNOWN.
Current runtime database identity UNKNOWN.
Historical incident database identity UNKNOWN.
Production/staging isolation NOT_VERIFIED.
Database-write impact UNKNOWN.
Independent security review PENDING.
C02 and SC_07 OPEN_CRITICAL.

## Authorization boundaries
This documentation-only PR must remain DRAFT. No code/config/workflow changes, database connection, SQL, secrets, migrations, merge, deployment or restart. PR creation != approval != merge authorization. STOP_340 and HARD_STOP remain ACTIVE. DATABASE_GO/MIGRATION_GO/MERGE_GO/DEPLOY_GO=NO. FINAL_STATE=SAFE_HOLD / INCIDENT_INVESTIGATION_ACTIVE.
