# VORNEQ — Suchkonzept (Entwurf V1) mit Anhang A: Korrekturnotizen

| Feld | Wert |
| --- | --- |
| DOCUMENT_ID | VORNEQ_SEARCH_CONCEPT_DESIGN_V1 + VORNEQ_SEARCH_CONCEPT_DESIGN_CORRECTION_NOTES_V1 |
| DATUM | 2026-11-04 |
| DOCUMENT_STATUS | DESIGN_NOTES_ONLY / DRAFT |
| REVIEW_VERDICT | CONDITIONALLY_ACCEPTABLE / CORRECTIONS_IDENTIFIED |
| DESIGN_ACCEPTANCE | CONDITIONAL |
| AUTHORIZATION_SCOPE | DOCUMENTARY_ONLY / NO_EXECUTION |
| CODE_BASELINE | 3b0c8c2 (Suchcode bis 8385d68 unverändert, lokal per `git diff` geprüft) |
| EVIDENCE_SOURCE | LOCAL_ORIGIN_MAIN_SNAPSHOT |
| LIVE_GITHUB_VERIFICATION | NOT_PERFORMED |
| RUNTIME_VERIFICATION | NOT_PERFORMED |
| FINAL_STATE | SAFE_HOLD / NO_GO |

## Eigentümer-Ausnahme für diese Ablage

Der Eigentümer (Konto 13640226) hat am 2026-11-04 die Ablage dieses Dokuments als **Eigentümer-Ausnahme** erklärt.

- Umfang: ein Branch, ein Commit mit diesem Dokument. Kein PR, kein Merge, kein CI, kein Deploy, keine Datenbankoperation.
- Diese Ausnahme hebt HARD_STOP **nicht** auf und ist keine unabhängige Verifizierung (siehe SEARCH-DESIGN-01).
- Ein PR wurde bewusst nicht erstellt: ein PR gegen `main` würde `ci.yml`, `security.yml`, `quality-verification.yml` und `backup-restore.yml` auslösen; CI_GO = NO.
- Dieses Dokument ist keine Autorisierung zur Umsetzung.

Grundregel: PROPOSAL ≠ APPROVAL ≠ EXECUTION_AUTHORIZATION ≠ VERIFIED_EVIDENCE.

Bei Widersprüchen zwischen Hauptteil und Anhang A gilt **Anhang A**.

## 1. Ziel und Positionierung

VORNEQ soll Google Search nicht in der allgemeinen Websuche schlagen, sondern bei einer bestimmten Frage besser sein: „Wie belastbar ist diese Behauptung, und woher stammen ihre Nachweise?“

| Nutzerfrage | Google Search | VORNEQ (Ziel) |
| --- | --- | --- |
| Welche Seiten gibt es zu X? | sehr stark | kein Ziel |
| Ist Behauptung X verifiziert? | nur verwandte Seiten | Prüfstatus im Ergebnis |
| Aus welcher Originalquelle stammt dieser Nachweis? | nicht vorhanden | nachverfolgbare Herkunftskette |
| Warum steht dieses Ergebnis oben? | intransparent | erklärbare Rangfaktoren |
| Behauptungen mit mindestens zwei unabhängigen Quellen | nicht möglich | strukturierter Filter |

## 2. Aktueller Stand der Suche (Codelektüre, nicht zur Laufzeit getestet)

| Aspekt | Stand im Code |
| --- | --- |
| Route | `/<sprache>/search/?q=` per GET (`i18n_patterns`, `prefix_default_language=True`) |
| Service | `UnifiedSearch` in `apps/search/services.py` |
| Durchsuchte Inhalte | Article, Product, LibraryItem, MediaAsset, AudioItem |
| Nicht durchsucht | Claim, Evidence, Provenance (`apps/evidence`) |
| Abgleich | `icontains` auf Titel, Zusammenfassung, Inhalt (en/de) |
| Ranking | nur nach Veröffentlichungsdatum, keine Relevanzbewertung |
| Trust-Layer | laut Docstring bewusst ohne Trust-Layer-Anreicherung |
| Grenzen | Anfrage max. 200 Zeichen, 12 Ergebnisse pro Seite, max. 50 |

Die Adapter-Architektur erlaubt neue Quellen ohne Umbau.

Offene Beobachtung: `render.yaml` verweist weiterhin auf `saman-kherad-staging.onrender.com` (laut Unterlagen gelöscht); die Production-Domain ist im Repository nicht erfasst.

