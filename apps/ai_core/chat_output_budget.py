"""Optional, model-bound Stage 2 budget. Production is never enabled here."""
from dataclasses import dataclass
import os
from django.conf import settings


@dataclass(frozen=True)
class OutputBudget:
    model: str
    output_tokens: int
    context_tokens: int

    @property
    def answer_chars(self):
        # V7-02: Validierungsgrenze aus dem Token-Budget (kein fester 6400-Deckel).
        # Die harte Grenze bleibt max_output_tokens beim Provider; ein Token kann
        # mehrere Zeichen tragen, daher großzügig (kein Tokenizer, keine Kürzung).
        from apps.ai_core.model_limits import ANSWER_CHARS_PER_TOKEN
        return ANSWER_CHARS_PER_TOKEN * self.output_tokens

    @property
    def section_chars(self):
        """Obergrenze je Antwortabschnitt (bis zu 6 Abschnitte); mindestens die bisherigen 1400."""
        return max(1400, self.answer_chars // 6)

    def fits_context(self, input_bytes, overhead):
        return input_bytes + overhead + self.output_tokens <= self.context_tokens


def _bounded(raw, minimum, maximum):
    if (not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal()
            or len(raw) > 7):
        return None
    value = int(raw)
    return value if minimum <= value <= maximum else None


def configured_output_budget():
    from apps.ai_core.response_engine_v3 import stage2_enabled
    if not stage2_enabled(settings):
        return None
    if settings.VORNEQ_ENV not in ("development", "staging"):
        return None
    model = getattr(settings, "VORNEQ_AI_CHAT_BUDGET_MODEL", "")
    if not isinstance(model, str) or not model or len(model) > 100:
        return None
    if model != os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""):
        return None
    # V7-02: Oberhalb des bisherigen Pilotdeckels (8192) nur, wenn die zentrale
    # Modell-Policy vollständig konfiguriert ist (Registry-/Kontextgrenzen geprüft).
    from apps.ai_core.model_limits import HARD_MAX_OUTPUT_TOKENS, chat_limits
    limits = chat_limits()
    upper = 8192
    if limits.extended and limits.model_id == model:
        upper = min(HARD_MAX_OUTPUT_TOKENS, limits.max_output_tokens)
    cap = _bounded(getattr(settings, "VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET", ""), 1536, max(upper, 8192))
    context = _bounded(getattr(settings, "VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS", ""), 8192, 1000000)
    if cap is None or context is None or context < cap + 4096:
        return None
    if settings.VORNEQ_ENV == "staging":
        from apps.ai_core.request_recovery import enabled as recovery_enabled
        from apps.ai_ledger.service import ledger_enabled
        if (not ledger_enabled() or not recovery_enabled()
                or model != getattr(settings, "VORNEQ_AI_STAGING_APPROVED_MODEL", "")):
            return None
    return OutputBudget(model, cap, context)
