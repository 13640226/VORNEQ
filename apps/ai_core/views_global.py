"""Global AI V1 endpoint. Default OFF; development or authorized staging only.

All Phase B controls are kept (environment, hosted-runtime guard, staging trial
identity/SHA/service pins, authentication, staging actor allowlist, CSRF,
strict JSON). Global AI adds its own feature flag and its own quota.
"""
import json
import os
import logging

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from apps.ai_core.engine.budget import BudgetExceeded
from apps.ai_core.engine.citation import (
    EvidenceRejected, GeneratedAnswerRejected, CitationIdentityRejected,
    CitationDigestRejected, CitationQuoteRejected,
)
from apps.ai_core.engine.global_grounded import GLOBAL_INSTRUCTIONS, HISTORY_INSTRUCTIONS, GlobalUnsupported, UnsupportedNumericClaim, ask_global
from apps.ai_core.engine.sectioned import UnsupportedSectionNumber
from apps.ai_core.engine.grounded import PhaseBDisabled
from apps.ai_core.gateway import InputError, validate
from apps.ai_core.chat_input_budget import global_budget
from apps.ai_core.global_budget import reserve_global_request
from apps.ai_core.global_router import UNSUPPORTED, route_question
from apps.ai_core.providers.exceptions import GatewayError, ProviderInvalidResponse, ProviderTimeout
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core import response_engine_v3
from apps.ai_core.staging_budget import reserve_staging_request
from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.production_policy import production_actor_allowed, production_enabled
from apps.ai_core.staging_policy import actor_allowed, hosted_runtime, trial_enabled
from apps.ai_ledger.service import ledger_enabled
from apps.ai_core.retrieval_registry import default_retriever
from apps.ai_core.web_retrieval import RetrievalError, RetrievalTimeout
from apps.ai_core import request_recovery

_log = logging.getLogger(__name__)


_SAFE_REJECTION_CODES = {
    GeneratedAnswerRejected: "invalid_generated_output",
    CitationIdentityRejected: "citation_identity_rejected",
    CitationDigestRejected: "citation_digest_mismatch",
    CitationQuoteRejected: "citation_quote_mismatch",
    UnsupportedNumericClaim: "unsupported_numeric_claim",
    UnsupportedSectionNumber: "section_numeric_claim",
}


def _evidence_rejection_code(error):
    """Return only a fixed operational enum; never inspect/log exception details."""
    return _SAFE_REJECTION_CODES.get(type(error), "evidence_rejected")


def _respond(data, *, status=200, request=None, request_id=None):
    if request_id is not None and request is not None:
        try:
            request_recovery.finish(request, request_id, http_status=status, response=data)
        except (request_recovery.RecoveryUnavailable, request_recovery.RecoveryNotFound):
            # The guard remains (or the Redis connection is down). Never try the model again.
            _log.warning("ai_chat_recovery_result_unavailable")
    reply = JsonResponse(data, status=status)
    reply["Cache-Control"] = "private, no-store"
    return reply


@never_cache
@require_GET
def recovery_status_view(request):
    if not request_recovery.enabled() or not global_ai_available():
        raise Http404("Recovery disabled")
    if settings.VORNEQ_ENV == "production":
        allowed = production_actor_allowed(request.user)
    elif settings.VORNEQ_ENV == "staging":
        allowed = actor_allowed(request.user)
    else:
        allowed = False
    if not allowed:
        raise Http404("Request unavailable")
    try:
        state = request_recovery.status(request, request.GET.get("request_id", ""))
    except request_recovery.RecoveryInvalid:
        return _respond({"error": "invalid_request_id"}, status=400)
    except request_recovery.RecoveryNotFound:
        return _respond({"error": "not_found"}, status=404)
    except request_recovery.RecoveryUnavailable:
        return _respond({"error": "recovery_unavailable"}, status=503)
    return _respond(state)


