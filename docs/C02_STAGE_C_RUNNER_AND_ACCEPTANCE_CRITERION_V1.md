# C02 — Operative Verbindungsprüfung, Abnahmekriterium und Runner Stufe C (V1)

| Feld | Wert |
|---|---|
| Datum | 2026-11-15 |
| Basis | `main` @ `048172780bb645f5043bed019e084f1814e7ca07` |
| Branch | `feat/c02-stage-c-runner` |
| Status | **VORSCHLAG / ENTSCHEIDUNG DES EIGENTÜMERS AUSSTEHEND** |
| Endzustand | `C02 = OPEN` · `PRODUCTION_MIGRATION_GO = NO` · `PAID_AI = OFF` |

Diese Änderung enthält **keine** Production-Migration, keine Datenbank-, Allowlist-, Secret- oder Render-Änderung. Der Schreibpfad für Production ist im Code gesperrt (`PRODUCTION_WRITE_ENABLED = False`, durch einen Test festgeschrieben). Merge oder Deploy dieser Änderung erlauben keine Migration.

## 1. Ausgangslage: Antwort von Render

Grundlage ist der Bericht des Eigentümers vom 2026-11-15. Die E-Mail selbst wurde in dieser Sitzung nicht eingesehen.

Die Antwort von Render stammt von einem automatisierten Agenten, nicht von einem Menschen. Ihr Inhalt:
- Render bietet keinen kryptografischen Nachweis, der eine PostgreSQL-Sitzung an eine Resource-ID bindet.
- Empfohlen wird eine operative Prüfung: Die `DATABASE_URL` des Dienstes muss der **Internal URL** der Ziel-Datenbank im Dashboard entsprechen.
- Interne Verbindungen innerhalb desselben Kontos und derselben Region laufen über das private Netz von Render.

Daraus folgt: `POSTGRES_BACKEND_CRYPTOGRAPHIC_IDENTITY = NOT_AVAILABLE`. Das ist eine Eigenschaft der Plattform, kein offener Prüfschritt. Ein Kriterium, das diesen Nachweis verlangt, wäre nie erfüllbar.

## 2. Priorität 1: operative Prüfung ohne Offenlegung von Geheimnissen

Die Prüfung vergleicht die `DATABASE_URL` der Laufzeit mit der Internal URL aus dem Dashboard über einen HMAC-SHA256. Der Schlüssel ist eine frische, einmalige Nonce. Die URL selbst wird nie ausgegeben, nie als Kommandozeilen-Argument übergeben und nie gespeichert.

**Schritt 1 — Nonce erzeugen** (lokal, für jede Prüfung neu):

```text
python -c "import secrets; print(secrets.token_hex(32))"
```

**Schritt 2 — Render Web Shell des Production-Dienstes** `srv-dadn07eq1p3s73eccau0`:

```text
DJANGO_SETTINGS_MODULE=config.settings_render python manage.py c02_internal_url_binding --nonce <NONCE>
```

Erwartete Ausgabe:
- `C02_HOST_CLASS: INTERNAL_EXACT` — der Host ist exakt `dpg-dagru1h42hec73eqr960-a`, ohne Domain. Das ist die Form des privaten Netzes.
- `C02_LOGICAL_TARGET_MATCH: True`
- `C02_DJANGO_SETTINGS_FROM_DATABASE_URL: True` — Djangos aktive Verbindung stammt aus genau dieser URL.
- `C02_OPERATIONAL_PRECHECK: True`
- dazu `C02_DATABASE_URL_HMAC_SHA256: <digest>`

Der Befehl öffnet keine Datenbankverbindung und führt kein SQL aus.

**Schritt 3 — lokal auf dem eigenen Rechner:** Im Render Dashboard die Datenbank `dpg-dagru1h42hec73eqr960-a` öffnen, dann **Connect → Internal** und die Internal Database URL kopieren. Danach:

```text
python scripts/c02_tests/internal_url_digest.py --nonce <NONCE> --expected-digest <digest aus Schritt 2>
```

Die URL wird verdeckt eingegeben. Erwartet werden `DASHBOARD_URL_HOST_IS_INTERNAL_EXACT: True` und `C02_DIGEST_COMPARISON: MATCH`. Das Skript nutzt nur die Standardbibliothek und hat weder Netzwerk- noch Datenbankzugriff.

**Was ein MATCH belegt:**
- Der Production-Dienst nutzt exakt die Internal URL, die das authentifizierte Render-Control-Plane für diese Resource-ID anzeigt.
- Die Verbindung läuft über den internen Hostnamen und damit über das private Netz.

**Was ein MATCH nicht belegt:**
- Es gibt weiterhin keinen kryptografischen Nachweis der Backend-Identität.
- Der Ehrlichkeit des Render-Control-Planes wird vertraut.

Das Ergebnis ist mit Nonce, Digest, Zeitpunkt und deployter SHA im Issue #407 festzuhalten.

## 3. Priorität 2: vorgeschlagenes Abnahmekriterium für C02

Dies ist ein Vorschlag. **C02 bleibt offen**, bis der Eigentümer SHA-gebunden entscheidet.