## 3. Unterscheidende Fähigkeiten (Vorschlag)

1. Ergebnis mit Prüfstatus (Verified, Rejected, Under Review, Unknown, Disputed — siehe SEARCH-DESIGN-03).
2. Herkunftskette im Ergebnis: Claim → Evidence → Source.
3. Strukturierte Filter: Prüfstatus, Anzahl unabhängiger Quellen, Quellentyp, Zeitraum, Organisation.
4. Transparente Rangfaktoren.
5. Mehrsprachige Suche: zuerst über vorhandene en/de-Felder, später semantisch.
6. Widersprüche sichtbar machen, nicht nur bestätigende Nachweise.

Ob die Modelle in `apps/evidence` (claim, evidence, evidence_state, provenance, relation) alle nötigen Felder haben, ist nicht geprüft.

## 4. Vorgeschlagene Architektur

Abfrage (q, Filter, Sprache) → UnifiedSearch / normalize_query → **Authorization- und Tenant-Filter (fail-closed, neu)** → Such-Adapter (bestehend: Article, Product, Library, Media, Audio; **neu: Claim, Evidence, Provenance**) → **Ranking (neu)** → **Ergebnis mit Prüfstatus und Herkunftskette (neu)**.

Korrektur durch SEARCH-DESIGN-04: In der ersten Version richtet sich das Ranking nur nach Textrelevanz; Prüfstatus und Aktualität sind Zusatzinformation bzw. Filter, kein Rangfaktor.

## 5. Sicherheitsanforderungen und Organisationsgrenzen

Suche ist der riskanteste Pfad für Datenabfluss. Die Aufnahme von Claim und Evidence folgt den Verträgen V3.1-A und V3.1-B.

- Zugriffsfilter im Service Layer, vor Zählung und Paginierung — nicht im Template.
- Ergebniszahlen dürfen private Behauptungen anderer Organisationen nicht verraten.
- Öffentliche Suche nur für Inhalte, die das Central Publication Integrity Gate passiert haben.
- Fail-Closed bei unbekanntem Status oder Berechtigungsfehler.
- Keine IDOR: Detail- und Herkunftslinks prüfen die Berechtigung erneut.
- Audit-Log ohne Klartext der Suchanfrage.
- Rate Limiting gegen Scraping und Datenbanklast.

## 6. Phasen und Abnahmekriterien (Vorschlag)

Jede Phase nur nach unabhängiger Freigabe und mit Laufzeitnachweisen. Ob eine Phase eine Migration braucht, ist laut SEARCH-DESIGN-04 nicht abschließend geklärt.

| Phase | Inhalt | Migration | Abnahmekriterium (Vorschlag) |
| --- | --- | --- | --- |
| 1. Evidence-Adapter | ClaimAdapter, EvidenceAdapter mit `icontains`, nur öffentlich veröffentlichte Inhalte | nicht abschließend geklärt | Tests zur Organisationsgrenze; keine nicht-öffentliche Claim in Ergebnis oder Zählung |
| 2. Textranking | PostgreSQL Full-Text (SearchVector, SearchRank) statt Datumssortierung | möglich (z. B. GIN-Index) | Präzision auf festem Testanfragensatz; Antwortzeit im Budget |
| 3. Prüffilter | Prüfstatus, Anzahl unabhängiger Quellen, Quellentyp | wahrscheinlich | Filter korrekt auf Referenzdaten; Unknown fail-closed |
| 4. Herkunftskette | Anzeige Claim → Evidence → Source und Rangfaktoren | nein | jedes Kettenglied besteht die Berechtigungsprüfung |
| 5. Semantische Suche | Embeddings mit pgvector, sprachübergreifend | ja | Egress-Kontrolle zum Embedding-Dienst; keine privaten Daten nach außen |

## 7. KI-Schicht (Vorschlag)

KI arbeitet auf dem Nachweiskern; jede KI-Ausgabe ist PROPOSAL, nie VERIFIED.

| Fähigkeit | Eingabe | Ausgabe | Abhängigkeit |
| --- | --- | --- | --- |
| Semantische Suche | Nutzeranfrage | sprachübergreifende Treffer | Phase 5 |
| Belegte Antwort (RAG) | Anfrage + berechtigte Nachweise | Antwort mit Pflichtverweis auf jeden Nachweis | semantische Suche |
| Claim-Extraktion | Text oder Dokument | vorgeschlagene Claims (Entwurf) | Claim Dossier |
| Nachweisvorschlag | eine Claim | passende vorhandene Nachweise | semantische Suche |
| Widerspruchserkennung | Nachweise einer Claim | widersprüchliche Nachweise für den Reviewer | Nachweisvorschlag |

