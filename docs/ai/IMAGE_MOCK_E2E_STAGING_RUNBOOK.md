# VORNEQ Bildgenerierung V1 – einmaliger Mock-E2E-Test auf Staging

Status: **CODE-ONLY / NICHT AUSGEFÜHRT**. Dieses Dokument ist keine
Ausführungsgenehmigung. Es beschreibt den einmaligen, auf Staging begrenzten
Live-Test

```
API → PostgreSQL-Queue → Worker-once (Mock) → privates R2-Objekt → signierte Owner-URL → Bereinigung
```

ohne OpenAI-Aufruf, ohne dauerhaften Worker und ohne Production-Änderung.

## Was der Test tut

Befehl: `run_staging_image_mock_e2e_once` (Modul `apps/core/staging_image_mock_e2e.py`).

1. **Immer zuerst read-only Preflight** (`inspect`): Render-Service
   `srv-dbm7dvc9v7es7393g70g`, exakter `RENDER_GIT_COMMIT`, `VORNEQ_ENV=staging`,
   `DEBUG=False`, PostgreSQL-Identität (`vorneq_staging_db_9i8v`, Rolle, PG 18,
   kein Standby), Migrationshistorie `ai_core` 0001–0004, privater R2-Bucket
   `vorneq-staging-ai-images`, **alle Image-Gates des Service geschlossen**,
   keine Emergency-Stop-Sperre, **Queue leer** (keine `queued`/`running`/`uncertain` Jobs).
2. Nur mit `--execute`: Prüfung des Arm-Schalters, des SHA-gebundenen
   Owner-Strings und eines **frischen, unbearbeiteten GitHub-Owner-Kommentars**
   in Issue #664 (live per TLS abgerufen, max. 30 Minuten gültig, Backup ≤ 2 h alt).
3. **Gegenseitiger Ausschluss:** Session-Advisory-Lock in PostgreSQL
   (`pg_try_advisory_lock(202611200501)`) für den gesamten Lauf; ein zweiter,
   gleichzeitiger Lauf wird vor Quittung und Schreibzugriff abgelehnt. Ebenso
   abgelehnt wird ein Lauf, wenn noch Benutzer `vorneq-e2e-*` eines früheren
   Laufs existieren.
4. **Einmal-Quittung** in `audit_auditevent` (Autocommit, eigene Verbindung)
   **vor** jedem Test-Schreibzugriff. Eine zweite Ausführung mit derselben
   Release-ID wird abgelehnt.
5. Zwei Wegwerf-Benutzer `vorneq-e2e-<zufall>-owner/-other` (ohne Passwort).
6. Das Image-Gate wird **nur innerhalb dieses einen Prozesses** geöffnet
   (`override_settings`), ausschließlich Provider `mock`, Paid-Gate geschlossen,
   Allowlist = nur die zwei Wegwerf-Benutzer, Tageslimit 1. Das Modul `openai`
   ist im Prozess gesperrt (`sys.modules["openai"] = None`).
7. Prüfungen über die echten Django-Views (In-Process-Client mit dem echten
   Staging-Host, HTTPS): anonym → 401, ohne CSRF-Token → 403, Owner-Submit → 202,
   identische Wiederholung → 200 ohne zweiten Job.
8. Nur wenn **genau dieser eine Job** in der Queue liegt: einmal
   `process_next_image_job()` → `completed`, `is_mock`, Prompt gelöscht,
   kein Ledger-Reservat, Objekt-Key `ai-generated/<owner>/<job>.png`.
9. Owner-Detail → signierte URL; anderer Benutzer → 404; anonym → 401.
   Download über die signierte URL (nur Host `*.r2.cloudflarestorage.com`,
   keine Redirects) → PNG, SHA-256 = gespeicherter Digest. Dieselbe URL ohne
   Signatur → 400/401/403.
10. **Bereinigung immer** (auch bei Fehlern), jeweils einzeln verifiziert:
   Sessions (Logout), R2-Objekt gelöscht und nicht mehr vorhanden, Jobs der
   Wegwerf-Benutzer gelöscht, Tagesquote exakt auf den Vorzustand zurückgesetzt,
   Wegwerf-Benutzer gelöscht.

Ergebniszeilen: `E2E_STEP_OK …`, `E2E_CLEANUP … OK|FAILED`,
`STAGING_IMAGE_MOCK_E2E_RESULT: PASS_CLEANUP_VERIFIED`.
Signierte URLs, Token und Prompts werden **nicht** ausgegeben.

## Was der Test bewusst nicht tut

- Kein OpenAI-/kostenpflichtiger Aufruf, keine Änderung der Image-Gates des
  Web-Service, kein dauerhafter Worker, kein `--loop`, keine Migration,
  keine Production-Änderung.
- Die Einmal-Quittung und Audit-Ereignisse (z. B. Logins der Wegwerf-Benutzer)
  bleiben absichtlich bestehen (append-only Audit).
- Wird der Prozess hart beendet (z. B. Render-Timeout, SIGKILL), läuft die
  Bereinigung nicht. Reste sind über `--find-residue` auffindbar (siehe unten);
  es gibt bewusst keine automatische Löschung.
- Der API-Test läuft In-Process gegen die echten Views und Middleware, nicht
  über das öffentliche Netz/den Render-Load-Balancer.

## Voraussetzungen

1. PR mit diesem Befehl ist gemergt, CI grün (SQLite + PostgreSQL, 3.11/3.12/3.14),
   und genau dieser SHA läuft auf Staging.
2. Frisches Staging-Backup (≤ 2 h) mit isoliertem Restore-Nachweis (SHA-256, Evidence-ID).
3. Read-only Preflight erfolgreich (siehe unten).

