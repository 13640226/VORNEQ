# VORNEQ — Bestandsaufnahme der STOP-Verweise nach Inkrafttreten von #620

| Feld | Wert |
|---|---|
| Datum | 2026-11-15 |
| Basis | `main` @ `321af35ed86654b4b76472845a79d9cc8e08f22f` |
| Bezug | `OWNER_GLOBAL_STOP_RETIREMENT_PROPOSAL_V1_2026-11-15.md`, §6 Nr. 1 und 3 |
| Art | Dokumentation, Regressionstests und CODEOWNERS. Workflows, `db_target_guard.py`, Datenbank, Render und Secrets sind nicht verändert. |

## 1. Methode

Gesucht wurde mit `git grep -I -i -E 'STOP_340|HARD_STOP|SAFE_HOLD|NO_GO|hard stop|hard-stop'` im gesamten Baum von `321af35`. Diese Datei und die neuen Tests sind dabei nicht mitgezählt. Die Zählung nennt Zeilen mit Treffern pro Datei. Jede Datei wurde nach ihrer wirksamen Funktion eingeordnet, nicht nach dem Dateinamen allein. Die Einordnung ist eine Eigentümer-Dokumentation und **keine unabhängige Prüfung**.

GitHub-Zustand am 2026-11-15 (REST-API, gelesen):
- `GET /repos/13640226/VORNEQ/rulesets` → `[]`
- `GET /repos/13640226/VORNEQ/branches/main` → `protected: false`
- Kein Ruleset und kein Branch-Schutz verlangt damit ein Review.

## 2. Kategorien

| Kategorie | Bedeutung | Behandlung | Dateien |
|---|---|---|---|
| **K1** | Ausführbare technische Sperre | bleibt; durch Regressionstests abgesichert | 6 |
| **K2** | Sperre für ein einzelnes privilegiertes Vorhaben (Production-DB, bezahlte KI, CI-Runner-Privilegien, Deploy) | bleibt bis zu einer eigenen, eng gefassten Freigabe (§2 „Privileged changes“) | 14 |
| **K3** | Historischer Nachweis (Audit, Incident, Bericht, eingefrorene Baseline) | unverändert; keine Wirkung auf neue Entwicklung | 34 |
| **K4** | Frühere globale Verfahrensregel (pauschaler STOP, Pflicht-Reviewer, Freigabeschleife) | für gewöhnliche Entwicklung prospektiv ersetzt; Datei bleibt als Nachweis | 6 |

Kein Verweis der Kategorie K1 bezieht sich auf `STOP_340`. **Kein ausführbarer Code und kein Workflow hängt von `STOP_340` ab.** Der pauschale Architektur-STOP war rein dokumentarisch.

## 3. Vorrangregel

Für gewöhnliche Entwicklung gilt ab `321af35`:
- `OWNER_GLOBAL_STOP_RETIREMENT_PROPOSAL_V1_2026-11-15.md` §3
- zusammen mit `OWNER_DIRECT_MERGE_POLICY_V1_2026-11-06.md`

Angaben wie `STOP_340 = ACTIVE`, `HARD_STOP = ACTIVE` oder `FINAL_STATE = SAFE_HOLD / NO_GO` in K3- oder K4-Dateien beschreiben den damaligen Stand. Neue Arbeit blockieren sie nicht. Historische Dateien werden bewusst **nicht** umgeschrieben.

Grenzen dieser Regel:
- Sie gilt nicht für K1 und K2.
- Sie schließt keinen Befund: C02, SC_07, GOV_BREACH_01 und P0_MARKETPLACE_SYNTHETIC_PUBLICATION_01 bleiben offen.
- Die ursprüngliche Charter-Quelle des HARD_STOP gilt laut `VORNEQ_FOUR_FROZEN_CONTRACTS_SOURCE_RECOVERY_REPORT_V1.md` als nicht wiederhergestellt. Eine konkrete entgegenstehende Klausel wurde nicht gefunden. Wird später eine gefunden, ist sie mit Quelle und Umfang zu benennen (§3 der Retirement-Regel). Ein neuer pauschaler STOP ist dann nicht automatisch die Folge.

## 4. Änderungen in diesem Patch

1. **`.github/CODEOWNERS`:** `@hamidrezaasadian7-boop` wird durch `@13640226` ersetzt.
   - Bisher erhielt bei jedem PR automatisch ein Konto eine Review-Anfrage, das laut Eigentümer nicht unabhängig ist und nicht verfügbar ist.
   - Ohne Branch-Schutz war das nie erzwungen. Es widersprach aber der geltenden Regel (Kategorie K4).
