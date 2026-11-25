"""Wrap a model provider with the shared prepaid ledger: reserve -> call -> settle.

The reservation happens immediately before the (single, max_retries=0)
provider call; retrieval-only paths (insufficient evidence) cost nothing.
"""
import itertools

from apps.ai_core.providers.exceptions import GatewayError
from apps.ai_core.providers.openai_responses import build_request_payload, build_request_payload_v2, build_knowledge_payload
from apps.ai_ledger import service as ledger
from apps.ai_ledger.call_authorization import authorized_paid_call


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
            with authorized_paid_call(reservation, kind="text"):
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
            with authorized_paid_call(reservation, kind="text"):
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


    def stream_knowledge(self, *, question, language, prior_turns=()):
        """V7-03: reserve -> EIN gestreamter Aufruf -> settle (Generator).

        * Reservierung (Worst Case: Eingabe-Bytes + ``max_output_tokens``) VOR dem Aufruf.
        * Die Aufruffreigabe (``authorized_paid_call``) gilt nur für den ersten Schritt
          des inneren Generators, in dem der SDK-Client entsteht und die Anfrage
          gesendet wird – nicht während der Generator pausiert.
        * Abrechnung genau einmal im ``finally``: mit Usage -> FINALIZED; ohne Usage
          (Stop, Verbindungsabbruch, Timeout) -> UNCERTAIN (volle Reservierung, nie 0);
          nachweislich nicht gesendet -> ``release``.
        """
        payload = build_knowledge_payload(question, language, prior_turns=prior_turns)
        instructions = self.inner.stream_knowledge_instructions(language)
        input_bytes = len(instructions.encode("utf-8")) + len(payload.encode("utf-8"))
        self.inner.check_context_budget(input_bytes)
        reservation = ledger.reserve(actor_id=self.actor_id, model=self.inner.model,
                                     input_bytes=input_bytes, max_output_tokens=self.inner.max_output_tokens)
        self.last_reservation = reservation
        self.inner.last_usage = None
        outcome = "interrupted"
        inner = None
        try:
            inner = self.inner.stream_knowledge(question=question, language=language, prior_turns=prior_turns)
            with authorized_paid_call(reservation, kind="text"):
                first = next(inner)
            for item in itertools.chain((first,), inner):
                if item[0] == "final":
                    outcome = "completed" if item[1].status == "completed" else item[1].status
                yield item
        except GatewayError as exc:
            outcome = type(exc).__name__
            raise
        except GeneratorExit:
            if outcome == "interrupted":
                outcome = "stream_closed"
            raise
        except StopIteration:
            outcome = "stream_ended"
        except BaseException:
            outcome = "unexpected_error"
            raise
        finally:
            if inner is not None:
                inner.close()
            if getattr(self.inner, "request_sent", True) is False:
                ledger.release(reservation, reason="not_sent")
            else:
                ledger.settle(reservation, usage=self.inner.last_usage, outcome=outcome[:40])
