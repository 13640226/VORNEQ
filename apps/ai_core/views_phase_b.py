"""Opt-in Phase B endpoint (development/staging only; never production).

V4-01: on staging every paid call runs through the shared prepaid ledger."""
import json
import os

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from apps.ai_core.gateway import InputError, validate
from apps.ai_core.engine.budget import BudgetExceeded, reserve_request
from apps.ai_core.engine.citation import EvidenceRejected
from apps.ai_core.engine.grounded import PhaseBDisabled, ask_grounded
from apps.ai_core.providers.exceptions import GatewayError, ProviderTimeout
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.staging_policy import trial_enabled, actor_allowed, hosted_runtime
from apps.ai_core.staging_budget import reserve_staging_request
from apps.ai_core.paid_provider import paid_text_provider, require_paid_text_ledger
from apps.ai_ledger.service import ledger_enabled


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON fields")
        result[key] = value
    return result


@never_cache
@csrf_protect
@require_POST
def ask_phase_b(request):
    if not getattr(settings, "VORNEQ_AI_PHASE_B_ENABLED", False):
        raise Http404("Phase B disabled")
    if settings.VORNEQ_ENV == "staging" and not trial_enabled():
        raise Http404("Phase B staging trial disabled")
    if settings.VORNEQ_ENV not in ("development", "staging"):
        raise Http404("Phase B disabled outside development/staging")
    if settings.VORNEQ_ENV == "development" and hosted_runtime():
        raise Http404("development AI path disabled on hosted runtime")
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if settings.VORNEQ_ENV == "staging" and not actor_allowed(request.user):
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
    try:
        # V4-01: on staging the paid call is ledger-bound (BudgetedProvider:
        # reserve -> call -> settle). The ledger check runs BEFORE the legacy
        # per-day counter, so a missing ledger never consumes quota and
        # VORNEQ_AI_STAGING_UNMETERED can no longer remove the only cost control.
        ledger_bound = require_paid_text_ledger(ledger_check=ledger_enabled)
        if settings.VORNEQ_ENV == "staging":
            reserve_staging_request()
        elif not ledger_bound:
            reserve_request(request.user.pk)
        provider = paid_text_provider(
            actor_id=request.user.pk,
            provider_class=OpenAIResponsesProvider,
            ledger_check=ledger_enabled,
            model=os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""),
            timeout_s=30 if settings.VORNEQ_ENV == "staging" else 15,
            max_output_tokens=2048 if settings.VORNEQ_ENV == "staging" else 512,
        )
        response = ask_grounded(question, language, actor=request.user,
                                provider=provider, enabled=True)
    except BudgetExceeded:
        return JsonResponse({"error": "rate_limited"}, status=429)
    except (EvidenceRejected, PhaseBDisabled):
        return JsonResponse({"error": "INSUFFICIENT_EVIDENCE"}, status=422)
    except ProviderTimeout:
        return JsonResponse({"error": "provider_timeout"}, status=504)
    except GatewayError:
        return JsonResponse({"error": "provider_unavailable"}, status=503)
    result = JsonResponse(response)
    result["Cache-Control"] = "private, no-store"
    return result
