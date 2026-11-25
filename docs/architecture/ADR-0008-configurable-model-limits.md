# ADR-0008: Konfigurierbare Modellgrenzen und professioneller KI-Chat (V7-02)

Status: vorgeschlagen (Draft-PR, nicht gemergt, nicht deployt). Datum: 2026-11-25.
Basis: `main` 5e74c71 (nach PR #745, ADR-0007).

## 1. Bisheriger Zustand

Die Chat-Grenzen waren über viele Module verteilt und fest codiert:

| Stelle | Feste Grenze |
|---|---|
| `chat_input_budget.LEGACY` | 200 Zeichen, 2048 Byte Request |
| `chat_input_budget.MAX_PILOT_BUDGET` | Eingabe-Pilot höchstens 8192 |
| `views_conversations.MAX_BODY`, `views_phase_b`, `views.py` | 2048 Byte |
| `response_engine_v3` | `PILOT_ANSWER_CHARS=2400`, Ausgabe 3072/2048/512 Tokens |
| `chat_output_budget.answer_chars` | `min(6400, 2·output_tokens)` |
| `chat_output_budget.configured_output_budget` | Ausgabe 1536…8192 |
| `engine/sectioned.py` | Abschnitt 700 bzw. `min(answer, 1400)` |
| `engine/citation.validate_generated` | `max_answer_chars` 1…2400 |
| `providers/openai_responses.py` | Prompt „at most 1400 characters per answer section“ |
| `conversations/context.py` | 6 Turns, 3000 Zeichen, 1000 Zeichen je Nachricht |
| `assets/js/phase-c-chat.js` | Frage 200…8192, Antwort ≤ 6400, Abschnitt ≤ 1400 |

## 2. Probleme

- Keine zentrale Stelle für Kontextfenster, Ein-/Ausgabe, Verlauf und Reserven.
- Zeichen wurden teils wie Tokens behandelt; persische Texte (2 Byte/Zeichen) und Emoji
  (4 Byte) wurden unterschätzt.
- Lange Verlaufsnachrichten (> 1000 Zeichen) wurden stillschweigend übersprungen.
- Fehler (413/422) leerten im Browser das Eingabefeld.
- Fehlercodes ohne maschinenlesbaren Grund (Ledger, Not-Aus, Eingabegröße).

## 3. Neue Architektur

`apps/ai_core/model_limits.py` ist die **einzige** Policy. Alle bisherigen Stellen
lesen daraus (`chat_input_budget.global_budget`, `chat_output_budget`, `context.prior_turns`,
`openai_responses.check_context_budget`, `ai_gateway_report`). Es gibt keine zweite
Registry und kein neues Gateway (ADR-0007 bleibt gültig).

`ModelLimits` (eingefroren) enthält alle Felder aus COR-01: `model_id`, `provider_id`,
`context_window`, `max_input_tokens`, `max_output_tokens`, `max_request_bytes`,
`max_message_characters`, `max_history_tokens`, `max_attachment_bytes`,
`reserved_output_tokens`, `system_prompt_tokens`, `tool_context_tokens`,
`retrieval_context_tokens`, `token_safety_margin`, `tokenizer_strategy`,
`pricing_reference`, `verification_status`, `verified_at` sowie `source` und `conflicts`.

Drei Quellen:

- `LEGACY_DEFAULT` (Standard): exakt das bisherige Verhalten (200 Zeichen, 2048 Byte).
- `INPUT_PILOT`: bisheriger Eingabe-Pilot (≤ 8192, ohne Kontextangabe).
- `OPERATOR_CONFIGURED`: vollständige Planung mit Kontextfenster.

## 4. Integration in die Modell-Registry

`chat_limits()` liest den Katalog aus `provider_registry.CATALOG`. Ist ein Modell dort
mit verifizierten Werten (`context_window`, `max_input_tokens`, `max_output_tokens`)
hinterlegt, begrenzen diese die Konfiguration nach oben (Konflikt wird gemeldet,
z. B. `context_window_above_registry`). Unbekannte Werte werden **nie geraten**:
`verification_status` bleibt `NOT_VERIFIED`, Preise bleiben `NOT_VERIFIED`.
Das Budget-Modell muss exakt `VORNEQ_AI_PHASE_B_MODEL` entsprechen.

## 5. Token-Algorithmus (COR-03)

Strategie `utf8_bytes_upper_bound`: byte-level BPE (OpenAI-Textmodelle) erzeugt
höchstens ein Token je UTF-8-Byte. Daher gilt `tokens ≤ bytes` – eine konservative
Obergrenze ohne Tokenizer-Abhängigkeit. Persisch zählt 2, Umlaute 2, Emoji 4 Tokens
je Zeichen. Jede Nachricht erhält zusätzlich 8 Tokens Rahmen. Unbekannte Strategien
oder ungültiges Unicode (einzelne Surrogates) → `LimitError` (fail closed).

Planung (`plan_context`): System-Prompt + Nutzer-Prompt + Verlauf + Quellen +
Tool-Kontext + Anhänge + reservierte Ausgabe + Sicherheitsmarge ≤ Kontextfenster,
sonst `CONTEXT_LIMIT_EXCEEDED`. Reserven: System-Prompt 4000, Retrieval 30 000
(5 Quellen × 1500 Zeichen × 4 Byte), Tool-Kontext 0, Anhänge 0 (nicht unterstützt),
Marge `max(512, 5 % des Fensters)`.

Eingabe-Bytes je Request: `6 · max_input + 512` (JSON-Escaping), hart begrenzt auf 2 MiB.

## 6. Kontext-Policy (COR-05)

Mit `OPERATOR_CONFIGURED` wählt `select_history` den Verlauf nach Token-Budget
(`max_history_tokens` = Restbudget nach allen Reserven) statt nach fester Turn-Zahl:
neueste Paare zuerst, nur ganze Frage/Antwort-Paare, Reihenfolge bleibt erhalten.
Der gespeicherte Verlauf bleibt vollständig (bis 500 Nachrichten je Unterhaltung);
nur der gesendete Kontext wird begrenzt. Die Unterhaltung wird weiterhin über den
Eigentümer geladen (`repository.get_conversation(owner, id)`) – keine
nutzerübergreifende Auswahl. Ohne Konfiguration gilt das bisherige Verfahren unverändert.

## 7. Finanzielle Reservierung (COR-06)

Unverändert gilt: „NO PAID AI CALL WITHOUT VALID LEDGER AUTHORIZATION.“
`BudgetedProvider` reserviert `input_bytes` (Anweisungen + Payload) und
`max_output_tokens` des Providers. Eine größere Ausgabe vergrößert damit automatisch
die Reservierung (Worst Case). Die Kontextprüfung (inkl. Sicherheitsmarge) läuft
**vor** der Reservierung; bei Überschreitung 413 ohne Reservierung und ohne Provider.
Reserve/Settle/Release, unsichere Kosten, Timeout, Idempotenz (Request-Recovery),
Tages- und Projektbudget bleiben unverändert. Kein neuer direkter SDK-Pfad
(AST-Wächter aus V4-01/V7-01 gelten weiter).

## 8. Sicherheit und Missbrauchsschutz (COR-10)

- `Content-Length` über dem Budget → 413 **vor** dem Lesen des Bodys.
- Eingabeprüfung vor Routing, Recovery-Claim, Quote, Ledger und Provider.
- Prompt-Injection- und PII-Prüfung (`screen_and_redact`) läuft über den gesamten Text;
  die öffentliche Suche bleibt auf 200 Zeichen begrenzt (`bounded_query`).
- Gehostet nur mit Ledger **und** Request-Recovery; Production nur mit exaktem Opt-in.
- Auth, CSRF, Rate-Limits, Not-Aus und Nutzerisolation unverändert.
- Fehlerantworten enthalten nur feste Enums, keine Ausnahmetexte oder Secrets.

## 9. Konfigurationsreferenz (COR-07)

Bestehende Variablen werden wiederverwendet (keine Duplikate):

| Variable | Bedeutung | Standard |
|---|---|---|
| `VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET` | maximale Eingabe-Tokens (512…1 000 000) | leer → Legacy |
| `VORNEQ_AI_CHAT_BUDGET_MODEL` | Modell der Policy (= `VORNEQ_AI_PHASE_B_MODEL`) | leer |
| `VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS` | Kontextfenster (8192…1 000 000) | leer |
| `VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET` | Ausgabe-Tokens (≥ 1536, ≤ 131 072) | leer → bisherige Werte |
| `VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT` | Production-Opt-in, nur exakt `true` (PR #712) | aus |

In diesem PR werden **keine** Render-Variablen geändert. Production-Ausgabe bleibt
unverändert (`configured_output_budget` ist weiterhin nur Development/Staging).

## 10. API-Kompatibilität (COR-09)

Bestehende Felder und HTTP-Status bleiben gleich; ergänzt wird nur `reason`:

| Fall | Antwort |
|---|---|
| Eingabe zu lang | 400 `{"error":"invalid_input","reason":"INPUT_TOO_LARGE","limit_chars":N}` |
| Request zu groß | 413 `{"error":"request_too_large","reason":"INPUT_TOO_LARGE","limit_bytes":N}` |
| Kontext zu klein | 413 `{"error":"context_limit_reached","reason":"CONTEXT_LIMIT_EXCEEDED"}` |
| Ledger/Budget | 429 `{"error":"rate_limited","reason":"LEDGER_UNAVAILABLE"/"BUDGET_REFUSED"/"EMERGENCY_STOP_ACTIVE"}` |

Weitere feste Gründe (`OUTPUT_LIMIT_INVALID`, `MODEL_UNAVAILABLE`, `MODEL_DISABLED`,
`INVALID_CONFIGURATION`) sind in `apps/ai_core/error_contracts.py` definiert.
Die Grounded-Phase-B-Route (`views_phase_b`) bleibt unverändert.

## 11. Frontend (COR-08)

- `maxlength`, Zähler und `data-vq-question-limit` kommen aus der Policy.
- Clientseitige harte Obergrenzen nur gegen absurde Werte (Frage 2 MiB, Antwort
  1 048 576 Zeichen); das Backend bleibt maßgeblich.
- Das Eingabefeld wird nur nach einer dargestellten Antwort geleert; bei jedem Fehler
  bleibt der Text erhalten. Neue lokalisierte Meldung `INPUT_TOO_LARGE` (fa/de/en).
- Lange Antworten: Markdown-Teilmenge (Code, Tabellen, Listen, Abschnitte, Zitate)
  bis zur Antwortgrenze; darüber bleibt der Text vollständig als Klartext.
- Streaming und Stop folgen in V7-03.

## 12. Teststrategie (COR-12/13)

`apps/ai_core/tests/test_v7_02_model_limits.py` (offline, ohne Netzwerk, ohne bezahlte
Aufrufe): Policy-Quellen, Production-Opt-in, ungültige Werte, Tokenschätzung fa/de/en/
Emoji/gemischt, Längen 200/201/1000/10k/50k und Kapazitätsgrenze, HTTP-Verträge,
Body-Abwehr vor dem Lesen, Ausgabe-/Abschnittsgrenzen, Kontextplanung inkl. Marge,
Verlaufsauswahl, Nutzerisolation, Fehlergründe, Bericht ohne Secrets, Import-Wächter,
Frontend-Vertrag. Bestehende Tests wurden nur um das neue `reason`-Feld bzw. die
aufgehobene 2400-Grenze ergänzt; keine Sicherheitsprüfung wurde entfernt.

## 13. Bekannte Einschränkungen

- `gateway.validate` normalisiert weiterhin Leerraum (Zeilenumbrüche werden zu
  Leerzeichen); eine Änderung betrifft Routing und Zitatprüfung und folgt separat.
- Die Tokenschätzung ist eine Obergrenze; reale Kosten liegen darunter (Reservierung
  wird beim Settle korrigiert).
- Die Grounded-Phase-B-Route und der Bild-Prompt (2000 Zeichen) sind nicht Teil dieser Policy.
- Registry-Werte für Kontextfenster/Preise sind nicht verifiziert (`NOT_VERIFIED`).
- Laufzeit von Ledger, Worker und Not-Aus ist nur durch Tests, nicht in Staging/Production belegt.

## 14. Rollback

Ohne gesetzte Variablen ist das Verhalten identisch mit vorher (Legacy). Rollback in
Betrieb: `VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET` leeren bzw.
`VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT` entfernen. Code-Rollback: Revert dieses PRs;
keine Migration, keine Datenänderung.
