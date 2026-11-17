# VORNEQ AI — Dauerhafte Gespräche V1: Ist-Analyse und Design

| Feld | Wert |
|---|---|
| Auftrag | `P0_VORNEQ_AI_PERSISTENT_CONVERSATION_ARCHITECTURE_AND_IMPLEMENTATION_V1`, Phasen A und B |
| Datum | 2026-11-17 |
| Basis | `main` @ `6170bc46b9bd798b9828ebde14847f7230d93aaf`, per GitHub-API geprüft; CI, Security Audit und Deploy Watch `success` |
| Branch | `feat/ai-persistent-conversation-v1`, lokal |
| Status | **IMPLEMENTIERT AUF ISOLIERTEM BRANCH** nach den Entscheidungen des Eigentümers vom 2026-11-17 (Abschnitt 9). Feature-Flag standardmäßig aus. Production, Production-DB und OpenAI wurden nicht berührt. |

## 1. Ist-Analyse (Phase A, nur lesend)

### 1.1 Modelle und Migrationen
- `ai_core` hat genau zwei Modelle:
  - `StagingAIBudgetDay` (Migration `0001`)
  - `AIChatRequestGuard` (Migration `0002`)
- `AIChatRequestGuard` speichert laut eigener Dokumentation **ausdrücklich keine Frage und keine Antwort**, sondern nur Request-ID, `actor_id`, Session-Digest, Fingerprint und Status.
- `ai_ledger` (Migration `0001`) liegt über `AILedgerRouter` in einer **eigenen Datenbank**. Fremdschlüssel von `ai_core` nach `ai_ledger` sind daher nicht möglich; Verweise erfolgen nur über die UUID.
- Für `ai_core` gibt es keine Admin-Registrierung.

### 1.2 Benutzer, Identität, Mandant
- Authentifizierung: `django.contrib.auth` mit allauth. `AUTH_USER_MODEL` ist der Standard.
- Die Plattform hat ein eigenes Besitzmodell: `core.Identity` (Arten: human/organization/agent/system), `UserIdentity` (1:1 User→Identity) und `ArtifactIdentityRole`. Notes und Documents nutzen es; ohne `UserIdentity` verweigern sie den Zugriff.
- **Es gibt kein Organisations-/Mandantenmodell mit Mitgliedschaften.** `Identity.kind=organization` existiert, aber nichts verbindet Menschen mit einer Organisation. Echte Mandantentrennung („Tenant A vs. B“) ist deshalb heute nicht prüfbar. Möglich ist nur die Trennung pro Benutzer.
- Der KI-Pfad arbeitet mit der Django-User-ID: `actor_id` im Ledger und im Guard, Production-Allowlist „Admin 1“. Ob Admin 1 eine `UserIdentity` hat, ist unbekannt.

### 1.3 Chat- und Recovery-Pfad
- Routen: `ask/`, `ask-grounded/`, `chat/`, `ask-global/`, `request-status/`.
- `ask_global_view` prüft der Reihe nach:
  - Feature-Gate
  - Login
  - Production-/Staging-Allowlist
  - nur JSON, ≤ 2048 Bytes, strikte Felder `{question, language}`
  - `gateway.validate` (Frage 1–200 Zeichen)
- Danach: Recovery-Claim (`X-VQ-Request-ID`), Routing, Burst-Throttle, Ledger (`BudgetedProvider`: reserve → Aufruf → settle), `ask_global` (Abruf → Ranking → Modell → Zitat- und Zahlenprüfung).
- Jede Frage ist unabhängig. `build_request_payload` sendet nur `{question, language, sources}`.
- Recovery: PostgreSQL-Guard als dauerhafte Idempotenz, Redis mit 15 min Antwort-Cache und 24 h Guard.

### 1.4 Ledger
- Die Reservierung errechnet sich aus der **exakten Nutzlast** (`build_request_payload`) und `max_output_tokens`.
- Abgerechnet wird nach den gemeldeten Tokens. Ohne Usage-Angabe bleibt der Betrag „uncertain“.
- Folge für dieses Vorhaben: Wird Gesprächskontext in dieselbe Nutzlast-Funktion aufgenommen, reserviert der Ledger automatisch korrekt mehr.

