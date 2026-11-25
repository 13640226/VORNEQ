# ADR-0007: Provider- und Modell-Registry, Gateway-Auflösung (V7-01)

Status: angenommen für V7-01 (Vervollständigung von PR #743). Datum: 2026-11-25.

## Kontext und aktuelle Architektur

- `apps/ai_core/gateway.py` ist **kein** Provider-Gateway, sondern der Orchestrator
  für öffentliche, zitierte Antworten (Validierung, Retrieval, `ask_public`).
- `apps/ai_core/global_router.py` routet Fragen nach Sprache/Quelle, nicht nach Provider.
- `apps/ai_core/providers/base.py` definiert nur das Protokoll `GroundedProvider`.
- Bezahlte Text-Provider entstehen ausschließlich in `paid_provider.paid_text_provider`
  (V4-01); gehostet immer in `BudgetedProvider` (reserve → call → settle).
- Bezahlte Bild-Aufrufe entstehen nur im Image-Worker nach einer Ledger-Reservierung.
- `apps/ai_ledger/call_authorization.py` verlangt vor jedem SDK-Client eine aktive
  Reservierung (`authorized_paid_call`).
- PR #743 führte `provider_registry.py`/`provider_resolution.py` als Metadaten-Prüfung
  an diesen Konstruktionsstellen ein; Modell-Registry und Auflösung waren unvollständig.

## Entscheidung (COR-01): bestehende Module erweitern, kein paralleles Gateway

Wir erweitern `apps/ai_core/provider_registry.py` und `apps/ai_core/provider_resolution.py`
an Ort und Stelle. Kein neues `apps/ai_gateway`, keine zweite Konstruktionsroute:

- Die einzigen Konstruktionsstellen bleiben `paid_text_provider`, der Image-Worker
  (`process_next_image_job`) und `voice.provider.get_provider`.
- Jede dieser Stellen ruft vor der Konstruktion `resolve(...)` auf (AST-geprüft).
- Eine spätere Extraktion in ein eigenes App-Paket ist möglich, sobald ein zweiter
  Provider existiert; sie wäre eine reine Verschiebung ohne Verhaltensänderung.

## Provider-Verträge (COR-02, COR-04)

`ProviderSpec`: `provider_id`, `display_name`, `capabilities`, `provider_type`
(`external_api`/`mock`), `enabled`, `paid`, `documentation_url`,
`data_processing_region`, `data_retention_status`, `dpa_status`,
`compliance_review_status`, `verified_at`.

- Zustände: `VERIFIED`, `NOT_VERIFIED`, `NOT_APPLICABLE` (nur Mocks).
- `VERIFIED` verlangt `verified_at` **und** `documentation_url` (Validierung).
- Mocks sind nie `paid`.
- Keine Secrets, keine Schlüssel, keine Endpunkte mit Zugangsdaten im Katalog.
- `NOT_VERIFIED` ist **keine** Aussage über rechtliche Konformität.

Capabilities: `TEXT_GENERATION`, `STRUCTURED_OUTPUT`, `STREAMING`, `TOOL_CALLING`,
`IMAGE_GENERATION`, `IMAGE_EDITING`, `EMBEDDING`, `SPEECH_TO_TEXT`, `TEXT_TO_SPEECH`,
`REALTIME_VOICE`, `VIDEO_GENERATION`, `MUSIC_GENERATION`, `THREE_D_GENERATION`
sowie intern `VOICE_MOCK`. Eine Capability im Vokabular bedeutet weder Implementierung
noch Aktivierung; der Bericht weist Capabilities ohne Provider als `NOT_IMPLEMENTED` aus.

Katalog V7-01: `openai-text`, `openai-image`, `mock-image`, `mock-voice`. Kein neuer
realer Provider.

## Modell-Verträge (COR-05, COR-06)

`ModelSpec`: `model_id`, `provider_id`, `display_name`, `capabilities`,
`input_modalities`, `output_modalities`, `context_window`, `max_input_tokens`,
`max_output_tokens`, `streaming_supported`, `tool_calling_supported`,
`structured_output_supported`, `pricing_reference`, `pricing_verified_at`,
`availability_status`, `enabled`.

- Bestehende Modelle tragen `availability_status = LEGACY_POLICY`: Sie bleiben durch die
  bisherigen Policies gesteuert (Image-Policy-Allowlist, Staging-/Production-Policy mit
  exaktem Modellvergleich). Die Bild-Allowlist hat nun eine Quelle
  (`LEGACY_OPENAI_IMAGE_MODELS`, Werte unverändert).
- Das Text-Modell steht nicht im Code (`VORNEQ_AI_PHASE_B_MODEL`); die Auflösung
  akzeptiert es nur als genau dieses konfigurierte Modell, die Freigabe bleibt in der Policy.
- Neue bezahlte Modelle (`REGISTRY_POLICY`) lassen sich nur mit `pricing_reference`
  **und** `pricing_verified_at` aktivieren (fail-closed).
- Preise, Kontextfenster und Verfügbarkeit sind in V7-01 nicht verifiziert (`None`/`NOT_VERIFIED`).

Kompatibilitätskonflikt (gemeldet, nicht eigenmächtig gelöst): Die bestehenden
Bildmodelle sind ohne verifizierte Preisreferenz aktiv. Die Kostenobergrenze setzen
Ledger-Reservierung und `VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD`. Ob für Legacy-Modelle
künftig ebenfalls eine verifizierte Preisreferenz Pflicht wird, entscheidet der Eigentümer.

## Gateway-Auflösung (COR-07, COR-09, COR-10)

`resolve(capability, *, actor, environment, model_id=None, provider_id=None,
ledger_bound=None, feature_enabled=None, scope="user")` prüft:

1. Umgebung bekannt (`development`/`staging`/`production`) und gleich `VORNEQ_ENV`.
2. Emergency Stop (alle Capabilities).
3. Provider bekannt, aktiv, Capability vorhanden; ohne `provider_id` nur bei eindeutiger
   Capability (kein stilles Routing).
4. Feature-Gate: das von der Konstruktionsstelle gerade ausgewertete Gate
   (`feature_enabled`) oder das Settings-Flag (`VORNEQ_AI_IMAGE_ENABLED`,
   `VORNEQ_AI_VOICE_ENABLED`). Text-Flags bleiben bei den Aufrufern (`LEGACY_CALL_SITE`).
5. Modell bekannt, aktiv, Capability vorhanden.
6. Bezahlt: authentifizierter Akteur; gehostet nur mit `ledger_bound=True`.
7. `scope` nur `"user"`; Organisations-/Projekt-Scopes erst nach Tenant-Isolation.

Ergebnis ist eine `Resolution`; `authorizes_paid_call` ist immer `False`. Fallback:
in V7-01 keiner. Künftiger Vertrag: Fallback nur zwischen vom Eigentümer als
gleichwertig markierten Modellen, je Versuch eigene Reservierung, Fehlschläge mit
unbekannten Kosten bleiben `UNCERTAIN` im Ledger, keine Weitergabe privater Daten an
Provider mit anderer Datenverarbeitungsgrundlage.

## Ledger-Integration und Sicherheitsgrenzen (COR-03, COR-11)

- Text: nur `paid_text_provider` → `BudgetedProvider` → `authorized_paid_call("text")`.
- Bild: Worker reserviert, prüft `reservation_still_open`, dann `resolve`, dann Adapter
  unter `authorized_paid_call("image")`. Eine Auflösungs-Ablehnung ist `request_sent=False`
  (Reservierung wird über den normalen Fehlerpfad freigegeben).
- Voice: nur der Offline-Mock; ein anderer Provider wird abgelehnt.
- `authorized_paid_call` akzeptiert nur strukturell gültige Reservierungen (UUID-ID,
  positiver Betrag); Freigaben laufen nach dem Aufruf ab und sind nach Art getrennt.
- AST-Wächter: Provider-Konstruktion nur nach `resolve` in derselben Funktion;
  `openai`-Importe nur in den beiden Adaptern (zusätzlich zu den V4-01-Wächtern).

## Fehlernormalisierung (COR-08)

`RegistryError` (ValueError) mit `code`: `ProviderUnavailable`, `ProviderDisabled`,
`ModelUnavailable`, `ModelDisabled`, `CapabilityMissing`, `AuthorizationDenied`,
`BudgetRefused`, `EmergencyStopActive`, `InvalidEnvironment`, `InvalidConfiguration`.
HTTP-Verträge bleiben: Text bildet Ablehnungen auf `LedgerUnavailable` ab, Bild auf
`ImageProviderError(request_sent=False)`, Voice auf `VoiceProviderBlocked`.

## Datenschutz

Keine personenbezogenen Daten im Katalog. Region, Aufbewahrung, DPA und Compliance
der realen Provider sind `NOT_VERIFIED`; ein Provider mit `dpa_status != VERIFIED`
darf künftig keine privaten Daten (RAG, Gedächtnis, Dateien) erhalten (Regel für V7-04ff).

## Künftiges Streaming und weitere Adapter

- Streaming (V7-03) verlangt eine Entscheidung zu ASGI; die Reservierung muss den
  gesamten Stream abdecken, Abbruch durch den Nutzer wird regulär abgerechnet.
- Weitere Adapter (zweiter Text-Provider, Embedding, STT/TTS) erst nach Due Diligence
  mit verifizierten Einträgen und dem FA/DE/EN-Bewertungsset (COR-12); in V7-01 keine
  kostenpflichtigen Tests.

## Rollback (COR-15)

`git revert` des finalen Merge-Commits dieses PRs. Keine Migration, keine neuen
Umgebungsvariablen, keine Datenänderung: Code vor und nach dem Revert arbeitet auf
demselben Schema. Die Regression-Suites (Chat, Bild, Voice, Ledger) belegen das
unveränderte Verhalten.
