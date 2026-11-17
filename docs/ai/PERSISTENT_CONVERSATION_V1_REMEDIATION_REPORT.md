# Bericht: Dauerhafte Gespräche V1 — Sicherheits-Nachbesserung und Vorab-Prüfung

- Task: `P0_VORNEQ_AI_PERSISTENT_CONVERSATION_V1_SECURITY_REMEDIATION_AND_FINAL_VALIDATION`
- Baseline: `6170bc46b9bd798b9828ebde14847f7230d93aaf`
- Branch: `feat/ai-persistent-conversation-v1`, nur lokal
- Datum: 2026-11-17
- Es gab **keine** unabhängige Prüfung. Der Bericht stammt vom selben Agenten, der die Änderungen geschrieben hat.
- Es gab keinen Push, keinen PR, keinen Merge, keinen Deploy, keine Staging- oder Production-Migration und keinen bezahlten OpenAI- oder Anthropic-Aufruf.

Begriffe:
- **getestet**: durch echte Ausführung in diesem Durchlauf belegt
- **Code-Review**: nur gelesen
- **nicht verifiziert**: weder getestet noch ausreichend gelesen

## 1. Befunde und Ursachen

| ID | Schwere | Befund | Ursache | Behebung | Status |
|---|---|---|---|---|---|
| P0-1 | P0 | Die Antwort wurde erst nach dem Provider-Aufruf gespeichert. Ein Absturz dazwischen hinterließ keine Spur und konnte zu einem erneuten, bezahlten Aufruf führen. | Es gab keinen dauerhaften Request-Zustand vor dem Aufruf. | `begin_turn` schreibt Frage und `pending`-Zeile vor Quota, Suche, Ledger und Provider. | getestet |
| P0-2 | P0 | Die Dokumentation behauptete eine Transaktion „zusammen mit `recovery.finish`“. `finish()` schreibt aber zuerst Redis und danach den DB-Guard, separat. | Falsche Annahme über Atomarität. | `complete_turn` schreibt Nachricht und Guard-Abschluss in **einer** PG-Transaktion (Alias `default`). Redis kommt danach als best effort. Die Doku ist korrigiert (§11.2). | getestet + Doku |
| P0-3 | P0 | Ein Replay nach Verlust des Redis-Ergebnisses konnte keinen Zustand liefern. | Das Ergebnis lag nur in Redis. | Replay aus der endgültigen PG-Zeile (`stored_response`, `replayed: true`). | getestet |
| P0-4 | P0 | Ein Speicherfehler nach dem Provider-Aufruf meldete trotzdem Erfolg. | `persisted` war nicht unterscheidbar. | Flag `persisted: false` in der Antwort plus Hinweis in der Oberfläche. Ein Replay ruft den Provider nicht erneut auf. | getestet (API); UI: Code-Review |
| P0-5 | P0 | Hängende `pending`-Zeilen ohne Auflösung. | Es fehlte ein Abgleich. | `ai_conversations_reconcile`: Bericht oder `--apply`; aus dem Cache oder als `uncertain`; Ledger-Bericht nur lesend. | getestet |
| P1-1 | P1 | Die Pilot-Policy galt nur beim Anlegen, nicht beim Fragen. | Die Prüfung fehlte in `conversation_message_view`. | `may_start` wird zusätzlich zu `_may_ask` geprüft. Der neue Test hat die Lücke gefunden. | getestet |
| P1-2 | P1 | Es gab keinen Pilot-Zugang unabhängig vom Flag. | – | `VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY` (Standard `allowlist`, leer = niemand) und `…_ALLOWED_USER_IDS`. | getestet |
| P1-3 | P1 | Ein Provider-Timeout wurde als normaler Fehler behandelt. | Der Fall „Ergebnis ungewiss“ fehlte. | Status `uncertain`. | getestet |
| P1-4 | P1 | Folgefragen ohne eigene Stichwörter fanden keine Quelle. | Die Suche nutzte nur die aktuelle Frage. | Deterministische Anreicherung, per Flag **aus**, gemessen (§4). | getestet + gemessen |
| P1-5 | P1 | Der Purge war bei DB-Fehlern nicht robust. | – | `CommandError` ohne Teil-Löschung, mit `--dry-run`. | getestet (bestehende Tests) |
| P2-1 | P2 | `ai_msg_conv_seq_idx` doppelt den Unique-Index. | Generierte Migration. | Dokumentiert, nicht geändert. | offen |
| P2-2 | P2 | Der Ledger-Abgleich ist nur eine Obergrenze, weil er `ask-global/`-Reservierungen mitzählt. | Es gibt keinen Fremdschlüssel über DB-Aliase hinweg. | Dokumentiert. | offen |

