# VORNEQ — AC-CI2-08: Nachweisregister der CI-Läufe vom 2026-11-04 (V1)

| Feld | Wert |
| --- | --- |
| DOCUMENT_ID | VORNEQ_AC_CI2_08_RUN_EVIDENCE_LEDGER_20261104_V1 |
| ERHOBEN | 2026-11-04, ca. 23:10 (Europe/Berlin), nur lesend über GitHub API |
| GENEHMIGUNG DER ABLAGE | OWNER-AUTH-CHANGE-DOC-AC-CI2-08-01 (Eigentümer 13640226) |
| BEWERTUNG | Schriftliche Bewertung durch den Eigentümer gemäß AC-CI2-09 (geändert) steht aus |
| FINAL_STATE | SAFE_HOLD / NO_GO |

Zweck: dauerhafte, SHA-gebundene Verankerung der CI-Ergebnisse (AC-CI2-08, Invariante 8), da GitHub-Actions-Logs nur befristet aufbewahrt werden. Das Register enthält keine Secrets.

## Übersicht je PR

| PR | Head-SHA | Inhalt | Jobs | erfolgreich | Status |
| --- | --- | --- | --- | --- | --- |
| #506 | `aab8796f8ddbae32c3aa3d0a1a4dc2d3bafa4fd9` | Actions auf SHA, postgres auf Digest; pip-audit ohne Installation | 7 | 7 | Draft, offen |
| #507 | `a0c02fc6d2cdb3b0491f1c8c568d7596e335cf2c` | Dokumentation AC-CI2-10 | 7 | 7 | Draft, offen |
| #508 | `74ef1339b02671e9ffe7e569146fcc7c9de0ecb5` | test-Jobs als UID 1001 ohne sudo im gepinnten Container (CI-01) | 7 | 7 | Draft, offen |
| #509 | `ebc5aea458dba68c73c060a5182aaeac1c7d5c36` | Dependency-Audit auf gehashter Lock-Datei (AC-CI2-03) | 7 | 7 | Draft, offen |
| #511 | `5393805eaa47c9fc79a39b90f6ece42a68ec383e` | Dokumentation OWNER-DEC-REVIEWER-REMOVAL-01 | 7 | 7 | Draft, offen |
| #512 | `d1e538b5911cac18fa28aa493a2a409ac17f94ce` | Wegwerf-PostgreSQL isoliert, Identitaetspruefung (CI-03) | 7 | 7 | Draft, offen |
| #513 | `e69c1fd6a545cb18332d7da6d21821ff3b6eb72c` | Projektcode ohne Internet (CI-02) | 7 | 7 | Draft, offen |
| #514 | `312b1f13fb03c28182910c3a4950d758c77f387a` | quality-verification ohne Root, sudo und Internet | 7 | 7 | Draft, offen |

## Einzelnachweise (Run und Job)

Alle Läufe: event = `pull_request`, actor = `13640226`, Repository = `13640226/VORNEQ`, App = GitHub Actions.

