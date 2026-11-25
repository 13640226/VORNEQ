"""V4-01 — Aufrufgrenze: ein kostenpflichtiger Provider-Aufruf ist nur innerhalb
einer gültigen Ledger-Reservierung möglich.

Die Konstruktionsgrenze (``apps.ai_core.paid_provider``) allein reicht nicht:
jeder bezahlte Adapter (Text: ``OpenAIResponsesProvider``, Bild:
``OpenAIImageProvider``) ruft ``require_authorized_paid_call`` auf, **bevor**
ein SDK-Client entsteht. Die Freigabe setzen ausschließlich die Ledger-
Aufrufer (``BudgetedProvider`` und der Image-Worker) direkt nach einer
erfolgreichen ``reserve``-Transaktion – über einen ``ContextVar``, also
pro Thread/Task isoliert und nach dem Aufruf garantiert zurückgesetzt.

Damit ist unabhängig von Umgebung, Render-Variablen oder Umgebungserkennung
kein bezahlter Aufruf ohne Reservierung möglich – auch nicht lokal mit
vorhandenem API-Schlüssel.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager

KINDS = frozenset({"text", "image"})
_ACTIVE: contextvars.ContextVar = contextvars.ContextVar("vorneq_ledger_authorized_call", default=None)


class UnauthorizedPaidCall(RuntimeError):
    """Bezahlter Provider-Aufruf ohne gültige Ledger-Reservierung."""


def _valid(reservation) -> bool:
    # Freigaben setzen nur Ledger-Aufrufer mit dem Ergebnis von reserve*()
    # (AST-Test: authorized_paid_call nur in BudgetedProvider und Image-Worker).
    return reservation is not None


@contextmanager
def authorized_paid_call(reservation, *, kind: str):
    if kind not in KINDS or not _valid(reservation):
        raise UnauthorizedPaidCall("invalid ledger reservation for paid call")
    token = _ACTIVE.set((getattr(reservation, "id", None), kind))
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def require_authorized_paid_call(kind: str):
    """Gibt die Reservierungs-ID zurück oder bricht vor jedem SDK-Kontakt ab."""
    active = _ACTIVE.get()
    if active is None or active[1] != kind:
        raise UnauthorizedPaidCall("paid provider call requires a ledger reservation")
    return active[0]
