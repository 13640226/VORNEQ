"""JSON-only image endpoints; independent of existing text-chat views."""
import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.ai_core.models import AIImageJob
from .policy import actor_allowed
from .service import ImageQueueError, serialize_job, submit_image_job


def _respond(data, code=200, retry_after=None):
    response = JsonResponse(data, status=code)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    if retry_after is not None:
        response["Retry-After"] = str(retry_after)
    return response


_REFUSALS = {
    "invalid_request": 400, "invalid_request_id": 400,
    "invalid_prompt": 400, "unsupported_size": 400, "request_id_conflict": 400,
    "rate_limited": 429, "global_daily_cap": 429, "user_daily_cap": 429,
    "service_misconfigured": 503,
}


def _refusal(code, retry_after=None):
    # Only explicit pre-admission exceptions use this contract.
    status = _REFUSALS[code]
    data = {"error": code, "error_code": code, "request_rejected": True}
    if status == 429:
        retry_after = max(1, int(retry_after or 1))
        data["retry_after_seconds"] = retry_after
    return _respond(data, status, retry_after if status == 429 else None)


@require_http_methods(["GET", "POST"])
def image_jobs_view(request):
    if not request.user.is_authenticated:
        return _respond({"error": "authentication_required"}, 401)
    if not actor_allowed(request.user):
        return _respond({"error": "unavailable"}, 404)
    if request.method == "GET":
        own = AIImageJob.objects.filter(owner=request.user).order_by("-created_at", "-pk")
        if request.GET.get("active") == "1" and not request.GET.get("latest"):
            active = own.filter(status__in=(AIImageJob.STATUS_QUEUED, AIImageJob.STATUS_RUNNING))
            # Bounded metadata lookup, not history or signed URL enumeration.
            return _respond({"results": [serialize_job(job) for job in active[:10]]})
        if request.GET.get("latest") == "1" and not request.GET.get("active"):
            # The job may have finished between reload and active discovery.
            # Return the identity only; detail enforces ownership and signs URLs.
            job_id = own.values_list("pk", flat=True).first()
            return _respond({"id": str(job_id) if job_id else None})
        return _refusal("invalid_request")
    if request.content_type != "application/json" or len(request.body) > 8192:
        return _refusal("invalid_request")
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError()
        prompt, size = body["prompt"], body.get("size", "1024x1024")
    except (KeyError, ValueError, TypeError):
        return _refusal("invalid_request")
    try:
        rid = uuid.UUID(body["request_id"])
        if rid.version != 4:
            raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError):
        return _refusal("invalid_request_id")
    try:
        job, created = submit_image_job(request.user, request_id=rid, prompt=prompt, size=size)
    except ImageQueueError as exc:
        if exc.code not in _REFUSALS:
            raise
        return _refusal(exc.code, exc.retry_after)
    except PermissionError:
        # Preserve the existing gate/authorization response.
        return _respond({"error": "unavailable"}, 404)
    return _respond(serialize_job(job), 202 if created else 200)


@require_http_methods(["GET"])
def image_job_detail_view(request, job_id):
    if not request.user.is_authenticated:
        return _respond({"error": "authentication_required"}, 401)
    if not actor_allowed(request.user):
        return _respond({"error": "unavailable"}, 404)
    job = AIImageJob.objects.filter(pk=job_id, owner=request.user).first()
    if job is None:
        return _respond({"error": "not_found"}, 404)
    return _respond(serialize_job(job))