| PR | Head-SHA (kurz) | Workflow | Run-ID | Job | Ergebnis |
| --- | --- | --- | --- | --- | --- |
| #506 | `aab8796f8ddb` | Backup Restore Rehearsal | 41817792900 | postgres-backup-restore | success |
| #506 | `aab8796f8ddb` | CI | 41817792943 | test (3.11) | success |
| #506 | `aab8796f8ddb` | CI | 41817792943 | test (3.12) | success |
| #506 | `aab8796f8ddb` | CI | 41817792943 | test-postgres (3.11) | success |
| #506 | `aab8796f8ddb` | CI | 41817792943 | test-postgres (3.12) | success |
| #506 | `aab8796f8ddb` | Global Quality Verification | 41817793006 | quality-verification | success |
| #506 | `aab8796f8ddb` | Security Audit | 41817792976 | dependencies | success |
| #507 | `a0c02fc6d2cd` | Backup Restore Rehearsal | 41818532751 | postgres-backup-restore | success |
| #507 | `a0c02fc6d2cd` | CI | 41818532724 | test (3.11) | success |
| #507 | `a0c02fc6d2cd` | CI | 41818532724 | test (3.12) | success |
| #507 | `a0c02fc6d2cd` | CI | 41818532724 | test-postgres (3.11) | success |
| #507 | `a0c02fc6d2cd` | CI | 41818532724 | test-postgres (3.12) | success |
| #507 | `a0c02fc6d2cd` | Global Quality Verification | 41818532743 | quality-verification | success |
| #507 | `a0c02fc6d2cd` | Security Audit | 41818532719 | dependencies | success |
| #508 | `74ef1339b026` | Backup Restore Rehearsal | 41820654079 | postgres-backup-restore | success |
| #508 | `74ef1339b026` | CI | 41820653953 | test (3.11) | success |
| #508 | `74ef1339b026` | CI | 41820653953 | test (3.12) | success |
| #508 | `74ef1339b026` | CI | 41820653953 | test-postgres (3.11) | success |
| #508 | `74ef1339b026` | CI | 41820653953 | test-postgres (3.12) | success |
| #508 | `74ef1339b026` | Global Quality Verification | 41820654012 | quality-verification | success |
| #508 | `74ef1339b026` | Security Audit | 41820654037 | dependencies | success |
| #509 | `ebc5aea458db` | Backup Restore Rehearsal | 41838968737 | postgres-backup-restore | success |
| #509 | `ebc5aea458db` | CI | 41838968649 | test (3.11) | success |
| #509 | `ebc5aea458db` | CI | 41838968649 | test (3.12) | success |
| #509 | `ebc5aea458db` | CI | 41838968649 | test-postgres (3.11) | success |
| #509 | `ebc5aea458db` | CI | 41838968649 | test-postgres (3.12) | success |
| #509 | `ebc5aea458db` | Global Quality Verification | 41838968789 | quality-verification | success |
| #509 | `ebc5aea458db` | Security Audit | 41838968747 | dependencies | success |
| #511 | `5393805eaa47` | Backup Restore Rehearsal | 41902246982 | postgres-backup-restore | success |
| #511 | `5393805eaa47` | CI | 41902246927 | test (3.11) | success |
| #511 | `5393805eaa47` | CI | 41902246927 | test (3.12) | success |
| #511 | `5393805eaa47` | CI | 41902246927 | test-postgres (3.11) | success |
| #511 | `5393805eaa47` | CI | 41902246927 | test-postgres (3.12) | success |
| #511 | `5393805eaa47` | Global Quality Verification | 41902246914 | quality-verification | success |
| #511 | `5393805eaa47` | Security Audit | 41902247021 | dependencies | success |
| #512 | `d1e538b5911c` | Backup Restore Rehearsal | 41904003910 | postgres-backup-restore | success |
| #512 | `d1e538b5911c` | CI | 41904003993 | test (3.11) | success |
| #512 | `d1e538b5911c` | CI | 41904003993 | test (3.12) | success |
| #512 | `d1e538b5911c` | CI | 41904003993 | test-postgres (3.11) | success |
| #512 | `d1e538b5911c` | CI | 41904003993 | test-postgres (3.12) | success |
| #512 | `d1e538b5911c` | Global Quality Verification | 41904003915 | quality-verification | success |
| #512 | `d1e538b5911c` | Security Audit | 41904003908 | dependencies | success |
| #513 | `e69c1fd6a545` | Backup Restore Rehearsal | 41910029519 | postgres-backup-restore | success |
| #513 | `e69c1fd6a545` | CI | 41910029447 | test (3.11) | success |
| #513 | `e69c1fd6a545` | CI | 41910029447 | test (3.12) | success |
| #513 | `e69c1fd6a545` | CI | 41910029447 | test-postgres (3.11) | success |
| #513 | `e69c1fd6a545` | CI | 41910029447 | test-postgres (3.12) | success |
| #513 | `e69c1fd6a545` | Global Quality Verification | 41910029307 | quality-verification | success |
| #513 | `e69c1fd6a545` | Security Audit | 41910029249 | dependencies | success |
| #514 | `312b1f13fb03` | Backup Restore Rehearsal | 41919123830 | postgres-backup-restore | success |
| #514 | `312b1f13fb03` | CI | 41919124246 | test (3.11) | success |
| #514 | `312b1f13fb03` | CI | 41919124246 | test (3.12) | success |
| #514 | `312b1f13fb03` | CI | 41919124246 | test-postgres (3.11) | success |
| #514 | `312b1f13fb03` | CI | 41919124246 | test-postgres (3.12) | success |
| #514 | `312b1f13fb03` | Global Quality Verification | 41919123834 | quality-verification | success |
| #514 | `312b1f13fb03` | Security Audit | 41919123715 | dependencies | success |

## Laufzeitbelege zur Isolation (aus Job-Logs)

| PR / Run | Job | Beleg |
| --- | --- | --- |
| #512 / 41904003993 | test-postgres (3.11, 3.12) | `identity: vorneq|vorneq|172.18.0.3` vor `migrate` |
| #512 / 41904003910 | postgres-backup-restore | `identity: source_db|vorneq|172.18.0.3` vor dem ersten Schreiben |
| #513 / 41910029447 | test (3.11, 3.12) | `egress blocked: pypi.org, github.com unreachable`; `Ran 792 tests` |
| #513 / 41910029447 | test-postgres (3.11, 3.12) | `egress blocked`; `identity: vorneq|vorneq|172.18.0.2`; `Ran 792 tests` |
| #513 / 41910029519 | postgres-backup-restore | `egress blocked: pypi.org unreachable`; `identity: source_db|vorneq|172.18.0.2`; `backup/restore rehearsal OK` |

## Grenzen

- Das Register belegt CI-Ergebnisse; es ist keine Freigabe für Merge oder Deploy und öffnet kein Gate.
- Die Verifizierung von #514 auf Laufzeitebene (Logs) ist in diesem Register nur als Job-Ergebnis erfasst.
- HARD_STOP = ACTIVE · C02 = OPEN_CRITICAL · GOV_BREACH_01 = OPEN · GATES_OPENED = 0.
