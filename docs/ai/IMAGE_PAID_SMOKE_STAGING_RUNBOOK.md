# VORNEQ Bildgenerierung – einmaliger, kostenpflichtiger Smoke-Test auf Staging

Status: **CODE-ONLY / NICHT AUSGEFÜHRT / NO_GO**. Dieses Dokument ist keine
Ausführungsgenehmigung. Es beschreibt einen einzigen, begrenzten Aufruf der
OpenAI Images API (`gpt-image-2.6-flare`, `quality=low`, `complexity=low`,
`1024x1024`, `n=1`) für **einen** Wegwerf-Benutzer auf Staging. Kein Worker,
kein Retry, keine Production-Änderung, keine Migration.

Befehl: `run_staging_image_paid_smoke_once` (Modul `apps/core/staging_image_paid_smoke.py`).

## Kostenmodell (Stand der offiziellen Preisliste vom 20.11.2026)

- `gpt-image-2.6-flare`: Text-Input 5 USD / 1 Mio. Tokens, Bild-Output 30 USD / 1 Mio. Tokens
  (`OFFICIAL_PRICES_MICRO_PER_MTOK`). Ein offizieller Preis pro Bild für 2.6 ist
  nicht veröffentlicht; der tatsächliche Verbrauch steht in `usage` der Antwort.
- Reservierung vor dem Aufruf = Ledger-Formel
  `ceil(((Prompt-Bytes + 2000) × 5 000 000 + Output-Bound × 30 000 000) / 10^6 × 1,25)` Mikro-USD.
- Fester Smoke-Prompt: 70 Bytes. Damit gilt:
  - Output-Bound 1 000 → 50 438 Mikro-USD (≈ 0,050 USD)
  - Output-Bound 2 000 → 87 938 Mikro-USD (≈ 0,088 USD)
  - **größter Bound für 0,10 USD: 2 321 Tokens**
- Die Reservierung begrenzt die **Buchung im Ledger**, nicht die Abrechnung durch
  OpenAI. Überschreitet `usage.output_tokens` den Bound, wird der tatsächliche
  Betrag im Ledger erfasst, das Bild aber nicht freigegeben (`usage_exceeded_bound`).
  Eine harte Kostenobergrenze vor dem Aufruf ist daher **nicht beweisbar**; das
  Ausgabenlimit des OpenAI-Projekts ist eine **zwingende, unabhängige** Kontrolle
  und wird im Owner-Manifest bestätigt (`openai_project_budget_usd`, nicht prüfbar).

## Sicherungen

1. Read-only Preflight (Standard): Identität (Service, SHA, PostgreSQL, Migrationen
   `ai_core` 0001–0004), Service-Gates geschlossen, Queue leer, keine Reste,
   Modell/Complexity/Preisreferenz, Output-Bound, Request- und Tagesobergrenze,
   Worst Case ≤ Obergrenze, HMAC-Schlüssel, `VORNEQ_OPENAI_IMAGE_API_KEY` vorhanden (nur
   Existenz, niemals Fallback auf `OPENAI_API_KEY` des Chats), SDK installiert, keine Worker-Identität, Ledger (siehe unten).
   Ergebnis `STAGING_IMAGE_PAID_SMOKE_PREFLIGHT: GO|NO_GO`.
2. Ledger-Prüfung ausschließlich in einer `READ ONLY`-Transaktion: Ledger aktiv,
   Datenbankidentität, Tabellen, Migration `ai_ledger.0001_initial` in der
   Ledger-DB vermerkt, eigenes Bild-Konto (≠ Chat-Konto), `model_id`,
   **`allowed_environments == "staging"`**, kein Emergency-Stop, offizielle Preise,
   Restguthaben ≥ Obergrenze, keine offenen Reservierungen. Zusätzlich
   `LEDGER_SHARED_WITH_PRODUCTION=True|False` (das Ledger ist absichtlich
   Staging und Production gemeinsam).