2. **Retirement-Dokument:** Statuszeile aktualisiert und §8 „Inkrafttreten“ ergänzt. §7 bleibt als Stand vor dem Merge erhalten.
3. **`config/tests/test_governance_technical_controls.py`:** Regressionstests nach §6 Nr. 4. Sie lesen nur Dateien und führen weder Workflows noch DB-Verbindungen noch Provider-Aufrufe aus:
   - Die vier DB-Workflows bleiben mit `if: ${{ false }}` deaktiviert. Alle DB-Workflows haben nur `workflow_dispatch` als Auslöser.
   - In `migrate-production.yml` läuft der SAFE_HOLD-Guard vor jedem `manage.py`. Er hat `ALLOW_PRODUCTION_TARGET='false'`, kein `continue-on-error` und kein `if`.
   - `db_target_guard.decide()` lehnt alle 12 Eingabekombinationen ab.
   - `merge_authorization`: Eigentümer ist `13640226`. Das frühere Reviewer-Konto kann nicht freigeben. Die Freigabe ist SHA-gebunden.
   - `CODEOWNERS` nennt nur den Eigentümer.
   - `VORNEQ_AI_EMERGENCY_STOP` allein schaltet eine sonst vollständig freigegebene Production-KI ab. Damit ist der Not-Aus vom Architektur-STOP unabhängig.

## 5. Offene Punkte (nicht in diesem Patch)

- **Production-Migration `ai_core.0001`/`0002`:** Über `migrate-production.yml` ist sie technisch nicht möglich (K1). Benötigt wird ein eng gefasster Ersatz für die positive Ziel-Attestierung in `db_target_guard.py`:
  - gebunden an SHA, Datenbank-Identität und exakt diese zwei Migrationen
  - einmalig verwendbar
  - mit Negativtests
  - Das ist ein eigenes Vorhaben mit eigener Freigabe.
- **`P0_MARKETPLACE_SYNTHETIC_PUBLICATION_01`:** offen, unabhängig von dieser Bestandsaufnahme.

## 6. Vollständige Liste