### 1.5 Datenbank und Migrationen in Production
- Neue Tabellen landen in der **Default-Datenbank** (Production-DB) und brauchen `ai_core.0003`.
- Der bestehende C02-Runner (`apps/core/c02_stage_c_runner.py`) ist **fest auf `EXPECTED_PLAN = 0001 + 0002` gebunden**. Eine neue Migration braucht einen eigenen, erweiterten und freigegebenen Pfad. Das ist ein eigenes Vorhaben vor jedem Production-Rollout.

### 1.6 Datenschutz-Risiken (neu durch dieses Vorhaben)
1. **Grundsatzwechsel:** Bisher speichert VORNEQ keine KI-Fragen oder -Antworten. Künftig enthält die Production-DB Gesprächsinhalte, die persönliche Daten enthalten können. Das braucht eine ausdrückliche Entscheidung des Eigentümers und einen Hinweis in der Oberfläche.
2. Inhalte gelangen in Backups (`postgres_backup.sh`). Gelöschte Gespräche bleiben bis zum Ende der Backup-Aufbewahrung dort.
3. Datenbank-Administratoren könnten Inhalte lesen. Es gibt keine Admin-Registrierung und keine Inhalte in Logs. Eine Verschlüsselung auf Feldebene ist nicht Teil von V1.
4. Bestehende Logik zu personenbezogenen Daten: `screen_and_redact` schwärzt sie vor Suche und Modell. Gespeichert wird der Originaltext des Benutzers (seine eigenen Daten); an Suche und Modell gehen weiterhin nur geschwärzte Fassungen.
5. IDOR: Gespräche werden ausschließlich über `owner=request.user` abgefragt. Fremde IDs ergeben `404`, nie `403`, damit die Existenz eines Gesprächs nicht verraten wird.

## 2. Umfang von V1 (bewusst eng)

**In V1:**
- dauerhafte Gespräche und Nachrichten in PostgreSQL
- Liste, Fortsetzen, Umbenennen, Archivieren, Löschen, Export (JSON), einfache Suche
- Kontextaufbau aus den letzten Wortwechseln
- Anbindung von Chat AI V2

**Nur entworfen, nicht in V1** (eigene Migration und Kostenfrage):
- Zusammenfassungen (zusätzlicher Modellaufruf je Gespräch)
- Langzeitgedächtnis
- Projekte
- Anhänge
- Embeddings

**Begründung:** Jede Production-Migration läuft über den C02-Pfad. Leere Tabellen „auf Vorrat“ erhöhen das Risiko ohne Nutzen. Die Entwürfe in Abschnitt 4 sichern, dass V1 sie später ohne Umbau aufnehmen kann.

Unverändert bleiben:
- `ask-global/` und alle bestehenden Endpunkte (abwärtskompatibel)
- Ledger, Zitat- und Zahlenprüfung, Recovery, Emergency Stop, Allowlist
- die 200-Zeichen-Grenze und der Output-Deckel von 2048 Tokens; deren Lockerung ist Phase 2

## 3. Schema V1 (`ai_core.0003_conversation`, additiv)

### `AIConversation`

| Feld | Typ | Regel |
|---|---|---|
| `id` | UUID, PK | zufällig, nicht erratbar |
| `owner` | FK `AUTH_USER_MODEL`, `on_delete=CASCADE` | einziger Zugriffsschlüssel; Löschen des Kontos löscht die Gespräche |
| `title` | `CharField(120)` | anfangs aus der ersten Frage gekürzt; umbenennbar |
| `language` | `CharField(2)` | `fa`/`de`/`en` |
| `created_at`, `updated_at`, `last_message_at` | DateTime | |
| `archived_at` | DateTime, null | archiviert ≠ gelöscht |
| `deleted_at` | DateTime, null | Papierkorb (D2): nach 30 Tagen endgültig gelöscht durch `ai_conversations_purge` |
| `message_count` | PositiveInteger | Obergrenze, siehe unten |

- Index: `(owner, deleted_at, archived_at, last_message_at)` und `(deleted_at)`.

### `AIMessage`

