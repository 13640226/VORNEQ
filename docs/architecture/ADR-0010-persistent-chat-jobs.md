# ADR-0010: Dauerhafte Antwort-Jobs (V7-03.1a)

Status: vorgeschlagen (Draft-PR, nicht gemergt, nicht deployt). Datum: 2026-11-25.
Basis: `main` 7e83199 (Merge von PR #748, V7-03). Folgt ADR-0009.

## 1. Kontext und Bestandsaufnahme

- V7-03 streamt im Web-Worker (WSGI, Gunicorn sync). Nach Browser-Abbruch wird bis
  zur Deadline (85 s) weitergelesen; ein Worker-Neustart beendet den Aufruf (ADR-0009 §7).
- Vorhanden und wiederverwendet: `AIConversation`/`AIMessage` (Persistenz, Checkpoints),
  `conversations.service.begin_turn/complete_turn/classify`, `conversations.context`
  (Verlaufsbudget), `views_global.prepare_paid_text` (Ledger-Pflicht, Not-Aus, Quote,
  `paid_text_provider`), `BudgetedProvider.stream_knowledge` (Reservierung + genau eine
  Abrechnung), `streaming.PARTIAL_ERROR_CODES`, Image-Queue-Muster
  (`image_generation/service.py`: Advisory-Lock + `SKIP LOCKED`).
- `apps/ai_core/streaming.py` ist ein Modul; es wird **kein** Paket `streaming/`
  angelegt. Neu ist `apps/ai_core/chat_jobs.py`.
- Identität: bestehendes `AUTH_USER_MODEL`; keine neue Identitätsentität.
- `render.yaml` enthält nur den Web-Dienst; ein Background-Worker ist nicht provisioniert.

## 2. Entscheidung

PostgreSQL-Durable-Queue (Tabelle `ai_core_aichatjob`), kein Transactional Outbox:
Job, Frage und PENDING-Antwort entstehen in **einer** Transaktion; ein Outbox brächte
keinen zusätzlichen Schutz, solange Redis nur Weckhinweis ist. Redis-Ausfall verliert
keinen Job (Test `test_redis_failure_on_wakeup_is_logged_and_job_is_durable`).

## 3. Zustandsmaschine

```
QUEUED ─claim→ CLAIMED ─→ RUNNING ─→ COMPLETED | INCOMPLETE | FAILED | UNCERTAIN
  │              │           └─(Stop)→ CANCEL_REQUESTED ─→ CANCELLED | COMPLETED | INCOMPLETE | FAILED | UNCERTAIN
  │              └─(Stop)→ CANCEL_REQUESTED
  └─(Stop, nichts gesendet)→ CANCELLED
```

Terminale Zustände haben keine Übergänge. Kein Weg zurück nach `QUEUED` (kein
automatischer Retry eines möglicherweise gesendeten Aufrufs). Jede Änderung ist ein
bedingtes UPDATE auf den alten Status; DB-Constraints sichern gültige Werte und
„CLAIMED/RUNNING ⇒ worker_id + Lease“.

## 4. Claim, Lease, Fencing, Heartbeat

- `claim(worker_id)`: `SELECT … FOR UPDATE SKIP LOCKED` auf den ältesten `QUEUED`-Job,
  dann bedingtes UPDATE (`status=queued`, `fencing_token=alt`) → `CLAIMED`,
  `fencing_token+1`, `lease_until = now + lease`.
- Jede Worker-Schreiboperation (`heartbeat`, `transition`, `checkpoint`, `bind_ledger`,
  Abschluss) verlangt `worker_id` + `fencing_token` + `lease_until > now`; sonst
  `StaleLease`. Ein abgelöster Worker kann weder Status, Checkpoint, Ledger-Bindung
  noch Abschluss schreiben (Tests mit Re-Claim und gefälschtem Token).
- Lease-Standard 120 s (> Provider-Timeout 60 s); Checkpoints verlängern die Lease.
- Reaper (Lease abgelaufen) ist V7-03.1c; er darf nur nachweislich nicht gesendete
  Claims (`provider_request_sent = false`) erneut freigeben.

## 5. Idempotenz (eigentümer-gebunden)

- Eindeutigkeit `(owner, request_id)` statt global; `fingerprint = sha256(operation
  "chat.answer.v1", owner, conversation, language, question)`.
- Gleiche ID + gleicher Fingerabdruck → derselbe Job, auch nach `COMPLETED`/`FAILED`
  (kein zweiter Job, keine zweite Nachricht, keine Reservierung).
- Gleiche ID + anderer Inhalt **oder** andere Unterhaltung desselben Nutzers →
  `request_id_conflict`.
- Die gleiche ID eines **anderen** Nutzers ist ein eigener Namensraum: neuer Job ohne
  Konflikt – identisches Verhalten wie für eine unbenutzte ID, daher keine Auskunft über
  fremde Jobs oder Unterhaltungen. Fremde Unterhaltungen → `ConversationNotFound`.
- `AIMessage.request_id` ist global eindeutig (bestehendes Schema); Job-Nachrichten
  erhalten daher `uuid5(Namensraum, "chat.answer.v1:<owner>:<request_id>")` – nie gleich
  einer Client-UUIDv4 und nie zwischen Nutzern kollidierend.

## 6. Kapazität

Global und je Nutzer aktive Jobs (`QUEUED/CLAIMED/RUNNING/CANCEL_REQUESTED`), geprüft
unter `pg_advisory_xact_lock` in derselben Transaktion wie das Anlegen – keine
ungeschützte Zählung. Werte aus `VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_GLOBAL` (Standard 32) und
`…_PER_USER` (Standard 2); ungültige Werte → Standard. Keine Tageslimits.
Der Mutationstest (Lock entfernt) schlug auf PostgreSQL reproduzierbar fehl.
SQLite serialisiert Schreibzugriffe; echte Nebenläufigkeit ist nur auf PostgreSQL getestet.

## 7. Ledger-Bindung

- Keine Reservierung beim Einreihen; reserviert wird erst im Worker unmittelbar vor dem
  Aufruf über `prepare_paid_text_for_actor` → `BudgetedProvider.stream_knowledge`.
- **Crash-Fenster Reservierung ↔ Job:** Job und Ledger liegen in **getrennten**
  Datenbanken; keine Django-Transaktion umfasst beide. Deshalb erzeugt der Worker die
  Reservierungs-ID (UUIDv4) selbst, speichert sie fencing-geschützt am Job
  (`ledger_state = reserving`) und übergibt sie an `ledger.reserve(reservation_id=…)`.
  Stürzt der Worker nach der Reservierung ab, ist sie über `AIChatJob.reservation_id`
  (Index) auffindbar; ohne Ledger-Zeile wurde nichts reserviert. Eine bereits vergebene
  ID schlägt im Ledger fail-closed fehl (kein zweiter Betrag). Der Job bleibt aktiv und
  wird nie automatisch neu gestartet.
- **Abrechnung unabhängig von der Lease:** `BudgetedProvider` rechnet im `finally`
  genau einmal ab – auch wenn die Lease inzwischen verloren ist (bekannte Usage wird
  also nie verworfen). Nur die Bindung am Job ist fencing-geschützt; bei Verlust wird
  `ai_chat_job_lease_lost … reservation=<id> settlement=<state>` protokolliert.
  Parallele/doppelte Abrechnung: der Ledger sperrt die Zeile und bestätigt genau eine
  (`LedgerCorrelationPostgresTests`).
- `reservation_id`, `provider_request_sent` und `ledger_state` (`none/reserved/finalized/
  uncertain/released/unacknowledged`) werden fencing-geschützt am Job gespeichert,
  **unabhängig** vom Job-Status (z. B. Job `CANCELLED`, Ledger `uncertain`).
- Usage bekannt → finalized; gesendet, Usage unbekannt → uncertain (nie 0);
  nachweislich nicht gesendet → released; nicht bestätigt → unacknowledged (Log).
- Reservierungsablehnung (Budget/Ledger/Not-Aus) → Job `FAILED`, kein Provider-Aufruf.

## 7a. Not-Aus

| Grenze | Verhalten |
|---|---|
| vor Claim | `claim` übernimmt nichts (Jobs bleiben `QUEUED`) |
| vor Reservierung / Provider | Prüfung in `run_claimed`; `ledger.reserve` prüft Umgebung + Konto erneut |
| während Stream/Checkpoint | Prüfung an jedem Checkpoint → `INCOMPLETE` (`emergency_stop`) |
| Stop | `request_cancel` bleibt erlaubt |
| Abrechnung | nie durch Not-Aus blockiert (bekannte Usage → finalized, sonst uncertain) |

## 8. Checkpoints

Teiltext nur in der PENDING-`AIMessage` (keine Textkopie im Job), `checkpoint_sequence`
streng monoton (ältere/wiederholte Sequenzen werden ignoriert), höchstens alle 2000
Zeichen oder 1,5 s. Teilantworten werden nie `COMPLETED` und nie Kontext.
Abschluss (Job-Terminalstatus + `complete_turn`) in **einer** Transaktion; schlägt sie
fehl, bleibt der Job aktiv (Log `ai_chat_job_finish_failed`) für die Reconciliation.

## 9. Betrieb und Gates

- `VORNEQ_AI_CHAT_JOBS_ENABLED` (Development/Staging), `…_PRODUCTION_ENABLED`; Standard aus.
- Worker: `manage.py run_chat_jobs [--loop] [--max-jobs N]`; verweigert den Start bei
  geschlossenem Gate. **Kein HTTP-Endpunkt** in V7-03.1a; bestehendes Streaming/JSON
  unverändert.
- Ein Betrieb auf Render erfordert einen separaten Worker-Dienst **und** eine Ledger-
  Freigabe für diesen Dienst (der Ledger akzeptiert heute nur Web-Dienst und den
  Staging-Bild-Worker). Beides ist eine Entscheidung des Eigentümers (Kosten, Sicherheit).
- `ai_gateway_report` zeigt den Abschnitt `chat_jobs` (ohne DB-Abfragen).

## 10. Migration

`apps/ai_core/migrations/0005_chat_job_v1.py`: nur `CreateModel` (neue Tabelle, Indizes,
Constraints) – keine Änderung bestehender Daten. Vorwärts/rückwärts im Test auf SQLite
und PostgreSQL geprüft (`MigrationTests`). Ein Rückwärtsschritt löscht die Tabelle samt
Job-Historie (Ledger-Daten liegen separat); vor einem Rollback in einer Umgebung mit
Jobs ist ein Export nötig.

## 10a. Worker-Infrastruktur (nur Entwurf, nicht aktiviert)

- Prozess: `manage.py run_chat_jobs --loop --poll-seconds 2` (Standard ohne `--loop`:
  ein Job). Ein Job je Prozess gleichzeitig; Skalierung über mehrere Prozesse (SKIP
  LOCKED). Abbruch (SIGTERM) beendet den Prozess; ein laufender Job bleibt `RUNNING`
  mit Lease und wird vom Reaper (V7-03.1c) behandelt – kein automatischer Retry.
- Identität: eigener Render-Dienst mit eigener `RENDER_SERVICE_ID`. Der Ledger lehnt
  heute jeden Dienst außer Web-Diensten und dem Staging-Bild-Worker ab
  (`_approved_client`). Eine Freigabe wäre eine bewusste Ledger-Änderung (Eigentümer).
- Datenbank: je Worker-Prozess 1 Verbindung zur Haupt-DB + 1 zum Ledger.
- Redis: nur Weckhinweis (`vorneq:chat-jobs:wakeup`); Polling bleibt maßgeblich.
- Kosten/Ressourcen: nicht geschätzt (keine verifizierten Preise); Entscheidung nach
  V7-03.1b/c.

## 11. Nebenbefund V7-03

Eine Reservierungsablehnung im ersten Stream-Schritt (z. B. `BudgetExhausted`) führte in
`KnowledgeStream.events` zu einem Abbruch mitten im Stream (PENDING-Turn). Jetzt:
`response.failed` mit `error = rate_limited` (bestehender Vertrag der JSON-Route) und
unterscheidendem `reason`: `BUDGET_REFUSED`, `LEDGER_UNAVAILABLE` oder
`EMERGENCY_STOP_ACTIVE`; eine ungültige Aufruffreigabe (`UnauthorizedPaidCall`) meldet
`provider_unavailable` + `authorization_denied`. Turn nie `pending`, kein Provider-Aufruf,
keine Ausnahmetexte im Ereignis.

## 12. Nächste Schritte

- V7-03.1b: HTTP-Endpunkte (Anlegen/Abbrechen), Redis-Ereignisse, SSE mit
  `Last-Event-ID`, Snapshot aus PostgreSQL, Frontend.
- V7-03.1c: Reaper, Reconciliation (Job ↔ Reservierung), Aufbewahrung, Lasttests.
- V7-08 Lite: Seed `docs/evaluation/ai-benchmark-v0.json` (nicht ausgeführt,
  Schwellen erst nach gemessener Baseline).
