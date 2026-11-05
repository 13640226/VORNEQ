# C02 – Prüfumfang: Identität der Produktionsdatenbank (ENTWURF V1.3)

**Kennung:** C02_DB_IDENTITY_INSPECTION_SCOPE_DRAFT_V1.3  
**Projekt:** VORNEQ · **Priorität:** P0  
**Status:** DRAFT / OWNER_ACCEPTANCE_PENDING  
**Dokumentarisches Urteil:** READY_FOR_OWNER_DECISION (keine unabhängige Verifikation)  
**Autorisierung:** DOCUMENTARY_ONLY / NO_EXECUTION  
**Bezug:** Issue #340 · C02-AC03 V1.3 / Issue #493 · SC_07 V1.6 · Audit-Basis `ddc5d8853deec7a204c4b8b801faffb2916f41a2`

**Versionshistorie:** V1, V1.1, V1.2 = CORRECTION_REQUIRED; V1.3 = DRAFT / OWNER_ACCEPTANCE_PENDING.

## 0. Ausdrücklich nicht autorisiert

Dieses Dokument und seine Veröffentlichung autorisieren **keine** Evidenzerhebung, Reviewer-Zugriffe, Datenbankverbindungen, SQL, Migrationen, Merge, Deploy, Restart, Löschung, Restore, Code- oder Testausführung, Workflow-Starts, Secret-Einsicht, Reveal, Render-API/MCP/CLI/Shell/SSH, `query_render_postgres`, Änderungen an GitHub oder Render oder Aufhebung bestehender Gates. Jede operative Handlung benötigt eine gesonderte ausdrückliche Owner-Entscheidung und die anwendbaren Sicherheits-Gates. Dokumentenannahme ist keine Durchführungsgenehmigung.

## 1. Prüffrage und Beweisgrenzen

**Hauptfrage:** Mit welcher konkreten PostgreSQL-Instanz ist der laufende Dienst VORNEQ V2 tatsächlich verbunden?

Erwartet: `vorneq-production-db`. Auszuschließen: `vorneq-dr-restore`, die nach Owner-Angaben gelöschten Instanzen `vorneq-staging-db` und `ffli-db`, sowie unbekannte Instanzen. Ressourcennamen allein beweisen keine Identität.

Drei getrennte Ebenen:
- **L1 CONFIGURED_TARGET:** laut Konfiguration vorgesehenes Ziel.
- **L2 RESOURCE_BINDING:** konkret verknüpfte Provider-Ressource.
- **L3 RUNTIME_CONNECTION_IDENTITY:** tatsächliches PostgreSQL-Ziel des laufenden Anwendungsprozesses.

L1 beweist nicht L2; L2 beweist nicht L3. Deployments, Connection-Pooling, Proxies, DNS, Failover und Restores können die Zuordnung verändern.

**Erwartete Nachweisgrenze:** Mit den nach Abschnitt 4 zulässigen Mitteln ist L3 voraussichtlich nicht hinreichend feststellbar. Das erwartete Höchstergebnis betrifft die Konsistenz von L1 und L2. Ein Ergebnis `INDEPENDENTLY_ASSESSED_CONSISTENT` gilt nur für ausdrücklich benannte Ebenen und darf nicht als Runtime-Nachweis ausgegeben werden. Ohne hinreichende Runtime-Evidenz: `RUNTIME_CONNECTION_IDENTITY = UNVERIFIED`. Für die mögliche C02-Schließung ist voraussichtlich ein separat bewerteter und ausdrücklich autorisierter Prüfvertrag der Stufe 2 erforderlich.

## 2. Rollen und Verantwortlichkeiten

| Rolle | Darf | Darf nicht |
|---|---|---|
| Owner (`13640226`) | Nach gesonderter Freigabe Evidenz erheben, schwärzen und bereitstellen | Eigene Evidenz unabhängig bestätigen |
| Unabhängiger Reviewer gemäß SC_07 V1.6 | Authentizität, Reproduzierbarkeit, zeitliche Gültigkeit, Ausreichendheit und Ergebnis bewerten | Mitwirkung an der Evidenzerstellung als unabhängige Prüfung darstellen |
| Dokumentarische Assistenz (einschließlich KI) | Struktur, Konsistenz, Risiken und Lücken analysieren | Unabhängige Verifikation ersetzen oder operative Freigaben erteilen |