| Feld | Typ | Regel |
|---|---|---|
| `id` | UUID, PK | |
| `conversation` | FK, `CASCADE` | |
| `sequence` | PositiveInteger | eindeutig je Gespräch (`UniqueConstraint`) |
| `role` | `user` \| `assistant` | **Keine** Rollen `system`/`developer`/`tool`: Anweisungen bleiben im Code und werden nie gespeichert, damit gespeicherter Text nicht zur Anweisung werden kann |
| `content` | `TextField` | Benutzer ≤ Eingabegrenze; Assistent ≤ 1000 Zeichen (heutiger Validator) |
| `status` | `completed` \| `insufficient_evidence` \| `failed` | Fehlversuche ohne Antworttext, nur mit festem `error_code` |
| `error_code` | `CharField(40)` | nur bekannte Enum-Werte |
| `citations` | JSON | nur die **serverseitig validierten** Zitate: `source_id`, Titel, URL, Publisher, `evidence_quote`, `retrieved_at` |
| `request_id` | UUID, null, **eindeutig** | Brücke zu `AIChatRequestGuard`; verhindert doppelte Speicherung |
| `ledger_reservation_id` | UUID, null | Verweis in die Ledger-DB, kein FK |
| `model`, `input_tokens`, `output_tokens` | | Metadaten, keine Kosten-Wahrheit |
| `created_at` | DateTime | |

- Index: `(conversation, sequence)`.
- Grenzen: höchstens 500 Nachrichten pro Gespräch und 200 Gespräche pro Benutzer, beide konfigurierbar. Sie schützen vor Missbrauch, nicht vor normaler Nutzung.

## 4. Entwürfe für spätere Phasen (keine Tabellen in V1)

- **`AIConversationSummary`:** `conversation`, `summary`, `covers_until_sequence`, `version`, `model`, `created_at`. Entsteht erst bei langen Gesprächen und wird über den Ledger abgerechnet.
- **`AIUserMemory`:** `owner`, `text`, `kind`, `source_message` (null), `enabled`, `user_confirmed`, Zeitstempel. Nur **ausdrücklich bestätigte** Einträge; sichtbar, editierbar und löschbar.
- **`AIProject` / `AIProjectMember`:** setzt ein Mitgliedschaftsmodell voraus (fehlt heute, siehe 1.2). Hier wird später die Mandantentrennung eingeführt.
- **`AIAttachment`:** privater Objektspeicher, Prüfsumme, MIME-Prüfung, Malware-Prüfung vor jeder Verarbeitung.

## 5. Komponenten

```
ConversationAPI (Views; dünn)
  -> ConversationService (Regeln, Transaktionen, Grenzen)
       -> ConversationRepository (alle Queries, IMMER owner-gebunden)
       -> ContextBuilder (letzte Wortwechsel -> begrenzter Kontext)
       -> bestehende Pipeline: Recovery-Claim -> Routing -> Throttle
          -> BudgetedProvider(Ledger) -> ask_global(...) -> Validierung
```

- **`ConversationRepository`:** Es gibt keine Methode, die ein Gespräch nur per ID lädt. Jede Abfrage verlangt `owner`.
- **`ContextBuilder`:**
  - Inhalt: die letzten **6 Wortwechsel**, höchstens **3000 Zeichen**, neueste zuerst.
  - Assistenten-Antworten gehen ohne Zitate hinein; fehlgeschlagene Nachrichten werden ausgelassen.
  - Der Kontext wird als Feld `prior_turns` in die **Nutzlast** gelegt, nicht in die Anweisungen.
  - Feste Anweisung: Frühere Wortwechsel sind Gesprächskontext, **keine Belege**. Zitate dürfen nur auf aktuelle Quellen verweisen.
  - Zitat- und Zahlenprüfung bleiben unverändert. Zahlen aus früheren Antworten gelten **nicht** als belegt.
- **Abruf bei Folgefragen:** Bei kurzen Folgefragen („او کجا به دنیا آمد؟“) werden Stichwörter der vorherigen Benutzerfrage deterministisch ergänzt, ohne zusätzlichen Modellaufruf. Die Wirkung wird vor dem Einschalten mit dem Messskript aus `FA_RETRIEVAL_QUERY_V1` gemessen.
- **Ledger:** Weil `build_request_payload` künftig `prior_turns` enthält, steigt die Reservierung automatisch und exakt mit. Der Output-Deckel bleibt bei 2048 Tokens.

