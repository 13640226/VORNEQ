# Environment Parity – Staging ↔ Production (PARITY-V1)

Stand: 2026-11-25, Release `5e5673b37e67571d3a2368de97dae5b6c0801fc3` auf beiden Umgebungen.

## Ziel

Staging entspricht in den Softwarefunktionen mindestens Production; neue Funktionen
laufen zuerst in Staging. Datenbanken, Secrets, Domains, Finanzgrenzen, Not-Aus und
Actor-Allowlists bleiben getrennt (Gruppe B).

## Werkzeug: `audit_environment_parity`

Rein lesend, keine externen Aufrufe, keine Secrets, keine personenbezogenen Daten.

```bash
# 1) In der Render-Shell von Staging (srv-dbm7dvc9v7es7393g70g)
python manage.py audit_environment_parity > staging.json

# 2) In der Render-Shell von Production (srv-dadn07eq1p3s73eccau0)
python manage.py audit_environment_parity > production.json

# 3) Lokal (beide Dateien, keine Verbindung zu einer Umgebung nötig)
python manage.py audit_environment_parity --compare staging.json production.json
```

Exit-Codes: `0` = PARITY, Fehler bei `DRIFT` (Gruppe A oder D) oder `INVALID`
(Snapshot unvollständig, Release unbekannt, falsche Umgebungsbezeichnung).
`--allow-drift` gibt den Bericht mit Exit-Code 0 aus; `--no-database` liest nur Code
und Konfiguration.

### Snapshot-Inhalt

| Abschnitt | Inhalt | Schutz |
|---|---|---|
| `settings` | INSTALLED_APPS, Middleware, Context Processors, Loader, Router, Cache-/Storage-Backends, Sprachen, Hosts | keine Credentials |
| `variables` | 117 Variablen aus dem Katalog | Secrets/Referenzen: nur PRESENT/MISSING; SHA-Pins: MATCHES_RELEASE/MISMATCH; Allowlists: Anzahl |
| `uncatalogued_vorneq_variables` | gesetzte `VORNEQ_*`/`DJANGO_*`-Variablen ohne Codebezug | nur Name |
| `platform_registry` | App-Manifeste, Navigation, Auflösbarkeit | – |
| `urls` | URL-Inventar (Anzahl, Namen, Hash) | – |
| `capabilities` | KI-Gates als einzelne Prädikate | Follow-Owner-Deployments = NOT_VERIFIED (bräuchte Netzwerk) |
| `migrations` | angewendet/offen/Konflikte je DB-Alias (Router-bewusst) | nur `django_migrations` lesen |
| `system_data` | Sites, Gruppen, Anzahl Permissions/ContentTypes | – |
| `accounts` | privilegierte Konten: pk, Rollen, Identity-Bindung, verifizierte Primär-E-Mail, Allowlist-Zugehörigkeit | keine Namen, keine E-Mails |

### Gruppen im Vergleich

* **A – unnötige Abweichung:** Funktion/Flag nur in Production aktiv, fehlende App,
  offene Migration, fehlende Gruppen, fehlendes Admin-Profil in Staging.
* **B – erlaubt:** DB, Secrets, Domains, CSRF, E-Mail, Not-Aus, Finanz-/Allowlist-Werte.
* **C – Staging zuerst:** Funktion nur in Staging aktiv.
* **D – Architektur:** nicht katalogisierte Variablen, falsch platzierte Umgebungsflags,
  nicht auflösbare Manifeste, Migrationskonflikte.
* **NV – nicht prüfbar offline.**

Neue Umgebungsvariablen müssen in `apps/core/environment_parity.py` katalogisiert
werden; `apps/core/tests/test_environment_parity.py` schlägt sonst fehl (Drift-Schutz in CI).

## Befund PARITY-V1 (anonym, read-only, 2026-11-25 00:41 UTC)

* 96 lokalisierte Routen × 2 Umgebungen: Status, Weiterleitungen, Navigation, Footer,
  Hauptinhalt (Hash) und CSS **identisch**; Screenshots pixelgleich.
* KI-Gate-Sonden (anonym, GET):

| Endpunkt | Staging | Production | Bedeutung |
|---|---|---|---|
| `/api/ai/v1/chat/` | 401 | 404 | Chat in Staging aktiv, in Production serverseitig **aus** |
| `/api/ai/v1/images/studio/` | 401 | 404 | Staging-UI aktiv; Production-Vorschau prüft erst nach Anmeldung (anonym immer 404) |
| `/api/ai/v1/conversations/` | 401 | 401 | in beiden aktiv |
| `/api/ai/v1/images/jobs/` | 401 | 401 | – |

Abweichungen, die nur angemeldet sichtbar sind, hängen im Code von Konto und
Konfiguration ab (Identity-Bindung, verifizierte E-Mail, `is_staff`/`is_superuser`,
Allowlists, Production-Bildvorschau fest auf `pk in (1, 3)`). Sie sind ohne Snapshot
aus beiden Umgebungen **NOT_VERIFIED**.