STAGING_BRIEF_INSTRUCTIONS = (
    "Third-party public excerpts are not VORNEQ claims. Never add numbers, dates or "
    "facts absent from cited excerpts. Preserve uncertainty and disagreements; "
    "keep source titles unchanged."
)


def _output_cap_for_environment(environment):
    """Bound hosted responses at 2048 tokens; keep development capped at 512."""
    return 2048 if environment in ("staging", "production") else 512


def _compact_sources_for_environment(environment):
    """Omit non-model source metadata on hosted runtimes; validation retains full evidence."""
    return environment in ("staging", "production")


def _provider_timeout_for_environment(environment):
    """Bound hosted provider latency below the 100-second Gunicorn worker limit.

    Both Staging and Production allow 60 seconds for a single provider call;
    remaining headroom covers retrieval, Ledger and recovery writes.
    No retry, authorization, citation or budget policy changes.
    """
    return 60 if environment in ("staging", "production") else 15


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def global_ai_available():
    """Cheap, side-effect-free availability check (no search, no model)."""
    if getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False):
        return False
    if settings.VORNEQ_ENV == "production":
        return production_enabled()
    if not getattr(settings, "VORNEQ_GLOBAL_AI_ENABLED", False):
        return False
    if not getattr(settings, "VORNEQ_AI_PHASE_B_ENABLED", False):
        return False
    if settings.VORNEQ_ENV == "staging":
        return trial_enabled()
    return settings.VORNEQ_ENV == "development" and not hosted_runtime()


