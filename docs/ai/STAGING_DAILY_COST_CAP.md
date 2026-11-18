# Staging: unabhängige Tagesgrenze trotz Shared Ledger

## Lücke (vor diesem Fix)
- Sobald der Shared Ledger aktiv ist (`shared_budget = hosted and ledger_enabled()`), übersprang `views_global.run_global_pipeline` die Funktion `reserve_staging_request()`.
- `reserve_global_request(..., burst_only=True)` zählt dann keine Tageswerte mehr.
- Folge: `VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS` und `VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD` wirkten in Staging **nicht**. Begrenzt hat nur noch der Restbetrag des gemeinsamen Ledgers, den sich Staging und Production teilen.

## Fix
- `apps.ai_ledger.service.reserve()` setzt für `VORNEQ_ENV == "staging"` immer eine Tagesgrenze (`StagingDailyLimit`). Für Production ändert sich nichts.
- Die Grenze wird in `reserve_with_config()` **in derselben Transaktion** geprüft, in der das Konto mit `select_for_update` gesperrt ist. Gleichzeitige Requests (Threads, Gunicorn-Worker, Instanzen) laufen damit seriell und können die Grenze nicht überschreiten.
- Gezählt werden alle Staging-Reservierungen seit 00:00 UTC des laufenden Tages:
  - `finalized` mit dem beobachteten Betrag
  - `reserved` und `uncertain` mit dem **vollen** reservierten Betrag
  - fehlgeschlagene Abrechnung: Die Zeile bleibt `reserved` und zählt voll.
- Abgelehnt wird, wenn die Anzahl ≥ `MAX_DAILY_REQUESTS` ist oder wenn bereits gebunden + neue Reservierung > `DAILY_CAP_MICROUSD` wäre. Es entsteht dann keine Reservierung und es gibt keinen Modellaufruf. Antwort: `429 rate_limited`, Log nur `ai_ledger_staging_daily_cap_reached kind=requests|amount`.
- Fail-closed: fehlende oder ungültige Grenzwerte, Fehler der Ledger-DB während der Prüfung und Redis-Ausfall vor der Reservierung führen jeweils zu keiner Reservierung und keinem Aufruf.
- Die Grenze gilt **auch** mit `VORNEQ_AI_STAGING_UNMETERED` und `VORNEQ_GLOBAL_AI_UNLIMITED_STAGING`. Diese Schalter betreffen nur die alte Tabelle und die Request-Drossel.
- Gezählt werden **bezahlte Modellaufrufe** (Ledger-Reservierungen). Fragen, die vor dem Modell an fehlender Evidenz scheitern, kosten nichts und zählen nicht.
- Keine Migration und keine neue Env-Variable. Genutzt werden die vorhandenen Variablen.

## Betrieb
- Mit den heutigen Staging-Werten (3 Requests, 30 000 µUSD) und ≈ 10 800 µUSD Worst Case pro Stage-2-Request sind 3 bezahlte Aufrufe pro UTC-Tag möglich.
- Für die 100-Fragen-Bewertung müssen **beide** Grenzen bewusst und mit eigener Freigabe angehoben werden. Beispiel: `MAX_DAILY_REQUESTS=100` und eine Betragsgrenze nach Budget.
- `staging_policy.trial_enabled()` erlaubt ohne `VORNEQ_AI_STAGING_UNMETERED` höchstens 5 Requests pro Tag.

## Tests
`apps/ai_ledger/tests/test_ledger_staging_daily_cap.py` (20 Tests, Nebenläufigkeit nur auf PostgreSQL):
- Konfiguration und UTC-Tagesgrenze
- Anzahl- und Betragsgrenze
- `finalized`/`uncertain`/Abrechnungsfehler
- Vortage zählen nicht
- Production unberührt
- falsche Anwendung der Grenze
- DB-Fehler und Not-Aus
- 20 gleichzeitige Threads
- gemischt Staging/Production
- 10 getrennte OS-Prozesse
- Endpunkt Ende-zu-Ende: dritter Aufruf 429, Replay ohne Kosten, Redis- und Ledger-Ausfall, fehlende Konfiguration

Gegenprobe: Mit deaktiviertem Fix schlagen die Endpunkt-Tests fehl.
