"""Guarded Chat UI for authorized development, staging, and Production actors."""
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import get_language, override
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .chat_strings import chat_labels
from .response_engine_v3 import answer_limit, stage2_enabled
from .staging_policy import hosted_runtime, trial_enabled, actor_allowed
from .production_policy import production_actor_allowed
from .views_global import global_ai_available
from .web_retrieval import WikipediaRetriever
from .request_recovery import enabled as recovery_enabled
from .image_generation.page import image_studio_allowed


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
    # Persistent conversations ride on Global AI; off unless explicitly enabled.
    from .views_conversations import may_start
    conversations_on = bool(global_ai and getattr(settings, "VORNEQ_AI_CONVERSATIONS_ENABLED", False)
                            and may_start(request.user))
    with override(language):
        response = render(request, "ai_core/chat.html", {
            "chat_labels": chat_labels(language, environment=settings.VORNEQ_ENV),
            "chat_language": language,
            "chat_endpoint": reverse("ai_core:ask-global" if global_ai else "ai_core:ask-grounded"),
            "chat_source_hosts": " ".join(sorted(WikipediaRetriever.allowed_hosts)) if global_ai else "",
            "chat_v3_enabled": answer_limit(settings) > 1000,
            "chat_answer_limit": answer_limit(settings),
            "chat_citation_limit": 5 if stage2_enabled(settings) else 3,
            "chat_staging": settings.VORNEQ_ENV == "staging",
            "chat_production": settings.VORNEQ_ENV == "production",
            "chat_recovery_enabled": global_ai and recovery_enabled(),
            "chat_recovery_endpoint": reverse("ai_core:request-status"),
            "chat_conversations_enabled": conversations_on,
            "chat_image_studio_enabled": image_studio_allowed(request.user),
            "chat_image_studio_url": reverse("ai_core:image-studio"),
            "chat_conversations_endpoint": reverse("ai_core:conversations") if conversations_on else "",
        })
    response["Cache-Control"] = "no-store, private"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