## 2. Geänderte Dateien (gegen `6170bc46`)

- Kern:
  - `apps/ai_core/models.py`
  - `migrations/0003_conversation.py` (neu generiert, nie angewendet)
  - `request_recovery.py`: nur neue Funktionen, `finish()` unverändert
  - `conversations/service.py`, `repository.py`, `context.py`
  - `views_conversations.py`, `views_global.py`
  - `engine/global_grounded.py`, `engine/evidence_ranking.py`
  - `providers/openai_responses.py`, `budgeted_provider.py`
- Befehle: `ai_conversations_purge`, `ai_conversations_reconcile` (neu)
- Oberfläche: `chat_page.py`, `chat_strings.py`, `templates/ai_core/chat.html`, `assets/js/phase-c-chat.js`, `assets/css/phase-c-chat.css`
- Konfiguration: `config/settings.py`. Nur neue Schalter, alle standardmäßig aus oder restriktiv; keine Production-Werte geändert.
- Tests: `test_conversations_v1.py`, `test_conversations_recovery.py`, `test_conversations_ui.py`, `test_conversations_remediation.py` (neu, 19 Tests)
- Doku: `docs/ai/PERSISTENT_CONVERSATION_V1_DESIGN.md` (§6 korrigiert, §11 neu) und dieser Bericht

## 3. Testergebnisse (echte Ausführung)

Umgebung: Linux-Container, Python 3.13.18, Django 5.2, offline (Sockets und OpenAI-Client blockiert, Suche und Modell synthetisch).

| TEST | DATENBANK | PASSED | FAILED | SKIPPED | DAUER | ERGEBNIS |
|---|---|---|---|---|---|---|
| Python-Syntax (`py_compile`, geänderte Dateien) | – | alle | 0 | 0 | <1 s | PASSED |
| `manage.py check` | – | 0 Probleme | 0 | – | <5 s | PASSED |
| `makemigrations --check --dry-run` | – | „No changes detected“ | 0 | – | <5 s | PASSED |
| Migrationsplan `sqlmigrate ai_core 0003` | PostgreSQL 16.15 | 14 DDL | – | – | – | geprüft |
| Migration vorwärts → `0002` → vorwärts | PostgreSQL 16.15, Wegwerf-DB | 3 Schritte | 0 | – | – | PASSED |
| Nachbesserungstests (`test_conversations_remediation`) | SQLite | 17 | 0 | 2 (nur PG) | 2,4 s | PASSED |
| Nachbesserungstests inkl. Nebenläufigkeit | PostgreSQL 16.15 | 19 | 0 | 0 | 4,4 s | PASSED |
| Gesprächstests gesamt (4 Dateien) | SQLite | 51 | 0 | 2 | 9,0 s | PASSED |
| Gesamtsuite | SQLite | 1649 | 0 | 57 | 128,6 s | PASSED (1706 ausgeführt) |
| Gesamtsuite | PostgreSQL 16.15 | 1694 | 0 | 12 | 173,9 s | PASSED (1706 ausgeführt) |
| JS-Syntax (`node --check phase-c-chat.js`) | – | 1 | 0 | 0 | <1 s | PASSED |
| Browser-E2E (Playwright/Chrome, fa, 1440 + 390 px, Pilot `allowlist`+`1`) | SQLite (lokal) | 1 Ablauf | 0 | 0 | 14 s | PASSED |

