"""JSON-only image endpoints; independent of existing text-chat views."""
import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from apps.ai_core.models import AIImageJob
from .policy import actor_allowed
from .service import ImageQueueError, serialize_job, submit_image_job


def _respond(data, code=200):
    response = JsonResponse(data, status=code)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_http_methods(["POST"])
def image_jobs_view(request):
    if not request.user.is_authenticated:
        return _respond({"error": "authentication_required"}, 401)
    if not actor_allowed(request.user):
        return _respond({"error": "unavailable"}, 404)
    if request.content_type != "application/json" or len(request.body) > 8192:
        return _respond({"error": "invalid_request"}, 400)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError()
        rid = uuid.UUID(body["request_id"])
        if rid.version != 4:
            raise ValueError()
        prompt, size = body["prompt"], body.get("size", "1024x1024")
        job, created = submit_image_job(
            request.user, request_id=rid, prompt=prompt, size=size
        )
    except (KeyError, ValueError, TypeError, AttributeError, ImageQueueError):
        return _respond({"error": "invalid_or_limited_request"}, 400)
    except PermissionError:
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
