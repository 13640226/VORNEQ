# VORNEQ — Gemeinsames Prepaid-Budget für Global AI (Staging + Production) V1

**Stand:** 2026-11-14
**Basis:** `67f8578cc936f4affd6bceaf0c0e223455acaf0f`
**Status:** IMPLEMENTIERT, LOKAL GETESTET / NICHT PROVISIONIERT / NICHT AKTIVIERT / KEIN DEPLOY

## 1. Ziel und ehrliche Grenze

Global AI soll auf Staging und Production **ohne feste Tages-Request-Kontingente** laufen. Gedeckelt wird stattdessen über **eine gemeinsame Geldreserve**, abgeleitet aus einem verifizierten Prepaid-Guthaben beim Provider. Gleichzeitige Anfragen dürfen dasselbe Geld nicht zweimal reservieren.

**Keine Garantie gegen Überzug.** Der Provider liefert keinen synchronen, verbindlichen Kontostand und keinen harten Abschaltpunkt. Preise können sich ändern, Abrechnungen kommen verzögert. Das Ledger ist eine konservative Schätzung auf Anwendungsseite und keine Rechnung. Deshalb bleiben zusätzlich nötig: eine Sicherheitsreserve, das Spend-Limit des Provider-Projekts und eine deaktivierte automatische Aufladung.

## 2. Architektur

```
Staging-Request ─┐                           ┌─ Production-Request
                 ▼                           ▼
   Auth → Rolle/Allowlist → CSRF → Input → Router (lokal)
                 ▼
   Burst-Throttle pro Nutzer/Minute (Missbrauchsschutz, kein Tageslimit)
                 ▼
   Retrieval (kostenfrei für den Provider) → Ranking → Kontext
                 ▼
   BudgetedProvider:  reserve() ── erschöpft/Fehler → 429, KEIN Modellaufruf
                 ▼ (genau 1 Provider-Aufruf, max_retries=0)
   OpenAI Responses → settle(): FINALIZED (Usage-Tokens) | UNCERTAIN (volle Reservierung)
                 ▼
   Zitatprüfung → Antwort
```

- Das Ledger liegt in einer **eigenen PostgreSQL-Datenbank** (Alias `ai_ledger`, Variable `VORNEQ_AI_LEDGER_DATABASE_URL`). Beide Render-Dienste verbinden sich mit derselben Datenbank. Die Anwendungsdatenbanken bleiben getrennt.
- Der Router `apps/ai_ledger/router.py` migriert die Ledger-Modelle nur auf `ai_ledger` und dort keine anderen App-Modelle (verifiziert: in der Ledger-DB entstehen nur 3 Tabellen plus `django_migrations`).
- Tabellen werden nicht zur Laufzeit angelegt; es gibt die Migration `ai_ledger.0001_initial`. Der Request-time-`CREATE TABLE`-Prototyp ist ersetzt.

## 3. Datenmodell (integer micro-USD)

`BudgetAccount` ist genau ein Konto je `ledger_id`. Felder:

| Feld | Bedeutung |
|---|---|
| `total_allowance_micro` | konfigurierte Gesamterlaubnis |
| `safety_reserve_micro` | Reserve für verzögerte oder unsichere Kosten |
| `consumed_before_micro` | bereits vorher verbraucht, z. B. laut Billing-Konsole |
| `reserved_micro` | offene Reservierungen |
| `finalized_micro` | beobachtete Kosten |
| `uncertain_micro` | Kosten unbekannt, voll angerechnet |
| `emergency_stop` | Not-Aus im Ledger |
| `model_id` | einzig erlaubtes Modell |
| Ein- und Ausgabepreis | je 1 Mio. Token |
| `allowed_environments` | zugelassene Umgebungen |

Es gibt CHECK-Constraints für Nicht-Negativität, positive Preise, Währung USD und `reserved ≤ total`.

```
remaining = total − safety − consumed_before − reserved − finalized − uncertain
```

`BudgetReservation` speichert je Reservierung: `environment`, `service_id`, Git-SHA, Akteur, Betrag, Status (`reserved`, `finalized`, `uncertain`), Token, beobachtete Kosten und Ergebnis.