Owner-Evidenz begründet für sich keine unabhängige Bestätigung. Evidenzerhebung, Bereitstellung, Authentizitätsprüfung, Ausreichendheitsprüfung, Ergebnisbewertung und Owner-Entscheidung sind getrennt nachzuweisen. Ein zweites GitHub-Konto allein beweist keine Unabhängigkeit.

## 3. Evidenzquellen und Beweiskraft

| ID | Quelle | Erfasst wird | Nicht erfasst wird | Unabhängige Reproduzierbarkeit |
|---|---|---|---|---|
| E1 | `render.yaml` am gepinnten Commit | `fromDatabase`-Name/-Property | Runtime, Secrets | Direkt durch Reviewer, GitHub lesend |
| E2 | Django-Settings am gepinnten Commit | Bildung von `DATABASES`, Variablennamen | Werte, tatsächliche Verbindung | Direkt durch Reviewer, GitHub lesend |
| E3 | Render-Dashboard: Service → Environment | Schlüsselname, Verknüpfungsart | Werte, Reveal, Connection-Strings | Nur nach separater Lesefreigabe oder begleiteter Live-Sitzung |
| E4 | Render-Dashboard: Postgres | Name, Resource-ID, Region, Erstellung, Status | Zugangsdaten, Runtime | Wie E3 |
| E5 | Render Service Events | Zeitpunkte von Env-Änderungen und Deploys | Änderungsinhalte, tatsächliches Ziel | Wie E3 |
| E6 | `vorneq-dr-restore`-Metadaten | Herkunft, Erstellungszeit, verknüpfte Dienste | Zugangsdaten, aktive Verbindung | Wie E3 |

E1/E2 sind statische Konfigurationsevidenz. E3/E4 können Bindings stützen, nicht die tatsächliche Verbindung beweisen. E5 ist zeitliche Einordnung, kein Nachweis von Kontinuität. E6 dient der DR-Abgrenzung. Ein Name, Host oder Variablenname genügt nicht als Identitätsnachweis.

Jede Evidenz ist an UTC-Zeitpunkt/-Zeitraum zu binden. Befunde zu T1 gelten nicht automatisch zu T2. Env-Änderungen, Deploys, Restores, Failover, DNS-/Proxy-/Pooler-Änderungen können die Gültigkeit aufheben. Owner-Screenshots E3–E6 sind eingeschränkt beweiskräftig; Reviewer bewertet Quelle, Vollständigkeit, Schwärzung, Reproduzierbarkeit und Zeitbezug. SHA-256 beweist Artefaktintegrität ab Hash-Erstellung, nicht ursprüngliche Authentizität.

## 4. Zulässige Mittel (erst nach gesonderter Freigabe)

Zulässig: lesende Render-Dashboard-Ansicht durch Owner, begleitete Live-Sitzung mit qualifiziertem Reviewer, lesende GitHub-Webansicht am gepinnten Commit, Analyse geschwärzter Materialien und nicht vertraulicher Metadaten.

Nicht zulässig: `psql`, SQL, Shell/SSH, Render-CLI/API/MCP (auch lesend), `query_render_postgres`, Env-Reveal, Secret-Offenlegung, Codeausführung, Workflow-Starts, Tests, Migrationen, Deploys, Restarts, schreibende oder bestätigende UI-Aktionen. Erforderliche Erweiterungen stoppen die Erhebung und verlangen einen neuen Prüfvertrag mit ausdrücklicher Autorisierung.

## 5. Zugriffsbeschränkungen und Vertraulichkeit

### 5.1 Reviewer-Zugriff

Ein direkter Render-Zugang für einen Reviewer ist nur mit gesonderter, ausdrücklicher Owner-Freigabe zulässig.

