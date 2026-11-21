# Bild-Ledger-Konto, OpenAI-Kostenkontrollen und Abgleich offener Chat-Reservierungen

Stand: 2026-11-20. Status: **Entwurf / Planung**. Es wurde kein Konto angelegt, kein
Ledger-Eintrag geändert, keine Einstellung bei OpenAI oder Render verändert und kein
kostenpflichtiger OpenAI-Aufruf ausgeführt.

## A. Spezifikation des separaten Bild-Kontos

| Feld | Vorgabe | Durchsetzung |
|---|---|---|
| Ledger-ID | neue, zufällige UUIDv4, vom Eigentümer erzeugt; ≠ Chat-`VORNEQ_AI_LEDGER_ID` | `ai_ledger_image_provision` verweigert Gleichheit |
| Model-ID | `gpt-image-2.6-flare` | fest im Code, kein Flag |
| Eingabepreis | 5 000 000 micro-USD / 1 M Tokens (Text-Input, offizielle Preisliste) | aus `OFFICIAL_PRICES_MICRO_PER_MTOK` |
| Ausgabepreis | 30 000 000 micro-USD / 1 M Tokens (Bild-Output) | aus `OFFICIAL_PRICES_MICRO_PER_MTOK` |
| Allowed Environments | `staging` | fest im Code |
| Initial Allowance | Vorschlag 2,00 USD (Obergrenze im Code: 5,00 USD) | `--total-usd`, Code-Cap |
| Safety Reserve | Vorschlag 0,50 USD | `--safety-usd`; Allowance − Reserve ≥ ein Maximal-Request |
| Emergency Stop | beim Anlegen **TRUE** | fest im Code; Öffnen ist eine eigene Eigentümer-Entscheidung |
| Max Request Cost | 100 000 micro-USD (0,10 USD) | `VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD`, Code-Ceiling 1 000 000 |
| Daily Cost Cap | Vorschlag 200 000 micro-USD (0,20 USD) | `VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD` |
| Tageslimit Requests | 3 pro Nutzer, 10 global (Defaults) | bestehende Settings |

Anlage (nur nach ausdrücklicher Freigabe, schreibt in den gemeinsamen Ledger):

```
python manage.py ai_ledger_image_provision --ledger-id <UUID> --total-usd 2.00 --safety-usd 0.50
# Ausgabe prüfen (RESULT=DRY_RUN_NO_DATABASE_ACCESS), danach erst:
python manage.py ai_ledger_image_provision --ledger-id <UUID> --total-usd 2.00 --safety-usd 0.50 \
    --confirm-ledger-id <UUID> --execute
```

Prüfung danach: `run_staging_image_paid_smoke_once --ledger-audit` (READ ONLY) muss das
Bild-Konto mit `allowed_environments=staging`, offiziellen Preisen, `emergency_stop=True`
und ohne offene Reservierungen zeigen; das Chat-Konto muss unverändert sein.

## B. OpenAI-Kostenkontrollen (Quelle: offizielle Doku „Spend limits“, abgerufen 2026-11-20)

- Organisation und Projekt können je ein monatliches Spend-Limit haben; mit „Enforce a
  hard limit“ schlagen betroffene Requests mit HTTP 429 fehl
  (`project_spend_limit_exceeded` bzw. `organization_spend_limit_exceeded`). Ohne diese
  Option ist es nur ein Alert, der Traffic läuft weiter.
- Ein Projekt-Limit gilt nur für Traffic, der diesem Projekt zugerechnet wird. Die
  Zurechnung erfolgt über den API-Key: daher **eigenes Projekt nur für Staging-Bilder mit
  eigenem Projekt-API-Key**, getrennt vom Chat.
- **Durchsetzung ist nicht sofort**: Nutzung kann weiterlaufen, bis der Limit-Status
  propagiert ist; die erfasste Ausgabe kann das Limit leicht überschreiten. Eine Obergrenze
  für Überschreitung oder Verzögerung nennt die Doku nicht; ebenso nichts zu laufenden
  Requests. Das Hard Limit ist deshalb nur die äußere Schicht, nicht die primäre Grenze.
- Das von OpenAI vergebene Usage-Tier-Limit ist davon getrennt und keine Budgetgrenze.
- Empfehlung (vom Eigentümer im Dashboard umzusetzen, nicht durch Claude): eigenes Projekt
  „vorneq-staging-images“, Hard Limit 5 USD/Monat, Alert bei 1 USD, Projekt-Key mit
  minimalen Rechten, ausschließlich als Staging-Secret; zusätzlich ein Organisations-Hard-
  Limit als Katastrophen-Obergrenze. Ein Test, ob das Limit greift, erfordert Ausgaben und
  ist nicht Teil dieses PR.

