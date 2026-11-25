"""Global-chat input budget (V7-02: from the central model limit policy).

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
# Historische Pilot-Obergrenze; V7-02: größere Budgets nur mit Kontextfenster
# über ``apps.ai_core.model_limits`` (zentrale Policy).
MAX_PILOT_BUDGET = 8192


def global_budget():
    """Invalid/absent configuration never widens access or limits.

    V7-02: delegiert an die zentrale, modellabhängige Policy
    (``model_limits.chat_limits``); ``LEGACY`` bleibt der Fallback.
    """
    from apps.ai_core.model_limits import chat_limits
    limits = chat_limits()
    if not limits.widened_input:
        return LEGACY
    return InputBudget(limits.max_message_characters, limits.max_input_tokens, limits.max_request_bytes)