Der Zugang muss:
- auf den notwendigen Umfang beschränkt sein;
- **ausschließlich lesend sein; ist ein rein lesender Zugang technisch nicht verfügbar, ist kein direkter Reviewer-Zugang zu erteilen, und die Reproduktion erfolgt ausschließlich über eine begleitete Live-Sitzung nach Abschnitt 4.1;**
- zeitlich befristet sein;
- einer eindeutig identifizierten Person zugeordnet sein;
- **spätestens bei Ablauf der Befristung, bei Abbruch der Erhebung gemäß Abschnitt 6.1 oder bei Abschluss des Prüfmandats überprüft und entzogen werden – je nachdem, welches Ereignis zuerst eintritt.**

Auch während einer begleiteten Live-Sitzung bleiben Secret-Reveal, schreibende oder bestätigende UI-Aktionen und sämtliche Verbote aus Abschnitt 4 uneingeschränkt gültig.

### 5.2 Reviewer-Unabhängigkeit

`hamidrezaasadian7-boop` gilt nach aktuellem dokumentarischem Stand nicht als unabhängig bestätigte Prüfinstanz. SC_07 V1.6 bleibt maßgeblich.

### 5.3 Geheimnisschutz

Vor Weitergabe sensible Daten schwärzen: Passwörter, Tokens, Connection-Strings, Zugangsdaten, Secret-Werte sowie rekonstruierbare Teile. Hosts/URLs schwärzen, soweit sie vertrauliche Verbindungsinformationen offenlegen. Nicht geheime Resource-IDs nur im genehmigten Prüfrahmen verarbeiten.

## 6. Stoppkriterien und Sicherheitsvorfälle

### 6.1 Sofortiger Abbruch

Abbruch bei: (1) sichtbarem Secret; (2) Widerspruch E1/E3; (3) erkennbarer Bindung an DR oder unbekannte Instanz; (4) manuell gesetzter Variable ohne sichere Identifizierbarkeit; (5) notwendiger DB-Verbindung, Codeausführung oder Werteinsicht; (6) notwendiger Bestätigung/Schreibberechtigung; (7) Überschreitung des Umfangs; (8) relevanter Sicherheitsabweichung oder nicht auflösbarer Identitätsunsicherheit.

### 6.2 Unbeabsichtigte Secret-Offenlegung

Wird ein Secret-Wert sichtbar, ist die Erhebung unverzüglich abzubrechen. Der Wert wird nicht in Evidenz, Issues, PRs, Chats oder Berichten dokumentiert oder weitergegeben. Der Vorfall wird gesondert **ohne Secret-Wert** gemeldet. Über Rotation, Sperrung oder andere Maßnahmen entscheidet die zuständige autorisierte Stelle gesondert. Dieser Vertrag autorisiert keine Rotation oder Infrastrukturänderung.

### 6.3 Evidenzlücken

Fehlende, veraltete, widersprüchliche oder nicht reproduzierbare Evidenz ist kein positiver Identitätsnachweis. Stopp wegen unzureichender Evidenz ergibt grundsätzlich `INCONCLUSIVE`; `INCONSISTENT` verlangt einen belegten Widerspruch. Annahmen ersetzen keine Evidenz.

## 7. Ergebnisklassen

| Klasse | Bedeutung | Feststellung |
|---|---|---|
| `OWNER_REPORTED_CONSISTENT` | Owner-Evidenz erscheint im benannten Umfang konsistent | Owner, vorläufig |
| `INDEPENDENTLY_ASSESSED_CONSISTENT` | Qualifizierter Reviewer bestätigt Echtheit, Ausreichendheit und Konsistenz der benannten Aussagen | Unabhängiger Reviewer |
| `INCONSISTENT` | Hinreichend belegter Widerspruch | Owner oder Reviewer, mit Quelle |
| `INCONCLUSIVE` | Evidenz reicht nicht für belastbare Aussage | Owner oder Reviewer |

