"""Wrap a model provider with the shared prepaid ledger: reserve -> call -> settle.

The reservation happens immediately before the (single, max_retries=0)
provider call; retrieval-only paths (insufficient evidence) cost nothing.
"""
from apps.ai_core.providers.exceptions import GatewayError
from apps.ai_core.providers.openai_responses import build_request_payload, build_request_payload_v2, build_knowledge_payload
from apps.ai_ledger import service as ledger


class BudgetedProvider:
    def __init__(self, inner, *, actor_id: int):
        self.inner = inner
        self.actor_id = actor_id
        self.last_reservation = None

    def generate(self, *, question, language, sources, prior_turns=(), mode="grounded"):
        # The reservation covers the exact payload, including conversation context.
        if mode not in ("grounded", "sectioned"):
            raise ValueError("unsupported response mode")
        builder = build_request_payload_v2 if mode == "sectioned" else build_request_payload
        payload = builder(question, language, sources,
                          compact_sources=(getattr(self.inner, "compact_sources", False) is True),
                          prior_turns=prior_turns)
        # Ledger reserves full effective instructions, including language/V3 guidance.
        # Probe the declared provider class, not arbitrary instance attributes:
        # MagicMock dynamically invents callable attributes (including a
        # nonexistent instructions_for), which would undercount reserved bytes.
        effective = getattr(type(self.inner), "instructions_for", None)
        instructions = ((effective(self.inner, question, language, mode=mode)
                         if mode == "sectioned" else effective(self.inner, question, language))
                        if callable(effective) else getattr(self.inner, "instructions", ""))
        input_bytes = len(instructions.encode("utf-8")) + len(payload.encode("utf-8"))
        check_context = getattr(type(self.inner), "check_context_budget", None)
        if callable(check_context):
            check_context(self.inner, input_bytes)
        reservation = ledger.reserve(actor_id=self.actor_id, model=self.inner.model,
                                     input_bytes=input_bytes,
                                     max_output_tokens=self.inner.max_output_tokens)
        self.last_reservation = reservation
        self.inner.last_usage = None
        try:
            extra = {"prior_turns": prior_turns} if prior_turns else {}
            if mode == "sectioned":
                extra["mode"] = mode
            output = self.inner.generate(question=question, language=language, sources=sources, **extra)
        except GatewayError as exc:
            ledger.settle(reservation, usage=getattr(self.inner, "last_usage", None),
                          outcome=type(exc).__name__)
            raise
        except BaseException:
            ledger.settle(reservation, usage=None, outcome="unexpected_error")
            raise
        ledger.settle(reservation, usage=getattr(self.inner, "last_usage", None), outcome="completed")
        return output


    def generate_knowledge(self, *, question, language, prior_turns=()):
        payload = build_knowledge_payload(question, language, prior_turns=prior_turns)
        instructions = self.inner.knowledge_instructions(language)
        input_bytes = len(instructions.encode("utf-8")) + len(payload.encode("utf-8"))
        self.inner.check_context_budget(input_bytes)
        reservation = ledger.reserve(actor_id=self.actor_id, model=self.inner.model,
                                     input_bytes=input_bytes,
                                     max_output_tokens=self.inner.max_output_tokens)
        self.last_reservation = reservation
        self.inner.last_usage = None
        try:
            result = self.inner.generate_knowledge(
                question=question, language=language, prior_turns=prior_turns)
        except GatewayError as exc:
            ledger.settle(reservation, usage=self.inner.last_usage,
                          outcome=type(exc).__name__)
            raise
        except BaseException:
            ledger.settle(reservation, usage=None, outcome="unexpected_error")
            raise
        ledger.settle(reservation, usage=self.inner.last_usage, outcome="completed")
        return result