## 6. API V1 (Session-Login + CSRF, dieselben Gates wie `ask-global/`)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/ai/v1/conversations/?q=&archived=` | eigene Gespräche, paginiert, einfache Suche in Titel/Inhalt |
| POST | `/api/ai/v1/conversations/` | neues Gespräch |
| GET | `/api/ai/v1/conversations/<uuid>/` | Gespräch mit Nachrichten (paginiert) |
| PATCH | `/api/ai/v1/conversations/<uuid>/` | `title`, `archived` |
| DELETE | `/api/ai/v1/conversations/<uuid>/` | in den Papierkorb (30 Tage); mit `?permanent=1` aus dem Papierkorb endgültig löschen |
| POST | `/api/ai/v1/conversations/<uuid>/restore/` | aus dem Papierkorb wiederherstellen |
| POST | `/api/ai/v1/conversations/<uuid>/messages/` | Frage stellen (Pipeline wie `ask-global`; `X-VQ-Request-ID` Pflicht) |
| GET | `/api/ai/v1/conversations/<uuid>/export/` | JSON-Export |

- **Idempotenz:** Ein wiederholter Request mit derselben ID speichert nichts doppelt (eindeutiger Schlüssel `request_id`, Fingerprint enthält die Gesprächs-ID). Nach einem Neuladen kommt der Verlauf aus PostgreSQL, nicht aus Redis. Die frühere Aussage „in einer Transaktion zusammen mit `recovery.finish`“ war **falsch** und ist durch Abschnitt 11 ersetzt.
- **Fehler:** Fremde oder nicht existierende IDs ergeben `404`. Ist die Nachrichtengrenze erreicht, kommt `409` mit dem Hinweis, ein neues Gespräch zu beginnen.

## 7. Oberfläche (Übergang von Chat V2)

- Desktop: Seitenleiste mit „Neues Gespräch“, Suche und Liste. Mobil: Schublade.
- Das aktive Gespräch steht in der URL (`?c=<uuid>`), sodass Neuladen und Wiederkehren dasselbe Gespräch öffnen.
- Keine Inhalte in `localStorage`/`sessionStorage`. Dort liegt weiterhin nur die Request-ID für die Recovery.
- Umbenennen, Archivieren, Löschen (mit Bestätigung) und Export.
- Dauerhafter Hinweis: „Gespräche werden auf dem VORNEQ-Server gespeichert.“
- `ask-global/` bleibt für den Fall erhalten, dass die Funktion abgeschaltet ist (Flag `VORNEQ_AI_CONVERSATIONS_ENABLED`, Standard **aus**).

## 8. Tests (Phase D) und Rollout

Tests, alle offline mit einem Fake-Provider:
- 50 Nachrichten
- Neuladen, simuliert mit neuem Client und geleertem Redis-Cache
- Neustart, simuliert mit geschlossenen DB-Verbindungen
- Benutzer A gegen B (IDOR auf jeder Route)
- derselbe `request_id` zweimal ergibt genau ein Nachrichtenpaar und eine Reservierung
- Ledger-Eingabe enthält den Kontext
- Kontextgrenze
- frühere Zahlen gelten nicht als Beleg
- Löschen ist endgültig
- persischer RTL-Text
- SQLite und PostgreSQL

Rollout in dieser Reihenfolge, jeder Schritt mit eigener Freigabe:
1. PR
2. CI
3. Merge
4. Staging-Deploy und Staging-Migration
5. Erweiterung des C02-Runners auf `0003`
6. Production-Backup
7. Production-Migration
8. Deploy
9. Flag einschalten, nur für Admin 1

## 9. Entscheidungen des Eigentümers (vor Phase C nötig)

| Nr. | Frage | Empfehlung |
|---|---|---|
| D1 | Dürfen Fragen und Antworten dauerhaft in der Production-DB gespeichert werden (Grundsatzwechsel, Abschnitt 1.6)? | Ja, mit Hinweis in der Oberfläche, ohne Admin-Ansicht und ohne Inhalte in Logs |
| D2 | Löschen: endgültig sofort (Backups bis zu deren Ablauf) oder zuerst „Papierkorb“ (30 Tage)? | Endgültig sofort |
| D3 | Mandanten: in V1 Trennung pro Benutzer; Organisationen erst mit Mitgliedschaftsmodell? | Ja |
| D4 | Umfang der Migration `0003`: nur Gespräche und Nachrichten? | Ja |
| D5 | Kontext: letzte 6 Wortwechsel / 3000 Zeichen; frühere Antworten nie als Beleg? | Ja |