Jedes Ergebnis muss die Ebene L1, L2 oder L3 nennen. L1 ≠ L2 ≠ L3. Unabhängige Bewertung setzt Abschnitt 10 voraus und schließt weder SC_07 noch C02 automatisch. Ohne ausreichende Runtime-Evidenz bleibt L3 `UNVERIFIED`. Der Reviewer kann Stufe 2 empfehlen, aber nicht autorisieren.

## 8. Nachweisformat

**Je Evidenz (Owner):** Evidenz-ID · Quelle · UTC-Erhebung · Gültigkeitszeitpunkt/-zeitraum · Commit-SHA/Resource-ID · erhebende Person/Konto · Schwärzungsstatus und -umfang · SHA-256 · wörtliche Beobachtung ohne Secret-Werte · Einschränkungen.

**Je Evidenz (Reviewer):** Identität · Unabhängigkeitsnachweis · schriftliches Mandat · UTC-Prüfzeit · Reproduktion ja/nein/teilweise · Quellenauthentizität · zeitliche Gültigkeit · Ausreichendheit · Ebene L1/L2/L3 · Akzeptanzkriterium · Widersprüche · Grenzen · begründete Ergebnisklasse.

Owner-Erhebung und Reviewer-Bewertung sind getrennt nachvollziehbar. Ein Hash beweist nicht Quelle, Wahrheit, Vollständigkeit oder Unabhängigkeit.

## 9. Nicht-Ziele und Vorrang bestehender Kriterien

### 9.1 Nicht-Ziele

Nicht Bestandteil dieser begrenzten Erhebung: allgemeine Datenintegrität, Backup-Qualität, Kosten, Migrationsdurchführung, Mandantentrennung, allgemeine CI-Isolation, übrige Workflows, allgemeine Secret-Historie, GitHub Environments, umfassende CI-Logs und operative Runtime-Effekte. Hierfür können separate Prüfaufträge erforderlich sein. Ausschluss bedeutet weder Entfall noch Erfüllung bestehender Kriterien.

### 9.2 Vorrang bestehender Kriterien

