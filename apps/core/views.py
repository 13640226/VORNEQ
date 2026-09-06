from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.core.services import ReputationService
from apps.core.services.public_reputation import get_public_reputation


@require_GET
@login_required
def reputation_detail(request, user_id):
    user = get_object_or_404(get_user_model(), pk=user_id)
    return JsonResponse(ReputationService.snapshot(user))


@require_GET
def public_reputation_list(request, user_id):
    user = get_object_or_404(get_user_model(), pk=user_id)
    return JsonResponse(
        {
            "user": {"id": user.pk, "username": user.get_username()},
            "reputations": get_public_reputation(user),
        }
    )


@require_GET
def public_reputation_context(request, user_id, domain, method_code):
    user = get_object_or_404(get_user_model(), pk=user_id)
    reputations = get_public_reputation(
        user,
        domain=domain,
        method_code=method_code,
    )
    if not reputations:
        return JsonResponse({"detail": "Contextual reputation not found."}, status=404)
    return JsonResponse(
        {
            "user": {"id": user.pk, "username": user.get_username()},
            "reputation": reputations[0],
        }
    )
