# VORNEQ Global AI V1 — Technischer Vertrag

**Stand:** 2026-11-14
**Basis:** `20e6ff0882627ccfbf8d851613f1cc424189c633`
**Status:** DEFAULT OFF / IMPLEMENTED_AND_MOCK_TESTED / KEINE STAGING-AKTIVIERUNG / PRODUCTION UNVERÄNDERT

## 1. Zweck und Grenzen

Global AI V1 beantwortet allgemeine öffentliche Wissensfragen (Wissenschaft, Geschichte, Technik) auf Persisch, Deutsch und Englisch. Grundlage sind öffentliche Quellen, die eine vertrauenswürdige Retrieval-Schicht in derselben Anfrage geliefert hat.

- Das Modell erhält keine Werkzeuge.
- Es darf keine Quellen erfinden.
- Es sieht keine privaten VORNEQ-Daten.
- `verified` bleibt immer `false`. Die Zitatprüfung ist keine Faktenprüfung.

## 2. Ablauf

```
Frage → validate() → route_question()  (deterministisch, lokal, ohne Modell)
  ├─ unsupported_or_unsafe → 422, ohne Kontingent, ohne Suche
  ├─ official_vorneq       → bestehender Pfad ask_grounded() (geprüfte offizielle Snapshots)
  └─ general_public        → Global-Kontingent → [Staging: reserve_staging_request()]
                             → PublicWebRetriever.search() → authorized_web_context()
                             → keine Quelle: insufficient_evidence (Provider NICHT aufgerufen)
                             → OpenAIResponsesProvider.generate() → validate_generated()
                             → Antwort mit Provenienz (publisher, retrieved_at, source_class)
```

## 3. Router (`apps/ai_core/global_router.py`)

- **Sprache:** Persische Schrift → `fa`. Sonst entscheidet eine Wortzählung Deutsch gegen Englisch; Umlaute und ß zählen doppelt. Bei Gleichstand gilt die UI-Sprache als Fallback. Maßgeblich ist die Sprache der Frage, nicht die der Oberfläche.
- **`official_vorneq`:** Das Wort „VORNEQ“ steht als eigenständiges Wort in der Frage.
- **`unsupported_or_unsafe`:**
  - leer oder länger als 200 Zeichen
  - Injection-Muster
  - Fragen zu eigenen privaten Daten (fa/de/en)
  - Eingaben ohne Wortinhalt

## 4. Retrieval (`apps/ai_core/web_retrieval.py`)

### Bewertete Optionen

| Option | Entscheidung | Grund |
|---|---|---|
| OpenAI-Werkzeug `web_search` | abgelehnt | Die Quellen kämen vom Modell statt aus einer vertrauenswürdigen Schicht; das wäre ein uneingeschränktes Modellwerkzeug. |
| Kommerzielle Such-APIs | für V1 abgelehnt | Schlüssel, Kosten und Vertrag fehlen; nicht konfiguriert. |
| Wikimedia Action API | **gewählt** | öffentlich, ohne Schlüssel, fa/de/en, fester Host je Sprache, Klartext-Auszüge |

### Sicherheitsregeln

- Erlaubt sind nur die Hosts `fa.wikipedia.org`, `de.wikipedia.org` und `en.wikipedia.org`. Pfad und Parameter erzeugt der Code; Nutzertext erscheint nur URL-kodiert als Suchparameter.
- **SSRF-Schutz:** Alle aufgelösten Adressen müssen global routbar sein. Die TLS-Verbindung ist an die geprüfte IP gebunden, wobei das Zertifikat für den Hostnamen geprüft wird.
- **Antwortprüfung:**
  - Redirects werden verweigert.
  - Nur Status 200 wird akzeptiert.
  - Nur `application/json` wird akzeptiert.
  - Antworten sind auf 256 KiB begrenzt.
  - Timeout: 5 s.
- **Suchanfrage:** Höchstens 3 Ergebnisse, eine Anfrage pro Frage. Anfragen mit E-Mail-Adressen, Telefonnummern oder Secrets werden nicht gesendet.
- **Normalisierung:**
  - NFC-Normalisierung; unsichtbare Bidi- und Steuerzeichen werden entfernt, ZWNJ bleibt erhalten.
  - Titel höchstens 140 Zeichen, Auszug höchstens 500.
  - Deduplizierung nach Seiten-ID und URL.
  - URL-Prüfung: nur `https://<host>/wiki/…`, ohne Port, Query oder Zugangsdaten.

## 5. Evidenzstruktur und Zitatsicherheit (`engine/global_grounded.py`)

Felder: `source_id`, `source_key` (`web:wikipedia:<lang>:<pageid>`), `title`, `url`, `publisher`, `excerpt`, `retrieved_at`, `published_at` (in V1 nicht verfügbar, daher `null`) und `evidence_digest`.

`evidence_digest = SHA-256(source_key \n title \n excerpt \n url \n publisher)`

- Abgelehnt werden: Objekte, die keine `WebEvidence` sind; fremde Schlüssel (`official:`, `article:` usw.); Hosts außerhalb der Allowlist; `http`; URLs mit Zugangsdaten; mehr als 3 Quellen.
- Seitentext mit Instruktionsmustern wird verworfen und nicht weitergegeben.
- `validate_generated()` wird unverändert wiederverwendet. Sie lehnt ab:
  - unbekannte oder doppelte IDs
  - falsche Digests
  - nicht wörtliche Zitate
  - `verified=true`
  - falsche Sprache
  - leere Zitatlisten
- Unterschieden werden drei Prüfstufen:
  1. **Quellidentität:** geprüft über Schlüssel, Host und Digest.
  2. **Wörtliches Zitat:** geprüft.
  3. **Sachaussage:** nicht geprüft; daher `grounded_status = citation_and_quote_checked_claims_unverified`.

