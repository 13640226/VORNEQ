# VORNEQ — AC-CI2-10: Rollback, Fehlerbehandlung und Audit abgelehnter Anfragen (V1)

| Feld | Wert |
| --- | --- |
| DOCUMENT_ID | VORNEQ_AC_CI2_10_ROLLBACK_FAILURE_DENIAL_AUDIT_V1 |
| DATUM | 2026-11-04 |
| STATUS | DOCUMENTARY / OWNER-AUTHORED |
| BEZUG | AC-CI2-10 in `docs/governance/ci-security-architecture-v2.0.md` (Branch `docs/ci-security-architecture-v2-20261101`) |
| GENEHMIGUNG DER ABLAGE | OWNER-AUTH-CHANGE-DOC-AC-CI2-10-01 (Eigentümer 13640226) |
| FINAL_STATE | SAFE_HOLD / NO_GO |

Geltungsbereich: GitHub-Actions-Workflows des Repositorys 13640226/VORNEQ und Deploys des Render-Webdienstes VORNEQ. Dieses Dokument beschreibt Abläufe; es ist keine Freigabe für irgendeine Ausführung.

## 1. Rollback

| Änderung | Rollback-Verfahren | Wer | Nachweis |
| --- | --- | --- | --- |
| Workflow-Änderung, noch nicht gemergt | PR ohne Merge schließen; Branch bleibt als Nachweis erhalten | Eigentümer | Begründung im PR und im Governance-Dokument |
| Workflow-Änderung, bereits gemergt | Neuer PR mit `git revert` des betreffenden Commits; derselbe Genehmigungs- und CI-Weg | Eigentümer, mit neuer Änderungsgenehmigung | Original-SHA und Revert-SHA |
| Deploy auf Production | In Render: Events → letzter funktionierender Deploy → Rollback; Auto-Deploy bleibt aus | Eigentümer | Vorab: Ziel-SHA, Datum, Begründung (Kontrolle aus GOV_BREACH_01) |
| Secret oder Environment | Wert neu aus der Quelle (Render-Dashboard) setzen; kein Wert in Logs oder Dokumenten | Eigentümer | Nur Secret-Name und Zeitpunkt |
| Netzwerkregeln der Datenbanken | Vorherige Regel nur mit schriftlicher Genehmigung wiederherstellen; Standard: geschlossen | Eigentümer | Alte und neue Regel |

Regel: Ein Rollback umfasst niemals `push --force` auf `main`, das Umschreiben der Historie oder das Umgehen des Rulesets `main-protection`.

## 2. Fehlerbehandlung (Fail-Closed)

- **Roter Check im PR:** kein Merge bis zur Behebung der Ursache. Ein erneuter Lauf ist nur zulässig, wenn die Ursache dokumentiert ist, nicht um zufällig Grün zu erhalten.
- **Fehlender oder unvollständiger Check:** gilt als rot. Manuell gesetzte oder simulierte Statuswerte werden nicht akzeptiert.
- **Datenbank-Zielwächter** (`scripts/db_target_guard.py` mit `ALLOW_PRODUCTION_TARGET: 'false'`): jeder Fehler oder jedes unklare Ergebnis bedeutet vollständigen Abbruch des Workflows, ohne Übergang zu schreibenden Schritten.
- **Fehlendes Secret:** der Workflow bricht mit „not configured“ ab; Standard- oder Ersatzwerte sind unzulässig.
- **Fehlgeschlagener Deploy:** Render hält die vorherige Version live; ein neuer Versuch nur mit derselben SHA-Genehmigung oder einer neuen.
- **Unbekannter Fehler in einem Schritt:** Stopp, Dokumentation, keine automatische Korrekturmaßnahme.

## 3. Audit abgelehnter Anfragen

Jede abgelehnte oder gestoppte Anfrage bzw. Aktion wird mit folgenden Feldern dokumentiert:

| Feld | Beschreibung |
| --- | --- |
| DATE | Zeitpunkt |
| ACTOR | Wer angefragt oder ausgeführt hat (Konto) |
| REQUEST | Was (Merge, Deploy, Workflow, Einstellungsänderung) |
| DENIED_BY | Regel oder Kontrolle (z. B. G1, Environment-Schutz, DB-Zielwächter, Ruleset) |
| EVIDENCE | Link zu Run, PR oder Render-Ereignis |
| FOLLOW_UP | Nächster Schritt oder „keiner“ |

Ereignisquellen, die im Audit berücksichtigt werden müssen: abgelehnte Freigaben des Environments `production` in GitHub Actions, rote Checks in PRs, Render-Events sowie Abbrüche des DB-Zielwächters in Workflow-Logs.

### Beispiele vom 2026-11-04

| DATE | ACTOR | REQUEST | DENIED_BY | EVIDENCE | FOLLOW_UP |
| --- | --- | --- | --- | --- | --- |
| 2026-11-04 10:54 | Eigentümer (Chat) | Konto `thedivanandthesword` als unabhängigen Reviewer eintragen | Unabhängigkeitskriterien (Übereinstimmung mit der Commit-E-Mail des Eigentümers) | Governance-Dokument | Danach Entscheidung G-CRITERIA-V2 |
| 2026-11-04 11:25 | Eigentümer (lokales Skript) | Verschieben der Secrets auf Environment-Ebene | Fail-Closed-Prüfung im Skript (leerer Wert für `STAGING_DATABASE_URL`) | Terminalausgabe; nichts gelöscht | Wert manuell gesetzt, später entfernt |

## Grenzen

- Dieses Dokument hebt weder HARD_STOP noch eine andere Sperre auf und ist keine unabhängige Verifizierung.
- Es ändert keine Workflows, Required Checks, Rulesets, Secrets oder Environments.

**HARD_STOP = ACTIVE** · **C02 = OPEN_CRITICAL** · **GATES_OPENED = 0** · **FINAL_STATE = SAFE_HOLD / NO_GO**
