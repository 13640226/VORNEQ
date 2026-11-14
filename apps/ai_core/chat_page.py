"""Owner-authorized development preview, never accessible in staging/production."""
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import get_language, override
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .chat_strings import chat_labels
from .staging_policy import hosted_runtime, trial_enabled, actor_allowed
from .production_policy import production_actor_allowed
from .views_global import global_ai_available
from .web_retrieval import WikipediaRetriever


def is_chat_enabled():
    if settings.VORNEQ_ENV == "production":
        return global_ai_available()
    if settings.VORNEQ_ENV == "staging":
        return trial_enabled()
    return (
        settings.VORNEQ_ENV == "development"
        and not hosted_runtime()
        and getattr(settings, "VORNEQ_AI_PHASE_B_ENABLED", False)
        and getattr(settings, "VORNEQ_AI_PHASE_C_ENABLED", False)
    )


@never_cache
@require_GET
def chat_page(request):
    if not is_chat_enabled():
        raise Http404("AI chat preview disabled")
    if not request.user.is_authenticated:
        response = HttpResponse("Authentication required", status=401)
        response["Cache-Control"] = "no-store, private"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    if settings.VORNEQ_ENV == "staging" and not actor_allowed(request.user):
        raise Http404("AI chat preview unavailable")
    if settings.VORNEQ_ENV == "production" and not production_actor_allowed(request.user):
        raise Http404("AI chat unavailable")
    requested_language = request.GET.get("lang", "")
    language = requested_language if requested_language in ("fa", "de", "en") else (get_language() or "en")[:2]
    request.LANGUAGE_CODE = language
    global_ai = global_ai_available()
    with override(language):
        response = render(request, "ai_core/chat.html", {
            "chat_labels": chat_labels(language),
            "chat_language": language,
            "chat_endpoint": reverse("ai_core:ask-global" if global_ai else "ai_core:ask-grounded"),
            "chat_source_hosts": " ".join(sorted(WikipediaRetriever.allowed_hosts)) if global_ai else "",
            "chat_staging": settings.VORNEQ_ENV == "staging",
            "chat_production": settings.VORNEQ_ENV == "production",
        })
    response["Cache-Control"] = "no-store, private"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