## 6. Modellintegration

Der bestehende `OpenAIResponsesProvider` wird wiederverwendet. Neu ist nur der optionale Parameter `extra_instructions`: eine im Code fest definierte Konstante (≤ 600 Zeichen), die Unsicherheiten und Spannen so wiedergeben lässt, wie die Quelle sie nennt, und keine zusätzlichen Zahlen erlaubt.

Weiterhin gelten:
- `store=False`, `tools=[]`, `max_retries=0`
- strukturierte Ausgabe
- Ausgabe: Staging 1024 Token, Development 512
- Timeout: Staging 30 s, Development 15 s

Modell, Schlüssel und Billing bleiben unverändert.

## 7. Feature-Flag und Umgebung

`VORNEQ_GLOBAL_AI_ENABLED` gilt nur zusammen mit `VORNEQ_AI_PHASE_B_ENABLED` und dem Env-Wert `true`. Die Voreinstellung ist `false`.

- **Production:** unmöglich, weil Phase B dort nie aktiv ist.
- **Development:** nur ohne Hosted-Runtime-Kennung (G-02).
- **Staging:** zusätzlich muss `trial_enabled()` erfüllt sein (SHA, Service, Owner-Referenz, Modell, Key, Allowlist).

Bei deaktiviertem Flag antwortet der Endpunkt mit 404, bevor eine Suche, ein Kontingent oder ein Provider berührt wird.

## 8. Kostenkontrolle

Global AI hat ein eigenes Kontingent (`apps/ai_core/global_budget.py`), das auf dem Cache basiert (Redis auf Render) und bei Cache-Fehlern geschlossen bleibt.

| Grenze | Standard | Höchstwert |
|---|---|---|
| pro Nutzer und Minute | 3 | 5 |
| pro Nutzer und Tag | 20 | 50 |
| global pro Tag | 40 | 200 |

Das Kontingent gilt auch bei `VORNEQ_AI_STAGING_UNMETERED=true`; Global AI übernimmt keine unbegrenzte Policy. Auf Staging wird zusätzlich `reserve_staging_request()` aufgerufen.

Ebenfalls begrenzt: höchstens 3 Quellen, Modell-Input ≈ 3 × (140 + 500) Zeichen plus Frage (≤ 200), Ausgabe-Token wie in Abschnitt 6, Such-Timeout 5 s, Provider-Timeout wie in Abschnitt 6, Browser-Abbruch nach 35 s. Das Projekt-Spend-Limit beim Provider bleibt verpflichtend.

## 9. API

`POST /api/ai/v1/ask-global/` erwartet JSON `{"question": str, "language": "fa|de|en"}` und benötigt CSRF-Token und Login.

| Status | Bedeutung |
|---|---|
| 200 | `grounded_draft` oder `insufficient_evidence`, jeweils mit `route` |
| 401 | nicht angemeldet |
| 403 | CSRF fehlt oder Staging-Allowlist nicht erfüllt |
| 404 | deaktiviert |
| 400, 413, 415 | ungültige Eingabe |
| 422 | `UNSUPPORTED_QUESTION` oder `INSUFFICIENT_EVIDENCE` |
| 429 | Kontingent erschöpft |
| 503 | `search_unavailable` oder `provider_unavailable` |
| 504 | `search_timeout` oder `provider_timeout` |

Antworten enthalten `Cache-Control: private, no-store`.

## 10. Frontend

`chat.html` deklariert die erlaubten Quell-Hosts nur bei aktivem Flag. `phase-c-chat.js` behandelt Links so:

- Relative Links (offizielle Quellen) bleiben wie bisher.
- Externe Links nur für deklarierte Hosts mit `https`, ohne Zugangsdaten, Port, Query oder Fragment und nur mit `/wiki/`-Pfad. Sie öffnen mit `target=_blank` und `rel="noopener noreferrer external"`.
- Alles andere erscheint als Text.

Weitere Regeln:
- Der Herausgeber wird sichtbar angezeigt.
- Nach einer Antwort scrollt die Ansicht an den Anfang der Antwort, damit die Quellen sichtbar bleiben.
- Auf schmalen Bildschirmen gibt es keinen verschachtelten Scroll-Container; Links haben eine Touch-Höhe von mindestens 44 px.
- Es gibt kein `innerHTML`. Alle bestehenden Prüfungen bleiben: CSRF, `redirect: "error"`, `verified === false`, Antwortlänge.

## 11. Akzeptanzkriterien für eine kontrollierte Staging-Aktivierung

1. Offizielle CI ist grün.
2. Ein Live-Test der Wikimedia-Erreichbarkeit vom Staging-Host aus ist dokumentiert. Er braucht eine eigene Owner-Autorisierung.
3. Das Provider-Spend-Limit wurde erneut geprüft.
4. Eine Owner-Autorisierung, gebunden an den Ziel-SHA, liegt vor: `VORNEQ_GLOBAL_AI_ENABLED=true`, nur Staging.
5. Nach dem Test sind Ergebnisse, Kosten und Logs dokumentiert.

## 12. Restrisiken

- Wikipedia ist eine Tertiärquelle. Die Antwort zitiert sie ausdrücklich so; Quellen mit höherer wissenschaftlicher Autorität (Agenturen, Fachpublikationen) sind erst für V2 vorgesehen.
- Die Volltextsuche mit natürlichsprachigen Fragen kann unpassende Seiten liefern. Das Modell muss dann abstinent bleiben; die semantische Qualität ist nicht verifiziert.
- Das Kontingent ist kein monetäres Hard-Cap.
- Ein fehlendes `published_at` schränkt die Aktualitätsangabe ein.