Ohne D1 wird nichts implementiert. Alle anderen Punkte können später angepasst werden.

**Entscheidungen des Eigentümers (2026-11-17):**
- D1: ja, mit den vorgeschlagenen Bedingungen
- D2: **Papierkorb 30 Tage** (abweichend von der Empfehlung)
- D3, D4, D5: wie vorgeschlagen

## 10. Umsetzung und Ergebnisse (Phase C/D, 2026-11-17)

**Dateien:**
- Neu:
  - `apps/ai_core/conversations/` mit `repository.py`, `service.py`, `context.py`
  - `apps/ai_core/views_conversations.py`
  - Migration `ai_core/0003_conversation.py`
  - Befehl `ai_conversations_purge`
  - drei Testdateien
- Geändert:
  - `models.py`, `urls.py`, `chat_page.py`, `chat_strings.py`
  - Template, JS und CSS des Chats
  - `config/settings.py`: Flag und Grenzen
- Gezielt angepasst:
  - `build_request_payload`: `prior_turns` nur, wenn vorhanden
  - Provider, `BudgetedProvider`, `ask_global`: optionaler Parameter `prior_turns`
  - `views_global.ask_global_view`: Pipeline als `run_global_pipeline` herausgelöst, Verhalten unverändert

**Unverändert und durch Tests gesichert:**
- Endpunkt `ask-global/`
- Payload ohne Verlauf byte-identisch zum bisherigen Format
- Zitat- und Zahlenprüfung, Recovery, Emergency Stop, Allowlist
- Grenzen: 200 Zeichen, 2048 Tokens

**Tests (echte Ausführung, Python 3.13, Django 5.2):**
- Neu: 33 Tests in `test_conversations_v1`, `test_conversations_recovery`, `test_conversations_ui`
- Gesamtsuite SQLite: **1686 OK** (55 übersprungen)
- Gesamtsuite PostgreSQL 16.15 in CI-Topologie: **1686 OK** (12 übersprungen)
- `check` und `makemigrations --check` sauber
- Migration `0003` auf PostgreSQL vorwärts, rückwärts (`migrate ai_core 0002`) und erneut vorwärts ausgeführt
- Abgedeckt:
  - 50 Nachrichten
  - Logout, neue Session, geleerter Cache, geschlossene DB-Verbindungen (TransactionTestCase)
  - Redis-Verlust
  - Benutzer B erhält auf allen 7 Routen `404`
  - CSRF auf allen Änderungen
  - dieselbe `request_id` zweimal: genau ein Nachrichtenpaar und ein Modellaufruf
  - eine `request_id` in ein anderes Gespräch: `409`
  - Ledger: Verlauf erhöht die Reservierung; ein Replay erzeugt keine zweite Reservierung; die Reservierungs-ID wird gespeichert
  - Zahlen aus dem Verlauf werden als nicht belegt abgelehnt
  - fehlgeschlagene Wortwechsel gespeichert, aber nicht im Kontext
  - personenbezogene Daten im Verlauf geschwärzt; Injection-Text im Verlauf verworfen
  - Papierkorb, Wiederherstellen, endgültiges Löschen und Purge nach 30 Tagen
  - Löschen des Kontos kaskadiert
  - Verlauf bleibt bei Emergency Stop lesbar und exportierbar
- Browser (Playwright/Chrome, lokaler Server mit synthetischer Suche und synthetischem Modell im Prozess, ohne Netzwerk):
  - fa, Desktop 1440 und Mobil 390
  - Gespräch anlegen, Folgefrage mit Kontext
  - Neuladen und neue Session auf Mobil stellen alle 4 Nachrichten wieder her
  - neues Gespräch, Umbenennen, Suche, Papierkorb, Wiederherstellen
  - kein horizontales Scrollen, kein Bedienelement unter 44 px
  - Der Zahlenvalidator hat eine Antwort mit nicht belegter Zahl auch im Gesprächsmodus blockiert.

