# ADR-0009: Streaming, Stop und Antwort-Wiederherstellung (V7-03)

Status: vorgeschlagen (Draft-PR, nicht gemergt, nicht deployt). Datum: 2026-11-25.
Basis: V7-02.1 (`feat/ai-v7-02-1-dynamic-context-output`, PR #747) auf `main` 13842837.

## 1. Kontext

Antworten kamen bisher erst nach Abschluss des einzigen Provider-Aufrufs (bis 60 s).
Es gab keinen Stop; ein Browser-Timeout bedeutete Unsicherheit über Kosten und Ergebnis.
Laufzeit: Django 5.2 auf WSGI (`gunicorn config.wsgi:application`, synchrone Worker,
Worker-Timeout 100 s, `gunicorn.conf.py`), Render-Proxy, OpenAI-Responses-API.

## 2. Entscheidung – Transport

`POST` + `fetch`-Streaming mit SSE-Rahmen (`text/event-stream`) über
`StreamingHttpResponse`. Begründung:

- `EventSource` kann nur `GET` ohne eigene Header; wir brauchen `POST`, CSRF und
  `X-VQ-Request-ID`. `fetch` + `ReadableStream` erfüllt das in allen aktuellen Browsern.
- Kein ASGI-Umbau, kein zusätzlicher Dienst. Ein Stream belegt einen Worker höchstens
  `STREAM_DEADLINE_SECONDS = 85` (< 100 s Worker-Timeout) – dieselbe Belegung wie ein
  heutiger nicht gestreamter Aufruf. Keine Threads.
- Header `X-Accel-Buffering: no`, `Cache-Control: private, no-cache, no-store,
  no-transform`; im Stack gibt es keine GZip-Middleware, die puffern würde.
  `Connection: keep-alive` wird bewusst **nicht** gesetzt (Hop-by-Hop-Header, unter WSGI
  verboten). Ein Header allein beweist kein Streaming: das tatsächliche Verhalten des
  Render-Proxys muss in Staging mit Mock-/Testkonto geprüft werden (NOT_VERIFIED).

## 3. Umfang des Streamings

- **Wissensroute (`model_knowledge`)**: echte Text-Deltas (`response.delta`), danach
  serverseitige Validierung (`validate_knowledge`, Link-/Quellen-Wächter). Der Wächter
  läuft zusätzlich an jedem Checkpoint; Verstoß → Abbruch, `response.failed`.
- **Belegte Route (`grounded_draft`, Zitate, Abschnitte)**: unveränderte Pipeline mit
  voller Zitatprüfung, danach **ein** `response.completed`. Ungeprüfte Belegtexte
  werden nie angezeigt (Evidenz-Politik).
- Streaming nur in Unterhaltungen (serverseitige Persistenz ist Voraussetzung für
  Recovery). Ohne Unterhaltungen bleibt der bisherige Pfad.

## 4. Ereignisprotokoll (Version 1)

Jeder Rahmen: `id: <seq>`, `event: <type>`, `data: <JSON>`. JSON-Felder: `type`,
`sequence_number` (streng steigend), `request_id`, `conversation_id`, `response_id`
(= ID der Assistant-Nachricht), `timestamp`, `payload`.

| Typ | Payload |
|---|---|
| `response.created` | `protocol`, `mode` (`model_knowledge`/`validated`) |
| `response.started` | – (erstes Delta folgt) |
| `response.delta` | `text` (≤ 2048 Zeichen je Ereignis) |
| `response.usage` | `input_tokens`, `output_tokens` (keine Preise) |
| `response.completed` | `response` (identisch zum JSON-Vertrag) |
| `response.incomplete` | `error` (`output_limit_reached`/`stream_timeout`/`emergency_stop`), `reason`, `partial` |
| `response.cancelled` | `confirmed: true`, `cost: "uncertain"`, `partial` |
| `response.failed` | `error`, `reason_code`, `persisted` |
| `heartbeat` | – (spätestens alle 10 s ohne Delta) |

`response.section`/`response.citation` sind reserviert; Abschnitte und Zitate kommen
geprüft im `response.completed`. Ereignisse > 64 KiB werden serverseitig verweigert;
der Client verwirft unbekannte Typen, ungültiges JSON und Wiederholungen/Out-of-order
(`sequence_number ≤ letzter`). UTF-8 wird mit `TextDecoder(..., {stream: true})`
dekodiert; Multibyte-Grenzen zwischen Chunks sind damit unkritisch.

## 5. Lebenszyklus und Zustände (ohne Migration)

| Vorschlag | Abbildung |
|---|---|
| PENDING / RUNNING / STREAMING | `AIMessage.status = pending` (+ Checkpoint-Teiltext) |
| CANCEL_REQUESTED | `pending` + `error_code = cancel_requested` |
| CANCELLED | `failed` + `cancelled` (+ Teiltext) |
| INCOMPLETE | `failed` + `output_limit_reached` / `stream_timeout` / `emergency_stop` (+ Teiltext) |
| COMPLETED | `completed` |
| FAILED | `failed` + Fehlercode |
| UNKNOWN | `uncertain` (z. B. `provider_timeout`, Reconciler `interrupted`) |

Teilantworten sind nie `completed` und gelangen damit nie als vollständige Antwort in
den Kontext (`prior_turns` nutzt nur `completed`). `serialize_message` liefert
`complete` und `cancel_requested`; `stored_response` liefert `partial_answer` +
`complete: false`.

## 6. Stop-Semantik

- `POST …/conversations/<cid>/messages/<mid>/cancel/` (CSRF, Login, Actor-Policy,
  Eigentümerbindung über `conversation__owner_id`; fremd/unbekannt → 404).
- Setzt atomar `error_code = cancel_requested` **nur** solange `pending` (idempotent;
  danach `already_final`). Kein Redis nötig – funktioniert workerübergreifend.
- Antwort `202 {"status": "cancel_requested", "confirmed": false}`: lokal angefordert.
  **Bestätigt** ist der Stop erst durch `response.cancelled` im Stream, nachdem der
  Server den Provider-Stream geschlossen und den Teiltext gespeichert hat.
- Rennen Stop ↔ Abschluss: Wer zuerst committet, gewinnt; ein abgeschlossener Turn
  wird nie nachträglich als abgebrochen markiert (`complete_turn` nur aus `pending`).
- Verbindungsabbruch ist **kein** Stop (siehe 7).

## 7. Wiederherstellung

- Checkpoints: Teiltext höchstens alle 1,5 s oder 2000 Zeichen per `UPDATE` (nie pro
  Token); dieselbe Stelle prüft Stop-Flag und Not-Aus.
- Browser schließt/verliert die Verbindung: WSGI schließt den Generator; der Server
  liest denselben Provider-Stream **ohne weitere Ausgabe** bis Ende/Deadline weiter und
  speichert das Ergebnis. Nach Reload/Re-Login zeigt die Unterhaltung die Antwort aus
  PostgreSQL – **ohne neue bezahlte Anfrage**.
- **Belege für dieses Verhalten (lokal geprüft):**
  - Gunicorn 26.2.0 (`requirements.txt`), Sync-Worker: `workers/sync.py` iteriert
    `for item in respiter: resp.write(item)` in einem `try/finally`, das
    `respiter.close()` auch nach einem Schreibfehler (`OSError`) aufruft.
  - Django 5.2.17 `HttpResponseBase.close()` ruft die registrierten Closer auf
    (`StreamingHttpResponse` registriert `value.close`) **vor** `request_finished`
    – die DB-Verbindung ist beim Weiterlesen noch offen.
  - Lokaler Versuch mit echtem `gunicorn 26.2.0 -w 1` und einem Socket-Client, der nach
    zwei Chunks trennt: der Generator erhielt `GeneratorExit` und konnte danach weiter
    arbeiten (`generator_exit_received`, `drained_after_disconnect`).
  - Test `test_browser_disconnect_drains_and_persists_without_second_call`
    (SQLite und PostgreSQL): vollständige Antwort gespeichert, genau ein Provider-Aufruf.
- **Grenzen dieses WSGI-Ansatzes (nicht garantiert):** Weiterlesen ist auf die
  Deadline (85 s ab Start) und die Lebensdauer des Worker-Prozesses begrenzt. Ein
  Neustart/Deploy/OOM des Workers beendet den Aufruf; die Nachricht bleibt `pending`
  mit letztem Checkpoint und wird vom Reconciler `uncertain/interrupted`. Ein Abbruch
  wird erst beim nächsten Schreibversuch erkannt. Hält der Render-Proxy die
  Upstream-Verbindung trotz Client-Abbruch offen, läuft der Stream normal zu Ende.
  Dauerhafte, worker-unabhängige Fortsetzung und Wiederaufnahme per `Last-Event-ID`
  sind **V7-03.1** (Job + Background-Worker + Redis Stream + PostgreSQL-Checkpoints).
- Fehler beim Weiterlesen werden protokolliert (`ai_stream_detached_finish_failed`),
  nie still verschluckt; Djangos `close()` würde sie sonst ignorieren.
- Laufende Antwort beim Reload: Teiltext aus dem Checkpoint, markiert „schreibt…“.
- Worker-Neustart während des Streams: Nachricht bleibt `pending` mit letztem
  Checkpoint; der bestehende Reconciler (`ai_conversations_reconcile --apply`) setzt
  sie auf `uncertain/interrupted` (Teiltext bleibt sichtbar, als unvollständig markiert).
- Replays mit gleicher `X-VQ-Request-ID` laufen unverändert über den Recovery-Claim
  (PostgreSQL-Guard + Redis) und liefern JSON ohne Provider-Aufruf.

## 8. Ledger-Integration

„NO PAID AI CALL WITHOUT VALID LEDGER AUTHORIZATION.“ – unverändert:

- Vor dem ersten Byte: `prepare_paid_text` (gleich wie Pipeline): Ledger-Pflicht und
  Not-Aus, Quote, Ausgabe-Policy, einziger Provider über `paid_text_provider`
  (gehostet `BudgetedProvider`). Ablehnungen kommen als JSON (429 + `reason`).
- `BudgetedProvider.stream_knowledge`: Reservierung (Eingabe-Bytes + `max_output_tokens`)
  → `authorized_paid_call` nur für den ersten Generator-Schritt (SDK-Client + Senden)
  → genau eine Abrechnung im `finally`:
  - Usage vorhanden → `settle` (FINALIZED, tatsächliche Kosten);
  - Stop/Abbruch/Timeout ohne Usage → `settle(usage=None)` = UNCERTAIN mit voller
    Reservierung (**nie 0**, keine Freigabe ohne Beweis);
  - nachweislich nicht gesendet (`request_sent = False`) → `release("not_sent")`.
- Kein neuer SDK-Pfad: `OpenAIResponsesProvider.stream_knowledge` ist im bestehenden
  Adapter, prüft `_require_ledger_reservation` vor dem Client; AST-Grenzen
  (`test_v4_paid_provider_boundary`) wurden nur um genau diese Stellen ergänzt.
- Not-Aus während des Streams: `ledger.emergency_stop_active()` an jedem Checkpoint
  (Umgebung oder Ledger-Konto) → Abbruch, `response.incomplete` (`emergency_stop`).

## 9. Sicherheitsgrenzen

Gleiche Vorprüfung wie die JSON-Route (`_prepare_message`): Flag, Login, Actor-Policy,
CSRF, Recovery (gehostet), Body-/Eingabebudget, Eigentümer. Prompt-Injection-Prüfung
vor der Quote. Ereignisse enthalten nur feste Felder; keine Secrets, keine Ausnahme-
texte. Das Frontend fügt Deltas ausschließlich als `textContent` ein; Markdown-Rendering
(inkl. Syntaxhervorhebung) erzeugt nur Textknoten mit festen Klassen; CSP unverändert.

## 10. Kontextzuteilung

Unverändert aus V7-02.1 (`history_budget`): dynamisches Verlaufsbudget je Anfrage,
Summe ≤ Kontextfenster; der Stream nutzt dieselben `prior_turns`.

## 11. Frontend

Stop-Knopf (nur während des Streams), Schreibindikator (Caret, respektiert
`prefers-reduced-motion`), Teilantwort-Markierung, Copy-Code, Syntaxhervorhebung,
kein erzwungenes Scrollen, wenn der Nutzer nach oben gescrollt hat, Texte fa/de/en,
RTL/LTR (Code-Blöcke immer LTR), Theme-Tokens (Dark/Light).

## 12. Feature-Gates und Konfiguration

| Variable | Bedeutung | Standard |
|---|---|---|
| `VORNEQ_AI_CHAT_STREAMING_ENABLED` | Development/Staging, nur exakt `true` | aus |
| `VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED` | Production, eigener Schalter | aus |

Zusätzlich nötig: `VORNEQ_AI_CONVERSATIONS_ENABLED`, Global-AI-Gates, Actor-Policy,
gehostet Recovery und Ledger. In diesem PR keine Render-Änderung.

## 13. Tests

`apps/ai_core/tests/test_v7_03_streaming.py` (offline, Fake-Provider/-SDK): Erfolg,
fa/de/en, UTF-8 Byte für Byte, lange Antwort/Chunking/Checkpoints, Stop (vor erstem
Token, während, nach Abschluss), Rennen, Cancel-Autorisierung/Isolation/Idempotenz/CSRF,
Cross-User-Stream, Verbindungsabbruch mit Weiterlesen, Checkpoint-Sichtbarkeit,
Deadline, Ausgabelimit, Provider-Fehler, Timeout, Link-Wächter, Not-Aus (während/vor),
Ledger-Ablehnung als JSON, Feature-Gate, belegte Route, Replay ohne Aufruf,
Nicht-Streaming-Regression, Ledger (einmal reservieren, Usage-Settle, Stop = UNCERTAIN,
nicht gesendet = Release, Freigabe nur im ersten Schritt), SDK-Adapter mit Fake-Client,
Protokoll-Encoder, Gates, Bericht ohne Secrets, Frontend-Vertrag.

## 14. Deployment-Plan

1. #747 (V7-02.1) prüfen/mergen/deployen (eigene Freigabe).
2. Dieses PR mergen; Deploy über `deploy.yml` (Issue #448). Flags bleiben aus.
3. Staging: `VORNEQ_AI_CHAT_STREAMING_ENABLED=true`, Testkonto, Stop/Reload/Abbruch
   manuell prüfen, Ledger-Einträge (FINALIZED/UNCERTAIN) kontrollieren.
4. Production erst danach mit `VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED=true`.

## 15. Rollback

Flag entfernen → Streaming-Endpunkte 404, Frontend nutzt automatisch den JSON-Pfad.
Code-Revert ohne Migration und ohne Datenänderung möglich.

## 16. Restrisiken

- Synchrone Worker: viele gleichzeitige Streams belegen Worker (wie heute lange Aufrufe).
- Bei Verbindungsabbruch läuft der Aufruf bis zu 85 s weiter (bewusst, für Recovery).
- Stop ohne Usage-Ereignis → Kosten UNCERTAIN (manuelle Ledger-Abstimmung).
- Nicht bestätigte Abrechnung (`settle`/`release` liefert `None`) wird mit
  Reservierungs-ID protokolliert (`ai_stream_ledger_settlement_unacknowledged`); die
  Reservierung bleibt RESERVED bis zur manuellen Abstimmung, nie automatisch 0.
- Das SSE-Parsing liegt in `assets/js/vq-stream-parser.js` (DOM-frei) und ist mit
  `quality/test-chat-stream-parser.mjs` an jeder möglichen Byte-Grenze getestet.
- Belegte Antworten streamen nicht tokenweise; Heartbeats nur im Wissenspfad.
- Proxy-Verhalten von Render für lange SSE-Antworten ist lokal nicht prüfbar
  (Staging-Test erforderlich).
- Modell-Streaming-Fähigkeit in der Registry `NOT_VERIFIED`; laut OpenAI-Doku unterstützt.
