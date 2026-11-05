# C02 — Inventar-Nachtrag 2026-11-05

Dokument-ID: VORNEQ_C02_INVENTORY_ADDENDUM_2026_11_05
Bezug: `C02_RUNTIME_DB_IDENTITY_CONTRACT_V1_2.md` (eingefrorene Basis, unverändert)
Freigabe zur Erstellung: OWNER-AUTH-BUILD-C02-INVENTORY-01 (Eigentümer 13640226, 2026-11-05)
Status: DOKUMENTARISCH. Dieser Nachtrag öffnet kein Gate, ändert keinen Verdikt und schließt kein C02-CLOSE-Kriterium.

## 1. Korrektur des erwarteten Inventars

Der Vertrag V1.2 (Abschnitt „Expected inventory“) nennt für Staging veraltete Kennungen. Sie bezeichnen Ressourcen, die nicht mehr existieren (der frühere Staging-Dienst wurde gelöscht). Für alle weiteren C02-Prüfungen gilt dieses Inventar:

| Rolle | Render-Kennung | Name | Render-Projekt/Umgebung | Quelle |
|---|---|---|---|---|
| Production-Webdienst | `srv-dadn07eq1p3s73eccau0` | VORNEQ | — | unverändert |
| Production-Datenbank | `dpg-dagru1h42hec73eqr960-a` | vorneq-production-db | My project / Production | Render-Dashboard, 2026-11-05 22:59 |
| Staging-Webdienst | `srv-dbm7dvc9v7es7393g70g` | vorneq-staging | ohne Projekt | Render-Dashboard; `EXPECTED_SERVICE_IDS` in `scripts/deploy_control.py` |
| Staging-Datenbank | `dpg-dbm74m8u01pc738j8r1g-a` | vorneq-staging-db | ohne Projekt | Render-Dashboard, 2026-11-05 22:58 |
| DR-Restore-Datenbank | `dpg-dafs4did0e5s73dph9jg-a` | vorneq-dr-restore | My project / Staging | Render-Dashboard-URL, 2026-11-05 23:01 |

Ersetzt (nur dokumentarisch, nicht mehr gültig): Staging-Webdienst `srv-dadm6fv40ujc73c2dik0`, Staging-Datenbank `dpg-dbd7tqom7kps73c4dolg-a`.

Auffälligkeit (nur festgehalten, keine Änderung): `vorneq-dr-restore` liegt in der Render-Umgebung „Staging“, die aktuelle Staging-Datenbank dagegen in keinem Projekt.

## 2. Beobachtete Laufzeit-Selbstauskunft (Release 5dc8ba4)

Quelle: Feld `database` in `/health/` (PR #526), abgerufen 2026-11-05 22:40Z nach Deploys per Workflow (STAGING-04, PROD-04).

| Dienst | `name` (current_database) | `render_id` (aus konfiguriertem Host) |
|---|---|---|
| Production | `vorneq_production_db` | `dpg-dagru1h42hec73eqr960-a` |
| Staging | `vorneq_staging_db_9i8v` | `dpg-dbm74m8u01pc738j8r1g-a` |

Einordnung nach Vertrag V1.2:
- Vertrauensgrenze TB-03 (Django-Laufzeit): **Selbstauskunft**, kein unabhängiger Nachweis.
- `render_id` stammt aus der Konfiguration des Prozesses (CONFIGURATION), `name` aus der Datenbanksitzung (RUNTIME, selbst berichtet). CONFIGURATION_MATCH ≠ RUNTIME_PROOF.
- Laut Attributionsvertrag reicht ein von Django gemeldeter Datenbankname allein nicht. AT-04 (Instanz), AT-05 (unabhängige Verbindung↔Instanz), AT-06 (unabhängige Verbindung↔Ressource) und IC-01..IC-06 (Instanzabdeckung) sind **nicht** erfüllt.
- Verdikte bleiben daher: CURRENT_RUNTIME_DATABASE_IDENTITY = UNKNOWN (mit konsistenter Selbstauskunft), PRODUCTION_STAGING_ISOLATION = NOT_VERIFIED, HISTORICAL_RUNTIME_DATABASE_IDENTITY = UNKNOWN.

Die Beobachtung ist ein Hinweis ohne Widerspruch zum erwarteten Inventar, kein PASS.

## 3. GitHub-Umgebungen und Secrets (nur Namen, 2026-11-05)

| Umgebung | Secrets (Namen) | Schutz |
|---|---|---|
| Repository-Ebene | keine | — |
| `production` | DR_RESTORE_DATABASE_URL, PRODUCTION_DJANGO_SECRET_KEY, PRODUCTION_SOURCE_DATABASE_URL, PRODUCTION_TARGET_DATABASE_URL | required_reviewers, branch_policy |
| `staging` | keine | branch_policy |
| `deploy-staging` | RENDER_DEPLOY_HOOK_URL | branch_policy |
| `deploy-production` | RENDER_DEPLOY_HOOK_URL | branch_policy |

Befund: `STAGING_DATABASE_URL` ist in **keiner** Umgebung hinterlegt. Alle Staging-Workflows, die es lesen, würden am Prüfschritt „not configured“ scheitern. Die Identität der Secrets in `production` ist nicht geprüft (Workflow „Read-only Database Identity Probe“, nur mit eigener Freigabe).

## 4. Workflow-Umgebungen (Änderung in diesem PR)

| Workflow | vorher | nachher | Grund |
|---|---|---|---|
| `migrate-staging.yml` | production | **staging** | Staging-Job soll keine Produktions-Secrets erhalten |
| `seed-staging.yml` | production | **staging** | wie oben |
| `dr-staging-rehearsal.yml` | production | production (kommentiert) | liest bewusst Produktionsquelle und DR-Ziel |
| `inspect-database-identity.yml` | production | unverändert | prüft Produktions-Secrets |

Alle drei Datenbank-Workflows bleiben durch `if: ${{ false }}` (C02-Hard-Stop) deaktiviert; `scripts/db_target_guard.py` verweigert weiterhin jede Schreiboperation. Ohne `PRODUCTION_SOURCE_DATABASE_URL` klassifiziert der Guard weiterhin über geschützte Namen (`vorneq_production_db`) und bleibt fail-closed.

Offene Eigentümer-Aktion (nicht Teil dieses PR, eigene Freigabe nötig): `STAGING_DATABASE_URL` in der Umgebung `staging` hinterlegen, bevor ein Staging-Workflow je reaktiviert wird.

## 5. Unveränderter Sicherheitszustand

C02 = OPEN_CRITICAL; SC_07 = OPEN_CRITICAL; HARD_STOP = ACTIVE; G5 = CLOSED.
DATABASE_GO = NO; MIGRATION_GO = NO.
