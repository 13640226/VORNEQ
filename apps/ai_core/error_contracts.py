"""V7-02: stabile, maschinenlesbare Fehlergründe (COR-09).

Bestehende Felder (``error`` und HTTP-Status) bleiben unverändert; ergänzt wird
nur ein festes ``reason``-Enum. Niemals Ausnahmetext, Prompt, Modellantwort,
Schlüssel oder interne Pfade ausgeben.
"""
from __future__ import annotations

INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
CONTEXT_LIMIT_EXCEEDED = "CONTEXT_LIMIT_EXCEEDED"
OUTPUT_LIMIT_INVALID = "OUTPUT_LIMIT_INVALID"
MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
MODEL_DISABLED = "MODEL_DISABLED"
INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
BUDGET_REFUSED = "BUDGET_REFUSED"
LEDGER_UNAVAILABLE = "LEDGER_UNAVAILABLE"
EMERGENCY_STOP_ACTIVE = "EMERGENCY_STOP_ACTIVE"

REASONS = frozenset({
    INPUT_TOO_LARGE, CONTEXT_LIMIT_EXCEEDED, OUTPUT_LIMIT_INVALID, MODEL_UNAVAILABLE,
    MODEL_DISABLED, INVALID_CONFIGURATION, BUDGET_REFUSED, LEDGER_UNAVAILABLE,
    EMERGENCY_STOP_ACTIVE,
})


def budget_reason(exc):
    """Fester Grund für eine Ledger-/Budget-Ablehnung; unbekannt -> BUDGET_REFUSED."""
    from apps.ai_ledger.service import EmergencyStop, LedgerUnavailable
    if isinstance(exc, EmergencyStop):
        return EMERGENCY_STOP_ACTIVE
    if isinstance(exc, LedgerUnavailable):
        return LEDGER_UNAVAILABLE
    return BUDGET_REFUSED


def registry_reason(exc):
    """Grund für Registry-/Auflösungsfehler über deren festen ``code``."""
    code = getattr(exc, "code", "")
    mapping = {
        "model_unavailable": MODEL_UNAVAILABLE, "model_disabled": MODEL_DISABLED,
        "provider_unavailable": MODEL_UNAVAILABLE, "provider_disabled": MODEL_DISABLED,
        "invalid_configuration": INVALID_CONFIGURATION, "invalid_environment": INVALID_CONFIGURATION,
        "budget_refused": BUDGET_REFUSED, "emergency_stop_active": EMERGENCY_STOP_ACTIVE,
    }
    return mapping.get(str(code).lower(), INVALID_CONFIGURATION)


def input_too_large(error, *, limit_chars=None, limit_bytes=None):
    body = {"error": error, "reason": INPUT_TOO_LARGE}
    if type(limit_chars) is int and limit_chars > 0:
        body["limit_chars"] = limit_chars
    if type(limit_bytes) is int and limit_bytes > 0:
        body["limit_bytes"] = limit_bytes
    return body
