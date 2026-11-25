# V4-01 — Centralized AI Ledger Enforcement

Basis: `a9e678b19a2454040be091080c484a8acd73a339`.
Prinzip: **NO PAID AI CALL WITHOUT VALID LEDGER AUTHORIZATION.**

## Bestätigte Befunde (vorher)

| ID | Schwere | Stelle (Basis-SHA) | Ursache |
|---|---|---|---|
| V4-F01 | Hoch | `apps/ai_core/views_phase_b.py:58-68` | `/api/ai/v1/ask-grounded/` konstruierte `OpenAIResponsesProvider` ohne `BudgetedProvider`; einzige Grenze war `reserve_staging_request()`, die bei `VORNEQ_AI_STAGING_UNMETERED=true` sofort zurückkehrt (`staging_budget.py:15-17`). |
| V4-F02 | Hoch | `apps/ai_core/views_global.py:213-245` | Staging-Chat lief ohne Ledger, wenn `ledger_enabled()` falsch und `VORNEQ_AI_CHAT_STAGING_PREPAID_ONLY` aus war (Fallback auf `reserve_staging_request`, ebenfalls durch UNMETERED abschaltbar). Production brach erst **nach** Quota-Verbrauch und Provider-Konstruktion ab. |
| V4-F03 | Mittel | `views_global.py:230`, `views_phase_b.py:63` | Zwei unabhängige Konstruktionsstellen für den kostenpflichtigen Text-Provider, keine Architekturgrenze in CI. |
| V4-F04 | – | `scripts/ai_eval_stage2.py`, `docs/ai/AI_CORE_V3_STAGE2.md:62` | Evaluation-Baseline fehlt → V4-02 (nicht Teil dieses PR). |
| V4-F05 | Niedrig | `config/settings.py:434-436, 597-628` | 11 Kostengrenzen (`_staging_int`/`_image_int`) fehlten im Parity-Katalog; der Drift-Test erkannte diese Helfer nicht. |

## Provider Invocation Inventory (nach V4-01)

| Pfad | Datei:Zeile (Einstieg) | Provider | Bezahlt | Ledger | Reservierung → Aufruf → Abschluss | Not-Aus | Umgebung | Actor |
|---|---|---|---|---|---|---|---|---|
| Global Chat `/api/ai/v1/ask-global/` | `views_global.py:151` → `run_global_pipeline` (202) | OpenAI Responses (`OpenAIResponsesProvider.generate`/`generate_knowledge`) | ja | **Pflicht** (staging + production) via `paid_provider.paid_text_provider` | `BudgetedProvider`: `ledger.reserve` → Provider → `ledger.settle` (UNCERTAIN ohne Usage) | Gate + `require_paid_text_ledger` + `ledger.reserve` | `staging_policy.trial_enabled` / `production_policy.production_enabled` | Staging-Allowlist (Superuser) / Production-Policy |
| Konversationen `/api/ai/v1/conversations/<id>/messages/` | `views_conversations.py:207` → `run_global_pipeline` | wie oben | ja | **Pflicht** | wie oben, Reservierungs-ID am `AIMessage` | wie oben | wie oben | Eigentümer + Policy |
| Grounded `/api/ai/v1/ask-grounded/` | `views_phase_b.py:37` | OpenAI Responses | ja | **Pflicht** auf Staging; Production gesperrt (404) | wie oben; Ledger-Prüfung vor Legacy-Zähler | Gate (`trial_enabled`) + Ledger | nur development/staging | Staging-Allowlist |
| Image Worker | `image_generation/service.py:159` `process_next_image_job` | OpenAI Images (`OpenAIImageProvider`) | ja | **Pflicht** (unverändert) | `reserve_with_config`/`reserve_prepaid_image` → `reservation_still_open` → Provider → `settle`; UNCERTAIN bei Zweifel | Ledger + Paid-Gate doppelt geprüft | Staging-Worker-Identität | `actor_allowed(worker=…)` |
| Image Mock | `image_generation/service.py` (`MockImageProvider`) | lokal | nein | – | – | – | Mock-Worker beansprucht nur Mock-Jobs | – |
| Voice | `voice/provider.py:21` | `MockVoiceProvider` | nein | – | – | – | nicht-Mock wird abgelehnt | – |
| Public Retrieval | `web_retrieval.py`, `retrieval_registry.py` | Wikipedia (HTTP, Allowlist) | nein | – | – | – | – | – |
| Lokale Entwicklung | `paid_provider.require_paid_text_ledger` | Provider wird konstruiert, aber **nie bezahlt aufgerufen** | nein | keins – die Aufrufgrenze verweigert jeden SDK-Kontakt ohne Reservierung (auch mit API-Schlüssel) | – | Gate | development | lokal; nur Test-Doubles/Mocks |

