# Kostenpflichtiger Staging-Bild-Worker (Code, standardmäßig AUS)

Stand: 2026-11-21. Dieser PR enthält **nur Code und Tests**. Es wurde kein Render-Dienst
angelegt, keine Variable gesetzt, kein Ledger-Konto geändert und kein OpenAI-Aufruf
ausgeführt.

## Befund vorher

- `worker_enabled()` erlaubte ausschließlich den Mock-Provider.
- `reserve_with_config()` akzeptierte nur die Web-Dienst-IDs aus `EXPECTED_SERVICES`.
  Ein separater Worker-Dienst konnte daher nie reservieren – bezahlte Bild-Jobs aus dem
  Image Studio konnten nur auf dem Web-Dienst (z. B. per One-off-Job) verarbeitet werden.

## Änderung

| Ebene | Regel |
|---|---|
| `policy.worker_enabled()` | unverändert: nur Mock, eigene Worker-ID, SHA, Owner-Grant, Allowlist |
| `policy.paid_worker_enabled()` | neu: `VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED=true`, eigener Grant `VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH` (`OWNER-AUTH-AI-IMAGE-PAID-WORKER-STAGING-…`), eigene Worker-ID ≠ Web/Production, laufende Identität = Worker-ID, SHA, Allowlist und alle bezahlten Kontrollen (`_paid_controls_ready`) |
| Gegenseitiger Ausschluss | Mock-Worker verlangt `provider=mock` ohne Paid-Flag, Paid-Worker verlangt `provider=openai` mit Paid-Flag |
| `service.process_next_image_job()` | Paid-Worker beansprucht nur `provider=openai`-Jobs; Gate wird vor der Reservierung und unmittelbar vor dem Provider-Aufruf erneut geprüft; kein Retry |
| `ai_ledger.reserve_with_config()` | einzige Ausnahme vom Web-Dienst-Zwang: Umgebung `staging`, Schalter an, Worker-ID konfiguriert und gleich der laufenden Identität, Konto = `VORNEQ_AI_IMAGE_LEDGER_ID` ≠ Chat-ID, Konto `allowed_environments == "staging"` |

Das Chat-Konto ist für die Worker-Identität nie erreichbar, auch wenn es staging-only wäre.

## Tests

- `apps/ai_core/tests/test_image_paid_worker_identity_v1.py` (Policy, Queue, Gate-Neuprüfung)
- `apps/ai_ledger/tests/test_ledger_image_worker_client.py` (PostgreSQL, echte Sperren)
- Mutationsprüfung: 9 von 10 Mutationen erkannt; die verbleibende ist äquivalent
  (bei aktivem Mock-Worker greift der Mock-Filter ohnehin zuerst).

## Aktivierung (jeweils eigene Freigabe des Owners)

1. Merge dieses PR (`OWNER-AUTH-MERGE …`) und Deploy über den Deploy-Workflow.
2. Render Background Worker nur für Staging anlegen (kostenpflichtiger Dienst),
   Start-Befehl `python manage.py run_image_jobs --loop --poll-seconds 5`,
   Auto-Deploy AUS, dieselbe Commit-SHA.
3. Variablen **nur am Worker**: `VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=<neue srv-ID>`,
   `VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED=true`, `VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH`,
   `VORNEQ_AI_IMAGE_AUTHORIZED_SHA`, Allowlist, Bild-Key, Ledger- und R2-Variablen.
   Am Web-Dienst: `VORNEQ_AI_IMAGE_WORKER_SERVICE_ID` setzen, damit der Paid-Smoke-
   Preflight einen aktiven Worker erkennt (`no_worker_identity`).
4. `ai_ledger_image_control resume` nur nach Freigabe; `stop` bei jeder Unklarheit.
5. Erst Mock-Lauf, dann ein einzelner bezahlter Job eines Allowlist-Nutzers.

## Härtung (Defense in Depth, Folge-PR)

- `reserve_with_config()` ruft nur zwei Stellen auf: `ledger.reserve()` (Chat, immer
  Chat-Konto) und den Bild-Worker. Die Worker-Ausnahme prüft jetzt **im Ledger selbst**,
  unabhängig von der Image-Policy: staging-Runtime, `DEBUG=False`, globaler Stop aus,
  Bild-/Paid-Flags, Provider `openai`, Paid-Worker-Schalter und -Grant, Worker-ID =
  laufende Identität, `VORNEQ_AI_IMAGE_AUTHORIZED_SHA` = laufender Commit = SHA der
  Reservierung, Bild-Konto ≠ Chat-Konto.
- Kein Import der Image-Policy im Ledger (kein Zyklus); das Grant-Format ist bewusst
  dupliziert.
- TOCTOU: Render-Variablen ändern sich nur mit Neustart; die einzige Laufzeit-Sperre ist
  `emergency_stop` des Kontos. Neu: `reservation_still_open()` direkt vor dem
  Provider-Aufruf – ist das Konto inzwischen gestoppt oder die Reservierung nicht mehr
  offen, wird nicht gesendet und freigegeben (`ledger_stopped`).