C02 gilt für die Migration von `ai_core.0001` und `ai_core.0002` als erfüllt, wenn **alle** folgenden Punkte am Tag der Ausführung nachgewiesen sind:

| Nr. | Kriterium | Nachweis |
|---|---|---|
| A1 | Metadaten des Control-Planes: Resource-ID, DB-Name, User, PG 18, primary, Region, Environment | Render API/CLI, bereits als `VERIFIED_METADATA` vorhanden; am Ausführungstag erneut prüfen |
| A2 | `DATABASE_URL` = Internal URL aus dem Dashboard | Abschnitt 2: `MATCH` mit frischer Nonce |
| A3 | Djangos aktive Verbindung stammt aus dieser URL; Host `INTERNAL_EXACT` | `c02_internal_url_binding` |
| A4 | Die Live-Sitzung hat die erwartete DB, den erwarteten User, PG 18 und ist ein schreibbarer Primary | Runner Stufe C, in der Ausführungs-Transaktion |
| A5 | deployte SHA = autorisierte SHA | Runner (`RENDER_GIT_COMMIT`) |
| A6 | frisches, wiederherstellbares Backup derselben Datenbank | Backup-Referenz in `VORNEQ_C02_BACKUP_EVIDENCE`; Wiederherstellbarkeit durch den Eigentümer belegt |
| A7 | exakter Migrationsplan, leerer Vorzustand, Sperren, Atomarität, Prüfung vor dem Commit | Runner Stufe C |
| A8 | SHA-gebundene Freigabe des Eigentümers | `OWNER-AUTH-C02-MIGRATION-<ID> @ <sha>` |

**Akzeptiertes Restrisiko (ausdrücklich):** Es gibt keinen kryptografischen Nachweis der Backend-Identität (siehe Abschnitt 1). Das Vertrauen in das Render-Control-Plane ist dasselbe Vertrauen, auf dem der gesamte Betrieb ohnehin beruht.

Entscheidungsoptionen des Eigentümers:
- **(a) Empfohlen:** A1–A8 als Kriterium annehmen. Begründung: Mehr Nachweis bietet die Plattform nicht. Wird mehr verlangt, bleibt C02 dauerhaft offen.
- **(b)** wie (a), zusätzlich eine menschliche Bestätigung durch den Render-Support. Das erhöht die Sicherheit über die Aussage, liefert aber keinen technischen Nachweis.
- **(c)** C02 bleibt offen. Keine Migration.

## 4. Priorität 3: Runner Stufe C

Neu sind `apps/core/c02_stage_c_runner.py` und der Befehl `manage.py c02_stage_c_runner --target lab|production --expected-sha <sha> [--commit]`.

Ablauf in **einer** PostgreSQL-Transaktion auf **einer** Backend-Sitzung:
1. **Autorisierung vor jedem SQL:**
   - `production` wird sofort abgelehnt (`C02 OPEN: production write path disabled`).
   - `lab` akzeptiert nur `VORNEQ_ENV=development`, `C02_STAGE_C_LAB=YES`, keine `RENDER_*`-Variablen, einen lokalen Host und einen Namen `test_*` oder `isolated_c02_test`.
2. **Erneute Identitätsprüfung in der Live-Sitzung:** DB, User, PG-Major, schreibbarer Primary.
3. **Sperren:** `lock_timeout` 2 s, `statement_timeout` 60 s, `LOCK TABLE django_migrations … NOWAIT` und eine Advisory-Sperre auf Transaktionsebene.
4. **Vorzustand:** Weder Tabellen noch Historie von `ai_core` sind vorhanden. Der Plan ist exakt `0001` → `0002`.
5. **Ausführung:** `MigrationExecutor.migrate`. Davor und danach wird geprüft, dass PID, Treiber-Objekt und txid unverändert sind.
6. **Prüfung vor dem Commit:**
   - genau die zwei Tabellen
   - Index `ai_chat_guard_created_idx`
   - beide validierten Constraints
   - Historie exakt
   - Plan leer
   - Quell-SHA unverändert
   - Jeder Fehler führt zum Rollback der gesamten Transaktion.
7. **Commit** — oder im Probelauf (ohne `--commit`) ein bewusster Rollback.
8. **Prüfung nach dem Commit** in einer separaten `READ ONLY`-Transaktion: Zustand, Plan und `SELECT 1`.

Für den späteren Production-Pfad ist das Gate bereits spezifiziert und getestet; ein Test schaltet es nur für die Prüfung ein. Es verlangt:
- `VORNEQ_ENV=production`
- die erwartete Service-ID
- `RENDER_GIT_COMMIT` = autorisierte SHA
- `VORNEQ_C02_MIGRATION_AUTH` SHA-gebunden
- `VORNEQ_C02_BACKUP_EVIDENCE`
- AI aus
- `DATABASE_URL` mit internem Host, aus der die Django-Einstellungen stammen

Zum Einschalten ist ein **eigener PR** nötig, der `PRODUCTION_WRITE_ENABLED` und den Stolperdraht-Test ändert. Er braucht die Entscheidung nach Abschnitt 3.