`ExternalUsageRecord` hält vom Owner nachgetragenen externen Verbrauch fest.

## 4. Reservierung und Abrechnung (`apps/ai_ledger/service.py`)

### Reservierung
- Nur PostgreSQL ist zulässig.
- Identitätsprüfung: `current_database() == VORNEQ_AI_LEDGER_DB_NAME`; die Konto-`ledger_id` muss `VORNEQ_AI_LEDGER_ID` entsprechen.
- Die Laufzeitumgebung muss genau zu ihrer Render-Service-ID passen: Staging `srv-dbm7…`, Production `srv-dadn…`. Außerdem muss ein Git-SHA vorhanden sein.
- `SELECT … FOR UPDATE` auf die Kontozeile serialisiert alle Reservierungen über Worker, Instanzen und Umgebungen hinweg.

### Worst-Case-Betrag
`(UTF-8-Bytes von Instruktionen + Payload + 2000 Overhead-Token) × Eingabepreis + max_output_tokens × Ausgabepreis`, aufgerundet und mit 1,25 multipliziert.

Begründung: Ein BPE-Token umfasst mindestens 1 Byte, also gilt Token ≤ Bytes. `max_output_tokens` begrenzt auch Reasoning-Token. Es gibt 0 Retries.

### Abrechnung (settle)
- Liefert der Provider authentische Usage-Token, wird die Reservierung FINALIZED zu den beobachteten Kosten.
- Bei Timeout, Fehler oder fehlender Usage wird sie UNCERTAIN zum vollen Betrag.
- Nichts wird automatisch erstattet.
- Die Abrechnung ist idempotent.
- Scheitert die Abrechnung selbst, bleibt die Reservierung RESERVED und zählt weiter. Das ist die sichere Richtung.

### Fail-closed
Bei deaktivierter oder falscher Konfiguration, falscher DB-Identität, DB-Ausfall, fremdem Ledger, nicht freigegebenem Modell, nicht freigegebener Umgebung oder Not-Aus erfolgt **kein Modellaufruf** (HTTP 429).

## 5. Konfiguration (alle Werte standardmäßig AUS)

| Variable | Wirkung |
|---|---|
| `VORNEQ_AI_LEDGER_DATABASE_URL` | gemeinsame Ledger-DB (beide Dienste identisch) |
| `VORNEQ_AI_LEDGER_ENABLED` | nur wirksam bei `VORNEQ_ENV` ∈ {staging, production} **und** gesetzter URL |
| `VORNEQ_AI_LEDGER_ID` | UUID des Kontos (beide Dienste identisch) |
| `VORNEQ_AI_LEDGER_DB_NAME` | erwarteter Name der Ledger-Datenbank |
| `VORNEQ_AI_EMERGENCY_STOP` | blockiert alle neuen Modellaufrufe (Global AI, Staging-Trial, Production) |
| `VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED` | Production-Flag; nur bei `VORNEQ_ENV=production` |
| `VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA` | muss `RENDER_GIT_COMMIT` entsprechen |
| `VORNEQ_AI_PRODUCTION_OWNER_AUTH` | `OWNER-AUTH-AI-PRODUCTION-…` |
| `VORNEQ_AI_PRODUCTION_APPROVED_MODEL` | muss `VORNEQ_AI_PHASE_B_MODEL` und dem Ledger-Modell entsprechen |
| `VORNEQ_AI_PRODUCTION_ACTOR_POLICY` | `allowlist` (Standard) oder `authenticated` |
| `VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS` | höchstens 50 IDs (bei `allowlist`) |

## 6. Sicherheitspolitik

- **Production** (`apps/ai_core/production_policy.py`) setzt alle diese Bedingungen voraus:
  - `production` und `DEBUG` aus
  - eigenes Flag
  - exakte Service-ID und exakter SHA
  - Owner-Referenz
  - Modell und Key vorhanden
  - Ledger konfiguriert
  - kein Not-Aus

  Ohne Ledger ist Production immer deaktiviert (404). Wer das trotzdem bis zum Modell schafft, bekommt 429. `trial_enabled()` und `global_ai_available()` wurden nicht entfernt. Production hat einen eigenen, expliziten Zweig.