**Bekannte Grenzen von V1:**
1. Die Suche nutzt standardmäßig nur die aktuelle Frage. Folgefragen ohne eigene Stichwörter („und wer hat es erfunden?“) finden oft keine Quelle. Die deterministische Anreicherung ist inzwischen eingebaut, aber per Flag **aus** (Abschnitt 11.6).
2. Der Purge braucht einen täglichen Job (z. B. Render Cron). Ohne ihn bleiben Papierkorb-Einträge länger als 30 Tage liegen.
3. Für die Production-Migration `0003` braucht der C02-Runner eine eigene Erweiterung. Er ist fest auf `0001` und `0002` gebunden.
4. Keine Mandantentrennung über Organisationen (D3); kein Streaming; die Grenzen 200 Zeichen und 2048 Tokens bleiben (Phase 2).

## 11. Sicherheits-Nachbesserung (2026-11-17)

Dieser Abschnitt ersetzt alle früheren Aussagen zu Transaktionen, Idempotenz und Wiederherstellung. Stand: Baseline `6170bc46`, Branch `feat/ai-persistent-conversation-v1`.

### 11.1 Zustandsmodell eines Requests

| Schritt | Speicher | Garantie |
|---|---|---|
| 1. Claim (`AIChatRequestGuard`, `running`) | PostgreSQL `default` | Request-ID ist an Akteur, Session, Gesprächs-ID und Fingerprint gebunden. Fremde Session → `404`, anderes Gespräch oder andere Frage → `409`. |
| 2. `begin_turn` | PostgreSQL `default`, **eine** Transaktion | Frage und eine Assistenten-Zeile mit Status `pending` sind festgeschrieben, **bevor** Quota, Suche, Ledger oder Provider laufen. Scheitert das → `503 persistence_unavailable`, kein Provider-Aufruf, keine Reservierung. |
| 3. Pipeline | Ledger-Alias `ai_ledger` + Provider | unverändert: reserve → call → settle. |
| 4. `complete_turn` | PostgreSQL `default`, **eine** Transaktion | Endgültige Assistenten-Nachricht **und** Guard `running → finished` werden gemeinsam festgeschrieben (gleicher Alias, `select_for_update`). |
| 5. Redis-Ergebnis-Cache | Redis | **best effort nach dem Commit**, nie Teil der Transaktion. |

Status einer Assistenten-Zeile: `pending`, `completed`, `insufficient_evidence`, `failed`, `uncertain`. `provider_timeout` und Abbrüche nach dem Provider-Aufruf werden `uncertain`: Der Provider kann gearbeitet und abgerechnet haben.

### 11.2 Was **nicht** atomar ist

- PostgreSQL (`default`), Ledger (`ai_ledger`) und Redis sind drei getrennte Systeme. Es gibt **keine** gemeinsame Transaktion zwischen ihnen und auch kein Zwei-Phasen-Commit.
- Atomar ist nur Schritt 2 für sich und Schritt 4 für sich, jeweils innerhalb von `default`.
- Mögliche Abweichung: Der Provider wurde abgerechnet (Ledger `settled`), aber Schritt 4 scheitert. Dann bleibt die Zeile `pending`; die Antwort wird mit `persisted: false` ausgeliefert, und die Oberfläche zeigt „nicht gespeichert“. Ein Replay derselben ID ruft den Provider **nicht** erneut auf.

### 11.3 Grenzen der Wiederherstellung

- Wiederherstellbar ist nur, was dauerhaft geworden ist: nach Schritt 2 die Frage, nach Schritt 4 die Antwort.
- Eine Antwort, die nur im Redis-Cache liegt (15 Minuten), kann der Abgleich (11.4) innerhalb dieses Fensters übernehmen. Danach ist sie **nicht** wiederherstellbar; die Zeile wird `uncertain`.
- Was nie dauerhaft war (Absturz vor Schritt 2, Verlust des Redis-Ergebnisses vor dem Abgleich), kann **nicht** garantiert wiederhergestellt werden.

### 11.4 Abgleich (`ai_conversations_reconcile`)

