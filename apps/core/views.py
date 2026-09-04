from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.core.services import ReputationService


@require_GET
@login_required
def reputation_detail(request, user_id):
    user = get_object_or_404(get_user_model(), pk=user_id)
    return JsonResponse(ReputationService.snapshot(user))