- **Akteure:**
  - Staging: wie bisher Superuser plus Allowlist.
  - Production: angemeldet und aktiv, dazu Allowlist; oder ausdrücklich `authenticated`.
- **Unverändert:** CSRF, striktes JSON, Größenlimits, Router (private Daten → 422), SSRF/TLS/Allowlists, Zitat- und Zahlenprüfung, `verified=false`.
- **Kontingente:** Solange das Ledger aktiv ist, entfallen die Tageszähler (pro Nutzer und Tag, global pro Tag) und die Staging-Tagesreservierung. Bestehen bleibt ein Burst-Throttle pro Nutzer und Minute (Standard 3, höchstens 5) als Missbrauchsschutz. Ohne Ledger bleibt Staging exakt wie bisher.

## 7. Abgleich mit der Abrechnung (Reconciliation)

`python manage.py ai_ledger …` ruft weder den Provider noch Billing-APIs auf.

| Befehl | Zweck |
|---|---|
| `status` | nur lesend: alle Summen und `remaining` |
| `provision` | einmalig; bestätigte `--confirm-ledger-id`; Beträge in USD |
| `stop` / `resume` | Not-Aus im Ledger |
| `record-external --usd --note` | trägt in der Billing-Konsole beobachteten Verbrauch nach; erhöht `consumed_before` und kann niemals erstatten |

Empfohlener Ablauf: täglich Usage und Billing im Provider-Projekt ablesen und mit `finalized + uncertain` vergleichen. Fehlt etwas, Differenz mit `record-external` nachtragen. Lässt sich ein Abgleich nicht herstellen: `stop`.

## 8. Aktivierungs-Runbook (jeder Schritt braucht eine eigene Owner-Autorisierung)

1. **Guthaben prüfen** im Provider-Billing: Organisation und Projekt, tatsächlich verfügbares Guthaben, automatische Aufladung **aus**, Spend-Limit.
2. **Währung umrechnen:** EUR in USD mit dokumentiertem Kurs und Abschlag. Beispiel ohne Verifikation: 10 € werden konservativ angesetzt, etwa als `total = 8 USD`, `safety = 2 USD`.
3. **Ledger-PostgreSQL provisionieren:** eigene Instanz, eigener Nutzer mit Rechten nur auf diese DB, Zugriff ausschließlich für beide Render-Dienste. Danach `migrate --database ai_ledger` und `ai_ledger provision` mit verifizierten Modellpreisen.
4. **Beide Dienste** erhalten identische Werte für `VORNEQ_AI_LEDGER_*`. Danach in beiden Diensten `ai_ledger status`.
5. **Production-Build:** Der aktuelle Build installiert das OpenAI-SDK **nicht**. Vor der Aktivierung ist ein geprüfter, analog zum Staging-Build gelockter Build nötig (separater Change).
6. **Staging zuerst:** Ein kontrollierter Livetest mit wenigen Anfragen. Kosten und Ledger-Summen anschließend mit der Billing-Konsole vergleichen.
7. **Production:** SHA-gebundene Freigabe, Flag setzen, enger Allowlist-Start. Not-Aus testen.

## 9. Restrisiken

- Kein garantierter Schutz vor Überzug (siehe Abschnitt 1).
- Preisänderungen beim Provider erfordern ein neues `provision`. Es gibt heute kein `update-prices`; eine Änderung ist ein separater Change.
- Das Ledger ist ein Single Point: Fällt es aus, steht AI vollständig still (fail closed, gewollt).
- Der Burst-Throttle ist cache-basiert. Er schützt nur vor Missbrauch und nicht vor Kosten.
- Kosten der Wikimedia-Abfragen sind nicht enthalten (kostenfrei, aber rate-limitiert).
- `allowed_environments` und die Service-ID-Zuordnung sind im Code festgelegt; ein Dienstwechsel erfordert einen Code-Change.
