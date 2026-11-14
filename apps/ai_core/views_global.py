"""Global AI V1 endpoint. Default OFF; development or authorized staging only.

All Phase B controls are kept (environment, hosted-runtime guard, staging trial
identity/SHA/service pins, authentication, staging actor allowlist, CSRF,
strict JSON). Global AI adds its own feature flag and its own quota.
"""
import json
import os

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from apps.ai_core.engine.budget import BudgetExceeded
from apps.ai_core.engine.citation import EvidenceRejected
from apps.ai_core.engine.global_grounded import GLOBAL_INSTRUCTIONS, GlobalUnsupported, ask_global
from apps.ai_core.engine.grounded import PhaseBDisabled
from apps.ai_core.gateway import InputError, validate
from apps.ai_core.global_budget import reserve_global_request
from apps.ai_core.global_router import UNSUPPORTED, route_question
from apps.ai_core.providers.exceptions import GatewayError, ProviderTimeout
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.staging_budget import reserve_staging_request
from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.production_policy import production_actor_allowed, production_enabled
from apps.ai_core.staging_policy import actor_allowed, hosted_runtime, trial_enabled
from apps.ai_ledger.service import ledger_enabled
from apps.ai_core.retrieval_registry import default_retriever
from apps.ai_core.web_retrieval import RetrievalError, RetrievalTimeout


STAGING_BRIEF_INSTRUCTIONS = (
    "Third-party public excerpts are not VORNEQ claims. Never add numbers, dates or "
    "facts absent from cited excerpts. Preserve uncertainty and disagreements; "
    "keep source titles unchanged."
)


def _output_cap_for_environment(environment):
    """Raise Staging only; keep Production and development limits unchanged."""
    return 2048 if environment == "staging" else 1024 if environment == "production" else 512


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
        if length < 0 or length > 2048 or len(request.body) > 2048:
            return JsonResponse({"error": "request_too_large"}, status=413)
        body = json.loads(request.body, object_pairs_hook=_strict_object)
        if not isinstance(body, dict) or set(body) - {"question", "language"}:
            return JsonResponse({"error": "invalid_fields"}, status=400)
        question, language = validate(body.get("question"), body.get("language", "fa"))
    except (ValueError, TypeError, UnicodeDecodeError, InputError):
        return JsonResponse({"error": "invalid_input"}, status=400)
    # Deterministic local routing first: unsupported input costs no quota.
    if route_question(question, language).kind == UNSUPPORTED:
        return JsonResponse({"error": "UNSUPPORTED_QUESTION"}, status=422)
    hosted = settings.VORNEQ_ENV in ("staging", "production")
    # Shared prepaid ledger: mandatory in production, optional in staging. While
    # it governs cost, fixed daily counts are replaced by per-call money
    # reservations (a per-minute abuse throttle remains).
    shared_budget = hosted and ledger_enabled()
    try:
        reserve_global_request(request.user.pk, burst_only=shared_budget)
        if settings.VORNEQ_ENV == "staging" and not shared_budget:
            reserve_staging_request()
        provider = OpenAIResponsesProvider(
            model=os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""),
            timeout_s=30 if hosted else 15,
            max_output_tokens=_output_cap_for_environment(settings.VORNEQ_ENV),
            extra_instructions=(STAGING_BRIEF_INSTRUCTIONS if settings.VORNEQ_ENV == "staging"
                                else GLOBAL_INSTRUCTIONS),
            compact_sources=settings.VORNEQ_ENV == "staging",
        )
        if shared_budget:
            provider = BudgetedProvider(provider, actor_id=request.user.pk)
        elif settings.VORNEQ_ENV == "production":
            raise BudgetExceeded("production requires the shared prepaid ledger")
        response = ask_global(question, language, actor=request.user, provider=provider,
                              retriever=default_retriever(), enabled=True)
    except BudgetExceeded:
        return JsonResponse({"error": "rate_limited"}, status=429)
    except GlobalUnsupported:
        return JsonResponse({"error": "UNSUPPORTED_QUESTION"}, status=422)
    except (EvidenceRejected, PhaseBDisabled):
        return JsonResponse({"error": "INSUFFICIENT_EVIDENCE"}, status=422)
    except RetrievalTimeout:
        return JsonResponse({"error": "search_timeout"}, status=504)
    except RetrievalError:
        return JsonResponse({"error": "search_unavailable"}, status=503)
    except ProviderTimeout:
        return JsonResponse({"error": "provider_timeout"}, status=504)
    except GatewayError:
        return JsonResponse({"error": "provider_unavailable"}, status=503)
    result = JsonResponse(response)
    result["Cache-Control"] = "private, no-store"
    return result