Gestaltungsregeln:

- Nutzung über die API eines Sprachmodells; kein eigenes Modelltraining.
- KI sieht nur Nachweise, die Authorization- und Tenant-Filter passiert haben; Filter vor dem Prompt-Aufbau.
- Ohne Nachweis lautet die Antwort „kein Nachweis gefunden“; kein Rückgriff auf Allgemeinwissen des Modells.
- Jede KI-Ausgabe trägt „AI-generated · proposal“ und kann den Prüfstatus nicht direkt ändern.
- Inhalte von Nachweisen sind Daten, keine Anweisungen (Schutz vor Prompt Injection).
- Egress nur zur freigegebenen API-Adresse, Schlüssel an Environment gebunden; keine Organisationsdaten ohne ausdrückliche Eigentümerentscheidung.
- Jeder KI-Aufruf wird im Audit erfasst: Nutzer, Organisation, Modell, IDs der verwendeten Nachweise.

## 8. Governance-Voraussetzungen und offene Fragen

| Phase | Voraussetzung |
| --- | --- |
| 1 und 4 | Aufhebung von HARD_STOP oder gültige Ausnahme, SC_07 geschlossen, MERGE_GO und DEPLOY_GO |
| 2, 3 und 5 | zusätzlich C02 geschlossen, MIGRATION_GO und DATABASE_GO |
| 5 | zusätzlich Egress- und Secrets-Kontrolle gemäß SEC-P0 |

Offene Fragen:

- [ ] OWNER-DEC-STOP340-01 (2026-11-02, gültig bis 2026-12-02) vs. Handoff vom 2026-11-04 mit allen Gates = NO — siehe SEARCH-DESIGN-01.
- [ ] Production-Domain nicht im Repository erfasst; `render.yaml` verweist auf gelöschten Dienst.
- [ ] Haben die Modelle in `apps/evidence` Veröffentlichungsstatus und Eigentümer-Organisation?
- [ ] Soll der Prüfstatus später das Ranking beeinflussen? (Produktentscheidung, derzeit zurückgestellt)
- [ ] Persisch hat keine Modellfelder (nur en/de) — Priorität?
- [ ] Welcher Modellanbieter und welche Region (EU für DSGVO)?
- [ ] Können Organisationen KI für ihre Daten abschalten?
- [ ] Wie fließen KI-Kosten in das Billing-Modell ein?

---

## Anhang A — Korrekturnotizen zum Suchdesign

Dieser Anhang hält nur konzeptionelle Korrekturen fest. Er ändert den Hauptteil nicht; bei Widersprüchen gilt dieser Anhang.

### SEARCH-DESIGN-01 — Konflikt zwischen Eigentümerfreigabe und HARD_STOP (P0)

- OWNER-DEC-STOP340-01 ist, auch mit der angegebenen Gültigkeit bis 2026-12-02, für sich allein keine Freigabe zur Umgehung von HARD_STOP.
- Jede Ausnahme erfordert unabhängigen, überprüfbaren Nachweis von befugter Stelle, Umfang, Gültigkeitsbedingungen und Vereinbarkeit mit HARD_STOP.
- Bis dahin: HARD_STOP = ACTIVE; MERGE_GO, DEPLOY_GO, CI_GO, DATABASE_GO, MIGRATION_GO = NO.
- Keine Phase des Suchkonzepts ist zur Umsetzung freigegeben.

### SEARCH-DESIGN-02 — Verhinderung von Datenabfluss in der Suche (P0)

- Authorization und Tenant Isolation werden vor Erzeugung der sichtbaren Ergebnismenge angewendet; jeder Adapter verarbeitet nur Daten, auf die der Nutzer im jeweiligen Organisationsbereich zugreifen darf.
- Pflichtabdeckung: Search Results, Result Counts, Ranking, Facets, Pagination, Autocomplete, Search Suggestions, Cache, Result Details, Provenance Links.
- Öffentliche Inhalte müssen zusätzlich das Central Publication Integrity Gate passiert haben.
- Unbekannte Berechtigung, Fehler bei der Zugriffsprüfung oder unklare Organisationsgrenze → Fail-Closed.
- Keine Zählung, kein Ranking, kein Cache und keine Fehlermeldung darf die Existenz privater Daten einer anderen Organisation offenlegen.