Schutzschichten in Reihenfolge: Code-Ceiling pro Request → Ledger-Reservierung (Worst Case)
→ Tages-Caps → Ledger-Allowance/Emergency Stop → OpenAI-Projekt-Hard-Limit → Org-Limit.

## C. Abgleich der 6 offenen (uncertain) Chat-Reservierungen

Read-only-Audit (Staging-Job, beide Datenbanken in `READ ONLY`-Transaktionen,
`job-dc0c1fe1egvs73fbj270`, Commit `10563f4f`): 6 Reservierungen, Summe 34 676 micro-USD,
identisch mit `uncertain_micro` des Chat-Kontos. Nur Präfixe, keine Inhalte, Actor gehasht.

| Präfix | Umgebung | Erstellt (UTC) | Reserviert | Outcome | App-Nachweis |
|---|---|---|---|---|---|
| 9cd33105 | production | 2026-11-17 00:37:36 | 3 832 | ProviderUnavailable | Prod-DB, nicht zugänglich |
| 6cf0de74 | production | 2026-11-17 01:13:43 | 3 700 | ProviderUnavailable | Prod-DB, nicht zugänglich |
| d05240a9 | staging | 2026-11-17 18:33:51 | 6 937 | ProviderTimeout | AIMessage uncertain, `provider_timeout`, HTTP 504 |
| 930c2175 | production | 2026-11-17 22:03:59 | 6 689 | unexpected_error | Prod-DB, nicht zugänglich |
| fcf4000b | production | 2026-11-17 22:35:02 | 6 689 | ProviderInvalidResponse | Prod-DB, nicht zugänglich |
| 5d999f05 | production | 2026-11-18 02:42:49 | 6 829 | ProviderInvalidResponse | Prod-DB, nicht zugänglich |

Abgleichsverfahren (Eigentümer, nur lesend):

1. OpenAI-Dashboard → Usage, Projekt des Chat-Keys, Modell `gpt-5-mini`, Tagesauflösung
   für 2026-11-17 und 2026-11-18 (UTC). Requests und Tokens je Tag notieren.
2. Vom Tagesverbrauch die im Ledger **finalisierten** Reservierungen desselben Tages
   abziehen (per Read-only-Audit lieferbar). Rest = vermutlich den uncertain-Fällen
   zuzurechnen.
3. `ProviderUnavailable` vor Antwort wurde meist nicht berechnet; `ProviderTimeout` und
   `ProviderInvalidResponse` können berechnet worden sein. Die Rechnung ist maßgeblich.

Abschlusskriterien je Reservierung:

- **Berechnet belegt** (Usage-Rest > 0 im Zeitfenster): Betrag laut Dashboard per
  `ai_ledger record-external` mit Notiz „Abgleich <Präfix> <Datum>“ – nur mit
  Freigabe – und Reservierung bleibt als uncertain dokumentiert, bis ein eigener,
  geprüfter Settle-Pfad existiert.
- **Nicht berechnet belegt** (Usage-Rest = 0): bleibt bis zu einer freigegebenen
  Korrekturfunktion unverändert; kein automatisches Freigeben.
- **Nicht entscheidbar**: konservativ als verbraucht behandeln (Status quo, max. 34 676
  micro-USD ≈ 0,035 USD).

Kein Code in diesem PR verändert diese Reservierungen.

## D. Emergency Stop des Bild-Kontos (`ai_ledger_image_control`)

`ai_ledger stop|resume` ist an das Chat-Konto gebunden und darf für das Bild-Konto
nicht verwendet werden. Für das Bild-Konto gibt es ausschließlich:

```
python manage.py ai_ledger_image_control status --ledger-id <UUID>          # READ ONLY
python manage.py ai_ledger_image_control resume --ledger-id <UUID> --confirm-ledger-id <UUID>
python manage.py ai_ledger_image_control stop   --ledger-id <UUID> --confirm-ledger-id <UUID>
```

- Die ID muss `VORNEQ_AI_IMAGE_LEDGER_ID` entsprechen und sich von der Chat-ID unterscheiden.
- Geändert wird nur `emergency_stop` genau einer Zeile; das Chat-Konto ist nicht wählbar.
- Abgelehnt, ohne Änderung: Konto nicht staging-only, falsches Modell, abweichende Preise.
- `resume` zusätzlich abgelehnt, solange `reserved_micro` oder `uncertain_micro` > 0 ist.
- `resume` erst unmittelbar vor dem freigegebenen Paid Smoke, `stop` direkt danach;
  beides schreibt in den gemeinsamen Ledger und braucht eine ausdrückliche Freigabe.
