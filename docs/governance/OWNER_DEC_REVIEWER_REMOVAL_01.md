# VORNEQ — OWNER-DEC-REVIEWER-REMOVAL-01: Wegfall des unabhängigen Reviewers

| Feld | Wert |
| --- | --- |
| DECISION_ID | OWNER-DEC-REVIEWER-REMOVAL-01 |
| DATUM | 2026-11-04, 20:55 (Europe/Berlin) |
| ENTSCHEIDER | Eigentümer, GitHub-Konto 13640226 |
| STATUS | OWNER_DECISION / DOCUMENTARY |
| BASIS | origin/main @ 3af035f |
| FINAL_STATE | SAFE_HOLD / NO_GO |

## Wortlaut der Entscheidung (Übersetzung aus dem Persischen)

> Ich, Eigentümer 13640226, (1) hebe das Verbot der Änderung von CC-04 in der Direktive P0_VORNEQ_AUTHENTIC_CHARTER_SOURCE_WAIT_AND_INTAKE_GATE_V1 auf; (2) ändere CC-04 und AC-CI2-09 so, dass die schriftliche Freigabe des Eigentümers mit SHA den unabhängigen Reviewer ersetzt; (3) setze die Anzahl der erforderlichen Approvals im Ruleset auf 0, wobei PR-Pflicht und Required Checks erhalten bleiben. Begründung: Das Projekt ist ein Ein-Personen-Projekt, ein unabhängiger Reviewer ist nicht verfügbar. Das Risiko von Fehlern ohne zweite Prüfung, insbesondere bei C02, nehme ich an.

## Änderungen

### CC-04 (Assessor Selection Procedure V1.2, Issue #340, Kommentar 6560513948)

Ergänzung: Für VORNEQ als Ein-Personen-Projekt tritt an die Stelle eines persönlich unabhängigen Eligibility Assessors die **schriftliche Freigabe des Eigentümers (13640226)**, gebunden an die exakte Commit-SHA, mit Datum und Begründung. Der bisherige Text von CC-04 bleibt als Historie erhalten und wird nicht gelöscht.

### AC-CI2-09 (CI-Sicherheitsarchitektur V2.0)

Bisher: „independently eligible reviewer signs off, not an owner-controlled account.“

Neu: „Check results and evidence are assessed and signed off in writing by the owner (13640226), bound to the exact commit SHA.“

### Ruleset `main-protection` (id 22881408)

Required approvals: 1 → 0. Unverändert: PR-Pflicht, Required Checks `test (3.11)`, `test (3.12)`, `dependencies`, `postgres-backup-restore`, keine Bypass-Akteure. Die Umsetzung erfolgt durch den Eigentümer selbst in den GitHub-Einstellungen.

## Offenlegung

- Der Eigentümer hat am 2026-11-04 bestätigt, dass er die Merges von PR #510 und PR #504 selbst durchgeführt hat. Approve und Merge erfolgten jeweils über das Konto `hamidrezaasadian7-boop` (Abstand 18 bzw. 26 Sekunden). Damit war dieses Konto bei diesen Vorgängen kein unabhängiger Reviewer.
- PR #504 enthält `[skip ci]` im Commit-Titel und verstößt damit gegen `COMMIT_MESSAGE_POLICY_NO_SKIP_CI_V1`.
- Beide Merges erfolgten ohne vorab dokumentierte SHA-Freigabe, während MERGE_GO = NO galt.

## Ersatzkontrolle

Jeder Merge und jeder Deploy auf Production erfordert **vorab** eine schriftliche Freigabe mit exakter Commit-SHA, Datum und Begründung im Governance-Dokument. Ein Merge oder Deploy ohne diese Freigabe gilt als Governance-Abweichung.

## Grenzen

- SC_07 = WAIVED_BY_OWNER. HARD_STOP und C02 bleiben aktiv; diese Entscheidung öffnet kein Gate.
- Die übrigen Aussetzungen aus OWNER-DEC-GOV-CONFLICT-01 bleiben bestehen.
- Diese Entscheidung ist keine unabhängige Verifizierung.

**HARD_STOP = ACTIVE** · **C02 = OPEN_CRITICAL** · **GOV_BREACH_01 = OPEN** · **GATES_OPENED = 0** · **FINAL_STATE = SAFE_HOLD / NO_GO**