Nach dem ersten Lauf der neuen Tests gab es einen Fehlschlag (`503 != 403`). Ursache war die fehlende Pilot-Prüfung in der Nachrichten-Route (P1-1). Nach der Korrektur liefen alle oben genannten Läufe.

Abdeckung der neuen Tests:
- **A Persistenz:**
  - getestet: 50 Nachrichten, Logout/Login, neue Session, geschlossene DB-Verbindungen (bestehende Tests); Redis-Verlust und Redis-Neustart (`cache.clear()`)
  - nicht verifiziert: echter Django-Prozess-Neustart und echter PG-Reconnect; simuliert durch geschlossene Verbindungen
- **B Fehlerinjektion:** getestet:
  - PG-Fehler vor dem Provider: 503, kein Provider- und kein Suchaufruf
  - PG-Fehler nach dem Provider: `persisted:false`, kein zweiter Aufruf, Abgleich aus dem Cache
  - Redis nicht verfügbar vor der Persistenz: 503
  - Redis-Fehler nach dem Commit: `persisted:true`, Replay aus PG
  - Timeout: `uncertain`
  - Abbruch (`KeyboardInterrupt`) nach `begin_turn`: kein erneuter Aufruf; Abgleich markiert `uncertain`, die Zeile fällt aus dem Kontext
  - Fehler beim Guard-Abschluss: Antwort bleibt erhalten
  - nebenläufig gleiche ID: 1 Provider-Aufruf (PG)
  - nebenläufig verschiedene IDs: Sequenzen 1–4 (PG)
- **C Sicherheit:**
  - getestet: IDOR auf 7 Routen, CSRF (bestehend); Logout → 401; fehlerhafte UUID → 404; fehlerhaftes JSON → 400; Pilot-Policy (leer, Allowlist, ungültiger Wert); Injection und PII in vorheriger Frage nicht durchsuchbar; Logs ohne Frage und Antwort (`assertLogs`)
- **D Ledger:**
  - getestet: eine Reservierung pro logischem Request, auch beim Replay nach Redis-Verlust; ein Settle; `ledger_reservation_id` gespeichert; Kontext erhöht die Reservierung (bestehend)
  - Code-Review: Emergency Stop, Quota und Rate Limit unverändert im gemeinsamen Pfad `run_global_pipeline`; zusätzlich durch die Gesamtsuite abgedeckt
- **E Datenbank:**
  - getestet: vorwärts und rückwärts, Constraints in PG vorhanden, nebenläufiges Einfügen, Kaskade beim Konto-Löschen (bestehend)
- **F Oberfläche:**
  - getestet: Desktop und Mobil, RTL fa, Wiederherstellung, Seitenleiste, Suche, Umbenennen, Papierkorb, Wiederherstellen, kein horizontales Scrollen (−15 px Reserve), keine Ziele unter 44 px
  - Code-Review: Hinweis „nicht gespeichert“ bei `persisted:false`, kein `localStorage` für Inhalte, Archiv, Export, Tastaturbedienung
  - nicht verifiziert: Screenreader-Prüfung

## 4. Messung: kontextbezogene Suche

Die Messung lief auf dem Laptop gegen die echte Wikipedia-Suche, mit dem exakten Modulcode (Messdatei SHA-256 `d25c9a13fffbe8a56f713b8e220ba9965a12995cebed0d51424a0c47ed115dd2`). 34 Folgefragen, 0 Netzwerkfehler, Laufzeit 383 s. Rohdaten: `followup_eval_result_2026-11-17.json` (SHA-256 `33f72b0aae40f82f7c895bd0956325c25bd9811dc0114f21d162713903242f89`, liegt dem Eigentümer vor, nicht im Repo).

- Subjekt in der vorigen Frage:
  - alt 0/30 Treffer, neu 25/30 (fa 14/16, en 5/7, de 6/7)
  - keine Regression
