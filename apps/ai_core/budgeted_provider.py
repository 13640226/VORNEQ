"""Wrap a model provider with the shared prepaid ledger: reserve -> call -> settle.

The reservation happens immediately before the (single, max_retries=0)
provider call; retrieval-only paths (insufficient evidence) cost nothing.
"""
from apps.ai_core.providers.exceptions import GatewayError
from apps.ai_core.providers.openai_responses import build_request_payload
from apps.ai_ledger import service as ledger


class BudgetedProvider:
    def __init__(self, inner, *, actor_id: int):
        self.inner = inner
        self.actor_id = actor_id
        self.last_reservation = None

    def generate(self, *, question, language, sources):
        payload = build_request_payload(question, language, sources,
                                        compact_sources=getattr(self.inner, "compact_sources", False))
        input_bytes = len(getattr(self.inner, "instructions", "").encode("utf-8")) + len(payload.encode("utf-8"))
        reservation = ledger.reserve(actor_id=self.actor_id, model=self.inner.model,
                                     input_bytes=input_bytes,
                                     max_output_tokens=self.inner.max_output_tokens)
        self.last_reservation = reservation
        self.inner.last_usage = None
        try:
            output = self.inner.generate(question=question, language=language, sources=sources)
        except GatewayError as exc:
            ledger.settle(reservation, usage=getattr(self.inner, "last_usage", None),
                          outcome=type(exc).__name__)
            raise
        except BaseException:
            ledger.settle(reservation, usage=None, outcome="unexpected_error")
            raise
        ledger.settle(reservation, usage=getattr(self.inner, "last_usage", None), outcome="completed")
        return output
