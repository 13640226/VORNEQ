# P1 – Akzeptanzkriterien-Matrix, Teile OD-10 und AC-019 (ENTWURF, PARTIELL)

**Kennung:** `P1_ACCEPTANCE_MATRIX_PARTIAL_DRAFT_V2`  
**Vorgänger:** V1 (nur OD-10), als Arbeitsentwurf durch V2 ersetzt; keine Änderung an V1.  
**Status:** `DRAFT / PARTIAL / OWNER_ACCEPTANCE_PENDING`  
**Autorisierung:** `DOCUMENTARY_ONLY / NO_EXECUTION`  
**Datum:** 2026-11-03

## Quellen und Provenienz

- **OD-10:** [Nachtrag I, Issue #478, Kommentar 6557689901](https://github.com/13640226/VORNEQ/issues/478#issuecomment-6557689901), 2026-11-01; deklarierter Base-SHA `ddc5d8853deec7a204c4b8b801faffb2916f41a2`.
- **AC-019:** [Issue #478, Body, Abschnitt 4: Acceptance Criteria V1.1](https://github.com/13640226/VORNEQ/issues/478). Gleichwertigkeit mit der separat bezeichneten eingefrorenen V1.2 **nicht nachgewiesen**.
- Die Texte wurden am 2026-11-03 durch den ChatGPT-Assistenten über einen verbundenen GitHub-Connector abgerufen und im Gespräch wiedergegeben. Der Owner führte keinen eigenen Abruf durch. Authentifizierungsmechanismus, Berechtigungen und Mandatskonformität wurden nicht unabhängig geprüft (F-11). Kein reproduzierbarer Zeichen-für-Zeichen-/Hash-Abgleich der Wiedergabe gegen das Original.
- Diese Matrix enthält **komprimierte Arbeitsformulierungen** der Kriterien; sie ist **keine wortgetreue Quelltranskription**. Für normative Texte gelten ausschließlich die verlinkten Originalquellen.

**Zählung:** OD-10 = 25; AC-019 = 22; **47 gemeldete Kriterien**, getrennte Mengen. Keine automatische Deduplikation. `TEXT_RECONCILIATION = PARTIAL`, `RUNTIME_VERIFIED = 0`.

## OD-10 — Arbeitsmatrix (25 Kriterien)

| ID | Szenario (gekürzt) | Erwartung (gekürzt) | Status |
|---|---|---|---|
| AC-OD10-01 | Zulässige Publikation mit erfolgreichem M1 | Gültiger Gate/Snapshot und dauerhaftes M1; logisch nachvollziehbare Audit-Entscheidung, kein Delivery-Beweis | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-02 | M1-Ausfall vor externem Effekt | Keine sensitive Freigabe und kein Erfolgsstatus | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-03 | Authorization-DENY mit M2-Erfolg | DENY, nicht-sensitiver Reason-Code und Event | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-04 | M2-Write-Fehler bei DENY | DENY bleibt; kein Fail-open | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-05 | Ausfall optionaler Telemetrie | Keine Gate-Entscheidungsänderung oder DENY→ALLOW | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-06 | Sensitive Evidence im Request | Kein Rohinhalt in Audit-/Application-Logs | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-07 | Privater source_ref | Keine Offenbarung in Audit/Alert/Metrik | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-08 | Secret in Exception | Keine Ausgabe von Secret/Token/Credential | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-09 | Tenant A fragt Audit von Tenant B ab | Kein Zugriff und keine Existenzoffenbarung | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-10 | Unberechtigter Audit-Dashboard-Zugriff | DENY; Break-Glass separat AC-21 | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-11 | CR/LF/Control Characters | Keine Log-Injection/Event-Forgery | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-12 | Wiederholtes Event mit logischer ID | Keine ungültigen Duplikate/Doppelzählung | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-13 | Audit-Timeout mit unklarem Persistenzergebnis | Kein Erfolg; Idempotency und begrenzte Wiederholbarkeit | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-14 | Serielle Audit-Writer-Fehler | Keine unbeschränkte Retry-/Logging-Kaskade | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-15 | Snapshot ändert sich während Audit | Kein Output aus ungeprüftem TOCTOU-Snapshot | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-16 | Fehlender/ungültiger Gate | Audit allein autorisiert nicht | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-17 | Export fremder Tenant-Audits | Kein Export oder Metadaten-Abfluss | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-18 | Kleine Monitoring-Gruppen | Keine Tenant-Inferenz | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-19 | Ende Retention | Löschung/Anonymisierung oder dokumentierter Legal Hold | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-20 | Streaming vor M1 und Gate | Kein sensitives Byte vor Pflicht-Gates | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-21 | Conditional Break-Glass | Belegter Disabled Mode oder separat autorisierter vollständiger Mode B | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-22 | Audit Trail Tamper | Prevention und unabhängige Detection nach Threat Model | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-23 | Runtime und Audit Destination | Unabhängig verifizierte Identität; C02/SC_07 | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-24 | Policy Change Commit | Authorization → pre-commit M1 durable → Commit → Verification | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |
| AC-OD10-25 | Publication Delivery | Authorization getrennt von beobachtbarer Delivery | DOCUMENTARY_APPROVED_AS_REPORTED / NOT_VERIFIED |

**Quellenpräzisierung:** AC-21 = GAP-01/R10/TD-06/TD-14; AC-22 = GAP-02/R13/TD-08; AC-23 = GAP-03/R15/TD-01/C02/SC_07; AC-24 = GAP-04/R01/R13/TD-12; AC-25 = GAP-05/R01/R05/TD-03/TD-04. Nachtrag I meldet `25/25 DOCUMENTARY_APPROVED`, `0/25 VERIFIED`, `0 TESTS`. Unabhängige Owner-Entscheidungsprüfung bleibt offen.

## AC-019 — Arbeitsmatrix (22 Kriterien, Quellabschnitt V1.1)

| ID | Kurzbeschreibung | Status |
|---|---|---|
| AC-019-01 | Gültiges Evidence nur bei sämtlichen Publication Controls | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-02 | Ungültiger Digest verwirft ganze Antwort | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-03 | Fehlender/leerer/formal fehlerhafter Digest führt zu Denial | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-04 | Hash-Ausnahme erzeugt keine erfolgreiche Teilantwort | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-05 | Ein fehlerhaftes Evidence führt zu DENY_ALL | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-06 | Kein Raw Evidence Content öffentlich | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-07 | PRIVATE/PARTICIPANTS nicht öffentlich | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-08 | Kein raw source_ref Fallback | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-09 | Provenance nur nach Evidence-Prüfung und Disclosure-Policy | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-10 | Canonical-Target-Konflikt Fail-Closed | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-11 | Ungültige Tenant Ownership/Sharing führt zu Denial | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-12 | Counts/Summaries/Projection aus validiertem Set | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-13 | Fehler ohne sensible interne Werte | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-14 | Serialisierung konsistent mit geprüftem Snapshot | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-15 | Kein Consumer umgeht Gate | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-16 | Link-Count/Claim/Provenance konsistent | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-17 | Keine ungeprüften Nachlade-Queries | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-18 | Retired Relations nicht in aktueller Ansicht | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-19 | Cross-Tenant ohne Freigabe DENY | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-20 | source_type/Zeitstempel/public_source_ref Disclosure | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-21 | Cache/Streaming/Teilantworten umgehen Fail-Closed nicht | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |
| AC-019-22 | VALID_EMPTY von INTEGRITY_FAILURE getrennt | SOURCE_IDENTIFIED / V1.2_EQUIVALENCE_PENDING / NOT_TESTED |

**Abgrenzung:** `AC-OD10-01..25` und `AC-019-01..22` sind unterschiedliche Kennungen und werden nicht automatisch zusammengelegt. Die V1.2-Versionstreue der AC-019-Reihe muss separat belegt werden.

## F-11 — Mandatskonformität des Quellenabrufs nicht nachgewiesen

**Status:** `OPEN / GOVERNANCE_REVIEW_REQUIRED`  
**Sachverhalt:** Der Assistent verwendete einen verbundenen GitHub-Connector zum Lesen von Issue #478 und Kommentar #6557689901. Ein Mandatsentwurf `P1_…_READONLY_V1` soll Token und authentifizierte API ausdrücklich ausgeschlossen haben.  
**Grenze:** Die verbindliche Mandatsfassung, der Authentifizierungsmechanismus, die Berechtigungen und die Autorisierung dieses Abrufs sind nicht unabhängig geprüft. **Kein bestätigter Verstoß**, aber auch **keine nachgewiesene Mandatskonformität**.  
**Erforderlich:** Mandatsfassung und Berechtigungs-/Abrufwegabgleich, unabhängige Governance-Bewertung. Bis dahin keine zusätzliche Quellfreigabe aufgrund dieses Abrufs.

## Offene Quellen und Entscheidungen

- V3.1-B V1.1: 24 AC **nur handoff-reported**, `SOURCE_PENDING`.
- V3.1-C V1.2: 28 AC **nur handoff-reported**, `SOURCE_PENDING`.
- AC-019 V1.2: Normative Versionsgleichwertigkeit mit Issue #478 V1.1 `PENDING`.
- `P1_TOTAL_REPORTED = 99 (Handoff + Nachtrag I + Issue #478, unreconciled)`; keine Behauptung über verifizierte Gesamtzahl.
- `OWNER_ACCEPTANCE = PENDING`; unabhängige Security Review und technische Nachweise fehlen.

## Governance Locks

```text
STOP_340 = ACTIVE
HARD_STOP = ACTIVE
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
GOV_BREACH_01 = OPEN
DATABASE_GO = NO
MIGRATION_GO = NO
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
PRODUCT_RELEASE_GO = NO
TESTS_EXECUTED = 0
IMPLEMENTATION_AUTHORIZATION = NONE
FINAL_STATE = SAFE_HOLD / NO_GO
```

Diese Datei ist ein **Entwurf zur unabhängigen Prüfung**, kein Approval, kein Ausführungsauftrag und kein Nachweis wirksamer Sicherheitskontrollen.
