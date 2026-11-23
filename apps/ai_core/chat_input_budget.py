"""Opt-in bounded global-chat input pilot; production retains legacy limits.

UTF-8 bytes are a conservative token-cost proxy, not exact model tokenization.
The existing ledger still reserves against the actual serialized provider
payload and max_output_tokens. No provider, citation or output gate changes.
"""
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class InputBudget:
    question_chars: int = 200
    question_utf8_bytes: int = 0
    body_bytes: int = 2048

    def accepts(self, question):
        if len(question) > self.question_chars:
            return False
        if not self.question_utf8_bytes:
            return True
        try:
            return len(question.encode("utf-8")) <= self.question_utf8_bytes
        except UnicodeEncodeError:
            return False


LEGACY = InputBudget()
MAX_PILOT_BUDGET = 8192


def global_budget():
    """Invalid/absent configuration never widens access or limits."""
    env = getattr(settings, "VORNEQ_ENV", None)
    if env not in ("development", "staging", "production"):
        return LEGACY
    if env == "production" and getattr(settings, "VORNEQ_AI_CHAT_PRODUCTION_EXTENDED_INPUT", False) is not True:
        return LEGACY
    raw = getattr(settings, "VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET", "")
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal() or len(raw) > 4:
        return LEGACY
    value = int(raw)
    if not 512 <= value <= MAX_PILOT_BUDGET:
        return LEGACY
    if env in ("staging", "production"):
        # The old flat per-request reservation is insufficient for a larger
        # payload. The hosted pilot must use actual-payload ledger estimation
        # and durable request recovery. These checks are configuration-only.
        from apps.ai_ledger.service import ledger_enabled
        from apps.ai_core.request_recovery import enabled as recovery_enabled
        if not ledger_enabled() or not recovery_enabled():
            return LEGACY
    # JSON escaping can consume up to six bytes per ASCII input byte.
    return InputBudget(value, value, 6 * value + 512)
