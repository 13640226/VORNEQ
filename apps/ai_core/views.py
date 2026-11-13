"""Development-only Offline AI API; no external-provider code path."""
import json

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .gateway import InputError, ask_public
from .staging_policy import trial_enabled, actor_allowed


@never_cache
@csrf_protect
@require_POST
def ask(request):
    if not settings.VORNEQ_AI_CORE_ENABLED:
        raise Http404("AI Core disabled")
    if settings.VORNEQ_ENV == "staging" and not trial_enabled():
        raise Http404("AI Core staging trial disabled")
    if settings.VORNEQ_ENV not in ("development", "staging"):
        raise Http404("AI Core disabled outside development/staging")
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    if settings.VORNEQ_ENV == "staging" and not actor_allowed(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.content_type != "application/json":
        return JsonResponse({"error": "json_only"}, status=415)
    try:
        length = int(request.META.get("CONTENT_LENGTH", "0") or "0")
    except ValueError:
        return JsonResponse({"error": "invalid_content_length"}, status=400)
    if length > 2048:
        return JsonResponse({"error": "request_too_large"}, status=413)
    try:
        raw = request.body
        if len(raw) > 2048:
            return JsonResponse({"error": "request_too_large"}, status=413)
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    # Phase A explicitly rejects the former opt-in model interface.
    if not isinstance(data, dict) or set(data) - {"question", "language"}:
        return JsonResponse({"error": "invalid_fields"}, status=400)
    language = data.get("language", getattr(request, "LANGUAGE_CODE", "fa")[:2])
    try:
        result = ask_public(data.get("question"), language)
    except InputError:
        return JsonResponse({"error": "invalid_question_or_language"}, status=400)
    response = JsonResponse(result)
    response["Cache-Control"] = "no-store, private"
    return response