- Standard ist nur ein Bericht; `--apply` schreibt. `--older-than-minutes` mindestens 3, Standard 10.
- Veraltete `pending`-Zeilen werden aus dem Redis-Ergebnis abgeschlossen, sonst als `uncertain/interrupted` markiert. Es gibt nie einen erneuten Provider-Aufruf.
- Ledger-Teil (nur lesend): zählt Reservierungen im Zeitfenster ohne Verknüpfung zu einer Nachricht, pro Akteur. Es ist eine **Obergrenze**, denn sie enthält auch Reservierungen von `ask-global/`. Abweichungen sind so erkennbar und auditierbar; unsichere Nutzung bleibt im Ledger stehen und wird nicht gelöscht.
- Ausgabe nur mit Zählern und IDs, nie mit Inhalten.
- Ein Cron-Job ist **nur dokumentiert, nicht angelegt** (Freigabe des Eigentümers nötig). Vorschlag: täglich `ai_conversations_purge`, alle 15 Minuten `ai_conversations_reconcile --apply`.

### 11.5 Pilot-Zugang

- `VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY` ist `allowlist` (Standard) oder `authenticated`. Jeder andere Wert sperrt.
- `VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS` ist standardmäßig leer, dann darf niemand anlegen oder fragen. Pilot: `allowlist` + `1`.
- Die Policy gilt **zusätzlich** zum Flag und zu den bestehenden Gates (`production_actor_allowed`, Staging-Allowlist).
- Lesen, Export, Papierkorb und Löschen eigener Gespräche bleiben auch ohne Pilot-Zugang erlaubt (Datenschutzrechte).
- Die Nachbesserung hat eine Lücke geschlossen: Die Nachrichten-Route prüfte die Pilot-Policy vorher nicht.

### 11.6 Kontextbezogene Suche (Flag `VORNEQ_AI_CONTEXT_RETRIEVAL_ENABLED`, Standard **aus**)

- Sie ist deterministisch und braucht keinen Provider-Aufruf. Sie greift nur, wenn die Frage ein verweisendes Pronomen enthält (fa/de/en).
- Dann werden Stichwörter der **vorherigen Benutzerfrage** (nie der Antwort) ergänzt. Personenbezogene Daten oder Injection-Text in der vorherigen Frage verhindern die Anreicherung.
- Das Modell erhält weiter die echte Frage; nur der Suchtext ändert sich.
- Messung am 2026-11-17 auf dem Laptop, echte Wikipedia-Suche, exakter Modulcode (SHA-256 der Messdatei `d25c9a13…`), 34 Folgefragen, 0 Fehler. „Treffer“ heißt: Der Artikel zum Subjekt ist unter den Top 3.

| Sprache | Gruppe | n | Treffer alt | Treffer neu | Regressionen |
|---|---|---|---|---|---|
| fa | Subjekt in voriger Frage | 16 | 0 | 14 | 0 |
| fa | Subjekt nur in der Antwort | 2 | 0 | 0 | 0 |
| en | Subjekt in voriger Frage | 7 | 0 | 5 | 0 |
| en | Subjekt nur in der Antwort | 1 | 0 | 0 | 0 |
| de | Subjekt in voriger Frage | 7 | 0 | 6 | 0 |
| de | Subjekt nur in der Antwort | 1 | 0 | 0 | 0 |

- Keine der 40 gemessenen eigenständigen persischen Fragen aus #641 löst die Anreicherung aus (Test).
- Grenze: Liegt das Subjekt nur in der Antwort, hilft die Methode nicht. Das ist gewollt, denn Antworten sind keine Belege.
- Einschalten entscheidet der Eigentümer.

### 11.7 Migration `0003`

- 14 DDL-Anweisungen: 2× `CREATE TABLE`, Indizes, 4 Check-/Unique-Constraints, 2 Fremdschlüssel. Sie hängt von `0002` und `AUTH_USER_MODEL` ab und berührt den Ledger-Alias nicht.
- Die Tabellen sind neu. `ADD CONSTRAINT … FOREIGN KEY … REFERENCES auth_user` nimmt kurz einen `SHARE ROW EXCLUSIVE`-Lock auf `auth_user`; bei leeren neuen Tabellen ist die Prüfung sofort fertig.
- Hinweis P2: `ai_msg_conv_seq_idx` doppelt den Index des Unique-Constraints `ai_msg_conv_seq_unique`. Das ist harmlos, kostet aber Schreibaufwand und kann in einer Folge-Migration entfallen. Weil es Migration und Modell betrifft, ist es hier bewusst **nicht** geändert.
- Der C02-Runner unterstützt nur `0001`/`0002`; die Erweiterung braucht einen eigenen PR. Es gab **keine** Production- oder Staging-Migration.