### SEARCH-DESIGN-03 — Gültigkeit des Prüfstatus (P0)

- Anzeige des Prüfstatus nur auf Basis eines gültigen, nachverfolgbar gespeicherten Status.
- Vorgeschlagene UI-Labels: Verified, Rejected, Under Review, Unknown, Disputed — Übereinstimmung mit den realen Modellen in `apps/evidence` nicht bestätigt.
- Verified erfordert eine gültige Entscheidung, zugehörige Nachweise, nachverfolgbare Herkunft und Audit-Historie.
- KI-Ausgaben, automatische Vorschläge oder menschliche Bestätigungen ohne gültige Befugnis werden nie zu Verified.
- Unknown bedeutet „nicht festgestellt“, nicht „ungültig“.
- Widersprüchliche Nachweise werden offen angezeigt; keine irreführende Gewissheit.

### SEARCH-DESIGN-04 — Trennung von Relevanz und Glaubwürdigkeit (P1)

- In der ersten Version sind Textrelevanz und Prüfstatus unabhängig; das Ranking richtet sich nur nach Relevanz.
- Prüfstatus, Aktualität, Anzahl unabhängiger Quellen und Widersprüche sind nur erläuternde Information oder strukturierte Filter.
- Die Einbeziehung der Glaubwürdigkeit ins Ranking wird zurückgestellt, bis genaue Kriterien definiert und ihre Wirkung bewertet sind — damit Gegenbelege, neue Behauptungen und Ergebnisse mit Status Unknown nicht verdrängt werden.
- Der Migrationsbedarf von Phase 2 ist nicht zwingend: Full-Text Search kann ggf. ohne Schemaänderung funktionieren, ein GIN-Index oder gespeicherte Strukturen können aber eine Migration erfordern.
- Ohne reale Prüfung der Modelle ist auch nicht sicher, dass Phase 1 ohne Migration umsetzbar ist.

### SEARCH-DESIGN-05 — KI-Sicherheit, Datenschutz und DSGVO (P1)

- Alle KI-Ausgaben bleiben PROPOSAL; KI ändert den Prüfstatus nicht und ersetzt nicht den unabhängigen Reviewer.
- Vor jedem operativen Einsatz festzulegen: Anbieter und Verarbeitungsort, Speicherort und -dauer, Rechtsgrundlage nach DSGVO, internationale Datenübermittlung, Trainingsnutzung durch den Anbieter, Abschaltbarkeit je Organisation, Zugriffsbeschränkung auf berechtigte Daten, Schutz vor Prompt Injection, Egress- und Secrets-Kontrolle, Audit ohne Offenlegung sensibler Inhalte, Kosten- und Billing-Regeln.
- Die Wahl einer EU-Region allein belegt keine DSGVO-Konformität.
- Keine privaten Organisationsdaten an externe Anbieter ohne gültige Rechtsgrundlage, nötige Kontrollen und angemessene Freigabe.
- Die gemeinsame Nutzung eines Laptops durch Eigentümer und Reviewer ist bei der künftigen Bewertung von SC_07 zu berücksichtigen; getrennte Konten, Sitzungen, Zugangsdaten und Bestätigungsfaktoren sind nötig, belegen aber allein keine Unabhängigkeit.

### Endstatus des Anhangs

| Feld | Wert |
| --- | --- |
| CORRECTIONS_IDENTIFIED | 5 |
| DESIGN_ACCEPTANCE | CONDITIONAL |
| IMPLEMENTATION_AUTHORIZED | NO |
| CI_AUTHORIZED | NO |
| MERGE_AUTHORIZED | NO |
| DEPLOY_AUTHORIZED | NO |
| DATABASE_OPERATION_AUTHORIZED | NO |
| FINAL_STATE | SAFE_HOLD / NO_GO |
| NEXT_ACTION | WAIT_FOR_NEW_VERIFIABLE_HARD_STOP_EXCEPTION_AUTHORITY_EVIDENCE |

Die zurückgestellte Anfrage vom 2026-11-03 wird weder geschlossen noch wieder geöffnet. Es wird kein wiederholtes Audit und keine neue Ausführungsanweisung begonnen.

**SC_07 = OPEN_CRITICAL** · **C02 = OPEN_CRITICAL** · **STOP_340 = ACTIVE** · **HARD_STOP = ACTIVE**
