# VORNEQ Product UI V6-02 – Nachweise Vorher/Nachher

Aufgenommen mit Playwright + Google Chrome gegen den lokalen Dev-Server
(`runserver`, DEBUG, SQLite), identische Viewports und Themes für beide Phasen.
Vorher = `main` @ `57ef995` (V6-01), Nachher = Branch `feat/product-ui-v6-02-visual-transformation`.
Skript: `scripts/ui/homepage_v6_02_shots.py <before|after>`; Rohwerte in `before/metrics.json`, `after/metrics.json`.

| Ansicht | Header (px) vorher → nachher | Composer-Oberkante (px) | Wörter im Hauptbereich | Bedienelemente im ersten Viewport | Seitenhöhe (px) |
|---|---|---|---|---|---|
| Desktop dunkel 1440×900 | 64 → 56 | 512 → 221 | 343 → 152 | 13 → 17 | 2889 → 1102 |
| Mobil dunkel 390×844 | 91 → 56 | 556 → 117 | 342 → 139 | 8 → 20 | 4694 → 1722 |
| FA RTL Desktop | 64 → 56 | 512 → 235 | 377 → 158 | 13 → 17 | 2813 → 1150 |
| FA RTL Mobil | 91 → 56 | 531 → 160 | 375 → 143 | 8 → 20 | 4549 → 1784 |
| DE Desktop | 64 → 56 | 538 → 221 | 319 → 137 | 13 → 17 | 2961 → 1122 |
| Angemeldet Desktop | 64 → 56 | 512 → 221 | 370 → 167 | 16 → 24 | 3133 → 1342 |
| Angemeldet Mobil (FA, hell) | 91 → 56 | 558 → 160 | 395 → 156 | 8 → 23 | 5227 → 2073 |

Sichtbare Unterschiede: kompakter App-Header statt Site-Header; App-Sidebar (einklappbar, Drawer
unter 1024px) statt Rail; großer V5-Hero und V5-Abschnitte entfernt; Composer direkt oben;
Schnellaktionen; visuelles App-Raster mit echtem Status; neue Palette/Typografie (Design System V6-02);
neue Mobile-Bottom-Navigation (Start, Suche/Chat, Erstellen, Arbeitsbereich/Bibliothek, Mehr).

Vergleichsbilder: `compare-*.png` (links vorher, rechts nachher).

Responsive-Matrix (`after/responsive-matrix.json`): 108 Messungen
(320/360/390/430/768/1024/1280/1440/1920 × fa/de/en × dunkel/hell × Gast/angemeldet):
0 horizontale Überläufe, Header überall 56px, kleinstes Tap-Ziel 44px, keine JS-Fehler.

Lighthouse 13.6 (`lighthouse-summary.json`), lokaler Dev-Server ohne Kompression, nur Laborwerte –
keine Aussage über Production. INP ist im Labor nicht messbar (TBT als Näherung).
