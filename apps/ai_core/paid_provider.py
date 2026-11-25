"""V4-01 — einzige Konstruktionsstelle für kostenpflichtige Text-Provider.

Architekturregel: NO PAID AI CALL WITHOUT VALID LEDGER AUTHORIZATION.

* Gehostete Laufzeiten (VORNEQ_ENV ``staging`` oder ``production``): der
  Provider wird ausschließlich in ``BudgetedProvider`` (reserve -> call ->
  settle gegen das gemeinsame Prepaid-Ledger) ausgeliefert. Ist das Ledger
  nicht konfiguriert, wird **vor** jeder Provider-Konstruktion, Quota-Buchung
  oder Retrieval-Arbeit mit ``LedgerUnavailable`` abgebrochen.
* ``VORNEQ_AI_STAGING_UNMETERED`` und ``VORNEQ_GLOBAL_AI_UNLIMITED_STAGING``
  ändern nur anwendungsseitige Zähler, nie die Ledger-Pflicht. Das Ledger
  wendet in Staging seine eigene Tagesobergrenze unabhängig davon an
  (``apps.ai_ledger.service.reserve``).
* Lokale Entwicklung (``development`` und **kein** gehosteter Runtime,
  d. h. weder ``RENDER`` noch ``RENDER_SERVICE_ID`` gesetzt): der Provider wird
  ohne Ledger konstruiert, aber **nie bezahlt aufgerufen** – auch nicht mit
  vorhandenem API-Schlüssel. Die Aufrufgrenze
  (``apps.ai_ledger.call_authorization``) verlangt vor jedem SDK-Client eine
  aktive Ledger-Reservierung, die nur ``BudgetedProvider`` setzt. Lokal sind
  damit nur Test-Doubles/Mocks möglich; das gemeinsame Ledger wird lokal nie
  berührt.
* Jede andere Kombination wird abgelehnt.

Zwei unabhängige Grenzen: Konstruktion (hier) und Aufruf (Adapter). Fällt die
Umgebungserkennung falsch aus oder fehlen Render-Variablen, verhindert die
Aufrufgrenze den bezahlten Aufruf trotzdem.

Der Architekturtest ``apps/ai_core/tests/test_v4_paid_provider_boundary.py``
erzwingt per AST, dass ``OpenAIResponsesProvider`` nur hier konstruiert wird.
"""
from __future__ import annotations

from django.conf import settings

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.staging_policy import hosted_runtime
from apps.ai_ledger.service import EmergencyStop, LedgerUnavailable, ledger_enabled

HOSTED_ENVIRONMENTS = ("staging", "production")


def require_paid_text_ledger(*, ledger_check=None) -> bool:
    """Prüft vor jeder Quota-/Retrieval-/Provider-Arbeit, ob ein kostenpflichtiger
    Aufruf überhaupt zulässig ist. Rückgabe: ``True`` = Ledger-Pflicht (gehostet),
    ``False`` = lokale Entwicklung ohne Ledger. Sonst Ausnahme (fail-closed)."""
    if getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False):
        raise EmergencyStop("emergency stop (environment)")
    environment = getattr(settings, "VORNEQ_ENV", "")
    if environment in HOSTED_ENVIRONMENTS:
        # ``ledger_check`` is only a fast pre-check (lets callers keep their
        # module-level reference). It can never grant a paid call: hosted
        # providers are always wrapped in BudgetedProvider, whose
        # ledger.reserve() re-validates the ledger independently.
        if not (ledger_check or ledger_enabled)():
            raise LedgerUnavailable(f"{environment} requires the shared prepaid ledger")
        return True
    if environment == "development" and not hosted_runtime():
        return False
    raise LedgerUnavailable("paid provider not allowed in this runtime")


def paid_text_provider(*, actor_id: int, provider_class=OpenAIResponsesProvider, ledger_check=None,
                       **provider_kwargs):
    """Liefert den einzigen zulässigen kostenpflichtigen Text-Provider.

    Gehostet immer ``BudgetedProvider``; lokal in der Entwicklung der innere
    Provider. ``provider_kwargs`` werden unverändert an den Provider übergeben
    (Modell, Timeout, Ausgabegrenzen, Instruktionen) – Antwortinhalt und Prompt
    bleiben damit unverändert.

    ``provider_class`` erlaubt Aufrufern, ihre (in Tests gepatchte) Referenz
    durchzureichen. Die Ledger-Pflicht hängt **nicht** vom Aufrufer ab: auf
    gehosteten Laufzeiten wird jede Klasse in ``BudgetedProvider`` verpackt,
    dessen ``ledger.reserve`` unabhängig fail-closed prüft.
    """
    ledger_bound = require_paid_text_ledger(ledger_check=ledger_check)
    if type(actor_id) is not int or actor_id <= 0:
        raise LedgerUnavailable("invalid ledger actor")
    provider = provider_class(**provider_kwargs)
    if ledger_bound or getattr(settings, "VORNEQ_ENV", "") in HOSTED_ENVIRONMENTS:
        return BudgetedProvider(provider, actor_id=actor_id)
    return provider