| Kat. | Datei | Zeilen | Einordnung |
|---|---|---|---|
| K1 | `.github/workflows/dr-staging-rehearsal.yml` | 1 | Ausführbare Sperre (C02). Bleibt unverändert. |
| K1 | `.github/workflows/migrate-production-db.yml` | 1 | Ausführbare Sperre (C02). Bleibt unverändert. |
| K1 | `.github/workflows/migrate-production.yml` | 1 | Schritt „Fail-closed database target gate (SAFE_HOLD)“ mit `ALLOW_PRODUCTION_TARGET: 'false'` vor jedem `manage.py`-Befehl. Er blockiert derzeit **jede** Production-Migration, auch die zwei autorisierten `ai_core`-Migrationen. |
| K1 | `.github/workflows/migrate-staging.yml` | 2 | Ausführbare Sperre (C02). Bleibt unverändert. |
| K1 | `.github/workflows/seed-staging.yml` | 2 | Ausführbare Sperre (C02). Bleibt unverändert. |
| K1 | `scripts/db_target_guard.py` | 0 | `decide()` lehnt jede Kombination ab (fail-closed). Keine STOP-Zeichenkette, aber die eigentliche Sperre hinter SAFE_HOLD. |
| K2 | `docs/ai/AI_CORE_STAGING_ENABLEMENT_V1.md` | 1 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/governance/C02_DB_IDENTITY_INSPECTION_SCOPE_DRAFT_V1.3.md` | 3 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/governance/incidents/GOV-BREACH-01/C02_RUNTIME_DB_IDENTITY_CONTRACT_V1_2.md` | 2 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/runbooks/AI_CHAT_PRODUCTION_PAID_GUARD_PREPARATION_V1.md` | 2 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/runbooks/CAP_ACTOR_02_STAGING_REDIS_G4_DEPLOY_V1_3.md` | 1 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/OWNER_DEC_PR545_ISOLATED_RUNNER_PILOT_CONDITIONAL_V1.md` | 2 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_ISOLATED_RUNNER_PILOT_LIMITED_AUTHORIZATION_REQUEST_V1.md` | 3 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_ISOLATED_RUNNER_TECHNICAL_SPEC_V1.md` | 2 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_OC01_OC02_TWO_NODE_GATEWAY_COST_FEASIBILITY_V1.md` | 1 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_OC01_OC08_REMEDIATION_AND_PROVIDER_COST_V1.md` | 2 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_OC03_OC08_PREEXECUTION_CONTROLS_EVIDENCE_CONTRACT_V1.md` | 1 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_PILOT_FINAL_DOCUMENTARY_READINESS_MATRIX_V1.md` | 4 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_PILOT_PREEXECUTION_INDEPENDENT_EVIDENCE_REVIEW_V1.md` | 4 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K2 | `docs/security/PR545_PILOT_RESOURCE_COST_TTL_AUTHORITY_MATRIX_V1.md` | 2 | Sperre für ein einzelnes privilegiertes Vorhaben. Bleibt, bis dieses Vorhaben eine eigene Freigabe hat. |
| K3 | `docs/architecture/AI_CORE_PHASE_B_GROUNDED_LLM_V1.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/architecture/AI_CORE_PHASE_C_REAL_LLM_CHAT_UI_V1.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/architecture/AI_DEV_OPENAI_LIVE_BACKEND_E2E_V1.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/architecture/AI_DEV_PUBLIC_SOURCE_RETRIEVAL_AND_COST_GUARD_V1.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/audits/C02_EVIDENCE_PROVENANCE_REGISTER.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/audits/C02_PYTHON_371_FINAL_AUDIT_REPORT.md` | 2 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/audits/C02_SECURITY_GAP_REGISTER.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/audits/PR405-SLV-001-026-CONSOLIDATED-REPORT.md` | 4 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/audits/SG01-UA03-EXPANDED-298-FINAL-RECONCILIATION.md` | 6 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/design/entdecken-frozen-baselines-2026-10-29.md` | 4 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/design/entdecken-search-visual-parity-v1.4.md` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/AC_CI2_08_RUN_EVIDENCE_LEDGER_20261104_V1.md` | 2 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/AC_CI2_10_ROLLBACK_FAILURE_DENIAL_AUDIT_V1.md` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/CAP_ACTOR_02_HOBBY_S10_DOCUMENTARY_RECORD_20261111.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/CI_SECURITY_STATIC_REVIEW_AND_REMEDIATION_GATE_V1.md` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/COMMIT_MESSAGE_POLICY_NO_SKIP_CI_V1.md` | 2 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/OD10_APPROVED_BASELINE_V1_2_2026-11-01.md` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/P0_VORNEQ_AI_CORE_V2_SOURCE_AUDIT_PATCH_MAP_GOVERNANCE_CORRECTION_V1_1.md` | 7 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/P1_ACCEPTANCE_MATRIX_PARTIAL_DRAFT_V2.md` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/P1_VORNEQ_OWNER_RESPONSE_AI_CORE_INTEGRATION_RECEIPT_V1.md` | 5 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/VORNEQ_AI_CORE_VLIE_ROOM_HANDOFF_2026-11-06.md` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/VORNEQ_FOUR_FROZEN_CONTRACTS_SOURCE_RECOVERY_REPORT_V1.md` | 8 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/ci-security-architecture-v2.0.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/incidents/GOV-BREACH-01/C02_DOCUMENTARY_REVIEW_HISTORY.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/incidents/GOV-BREACH-01/C02_INVENTORY_ADDENDUM_2026-11-05.md` | 2 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/incidents/GOV-BREACH-01/GOV_BREACH_01_ROOT_CAUSE_AND_MERGE_AUTHORIZATION_CONTROL_V1.md` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/incidents/GOV-BREACH-01/MERGE_AUTHORIZATION_CONTROLS_CORRECTION_PROPOSAL_V1.md` | 4 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/phase-01-v3.1-documentary-freeze-evidence-wait-2026-10-31.md` | 4 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/pr-472-merge-deploy-deviation-readonly-2026-10-31.md` | 6 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/governance/service-gateway-v1-2-documentary-freeze-issue-466.md` | 4 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/reports/VORNEQ_AI_FREEMIUM_PHASE_A_AUDIT_REPORT_V1_1.html` | 5 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/reports/VORNEQ_AI_FREEMIUM_PRODUCT_AND_BILLING_CONTRACT_V1_FINAL.html` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `docs/reports/VORNEQ_AI_SUBSYSTEM_SOURCE_AUDIT_REPORT_V1_REVISED.html` | 3 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K3 | `templates/reports/platform_review.html` | 1 | Historischer Nachweis. Bleibt unverändert, ohne Wirkung auf neue Entwicklung. |
| K4 | `docs/governance/OWNER_DEC_REVIEWER_REMOVAL_01.md` | 3 | Die SHA-gebundene Eigentümer-Freigabe („Ersatzkontrolle“) wird heute technisch durch `merge-authorization.yml` erzwungen. Der pauschale Endzustand `SAFE_HOLD / NO_GO` ist überholt. |
| K4 | `docs/governance/OWNER_DIRECT_MERGE_POLICY_V1_2026-11-06.md` | 1 | Frühere globale Verfahrensregel. Für gewöhnliche Entwicklung ersetzt (siehe §3). Datei bleibt als Nachweis. |
| K4 | `docs/governance/OWNER_FULL_DEVELOPMENT_REOPENING_AUTHORIZATION_V1.md` | 1 | Frühere globale Verfahrensregel. Für gewöhnliche Entwicklung ersetzt (siehe §3). Datei bleibt als Nachweis. |
| K4 | `docs/governance/P0_VORNEQ_OWNER_REVIEWER_POLICY_RESTORATION_V1.md` | 7 | Status `PROPOSED / NOT_EFFECTIVE`; nennt `STOP_340 = ACTIVE`. Inhaltlich umgesetzt durch OWNER_DIRECT_MERGE_POLICY_V1 und #620. |
| K4 | `docs/governance/SC_07_REVIEWER_INDEPENDENCE_DISCLOSURE_DRAFT_V1.6.md` | 4 | Eine Pflicht zu unabhängigem Review für gewöhnliche Arbeit entfällt. Der Befund SC_07 bleibt offen: Das Eigentümerkonto darf nicht als unabhängige Sicherheitsprüfung gelten. |
| K4 | `docs/plans/how-it-works-full-upgrade-phase0-20261105.md` | 1 | Frühere globale Verfahrensregel. Für gewöhnliche Entwicklung ersetzt (siehe §3). Datei bleibt als Nachweis. |
