# Global AI V2 — Implementierungsbericht

**Task:** P0_VORNEQ_GLOBAL_AI_V2_MULTISOURCE_GROUNDED_ENGINE_20261114
**Basis:** `b3b699840ae3e670ae4445a06e3fefcd52b84d64` (main, per `git ls-remote` am 2026-11-14 verifiziert; #605 und #606 enthalten)
**Branch:** `feat/global-ai-v2-multisource-grounding`

## Audit der Ausgangslage (V1)

- #605 ist byte-identisch mit dem geprüften V1-Patch (Diff-SHA-256 `49ea2a67…`).
- #606 ergänzt `VORNEQ_GLOBAL_AI_UNLIMITED_STAGING`.

Grenzen von V1:

1. Es gibt nur einen fest verdrahteten Provider und keine Registry.
2. Es gibt keine Relevanzbewertung. Irrelevante Suchtreffer gehen direkt an das Modell.
3. Ist eine Zahl im Text erfunden, das Zitat aber wörtlich korrekt, wird die Antwort trotzdem akzeptiert.
4. Persisch wird erkannt, sobald irgendein persischer Buchstabe vorkommt; eine englische Frage mit einem persischen Wort wurde deshalb als `fa` erkannt.
5. In `web_retrieval.py` und in V1-Tests standen Bidi- und Steuerzeichen literal im Quelltext. Bandit meldet das als B613 (Trojan Source).

## Änderungen

| Datei | Art | Inhalt |
|---|---|---|
| `apps/ai_core/retrieval_registry.py` | neu | `PROVIDERS`, `MultiSourceRetriever`, `configured_provider_names`, `default_retriever` |
| `apps/ai_core/engine/evidence_ranking.py` | neu | Bewertung, Ranking, Dedupe über Provider, Zahlenprüfung |
| `apps/ai_core/engine/global_grounded.py` | geändert | Ranking vor Kontextaufbau, Zahlenprüfung, `evidence_assessment`, Instruktion zu Widersprüchen und Titeln |
| `apps/ai_core/global_router.py` | geändert | Spracherkennung für gemischte Schrift, erweiterte Muster für private Daten, Escape-Sequenzen statt Literalzeichen |
| `apps/ai_core/web_retrieval.py` | geändert | `source_type` und `licence` am Wikipedia-Provider, B613 behoben |
| `apps/ai_core/views_global.py` | geändert | Retriever kommt jetzt aus der Registry |
| `apps/ai_core/tests/test_global_ai_v2.py` | neu | 21 Tests |
| `apps/ai_core/tests/test_global_ai_api.py`, `test_global_ai_router_retrieval.py` | geändert | nur Escape-Sequenzen statt Literal-Steuerzeichen (B613) |
| `docs/ai/GLOBAL_AI_V2_CONTRACT.md`, dieser Bericht | neu | Dokumentation |

Rückwärtskompatibilität: Alle V1-Tests laufen unverändert. Neue Antwortfelder sind additiv. Endpunkt, Flags, Kontingente, CSRF, Authentifizierung und Staging-Pins bleiben gleich. Es gibt keine Migration und keine Frontend-Änderung.

## Testnachweise (echte Ausführung)

Umgebung: Python 3.13.18, Django 5.2.17, frische venvs aus `requirements.txt` (SDK-Läufe zusätzlich mit `requirements-ai-phase-c-dev.txt`, openai 3.49.0), PostgreSQL 16.15 in der CI-Topologie, Node 22.23.4 mit jsdom 24. In allen Global-AI-Tests waren Sockets und DNS blockiert, und ein Konstruktor-Guard verhinderte jedes Erzeugen eines OpenAI-Clients.

| Befehl | Ergebnis |
|---|---|
| `manage.py test apps.ai_core.tests.test_global_ai_v2 …_router_retrieval …_api …_unlimited_staging` | 72/72 OK |
| `manage.py test --parallel 1` (SQLite) | 1362 OK, 12 übersprungen (keiner neu) |
| `manage.py test --parallel 1` (PostgreSQL, `VORNEQ_QUARANTINE_CI_DB_TEST_MODE`) | 1362 OK, 8 übersprungen |
| `manage.py test apps.ai_core` mit SDK, SQLite / PostgreSQL | 198 OK (3 übersprungen) / 198 OK |
| `node chat_harness.test.js` (Frontend unverändert) | 8/8 |
| `manage.py check`, `makemigrations --check`, `py_compile` | OK, keine Migration |
| Mutationsprobe: Zahlenprüfung deaktiviert | `test_fabricated_number_is_rejected` schlägt fehl (erwartet) |
| Mutationsprobe: Ranking umgangen | `test_irrelevant_results_give_insufficient_evidence_without_model` schlägt fehl (erwartet) |
| `bandit -ll` (ai_core) | B613 behoben; einzig verbleibender Fund ist B104 in einem Test, der `0.0.0.0` als *verbotene* Adresse prüft (False Positive) |

## Grenzen und offene Punkte

- Kein zweiter realer Provider. Lizenz, Nutzungsbedingungen und Erreichbarkeit ließen sich in dieser Sitzung nicht verifizieren; die Architektur ist mit synthetischen Providern getestet.
- Keine Live-Abfragen an Wikimedia oder OpenAI (nicht autorisiert). Die Qualität der Treffer für echte Fragen ist daher NOT_VERIFIED.
- Die Zahlenprüfung erfasst keine ausgeschriebenen Zahlwörter. Eine semantische Faktenprüfung gibt es nicht; `verified` bleibt `false`.
- Die Präfix-Morphologie beim Ranking ist heuristisch. Sie kann sowohl Fehltreffer als auch verpasste Treffer erzeugen.
- Unbegrenzte Staging-Modi bergen ein Kosten- und Missbrauchsrisiko. Die harte Grenze bleibt allein das Spend-Limit beim Provider.
- Diese Änderung autorisiert weder Merge noch Deploy.
