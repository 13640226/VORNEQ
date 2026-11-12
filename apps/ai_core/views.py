"""Development-only, session-authenticated, CSRF-protected API."""
import json

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .gateway import InputError, ask_public
from .provider import OpenAIResponsesProvider, ProviderUnavailable

@never_cache
@csrf_protect
@require_POST
def ask(request):
    if settings.VORNEQ_ENV != "development" or not settings.VORNEQ_AI_CORE_ENABLED:
        raise Http404("AI Core disabled")
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
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
    if not isinstance(data, dict) or set(data) - {"question", "language", "allow_model"}:
        return JsonResponse({"error": "invalid_fields"}, status=400)
    consent = data.get("allow_model", False)
    if type(consent) is not bool:
        return JsonResponse({"error": "invalid_consent"}, status=400)
    language = data.get("language", getattr(request, "LANGUAGE_CODE", "fa")[:2])
    enabled = bool(settings.VORNEQ_AI_EXTERNAL_EGRESS_ENABLED)
    provider = None
    if enabled and consent:
        try:
            provider = OpenAIResponsesProvider(
                api_key=settings.VORNEQ_AI_API_KEY, model=settings.VORNEQ_AI_MODEL)
        except ProviderUnavailable:
            pass
    try:
        result = ask_public(data.get("question"), language, allow_model=consent,
                            egress_enabled=enabled, provider=provider)
    except InputError:
        return JsonResponse({"error": "invalid_question_or_language"}, status=400)
    response = JsonResponse(result)
    response["Cache-Control"] = "no-store, private"
    return response
