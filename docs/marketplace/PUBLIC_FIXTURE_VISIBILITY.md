# Marketplace: öffentliche Sichtbarkeit bekannter Fixtures vs. Synthetic Quarantine

## Zwei getrennte Konzepte

| | Öffentliche Sichtbarkeit (`marketplace/selectors.py`) | Synthetic Quarantine (`apps/core/synthetic_quarantine.py`) |
|---|---|---|
| Zweck | Bekannte Benchmark- und Smoke-Fixtures erscheinen **nie** auf öffentlichen Oberflächen. | Den **Datenzustand** (`is_published`) nachvollziehbar zurücknehmen und wiederherstellen |
| Wirkung | nur lesend: `exclude()`, keine Mutation, kein Löschen | ändert `is_published` per signiertem Manifest, mit Audit-Ereignissen und Revert |
| Gültigkeit | dauerhaft, in jeder Umgebung | nur Labor oder CI (`_identity`), nie Production |
| Kriterium | Slug-Präfix **oder** Seller-Name (Defense in Depth) | Mehrere Provenienz-Merkmale zusammen (`_provenance`) |

- `published_products()` ist der Publikationszustand (`approved` und `is_published`).
- `public_products()` ist `published_products()` ohne `known_fixture_q()`.
- Name- und Slug-Merkmale sind **kein** Herkunftsnachweis. Für Löschung oder Bereinigung braucht es eine eigene Provenienz-Prüfung und eine Freigabe.

## Geschützte öffentliche Oberflächen
- `marketplace.views`: Index, Suche und Kategorie im Index sowie Detail (sonst 404)
- `apps.search.services.ProductAdapter`: globale Suche (`/api/search/`, `/search/`) und damit auch `apps.ai_core.gateway.retrieve_public` (AI-Retrieval)
- `apps.verification.api`: Produkt-Summary (404) und öffentliche Artefakt-Auflösung

Unverändert und bewusst offen:
- `seller_dashboard` (der Eigentümer sieht eigene Produkte)
- Review-Queue für Staff
- `publication.py` (verhindert weiterhin **neue** Veröffentlichung, jetzt über dieselbe Regel `is_known_fixture`)

**Offener Entscheid:** `apps.core.services.context.resolve_artifact_from_input` (öffentliche Inspect-Auflösung) filtert Fixtures noch **nicht**. Der Staging-Befehl `inspect_staging_smoke` legt das Smoke-Produkt absichtlich öffentlich an und prüft genau diese Auflösung. Eine Änderung würde dieses Betriebswerkzeug brechen. Optionen:
1. Inspect ebenfalls schützen und den Smoke-Befehl auf einen nicht-öffentlichen Prüfpfad umstellen.
2. Inspect bewusst ausnehmen und dokumentieren.

Die Entscheidung trifft der Eigentümer.

## Testvertrag
- `marketplace/tests.py`:
  - `MarketplaceKnownFixtureVisibilityTests` (Index, Suche, Kategorie, Detail, Dashboard, keine Löschung)
  - `PublicFixtureGuardAllSurfacesTests` (globale Suche, AI-Retrieval, Verifikations-API, keine Mutation, Gleichheit von DB- und Python-Prädikat, gleiche Regel wie `publication.py`)
- `apps/core/tests/test_synthetic_quarantine.py`:
  - `test_public_product_and_library_http_detail_denied_after_quarantine`: Für Produkte wird der Übergang im **Datenzustand** (`published_products`) vorher und nachher bewiesen; HTTP bleibt durchgehend 404 (Schutz). Für Library-Einträge gilt weiter HTTP 200 → 404.
  - `test_revert_restores_publication_state_but_public_guard_still_holds`: Ein Revert stellt den Datenzustand exakt wieder her; der öffentliche Schutz bleibt bestehen.

## Rollback
Revert des PR: Die öffentlichen Oberflächen zeigen dann wieder alle veröffentlichten Produkte. Es sind keine Daten betroffen und keine Migration nötig.