## 1. Read-only Preflight (ohne Genehmigung möglich, keine Schreibzugriffe)

Als Render One-off Job auf dem Staging-Web-Service:

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py run_staging_image_mock_e2e_once --expected-sha "$RENDER_GIT_COMMIT"
```

Erwartet: `READ_ONLY_PREFLIGHT_COMPLETE` und `STAGING_IMAGE_MOCK_E2E_RESULT: READ_ONLY_NO_GO`.

## 2. Owner-Freigabe (nur der Owner, neuer unbearbeiteter Kommentar in Issue #664)

```text
STAGING_IMAGE_MOCK_E2E_OWNER_RELEASE_V1
{"decision":"AUTHORIZE_STAGING_IMAGE_MOCK_E2E_ONCE","release_id":"IMGE2E-EXAMPLE-REPLACE","sha":"<EXACT_STAGING_DEPLOY_SHA_40_HEX>","service_id":"srv-dbm7dvc9v7es7393g70g","postgres_id":"dpg-dbm74m8u01pc738j8r1g-a","database":"vorneq_staging_db_9i8v","provider":"mock","paid_calls":false,"bucket":"vorneq-staging-ai-images","max_jobs":1,"backup_sha256":"<FRESH_BACKUP_SHA256_64_HEX>","backup_evidence":"<VERIFIED_RESTORE_ID>","backup_exported_at":"<UTC_YYYY-MM-DDTHH:MM:SSZ>","restore_verified_at":"<UTC_YYYY-MM-DDTHH:MM:SSZ>","expires_at":"<UTC_YYYY-MM-DDTHH:MM:SSZ>","risk_acceptance":"ACCEPT_STAGING_MOCK_E2E_WRITE_AND_CLEANUP"}
```

`expires_at` höchstens 30 Minuten nach Erstellung des Kommentars. Jede
Abweichung (Provider, `paid_calls`, Bucket, `max_jobs`, Service, SHA, Backup)
führt zur Ablehnung. Ein Kommentar für 0004 kann nicht wiederverwendet werden.

## 3. Temporäre, eng begrenzte Staging-Variablen (Owner, nach Freigabe)

Diese Variablen öffnen **kein** Image-Gate; `VORNEQ_AI_IMAGE_ENABLED` und
`VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED` bleiben `false`.

```text
VORNEQ_IMAGE_MOCK_E2E_WRITE_MODE=ONE_USE_OWNER_RELEASE
VORNEQ_IMAGE_MOCK_E2E_ARMED_SHA=<EXACT_STAGING_DEPLOY_SHA_40_HEX>
VORNEQ_IMAGE_MOCK_E2E_AUTH=OWNER-AUTH-STAGING-AI-IMAGE-MOCK-E2E-<RELEASE_ID> @ <EXACT_STAGING_DEPLOY_SHA_40_HEX>
VORNEQ_IMAGE_MOCK_E2E_OWNER_COMMENT_ID=<NEW_UNEDITED_GITHUB_COMMENT_ID>
VORNEQ_IMAGE_MOCK_E2E_BACKUP_SHA256=<FRESH_BACKUP_SHA256_64_HEX>
VORNEQ_IMAGE_MOCK_E2E_BACKUP_EVIDENCE=<VERIFIED_RESTORE_ID>
VORNEQ_IMAGE_MOCK_E2E_GITHUB_READ_TOKEN=<SCOPED_READ_ONLY_TOKEN_FROM_RENDER_SECRET>
```

Den Token nie in die Job-Befehlszeile schreiben (Render protokolliert den Befehl).

## 4. Einmalige Ausführung

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py run_staging_image_mock_e2e_once \
  --expected-sha "$RENDER_GIT_COMMIT" \
  --release-id "<APPROVED_RELEASE_ID>" --execute
```

## 5. Danach

1. Alle `VORNEQ_IMAGE_MOCK_E2E_*` Variablen entfernen.
2. Read-only Preflight erneut: Queue leer, Gates geschlossen,
   `IMAGE_JOB_ROW_COUNT`/`IMAGE_QUOTA_ROW_COUNT` wie vor dem Test.
3. Ergebnis (Log-Zeilen, Release-ID, SHA, Kommentar-ID; keine URLs/Token) in Issue #664 dokumentieren.

## Reste nach Abbruch finden (read-only)

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py run_staging_image_mock_e2e_once --expected-sha "$RENDER_GIT_COMMIT" --find-residue
```

Meldet nur Anzahlen (Benutzer `vorneq-e2e-*`, deren Jobs, R2-Objekte unter
`ai-generated/<id>/`, verbrauchte Quittungen) und
`E2E_RESIDUE_RESULT: NONE|PRESENT_OR_UNKNOWN`. Ändert oder löscht nichts.
Eine Bereinigung von Resten ist eine eigene, gesondert freizugebende Maßnahme.

## Bei Fehlern

- `…_REFUSED`: es wurde nichts geschrieben (vor der Quittung abgebrochen).
- `…_ABORTED`: Quittung verbraucht; Testdaten wurden bereinigt, sofern nicht
  `CLEANUP_INCOMPLETE` gemeldet wird. **Nicht automatisch wiederholen.**
  Bei `CLEANUP_INCOMPLETE` zuerst `--find-residue` ausführen, dann manuell prüfen: R2-Präfix `ai-generated/<owner-id>/`,
  Benutzer `vorneq-e2e-*`, `ai_core_aiimagejob`, `ai_core_aiimagedailyquota`.
  Eine neue Ausführung benötigt eine neue Owner-Freigabe mit neuer Release-ID.

## Offline-Tests

`python manage.py test apps.core.tests.test_staging_image_mock_e2e`