Kein Management Command, Scheduled Job oder Worker außer dem Image Worker konstruiert einen kostenpflichtigen Provider (AST-Inventar, `test_v4_paid_provider_boundary`).

## Aufrufgrenze (Nachtrag vor Merge)

Die Konstruktionsgrenze allein reichte nicht: lokal mit `OPENAI_API_KEY` hätte ein unverpackter Provider einen echten Aufruf senden können. Deshalb zusätzlich:

* `apps/ai_ledger/call_authorization.py`: `authorized_paid_call(reservation, kind)` (ContextVar, pro Thread/Task, nach dem Aufruf garantiert zurückgesetzt) und `require_authorized_paid_call(kind)`.
* Freigabe setzen nur `BudgetedProvider.generate`/`generate_knowledge` (nach `ledger.reserve`) und der Image-Worker (nach `reserve_with_config`/`reserve_prepaid_image`).
* `OpenAIResponsesProvider.generate`/`generate_knowledge` und `OpenAIImageProvider.generate` prüfen die Freigabe **vor** Schlüsselprüfung, SDK-Import und Client-Konstruktion. Text: `ProviderUnavailable` (HTTP 503 `provider_unavailable`), Bild: `ledger_authorization_missing`, `request_sent=False`.
* AST-Test: Freigabe nur an den drei Ledger-Aufrufstellen; jeder bezahlte Adapter prüft vor `OpenAI(...)`.

Damit gilt das Prinzip unabhängig von `VORNEQ_ENV`, Render-Variablen oder Umgebungserkennung.

## Änderungen

* `apps/ai_core/paid_provider.py` (neu): einzige Konstruktionsstelle. `require_paid_text_ledger()` prüft **vor** Quota, Retrieval und Konstruktion: Not-Aus → Umgebung → Ledger. Gehostet wird jeder Provider in `BudgetedProvider` verpackt – auch wenn ein Aufrufer die Vorprüfung fälschen würde.
* `views_global.py`: Ledger-Pflicht für Staging **und** Production vor `reserve_global_request`; der ledgerlose Staging-Fallback (`reserve_staging_request`) entfällt.
* `views_phase_b.py`: ledger-gebunden; Ledger-Prüfung vor dem Legacy-Zähler (kein Quota-Verbrauch ohne Ledger).
* `config/settings.py`: nur Kommentare zur Bedeutung von `UNMETERED`/`PREPAID_ONLY`.
* `apps/core/environment_parity.py`: 11 Kostengrenzen katalogisiert; Drift-Test erfasst `_staging_int`/`_image_int`.

## Fehlervertrag (unverändert)

Alle Ledger-Ablehnungen (`LedgerUnavailable`, `BudgetExhausted`, `StagingDailyCapReached`, `EmergencyStop`) erben von `BudgetExceeded` und liefern wie bisher **HTTP 429 `{"error": "rate_limited"}`** – identisch zum bestehenden Production-Verhalten. Keine neuen Fehlercodes, keine Änderung an Antwortinhalt, Prompt, Modell, Zitaten oder Retrieval.

## Bedeutung von `VORNEQ_AI_STAGING_UNMETERED` (Compatibility)

Vorher: konnte die einzige Kostengrenze des Grounded-Pfads und des ledgerlosen Staging-Chats entfernen.
Nachher: überspringt nur den Legacy-Tageszähler (`StagingAIBudgetDay`). Ledger, Reservierung, Kostenabrechnung, Ledger-Tagesobergrenze (`apps.ai_ledger.service.reserve`, unabhängig von diesem Flag), Not-Aus und Autorisierung bleiben aktiv. Keine Render-Variable wird geändert.

## Betriebliche Voraussetzung vor dem Staging-Deploy

Ist das Ledger auf Staging **nicht** konfiguriert, antworten Staging-Chat und Grounded nach dem Deploy mit 429 (fail-closed, beabsichtigt). Vor dem Deploy prüfen (read-only):

```bash
python manage.py audit_environment_parity   # Staging-Shell
# variables.VORNEQ_AI_LEDGER_ENABLED.value == true, capabilities.ai_ledger.state == "ENABLED"
```

## Rollback

Ein reiner `git revert` öffnet V4-F01/F02 wieder. Daher:

1. Zuerst kostenpflichtige Pfade amtlich stoppen (Owner: `VORNEQ_AI_EMERGENCY_STOP=true` oder Trial-Gate schließen).
2. Offene Reservierungen prüfen (`BudgetReservation` RESERVED/UNCERTAIN; keine Löschung ohne Owner-Freigabe).
3. Dann kontrolliert vorherigen SHA über `deploy.yml` deployen.
4. Bezahlte Funktionen erst nach Owner-Freigabe und mit Ledger wieder öffnen.

Keine Migration; keine Datenänderung.
