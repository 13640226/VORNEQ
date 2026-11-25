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

## 5. Idempotenz

`request_id` (UUIDv4, eindeutig) + `fingerprint = sha256(owner, conversation, language,
question)`. Gleiche ID + gleicher Inhalt → derselbe Job (kein zweiter Job, keine zweite
Nachricht, keine Reservierung). Gleiche ID + anderer Inhalt/Eigentümer/Unterhaltung →
`request_id_conflict`. Fremde Unterhaltungen → `ConversationNotFound`.

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
- `reservation_id`, `provider_request_sent` und `ledger_state` (`none/reserved/finalized/
  uncertain/released/unacknowledged`) werden fencing-geschützt am Job gespeichert,
  **unabhängig** vom Job-Status (z. B. Job `CANCELLED`, Ledger `uncertain`).
- Usage bekannt → finalized; gesendet, Usage unbekannt → uncertain (nie 0);
  nachweislich nicht gesendet → released; nicht bestätigt → unacknowledged (Log).
- Reservierungsablehnung (Budget/Ledger/Not-Aus) → Job `FAILED`, kein Provider-Aufruf.

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

## 11. Nebenbefund V7-03

Eine Reservierungsablehnung im ersten Stream-Schritt (z. B. `BudgetExhausted`) führte in
`KnowledgeStream.events` zu einem Abbruch mitten im Stream (PENDING-Turn). Jetzt:
`response.failed` mit `rate_limited` + `reason`, Turn `FAILED`, kein Provider-Aufruf.

## 12. Nächste Schritte

- V7-03.1b: HTTP-Endpunkte (Anlegen/Abbrechen), Redis-Ereignisse, SSE mit
  `Last-Event-ID`, Snapshot aus PostgreSQL, Frontend.
- V7-03.1c: Reaper, Reconciliation (Job ↔ Reservierung), Aufbewahrung, Lasttests.
- V7-08 Lite: Seed `docs/evaluation/ai-benchmark-v0.json` (nicht ausgeführt,
  Schwellen erst nach gemessener Baseline).
