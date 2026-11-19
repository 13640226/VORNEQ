# Marketplace UI V2

- Umfang: Index, Produktdetail, Verkäufer-Dashboard
- Keine Migration, keine Datenänderung, keine neuen Endpunkte

## Grundsätze
- **Design-System:** Nur Tokens aus `tokens.css` und `theme-palettes.css`, kein fest codierter Farbwert (Test). Dadurch gelten alle Nutzer-Themes, auch „emerald“. Die Datei `assets/css/marketplace-v2.css` ist auf `.mkt-v2` begrenzt. Die bisherigen Dateien bleiben unverändert, die alten Klassen bleiben erhalten.
- **RTL:** Nur logische Eigenschaften (`margin-inline`, `inset-block` …), ein Test prüft das. `dir="auto"` gilt für gemischtsprachige Titel und Beschreibungen.
- **Barrierefreiheit:**
  - Mindestens 44 px Touch-Ziele
  - `:focus-visible` mit Fokusring
  - `prefers-reduced-motion`, `forced-colors`
  - Semantik: `role="search"`, `nav` mit `aria-current`, Listen, Brotkrumen
  - Screenreader-Kontext an „Details ansehen“ und „Bearbeiten“
- **Kontrast:** Kleine Texte nutzen `--color-text-secondary` (≥ 4,68:1 in allen Themes) statt `--color-text-muted` (3,78:1 im Standard-Hell-Theme). Primärbuttons nutzen große fette Schrift, weil `on-accent`/`accent` im Dark-Theme nur 3,08:1 erreicht.
- **Stabile Geometrie:** Feste `aspect-ratio` für Bild und Platzhalter, Bilder mit `width`/`height`, keine Hover-Verschiebung.

## Ehrlicher Handelszustand
- `Product.price` hat **keine Währung**, und es gibt keinen Checkout. Deshalb:
  - Preis 0: „Kostenlos“
  - Preis > 0: „Kostenpflichtiges Produkt“, im Detail mit „Ein Kauf ist noch nicht möglich.“
  - Kein Betrag ohne Einheit, keine erfundene Währung, kein Kauf- oder Warenkorb-Button (Tests)
- Wird eine Währung ergänzt (Migration, eigener Vertrag), zeigt `includes/price_state.html` künftig den Betrag an.

## Funktion
- **Sortierung:** Nur erlaubte Schlüssel (`newest`, `title`, `price_low`). Unbekannte Werte fallen auf `newest` zurück (Injection-Test).
- **Suchbegriff:** auf 100 Zeichen begrenzt.
- **Leerer Zustand:**
  - Katalog leer: „Es wurden noch keine Produkte veröffentlicht.“ mit echtem Pfad `product_create` (angemeldet) bzw. Login mit `next`.
  - Kein Treffer bei Filter: eigener Zustand.
- **Detail:**
  - Brotkrumen
  - Panel mit Preiszustand, Moderationshinweis und Aktualisierungsdatum
  - Download nur bei Entitlement (unverändertes `delivery.py`)
  - Alle Trust-, Verifikations-, Evidenz- und Reputations-Bausteine bleiben.
- **Dashboard:**
  - Zähler: gesamt, in Prüfung, freigegeben, veröffentlicht, abgelehnt
  - Pro Produkt Status, Veröffentlichungszustand und letzte Moderationsentscheidung mit Datum
  - Moderationsnotizen bleiben intern (Test).
  - Nur eigene Produkte (Test).

## Nicht enthalten / Folgearbeiten
- Übersetzung bestehender Verifikations- und Identitäts-Texte („Canonical identity“, „Public Evidence“ …). Diese Strings gelten auch in Library und Profil, und bestehende Tests erwarten dort Englisch. Das gehört in einen eigenen PR mit angepassten Tests.
- Die globale Schaltfläche „Back“ im Basis-Layout ist auf Persisch unübersetzt; sie liegt außerhalb des Marketplace.
- Persische Such-Normalisierung (ی/ي, ک/ك, ZWNJ), Upload-Inhaltsprüfung, Währung, Commerce

## Prüfung (lokal)
- **Playwright/Chromium** gegen einen lokalen Server mit synthetischen Daten (nur lokale SQLite):
  - Seiten: en/fa/de, Detail, leerer Zustand, Dashboard
  - Breiten: 390, 768 und 1440 px
  - Ergebnis: 20 Prüfungen ohne horizontales Scrollen, keine Bedienelemente unter 44 px, keine Konsolenfehler
- Behobene Befunde: Überlauf bei 390 px auf Deutsch (Sortierformular), kleines Inline-Link-Ziel