3. `--execute` nur mit Arm-Schalter, SHA-gebundenem Owner-String und frischem,
   unbearbeitetem GitHub-Owner-Kommentar (Issue #664, ≤ 30 min, Backup ≤ 2 h),
   danach erneut Preflight = GO.
4. Advisory-Lock (gemeinsam mit dem Mock-E2E), Einmal-Quittung in
   `audit_auditevent` vor jedem Schreibzugriff.
5. Gate nur prozesslokal für **einen** Wegwerf-Benutzer `vorneq-paid-smoke-*`,
   Tageslimit 1, `MAX_REQUEST = min(Manifest, Einstellung)`.
6. Provider: Moderation vorab, genau ein Aufruf, `max_retries=0`,
   `safety_identifier` = HMAC-SHA256 mit Server-Schlüssel (nie die rohe Benutzer-ID).
7. Ledger-Ausgang:
   - nachweislich **nicht gesendet** (Gate, Konfiguration, SDK, Vorab-Moderation,
     Obergrenze) → `release()` (FINALIZED, 0 USD, `released:<Grund>`);
   - **gesendet oder unklar** (HTTP 400/401/403/429/5xx, Timeout, Verbindungsabbruch,
     leere/ungültige Antwort, R2-Fehler danach) → `uncertain` zum vollen Betrag,
     kein Retry;
   - Erfolg → FINALIZED mit tatsächlichem `usage`.
8. Erfolg: signierter Download (SigV4) mit SHA-256-Abgleich, Zugriff ohne Signatur
   abgelehnt, danach Bereinigung (Objekt, Job, Quote, Benutzer). Ledger-Zeilen und
   Quittung bleiben (Audit). Bei `uncertain`: **keine** Bereinigung
   (`PAID_SMOKE_CLEANUP DEFERRED_FOR_RECONCILIATION`), manuelle Abstimmung.

## Befund: read-only Ledger-Audit vom 20.11.2026

Render-Job `job-dc0bj6gn74is73b2vvq0` auf `srv-dbm7dvc9v7es7393g70g`, SHA
`10563f4f…`, ausschließlich `SET TRANSACTION READ ONLY` (Skript-SHA-256
`ca2d6dfc…633d1`). Keine Schreibzugriffe, keine Zugangsdaten in der Ausgabe.

| Kontrolle | Status | Beleg |
|---|---|---|
| Ledger aktiv, URL gesetzt | VERIFIED | `ledger_enabled_setting=True`, `ledger_url_set=True` |
| Datenbankidentität | VERIFIED | `current_database=vorneq_ai_ledger` = erwartet; Host-Ressource `dpg-dbsb7i61egvs73dc37i0-a` |
| Rolle | VERIFIED | `current_user = session_user = vorneq_ai_ledger_user` |
| Primary (kein Replica) | VERIFIED | `in_recovery_replica=False`, PostgreSQL 18.6 |
| Tabellen und Spalten | VERIFIED | BudgetAccount, BudgetReservation, ExternalUsageRecord: Spalten = Modell |
| Migration in der Ledger-DB | VERIFIED | `ai_ledger_migrations=0001_initial`, keine fremden Apps |
| Chat-Konto | VERIFIED | 1 Konto, `gpt-5-mini`, `staging,production`, nicht gestoppt, Summen = Zeilen |
| Gemeinsame Nutzung | VERIFIED | 29 Reservierungen: 15 production, 14 staging (Chat-Konto) |
| Offene Reservierungen | VERIFIED | `reserved_micro=0`, keine älter als 15 min |
| Unklare Kosten Chat | OPEN | 6 × `uncertain`, zusammen 34 676 Mikro-USD (≈ 0,035 USD), Abgleich ausstehend |
| `VORNEQ_AI_IMAGE_LEDGER_ID` | MISSING | `image_ledger_id_set=False` |
| Eigenes Bild-Konto | MISSING | `account_count=1` (nur Chat) |
| OpenAI-Projektlimit | NOT_VERIFIED | von hier aus nicht prüfbar |

Moderation: Der Moderation-Endpunkt ist laut OpenAI kostenlos und zählt nicht
zu den Nutzungslimits; eine abgelehnte Vorab-Moderation verursacht daher keine
Bildkosten (`request_sent=False` ist zulässig).

Wiederholbar ohne Ad-hoc-Skript (nach Merge/Deploy):

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py run_staging_image_paid_smoke_once --expected-sha "$RENDER_GIT_COMMIT" --ledger-audit
```

## Voraussetzungen (jeweils eigene Owner-Entscheidung, nicht Teil dieses PR)

1. Ledger-Datenbank, Tabellen und Migration: **bestätigt** (siehe Befund). Keine
   weitere Migration nötig; keine Migration ohne gesonderte Freigabe.
2. Eigenes Bild-Konto im Ledger: neue `ledger_id`, `model_id=gpt-image-2.6-flare`,
   Preise 5 000 000 / 30 000 000, `allowed_environments=staging`, kleines Guthaben.
   Anlage ist ein Schreibzugriff auf das gemeinsame Ledger → gesonderte Freigabe.
3. Ausgabenlimit im OpenAI-Projekt gesetzt (z. B. ≤ 5 USD).
4. Staging-Variablen (Gates bleiben `false`):
   `VORNEQ_AI_IMAGE_LEDGER_ID`, `VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND` (≤ 2321),
   `VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD` (≤ 100000), `VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD`,
   `VORNEQ_AI_IMAGE_SAFETY_ID_KEY` (≥ 32 Zeichen, geheim), `VORNEQ_AI_IMAGE_COMPLEXITY=low`.
5. Merge und Staging-Deploy dieses PR (gesonderte Freigabe).

## 1. Read-only Preflight

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py run_staging_image_paid_smoke_once --expected-sha "$RENDER_GIT_COMMIT"
```

Endet immer mit `STAGING_IMAGE_PAID_SMOKE_RESULT: READ_ONLY_NO_GO`.

## 2. Owner-Freigabe (neuer, unbearbeiteter Kommentar in Issue #664)

```text
STAGING_IMAGE_PAID_SMOKE_OWNER_RELEASE_V1
{"decision":"AUTHORIZE_STAGING_IMAGE_PAID_SMOKE_ONCE","release_id":"IMGPAID-EXAMPLE-REPLACE","sha":"<SHA>","service_id":"srv-dbm7dvc9v7es7393g70g","postgres_id":"dpg-dbm74m8u01pc738j8r1g-a","database":"vorneq_staging_db_9i8v","provider":"openai","paid_calls":true,"model":"gpt-image-2.6-flare","size":"1024x1024","quality":"low","complexity":"low","max_jobs":1,"max_cost_microusd":100000,"image_ledger_id":"<IMAGE_LEDGER_UUID>","ledger_shared_with_production_accepted":true,"openai_project_budget_usd":5,"bucket":"vorneq-staging-ai-images","backup_sha256":"<SHA256>","backup_evidence":"<RESTORE_ID>","backup_exported_at":"<UTC>","restore_verified_at":"<UTC>","expires_at":"<UTC>","risk_acceptance":"ACCEPT_STAGING_PAID_IMAGE_SMOKE_COST_AND_SHARED_LEDGER_WRITE"}
```

## 3. Temporäre Variablen und Ausführung

```text
VORNEQ_IMAGE_PAID_SMOKE_WRITE_MODE=ONE_USE_OWNER_RELEASE
VORNEQ_IMAGE_PAID_SMOKE_ARMED_SHA=<SHA>
VORNEQ_IMAGE_PAID_SMOKE_AUTH=OWNER-AUTH-STAGING-AI-IMAGE-PAID-SMOKE-<RELEASE_ID> @ <SHA>
VORNEQ_IMAGE_PAID_SMOKE_OWNER_COMMENT_ID=<COMMENT_ID>
VORNEQ_IMAGE_PAID_SMOKE_BACKUP_SHA256=<SHA256>
VORNEQ_IMAGE_PAID_SMOKE_BACKUP_EVIDENCE=<RESTORE_ID>
```

Der vorhandene `VORNEQ_IMAGE_MOCK_E2E_GITHUB_READ_TOKEN` wird nur gelesen.

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py run_staging_image_paid_smoke_once --expected-sha "$RENDER_GIT_COMMIT" \
  --release-id "<RELEASE_ID>" --execute
```

Ausgabe u. a. `PAID_SMOKE_LEDGER status=… reserved_micro=… observed_micro=…
input_tokens=… output_tokens=…` – keine URL, kein Prompt, kein Schlüssel.
Danach alle `VORNEQ_IMAGE_PAID_SMOKE_*` entfernen, Preflight erneut ausführen und
den tatsächlichen Verbrauch mit der OpenAI-Abrechnung abgleichen
(`ExternalUsageRecord` nur durch den Owner).

## Offline-Tests

```bash
python manage.py test apps.ai_core.tests.test_image_paid_provider_v1 \
  apps.ai_core.tests.test_image_paid_worker_v1 apps.ai_ledger.tests.test_ledger_release \
  apps.core.tests.test_staging_image_paid_smoke
```

Ledger- und Ausführungstests laufen nur auf PostgreSQL (auf SQLite übersprungen).

## Globale Tagesquote (Befund IMGPAID-20261121-02)

Ursache des Abbruchs von `IMGPAID-20261121-02` (HTTP 400, „paid submit response invalid“):
der Runner setzte prozesslokal `VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=1`; ein am selben
UTC-Tag über das Image Studio eingereichter Mock-Job hatte `AIImageDailyQuota.submitted`
bereits auf 1 gesetzt (`1 >= 1` → `global image daily cap`). Der Preflight prüfte die Quote
nicht, daher wurde der Einmal-Beleg verbraucht; der Provider wurde nicht aufgerufen.

Korrektur:

- Preflight-Prüfung `global_daily_quota_available` (`submitted_today < globaler Dienst-Cap`).
- Dieselbe Prüfung unmittelbar **vor** dem Verbrauch des Einmal-Belegs → `Refused`
  (`PAID_SMOKE_PREFLIGHT_GLOBAL_QUOTA_EXHAUSTED`), kein Beleg, keine Reservierung, kein Aufruf.
- Der Runner erlaubt genau **eine** weitere Einreichung auf den heutigen Stand
  (`submitted_today + 1`), nie über dem Dienst-Cap; Quote wird weder zurückgesetzt noch entfernt.
- Abgelehnte Einreichung wird klassifiziert (`PAID_SMOKE_SUBMIT_REJECTED_GLOBAL_DAILY_CAP`,
  `…_AUTHORIZATION`, `…_REJECTED`) – ohne Prompt, Nutzer-ID oder Antworttext.
- Der Mock-E2E-Runner hat dieselbe feste Grenze 1 (Folgepunkt, hier nicht geändert).
