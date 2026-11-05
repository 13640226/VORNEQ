# GOV_BREACH_01 — Ursache und Merge-Autorisierungskontrolle (V1)

| Feld | Wert |
| --- | --- |
| DOCUMENT_ID | GOV_BREACH_01_ROOT_CAUSE_AND_MERGE_AUTHORIZATION_CONTROL_V1 |
| Datum | 2026-11-05 |
| Eigentümer | 13640226 |
| Genehmigung | OWNER-DEC-MERGE-AUTH-BOOTSTRAP-01, OWNER-AUTH-BUILD-MERGE-AUTH-01 |
| Status | VORSCHLAG — GOV_BREACH_01 bleibt OPEN bis zur Eigentümerentscheidung |
| Bezug | MERGE_AUTHORIZATION_CONTROLS_CORRECTION_PROPOSAL_V1.md, C02_DOCUMENTARY_REVIEW_HISTORY.md |

PROPOSAL ≠ APPROVAL ≠ EXECUTION_AUTHORIZATION ≠ VERIFIED_EVIDENCE.

## 1. Vorfall

| Zeit (UTC) | PR | Merge-Commit | Beschreibung |
| --- | --- | --- | --- |
| 2026-10-31 18:16 | #468 | `78934c4` | Approve durch hamidrezaasadian7-boop um 18:12, Merge um 18:16, ohne gesonderte Merge-Autorisierung |
| 2026-10-31 16:56 | #467 | `8e1bbe97966b6f9ea137d5aa5a6a30a5cf8fdd4a` | Merge mit Review-Freigabe, aber ohne gesonderte Merge-Autorisierung |

Dasselbe Muster trat am 2026-11-04 bei #510 und #504 erneut auf (Merge über das zweite Konto, laut Eigentümer durch ihn selbst, ohne vorab erfasste Autorisierung).

## 2. Ursache

1. **Keine technische Durchsetzung:** Die Merge-Autorisierung des Eigentümers existierte nur in Chat und Dokumenten. GitHub prüfte ausschließlich Reviews und Status-Checks.
2. **Approve wurde als Merge-Autorisierung behandelt:** Ein Approve eines beliebigen Kontos mit Schreibrecht genügte dem Ruleset.
3. **Keine Funktionstrennung:** Beide Konten liefen auf demselben Laptop.
4. **Fail-Open:** Das Fehlen einer Autorisierung führte nicht zur Ablehnung des Merges.

Auswirkung auf Datenbanken: **UNKNOWN**. Dass die Merges keine Migration oder Schreibzugriffe auslösten, ist nicht belegt; dieser Punkt verbleibt unter C02.

## 3. Kontrolle

Ein verpflichtender Commit-Status `merge-authorization` auf dem Head-SHA jedes PR nach `main`.

- **Autorisierung:** PR-Kommentar des Eigentümers in genau einer Zeile:
  `OWNER-AUTH-MERGE <AUTH-ID> PR #<Nummer> @ <40-stelliger Head-SHA>`
- **Widerruf:** `OWNER-AUTH-REVOKE PR #<Nummer>`
- **Auswertung:** `.github/workflows/merge-authorization.yml` mit `pull_request_target` und `issue_comment`. Beide Trigger führen die Workflow-Datei aus `main` aus; der Evaluator wird per Sparse-Checkout aus `main` geladen. Kein Code des PR wird ausgecheckt oder ausgeführt, keine Secrets.
- **Berechtigungen:** `contents: read`, `pull-requests: read`, `statuses: write`.
- **Entscheidungslogik:** `scripts/merge_authorization.py` (nur Standardbibliothek). Jeder Fehler ergibt `failure` (Fail-Closed).

### Regeln (alle müssen erfüllt sein)

1. Autor ist `13640226`, Typ `User`, `author_association` = OWNER.
2. PR-Nummer im Kommentar = dieser PR.
3. SHA im Kommentar = aktueller Head-SHA (40 Hex-Zeichen, Kleinschreibung).
4. Kommentar wurde nie bearbeitet (`created_at` = `updated_at`).
5. Kein späterer Widerruf des Eigentümers für diesen PR.

Hinweis zu Regel „nach dem letzten Push": Da die Autorisierung an den exakten SHA gebunden ist und ein SHA vor seiner Entstehung nicht bekannt sein kann, ist diese Bedingung durch Regel 3 abgedeckt.

## 4. Abnahmetests

| Test | Szenario | Erwartung | Nachweis |
| --- | --- | --- | --- |
| T1 | Keine Autorisierung | DENY | Unit-Test |
| T2 | Gültige Autorisierung für Head-SHA | ALLOW | Unit-Test |
| T3 | Autorisierung für alten SHA nach neuem Push | DENY | Unit-Test |
| T4 | Anderes Konto, fehlende OWNER-Zuordnung, Bot | DENY | Unit-Test |
| T5 | Kurzer/großgeschriebener SHA, Zusatztext, Zitat | DENY | Unit-Test |
| T6 | Autorisierung für anderen PR | DENY | Unit-Test |
| T7 | Bearbeiteter oder gelöschter Kommentar | DENY | Unit-Test |
| T8 | Widerruf nach Autorisierung | DENY | Unit-Test |
| T9 | API-Fehler, fehlendes Token, fehlerhafte Daten | DENY (Fail-Closed) | Unit-Test |
| T10 | PR ändert den Evaluator | Auswertung mit Version aus `main` | Runtime, offen |
| T11 | Direkter Push nach `main` | Abgelehnt durch Ruleset | Runtime, offen (Ruleset-Änderung nötig) |

Die Unit-Tests stehen in `config/test_merge_authorization.py` und laufen im regulären CI (`manage.py test`).

## 5. Restrisiken

- Admin-Rechte erlauben weiterhin Änderungen am Ruleset.
- Wer Zugriff auf die Sitzung des Eigentümerkontos hat, kann autorisieren.
- Deploys aus dem Render-Dashboard und `workflow_dispatch` werden nicht abgedeckt (G4 bzw. Environment-Reviewer).
- Datenbank-Auswirkung bleibt UNKNOWN (C02).

## 6. Weiteres Vorgehen (jeweils gesonderte Eigentümerautorisierung)

1. Merge dieses PR mit SHA-Autorisierung (Bootstrap-Ausnahme).
2. Ruleset 22881408: `merge-authorization` als Required Check sowie Regeln `deletion` und `non_fast_forward`.
3. Runtime-Nachweise T10 und T11.
4. Eigentümerentscheidung zur Schließung von GOV_BREACH_01.
5. Bewertung von G3.

GATES_OPENED = 2 (G1, G2) · HARD_STOP = ACTIVE · C02 = OPEN_CRITICAL · GOV_BREACH_01 = OPEN