- Subjekt nur in der Antwort: 0/4 alt und neu. Erwartet; Antworten sind keine Belege.
- Verfehlt (neu), 5 Fälle, zum Teil mit nahe verwandtem Artikel unter den Top 3:
  - fa „او چگونه درگذشت؟“: „مرگ کوروش بزرگ“ statt „کوروش بزرگ“
  - fa Anrainer des Persischen Golfs: „جنگ خلیج فارس“, „شورای همکاری خلیج فارس“
  - en Höhe des Eiffelturms: „Eiffel Tower replicas…“
  - en/de Ort der Photosynthese: „Calvin cycle“, „Chlorophylle“
- Empfehlung: Die Messung spricht für ein Einschalten im Pilot. Die Entscheidung liegt beim Eigentümer; das Flag bleibt **aus**.

## 5. Abnahmekriterien

| Kriterium | Status |
|---|---|
| Dauerhafte Request-ID und Frage vor dem Provider-Aufruf | VERIFIED |
| Keine Persistenz-Erfolgsmeldung vor dem Commit | VERIFIED |
| Kein erneuter Provider-Aufruf nach Persistenzfehler | VERIFIED |
| Wiederherstellung nach Redis-Verlust | VERIFIED |
| Wiederherstellung nach echtem Prozess-Neustart | NOT_VERIFIED (nur simuliert) |
| Nachricht + Guard in einer PG-Transaktion; Redis nach dem Commit | VERIFIED |
| Keine falsche Atomaritätsaussage (PG/Redis/Ledger) | PASSED (Doku §11.2) |
| Idempotenz inkl. echter Nebenläufigkeit | VERIFIED (PostgreSQL) |
| Gleiche ID in anderem Gespräch abgelehnt | VERIFIED |
| Eine Reservierung pro logischem Request, auch beim Replay | VERIFIED |
| Abweichung „abgerechnet, aber nicht gespeichert“ erkennbar | VERIFIED (`pending` + Abgleich + Ledger-Bericht als Obergrenze) |
| Pilot-Zugang unabhängig vom Flag | VERIFIED |
| Owner-Bindung, 404 für Fremde | VERIFIED |
| Kontext 6/3000, PII geschwärzt, nie als Anweisung oder Beleg | VERIFIED (bestehende Tests) |
| Kontextsuche gemessen, ohne Regression, Flag aus | VERIFIED |
| Purge: nur fällige Einträge, Dry-Run, DB-fehlerfest | VERIFIED |
| Cron | OPEN (nur dokumentiert, Freigabe nötig) |
| Migration 0003 vorwärts und rückwärts, SQLite und PG | VERIFIED |
| C02-Runner für 0003 | OPEN (separater PR) |
| Legacy `ask-global/` unverändert bei Flag aus | VERIFIED (Gesamtsuite) |
| UI-Hinweis bei `persisted:false` | NOT_VERIFIED im Browser (Code-Review) |
| Screenreader | NOT_VERIFIED |
| CI auf GitHub (Python 3.11/3.12) | NOT_VERIFIED (kein Push) |

## 6. Restrisiken

1. Zwischen Provider-Abrechnung und `complete_turn` gibt es keine Atomarität. Sie ist grundsätzlich nicht erreichbar; die Folgen sind begrenzt durch `pending`, `persisted:false`, kein erneuter Aufruf und den Abgleich.
2. Läuft der Abgleich nicht innerhalb von 15 Minuten, ist eine solche Antwort verloren (`uncertain`). Ohne genehmigten Cron läuft der Abgleich nur manuell.
3. Der Ledger-Bericht ist nur eine Obergrenze.
4. Lokal läuft Python 3.13; CI nutzt 3.11/3.12. Das ist nicht lokal geprüft.
5. Production braucht die Erweiterung des C02-Runners und eine Datensicherung vor `0003`.

## 7. Nächste Schritte (jeweils mit Freigabe des Eigentümers)

1. Push des Branches
2. PR
3. CI
4. Merge
5. C02-Runner-PR für `0003`
6. Staging
7. Production-Backup und Migration
8. Deploy
9. Pilot mit `allowlist` + `1`
10. Cron für Abgleich und Purge
11. Entscheidung über `VORNEQ_AI_CONTEXT_RETRIEVAL_ENABLED`