@never_cache
@csrf_protect
@require_POST
def ask_global_view(request):
    if not global_ai_available():
        raise Http404("Global AI disabled")
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if settings.VORNEQ_ENV == "staging" and not actor_allowed(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    if settings.VORNEQ_ENV == "production" and not production_actor_allowed(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.content_type != "application/json":
        return JsonResponse({"error": "json_only"}, status=415)
    try:
        length = int(request.META.get("CONTENT_LENGTH", "0") or "0")
        budget = global_budget()
        if length < 0 or length > budget.body_bytes or len(request.body) > budget.body_bytes:
            return JsonResponse({"error": "request_too_large"}, status=413)
        body = json.loads(request.body, object_pairs_hook=_strict_object)
        if not isinstance(body, dict) or set(body) - {"question", "language"}:
            return JsonResponse({"error": "invalid_fields"}, status=400)
        question, language = validate(body.get("question"), body.get("language", "fa"), input_budget=budget)
    except (ValueError, TypeError, UnicodeDecodeError, InputError):
        return JsonResponse({"error": "invalid_input"}, status=400)
    # Bind the request ID before routing, including deterministic cost-free 422s,
    # so Refresh can recover even a rejected request without a ghost status.
    request_id = None
    if request_recovery.enabled():
        request_id = request.headers.get("X-VQ-Request-ID", "")
        try:
            prior = request_recovery.claim(request, request_id, question=question, language=language)
        except request_recovery.RecoveryInvalid:
            return _respond({"error": "invalid_request_id"}, status=400)
        except request_recovery.RecoveryNotFound:
            return _respond({"error": "not_found"}, status=404)
        except request_recovery.RecoveryConflict:
            return _respond({"error": "request_id_conflict"}, status=409)
        except request_recovery.RecoveryUnavailable:
            return _respond({"error": "recovery_unavailable"}, status=503)
        if prior["status"] in ("completed", "failed"):
            return _respond(prior["response"], status=prior["http_status"])
        if prior["status"] != "claimed":
            return _respond({"status": prior["status"], "request_id": request_id},
                            status=202 if prior["status"] == "running" else 409)
    data, status, _meta = run_global_pipeline(request, question, language)
    return _respond(data, status=status, request=request, request_id=request_id)


def _instructions_for(environment, with_history):
    base = STAGING_BRIEF_INSTRUCTIONS if environment == "staging" else GLOBAL_INSTRUCTIONS
    return (base + " " + HISTORY_INSTRUCTIONS) if with_history else base


def run_global_pipeline(request, question, language, *, prior_turns=(), search_question=None):
    """Shared Global AI pipeline after authentication, validation and recovery claim.

    Returns ``(json_body, http_status, meta)``; the caller persists/finishes.
    ``meta`` carries the ledger-wrapped provider (if any) and the model name.
    """
    meta = {"budgeted": None, "model": ""}
    # Unsupported input is rejected before quota, retrieval, or provider work.
    if route_question(question, language).kind == UNSUPPORTED:
        return {"error": "UNSUPPORTED_QUESTION"}, 422, meta
    hosted = settings.VORNEQ_ENV in ("staging", "production")
    # Shared prepaid ledger: mandatory in production, optional in staging. While
    # it governs cost, the cache-based daily counts are replaced by per-call money
    # reservations (a per-minute abuse throttle remains). On STAGING the ledger
    # additionally enforces an independent daily ceiling (paid calls + amount)
    # inside the locked reservation transaction: apps.ai_ledger.service.reserve().
    shared_budget = hosted and ledger_enabled()
    try:
        reserve_global_request(request.user.pk, burst_only=shared_budget)
        if settings.VORNEQ_ENV == "staging" and not shared_budget:
            reserve_staging_request()
        stage2 = response_engine_v3.stage2_enabled(settings)
        provider = OpenAIResponsesProvider(
            model=os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""),
            timeout_s=_provider_timeout_for_environment(settings.VORNEQ_ENV),
            max_output_tokens=(response_engine_v3.output_tokens(settings) if stage2
                               else _output_cap_for_environment(settings.VORNEQ_ENV)),
            extra_instructions=_instructions_for(settings.VORNEQ_ENV, bool(prior_turns)),
            compact_sources=_compact_sources_for_environment(settings.VORNEQ_ENV),
            response_v3_enabled=response_engine_v3.enabled(settings),
            response_stage2_enabled=stage2,
        )
        if shared_budget:
            provider = BudgetedProvider(provider, actor_id=request.user.pk)
            meta["budgeted"] = provider
        elif settings.VORNEQ_ENV == "production":
            raise BudgetExceeded("production requires the shared prepaid ledger")
        meta["model"] = getattr(provider, "model", "") or getattr(getattr(provider, "inner", None), "model", "")
        rlimit, elimit = response_engine_v3.retrieval_limits(settings)
        retriever = (default_retriever(max_results=rlimit, max_excerpt=elimit, exchars=1500)
                     if stage2 else default_retriever())
        response = ask_global(question, language, actor=request.user, provider=provider,
                              retriever=retriever, enabled=True, prior_turns=prior_turns,
                              search_question=search_question, stage2=stage2,
                              max_answer_chars=response_engine_v3.answer_limit(settings))
    except BudgetExceeded:
        return {"error": "rate_limited"}, 429, meta
    except GlobalUnsupported:
        return {"error": "UNSUPPORTED_QUESTION"}, 422, meta
    except (EvidenceRejected, PhaseBDisabled) as exc:
        reason_code = _evidence_rejection_code(exc)
        # Only a fixed enum, never raw prompt, response, citation or exception text.
        _log.warning("ai_evidence_rejected reason_code=%s", reason_code)
        return {"error": "INSUFFICIENT_EVIDENCE", "reason_code": reason_code}, 422, meta
    except RetrievalTimeout:
        return {"error": "search_timeout"}, 504, meta
    except RetrievalError:
        return {"error": "search_unavailable"}, 503, meta
    except ProviderTimeout:
        return {"error": "provider_timeout"}, 504, meta
    except ProviderInvalidResponse:
        # HTTP 200 from the provider is not proof of a usable structured answer.
        # Fixed code only: do not log or return raw provider content.
        _log.warning("ai_provider_response_rejected reason_code=invalid_provider_response")
        return {"error": "provider_unavailable", "reason_code": "invalid_provider_response"}, 503, meta
    except GatewayError:
        return {"error": "provider_unavailable"}, 503, meta
    return response, 200, meta
