# Persische Quellensuche: Stichwort-Anfrage statt ganzer Frage (V1)

| Feld | Wert |
|---|---|
| Datum | 2026-11-17 |
| Basis | `main` @ `305766749bde2047cc20baa2e18dc15dfcf03fb1` |
| Umfang | Nur die ausgehende Suchanfrage an `fa.wikipedia.org`. Englisch und Deutsch sind unverändert. Relevanzbewertung, Modell, Zitatprüfung, Ledger und Endpunkte sind unverändert. |

## Problem

`WikipediaRetriever` hat bisher die vollständige Frage als `gsrsearch` gesendet, z. B. „سلول خورشیدی چگونه کار می‌کند؟“. Die Wikipedia-Suche (CirrusSearch) verlangt alle Begriffe. Fragewörter und Hilfsverben wie „چیست“, „کجاست“ oder „می‌کند“ stehen kaum in Artikeltexten. Deshalb fehlte der Hauptartikel oft in den Top 3, und die Antwort fiel auf „keine ausreichende Quelle“ zurück oder stützte sich auf Randartikel.

## Änderung

`search_keywords(question, "fa")` in `apps/ai_core/engine/evidence_ranking.py`:
- normalisiert wie die Bewertung: NFKC, arabische ي/ك → persische ی/ک, persische Ziffern → ASCII
- entfernt die bestehenden Stoppwörter und eine Zusatzliste `_FA_SEARCH_EXTRA` (Fragewörter, leichte Verben, Bittformeln)
- behält ZWNJ in Wörtern, weil persische Artikeltitel ihn verwenden
- fällt auf die Frage zurück, wenn nichts übrig bleibt

Die Datenschutzprüfung (`screen_and_redact`, Abbruch bei `[REDACTED_…]`) läuft unverändert **vor** dem Aufbau der Anfrage. Es geht weiterhin genau eine Anfrage pro Frage hinaus, eher mit weniger Text als bisher.

## Messung (echt, lesend, 2026-11-17)

Gegen `fa.wikipedia.org`, ohne OpenAI und ohne VORNEQ-Server. Zwei Sätze mit je 20 Fragen. Treffer zählt **streng**: Ein Top-3-Titel muss exakt einem erwarteten Artikeltitel entsprechen. Es gab 0 Rate-Limit-Fehler in den gewerteten Läufen.

| Satz | ganze Frage (bisher) | Stichwörter (neu) |
|---|---|---|
| Satz 1, beim Schreiben der Liste bekannt | 5/20 | **12/20** |
| Satz 2, Held-out, erst danach formuliert | 13/20 | **17/20** |

- Im Held-out-Satz verliert die neue Anfrage keinen Fall, den die alte traf.
- Ein zusätzlich gemessenes Ranking-Profil `srqiprofile=popular_inclinks_pv` war schlechter und wird nicht verwendet.
- Die exakten 40 gemessenen Anfragen liegen als Fixture vor: `apps/ai_core/tests/fixtures/fa_search_queries_measured_2026-11-17.json`. `test_fa_search_keywords` stellt sicher, dass der Code byte-genau dieselben Anfragen erzeugt.
- Wiederholbar mit `python -X utf8 scripts/ai_eval/fa_wikipedia_search_eval.py`. Das ist manuell und nicht Teil der CI. Das Skript sendet 80 Anfragen an Wikipedia.

## Auditnotiz zu den gespeicherten Messwerten

Die bewerteten Trefferquoten sind zeit- und kriteriumsgebunden. Ein lokales Re-Scoring der gespeicherten Top-3-Titel mit den Solltiteln des im Patch enthaltenen Evaluationsskripts ergibt Satz 1 **5/20 -> 12/20** und Satz 2 **13/20 -> 17/20**. In der separaten lokalen Ausgabedatei fa_heldout_result.json steht fuer Satz 1 set1_strict **5/20 -> 11/20**: diese Berechnung nutzt eine abweichende Solltitel-Liste. Daher darf die 12/20-Zahl nur mit dem veroeffentlichten Set-1-Titelkriterium verglichen werden, nicht als universeller Trefferwert.

Die gespeicherten HTTP-Top-3-Ergebnisse befinden sich nur in Downloads/vorneq_fa_eval auf dem Eigentuer-Laptop und sind nicht Teil des Repository-Patches. Die 40er-Fixture sichert die exakte **Query-Erzeugung**; sie reproduziert nicht offline die historischen Live-Wikipedia-Rankings. Die messbaren Sucherfolge koennen sich bei erneuter Wikipedia-Abfrage aendern. Die Wirksamkeit fuer zitierfaehige Production-AI-Antworten bleibt unbewiesen.

## Grenzen und offene Punkte

- Die Stichprobe ist klein (40 Fragen) und von einer Person formuliert. Das Ergebnis zeigt eine klare Richtung, ist aber kein Benchmark.
- Verbleibende Fehlschläge betreffen vor allem Verben mit „می‌“-Präfix („می‌گذرد“), „به وجود آمد“ und Fragen, deren Antwort ein anderer Artikel ist („پایتخت آلمان“ → „برلین“). Eine allgemeine Regel für „می‌“-Verben ist der nächste Kandidat, erst nach eigener Messung.
- **Sicherheitsbefund (unabhängig von dieser Änderung):** Die Volltextsuche liefert gelegentlich unpassende, auch nicht jugendfreie Artikeltitel unter den Top 3, bei beiden Anfrageformen. Die Relevanzschwelle filtert einen Teil davon, aber nicht nachweislich alle. Empfohlen wird ein eigener Schritt: eine Ausschlussliste für Artikelkategorien bzw. Titel vor der Übergabe an das Modell, mit Tests.
- Die Wirkung auf echte Antworten in Production wurde nicht gemessen. Dafür braucht es einen kontrollierten, kostenpflichtigen Testlauf nach Deploy durch den Eigentümer.