Dieser Prüfumfang ersetzt oder schwächt keine bestehenden C02-Akzeptanzkriterien, insbesondere **C02-AC03 V1.3 (Issue #493)** zur Bestimmung des tatsächlichen Datenbankziels zum Ausführungszeitpunkt vergangener Workflows. Der Ausschluss von CI-Logs und Runtime-Effekten in 9.1 betrifft nur diese Erhebung, nicht die Geltung oder Erfüllung von AC03.

Die historische Identität der durch `STAGING_DATABASE_URL` und `PRODUCTION_SOURCE_DATABASE_URL` bezeichneten Ziele und ihre Beziehung zur aktuellen Produktionsdatenbank bleiben separat nachzuweisen. Zeitstempel, Hostnamen, Ressourcennamen und Migrationszeiten allein reichen nicht aus; Ersetzungen, Restores, DNS-Änderungen und Zielwechsel sind zu berücksichtigen. Je Aussage: `SOURCE_AUTHENTICITY`, `REVIEWER_INDEPENDENCE`, `EVIDENTIARY_SUFFICIENCY` getrennt bewerten.

**Bei Widerspruch gilt das strengere Sicherheits- und Akzeptanzkriterium.** Nicht erhobene Nachweise gelten nicht als erfüllt. Die genaue Übereinstimmung mit dem Originaltext von Issue #493 ist vor der formalen Owner-Annahme zu dokumentieren.

### 9.3 Eigenständige AC03-Prüfung

Die vollständige AC03-Prüfung gehört nicht zu dieser begrenzten Erhebung und benötigt einen eigenen, ausdrücklich autorisierten Prüfauftrag. AC03 bleibt Voraussetzung für eine mögliche C02-Schließung.

## 10. Bezug zu SC_07

### 10.1 Voraussetzungen unabhängiger Bewertung

Eine Feststellung darf als unabhängig bewertet anerkannt werden, wenn der Reviewer die Kriterien 1 und 2 von SC_07 V1.6, Abschnitt 5 erfüllt: **Benennung mit nachgewiesener Unabhängigkeit/Trennung** und **schriftliches Prüfmandat**. Die Unabhängigkeit muss vor der als unabhängig geltenden Prüfung nachgewiesen sein. **Der formale Abschluss von SC_07 ist hierfür keine Voraussetzung.**

### 10.2 Prüfung und formale Schließung

Nach Erfüllung von 10.1 und gesonderter Autorisierung darf die Prüfung durchgeführt und dokumentiert werden. SC_07 wird erst nach Erfüllung sämtlicher Schließungskriterien gemäß SC_07 V1.6, Abschnitt 5 geschlossen, einschließlich tatsächlicher Prüfung, Ergebnisdokumentation, Behandlung der Feststellungen und gesonderter Owner-Entscheidung. So entsteht kein zirkuläres Abhängigkeitsverhältnis.

### 10.3 Keine automatische Schließung

Reviewer-Benennung allein ist weder unabhängige Bewertung noch SC_07-Schließung. SC_07-Schließung schließt C02 nicht; C02 verlangt ausreichende, zeitlich gültige und unabhängig bewertete Identitätsnachweise, anwendbare AC und gegebenenfalls eine separate Runtime-Prüfung.

### 10.4 Autorisierungsgrenzen

Reviewer-Qualifikation erteilt keine operative Freigabe. Erhebung erfordert gesonderte ausdrückliche Autorisierung; verbotene Methoden bleiben verboten.

## 11. Freigabe und Status

Dokumentannahme bedeutet nur Annahme des Prüfrahmens. Sie autorisiert weder Erhebung noch Reviewer-Zugriff, DB/CI/Codeausführung, Migration, Merge, Deploy oder Änderungen. Jede Erhebung verlangt eine gesonderte ausdrückliche Owner-Entscheidung mit Gegenstand, Mitteln, Rollen, Stoppkriterien und Grenzen, im vorgesehenen Governance-Verfahren mit Bezug zu #340.

Vor späterer Erhebung: Dokumentannahme, gepinnte Audit-/Service-Identität, Quellen/Mittel, Metadatenumfang, Secret-Verfahren, Reviewer-Mandat/Unabhängigkeit, Stoppkriterien sowie AC03-/Stufe-2-Abgrenzung klären.

| Kontrolle | Status |
|---|---|
| C02 V1.3 | DRAFT / OWNER_ACCEPTANCE_PENDING |
| Dokumentarische Textkorrekturen | COMPLETED (keine unabhängige Prüfung) |
| Dokumentarisches Urteil | READY_FOR_OWNER_DECISION |
| Owner Acceptance | PENDING |
| Independent Security Verification | NOT_PERFORMED |
| Evidenzerhebung | NOT_AUTHORIZED |
| Runtime DB Identity | UNVERIFIED |
| C02 | OPEN_CRITICAL |
| SC_07 | OPEN_CRITICAL |
| STOP_340 / HARD_STOP | ACTIVE |
| DATABASE_GO / MIGRATION_GO / MERGE_GO / DEPLOY_GO | NO |
| FINAL_STATE | SAFE_HOLD / NO_GO |

## 12. Dokumentarisches Schlussurteil

V1.3 integriert die Entflechtung von SC_07-Prüfung und -Schließung, Secret-Incident-Behandlung, L1/L2/L3-Nachweisgrenze, unabhängige Reproduzierbarkeit, AC03-Vorrang und strikte Leserechte einschließlich Entzug bei Befristungsende, Abbruch oder Mandatsende.

**DOCUMENTARY_VERDICT = READY_FOR_OWNER_DECISION**  
**INDEPENDENT_SECURITY_VERIFICATION = NOT_PERFORMED**  
**NEW_EXECUTION_AUTHORIZATION = NONE**  
**FINAL_STATE = SAFE_HOLD / NO_GO**

Diese Veröffentlichung ist keine formale Owner-Annahme und keine operative oder unabhängige Sicherheitsfreigabe.