`post_migrate` (Content Types, Berechtigungen) wird bewusst nicht ausgelöst: Der Schreibumfang sind genau die zwei Migrationen. Für `ai_core` gibt es weder eine Admin-Registrierung noch Berechtigungsprüfungen.

## 5. Tests (echte Ausführung, 2026-11-15)

- `config.tests.test_c02_operational_binding` und `config.tests.test_c02_stage_c_runner`: **31 Tests, OK auf PostgreSQL 16.15** (lokal, CI-Topologie).
  - Auf SQLite laufen 19 davon; 12 PostgreSQL-Integrationstests werden dort übersprungen.
- Die Integrationstests nutzen die echte Test-Datenbank und decken ab:
  - Probelauf mit Rollback
  - Commit mit Schemaprüfung
  - zweiter Lauf wird abgelehnt
  - Teilzustand `0001` wird ohne Änderung abgelehnt
  - falsche Identität
  - Sitzungswechsel nach `migrate`
  - Fehler in der Prüfung vor dem Commit
  - SHA-Drift
  - unerwartete Ausnahme
  - Advisory-Sperre und Sperre auf `django_migrations` werden von einer echten zweiten Verbindung gehalten
  - Befehl Ende-zu-Ende
  - In allen Fehlerfällen bleibt der Zustand `(0, 0)`.
- Gesamtsuiten:
  - SQLite: **1573 OK** (45 übersprungen)
  - PostgreSQL 16.15 in CI-Topologie (Host `postgres`, `VORNEQ_QUARANTINE_CI_DB_TEST_MODE`): **1573 OK** (11 übersprungen)
  - `check` und `makemigrations --check`: sauber
- Nebenbefund aus dem ursprünglichen Patch-Test: In der Gesamtsuite waren `RENDER_GIT_COMMIT` und `RENDER_SERVICE_ID` danach in `os.environ` sichtbar; das Lab-Gate hat dies korrekt abgelehnt (`Render environment detected`).
  - Die parallelen Ledger-Tests C01 und C02 wurden als konkrete Ursache für ein mögliches Restore-Race durch `patch.dict(os.environ, ...)` identifiziert und im nachträglichen Review auf explizite, thread-sichere Identitätsparameter umgestellt.
  - Der Stage-C-End-to-End-Test verwendet unabhängig davon weiterhin `clear=True` als Defense-in-Depth.
  - Die neuen Regressionstests prüfen die Isolation. Ein vollständiger erneuter PostgreSQL-Suite-Lauf kann zusätzliche globale Nebenwirkungen aufdecken.

Nachträgliche unabhängige Prüfung (2026-11-15, separater Checkout): Die 31 neuen Stage-C-/Binding-Tests liefen auf einem separaten, lokalen PostgreSQL-18-Docker-Container vollständig erfolgreich. Nach Behebung der RENDER_*-Umgebungsleckage in den parallelen Ledger-Tests C01/C02 liefen 35 Tests auf PostgreSQL 18 erfolgreich (31 Stage-C-/Binding-Tests, 2 neue Isolations-Regressionstests und 2 echte Ledger-Concurrency-Tests). Zusätzlich liefen in SQLite die 31 Stage-C-/Binding-Tests mit 19 OK und 12 PostgreSQL-spezifischen Skips sowie die 2 Isolations-Regressionstests mit 2 OK. Keine Produktionsverbindung und keine Produktions-Migration wurden verwendet.

Ursache des RENDER_*-Lecks: `apps/ai_ledger/tests/test_ledger_postgres.py` verwendete `patch.dict(os.environ, ...)` innerhalb gleichzeitig laufender Worker in C01 und C02. Der bestehende C15-Test hatte bereits kommentiert, dass diese Nebenläufigkeit das globale `os.environ` beschädigen kann. C01 und C02 verwenden nun `do_reserve_explicit()` mit direktem `reserve_with_config(...)`, ohne globale Umgebungsänderung. Zwei Regressionstests unter `config/tests/test_c02_stage_c_env_isolation.py` prüfen explizite Identität und unveränderte Umgebungsvariablen. Die zuvor berichteten Gesamtsuiten (1573 Tests auf SQLite und PostgreSQL 16.15) stammen aus der Patch-Übergabe und sind nicht gleichbedeutend mit einer hier erneut durchlaufenen vollständigen PostgreSQL-18-Suite.

Restgrenze: PostgreSQL 18 wurde für die genannten 35 fokussierten Tests geprüft, nicht für die gesamte Django-Suite. Ein späterer Production-Runner bleibt gesperrt und erfordert einen separaten PR, frische Belege und SHA-gebundene Eigentümerfreigabe.

## 6. Nächste Schritte

1. Den Eigentümer-Ablauf aus Abschnitt 2 ausführen und das Ergebnis in #407 festhalten.
2. Entscheidung über das Kriterium (a), (b) oder (c) nach Abschnitt 3.
3. Erst danach, als eigener PR mit eigener Freigabe: `PRODUCTION_WRITE_ENABLED` umschalten, frisches Backup anlegen, SHA-gebundene Ausführung.
