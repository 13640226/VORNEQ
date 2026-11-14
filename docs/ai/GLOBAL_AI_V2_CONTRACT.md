# VORNEQ Global AI V2 — Technischer Vertrag (Erweiterung von V1)

**Stand:** 2026-11-14
**Basis:** `b3b699840ae3e670ae4445a06e3fefcd52b84d64` (nach #605 und #606)
**Status:** DEFAULT OFF / MOCK_TESTED / KEIN DEPLOY / KEINE AKTIVIERUNG / PRODUCTION UNVERÄNDERT

Dieser Vertrag ergänzt `GLOBAL_AI_V1_CONTRACT.md`. Alles dort Festgelegte gilt weiter, soweit hier nichts Abweichendes steht.

## 1. Pipeline

```
Frage → validate() → detect_language()/route_question()       (lokal, deterministisch)
      → official_vorneq: unveränderter Pfad ask_grounded()
      → unsupported_or_unsafe: 422 ohne Kontingent/Suche
      → general_public:
          Kontingent (V1, inkl. #606-Ausnahme nur Staging)
          → MultiSourceRetriever (Registry)                    (Quellen abrufen)
          → Provider-Ergebnisprüfung (Typ, Host, Anzahl)        (Quellen validieren)
          → rank_evidence()                                     (Evidenz bewerten/ranken)
          → authorized_web_context()                            (Kontext, Digest)
          → OpenAIResponsesProvider.generate()                  (Generierung)
          → validate_generated() + Zahlen-Prüfung               (Zitatprüfung)
          → Antwort + evidence_assessment                       (strukturierte Antwort)
```

## 2. Provider-Registry (`apps/ai_core/retrieval_registry.py`)

- Provider werden ausschließlich im Code in `PROVIDERS` registriert. Aktiviert werden sie über `settings.VORNEQ_GLOBAL_AI_PROVIDERS`; Standard ist `("wikipedia",)`.
- Unbekannte, doppelte oder mehr als 3 Namen sind ein Konfigurationsfehler. Die Anfrage endet dann mit `503 search_unavailable`, ohne Suche und ohne Modell.
- `MultiSourceRetriever` fragt die Provider der Reihe nach ab, jeden höchstens einmal mit maximal 3 Treffern.
  - **Kontrollierter Fehler** (`RetrievalError`) eines Providers: Status `error` bzw. `timeout` wird vermerkt, die anderen Provider laufen weiter.
  - **Alle Provider fehlgeschlagen:** zuerst ein Timeout (504), sonst der Fehler (503).
  - **Fail closed** gilt für die ganze Anfrage bei einer unerwarteten Exception, einem Ergebnis, das kein Tupel ist, einem Objekt, das keine `WebEvidence` ist, einem Host außerhalb der Allowlist *dieses* Providers oder bei Überschreitung des Ergebnislimits.
- Die Allowlist ist die Vereinigung der festen Provider-Allowlists. Nutzer können weder einen Provider noch einen Host noch eine URL vorgeben.
- **Zweiter realer Provider: nicht hinzugefügt.** In dieser Sitzung ließen sich API-Bedingungen, Lizenz, Nutzungsbedingungen und Erreichbarkeit eines weiteren Anbieters nicht belastbar prüfen. Die Architektur ist mit synthetischen Providern getestet. Für jeden künftigen Provider gilt:
  - API-Bedingungen und Lizenz sind dokumentiert;
  - Allowlist mit festen Hosts;
  - `source_type` und `licence` sind angegeben;
  - eigene Tests;
  - Freigabe durch den Owner.

## 3. Evidenzbewertung (`apps/ai_core/engine/evidence_ranking.py`)

Die Bewertung ist deterministisch und nutzt nur beobachtbare Eigenschaften. Der Score ist **kein** Wahrheitswert; `score_semantics = retrieval_relevance_not_truth`.

- **relevance:** Anteil der Inhaltsterme der Frage, die in Titel oder Auszug vorkommen.
  - Normalisierung: NFKC, persische und arabische Ziffern zu ASCII, arabische Varianten von ی/ک, casefold.
  - Stoppwörter für fa, de und en.
  - Leichte Präfix-Morphologie, z. B. کهکشان gegen کهکشان‌ها oder Stern gegen Sterne.
- **completeness:** Länge des Auszugs, normiert auf 300 Zeichen.
- **provenance:** gültiges `retrieved_at` (+0,5) und gültiges `published_at` (+0,5).
- **source_type:** Gewicht laut Tabelle; Wikipedia hat `encyclopedia` = 0,6.
- **Gesamtscore:** `0,6·relevance + 0,2·completeness + 0,1·provenance + 0,1·type`.
- **Dubletten über Provider hinweg:** gleicher Schlüssel, gleiche URL oder gleicher normalisierter Titel mit gleichem Auszug-Präfix zählt als Dublette.
- **Mindestrelevanz:** Es braucht mindestens einen Treffer und eine Relevanz ≥ 0,25. Sonst gibt es `insufficient_evidence`, und das Modell wird **nicht** aufgerufen.
- **Auswahl:** höchstens 3 Quellen; sortiert nach Score, bei Gleichstand nach der Reihenfolge der Provider.

## 4. Zitat- und Aussageprüfung

- `validate_generated()` bleibt unverändert. Sie prüft Quellidentität, Digest, wörtliches Zitat, Sprache und `verified=false`.
- **Neu: Zahlenprüfung.** Jede Ziffernfolge in der Antwort muss in einem *zitierten* Auszug oder in der Frage vorkommen. Verglichen wird ohne Trennzeichen, persische Ziffern sind gleichwertig. Andernfalls gibt es `422 INSUFFICIENT_EVIDENCE`. Die Prüfung ist absichtlich schmal: Ausgeschriebene Zahlwörter und semantische Aussagen erfasst sie nicht.
- **Widersprüche:** Widersprüchliche Quellen werden beide weitergegeben. Die festen Zusatzinstruktionen verlangen, Widersprüche zu benennen und beide Seiten zu zitieren.
- **Keine Verifikation:** Mehrere übereinstimmende Quellen gelten **nicht** als unabhängige Verifikation. Die Antwort enthält immer `verified: false` und `evidence_assessment.independent_verification: false`.

## 5. Antwortfelder (additiv, rückwärtskompatibel)

`evidence_assessment` = `{score_semantics, sources_considered, providers:[{name,status}], cited:[{source_key, relevance, completeness, score}], independent_verification:false}`

Alle V1-Felder bleiben unverändert. Das Frontend ignoriert zusätzliche Felder.

## 6. Mehrsprachigkeit

- **Persisch bleibt Persisch.** Persische Schrift zusammen mit einem persischen Funktions- oder Fragewort führt zu `fa`, ebenso wenn mindestens so viele persische wie lateinische Buchstaben vorkommen. Beispiele: „Quantum computing چیست؟“, „CPU و GPU چه فرقی دارند؟“.
- **Kein Wechsel durch Zitate.** Eine englische oder deutsche Frage mit einem einzelnen persischen Wort bleibt in ihrer Sprache, z. B. „What does سلام mean?“.
- **Umlaute, ß und ZWNJ** bleiben in Quelltexten erhalten. Nur für den Abgleich wird normalisiert.
- **Quelltitel** werden nicht übersetzt; das steht auch in den Instruktionen.
- **Private Daten:** Die Muster wurden erweitert, u. a. um Profil, E-Mail, Verlauf und اطلاعات/پروفایل/ایمیل/تاریخچه + من.

## 7. Kosten und Freigaben

Unverändert gegenüber V1 und #606:

- Das Global-Kontingent ist Standard.
- `VORNEQ_GLOBAL_AI_UNLIMITED_STAGING` hebt nur das Global-Kontingent auf, nur auf Staging. Trial-Identität, Allowlist und CSRF gelten weiter.
- `VORNEQ_AI_STAGING_UNMETERED` bleibt ein getrennter Schalter.
- Production ist unmöglich.
- **Not-Aus:** `VORNEQ_GLOBAL_AI_ENABLED` entfernen; danach antwortet der Endpunkt sofort mit 404.
- Ein unbegrenztes internes Kontingent bedeutet **keine** unbegrenzte Kapazität beim Provider und schützt nicht vor Kosten. Das Spend-Limit des OpenAI-Projekts bleibt die harte Grenze und wird hier nicht verändert.

## 8. Voraussetzungen für eine Staging-Evaluation

1. Offizielle CI auf dem PR-Head ist grün.
2. SHA-gebundene Merge- und Deploy-Autorisierung (G4).
3. Ein dokumentierter Erreichbarkeitstest von Wikimedia auf Staging, mit eigener Autorisierung.
4. Das Spend-Limit wurde vorher erneut geprüft.
5. Flag-Freigabe nur für Staging.
