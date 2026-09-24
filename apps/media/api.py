import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.media.embedding import DeterministicLocalEmbeddingProvider
from apps.media.similarity import MediaSimilarityService
from apps.media.vector_index import DatabaseVectorIndex


MAX_QUERY_IMAGE_BYTES = 10 * 1024 * 1024
MAX_RESULTS = 50
DISCOVERY_NOTE = (
    "Similarity search is discovery only. It does not verify authenticity, "
    "provenance, trust, or truth."
)


def _service():
    # The deterministic provider is deliberately development-only. Production
    # must configure a real provider in a later adapter PR.
    if not settings.DEBUG:
        return None
    return MediaSimilarityService(
        provider=DeterministicLocalEmbeddingProvider(),
        index=DatabaseVectorIndex(),
    )


def _parse_limit(value):
    try:
        limit = int(value or 10)
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer")
    if limit < 1 or limit > MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}")
    return limit


def _unavailable_response():
    return JsonResponse(
        {
            "error": "embedding_provider_not_configured",
            "detail": "A production embedding provider is not configured.",
        },
        status=503,
    )


@require_POST
def search_by_image(request):
    service = _service()
    if service is None:
        return _unavailable_response()

    image = request.FILES.get("image")
    if image is None:
        return JsonResponse({"error": "image_required"}, status=400)
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        return JsonResponse({"error": "invalid_image_type"}, status=400)
    if image.size > MAX_QUERY_IMAGE_BYTES:
        return JsonResponse({"error": "image_too_large"}, status=413)

    try:
        limit = _parse_limit(request.POST.get("limit"))
        results = service.search_by_image(
            image.read(),
            mime_type=content_type,
            limit=limit,
        )
    except ValueError as exc:
        return JsonResponse({"error": "invalid_request", "detail": str(exc)}, status=400)

    return JsonResponse({"results": results, "count": len(results), "note": DISCOVERY_NOTE})


@require_POST
def search_by_text(request):
    service = _service()
    if service is None:
        return _unavailable_response()

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_json"}, status=400)
    else:
        payload = request.POST

    text = str(payload.get("text", "")).strip()
    if not text:
        return JsonResponse({"error": "text_required"}, status=400)
    if len(text) > 2000:
        return JsonResponse({"error": "text_too_long"}, status=400)

    try:
        limit = _parse_limit(payload.get("limit"))
        results = service.search_by_text(text, limit=limit)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_request", "detail": str(exc)}, status=400)

    return JsonResponse({"results": results, "count": len(results), "note": DISCOVERY_NOTE})
