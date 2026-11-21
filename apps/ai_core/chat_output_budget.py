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
        # Independent text safety bound, NOT an exact tokenizer.
        return min(6400, 2 * self.output_tokens)

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
    cap = _bounded(getattr(settings, "VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET", ""), 1536, 8192)
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
