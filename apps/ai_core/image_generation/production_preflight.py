"""Production image admission preflight. Read-only; never authorizes a paid request.

The operational Production job and worker gates remain independently closed.
"""
from __future__ import annotations

from django.conf import settings

from .policy import production_release_identity, PRODUCTION_SERVICE_ID


def production_image_preflight(user):
    """Return independently auditable booleans without exposing secrets."""
    import os

    project = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_PROJECT_BUDGET_MICROUSD", None)
    daily = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_DAILY_CAP_MICROUSD", None)
    request = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_MAX_REQUEST_MICROUSD", None)
    budget_valid = (
        type(project) is int and project == 5_000_000
        and type(daily) is int and daily == 200_000
        and type(request) is int and 1 <= request <= 100_000
        and request <= daily <= project
    )
    return {
        "environment": getattr(settings, "VORNEQ_ENV", "") == "production",
        "debug_disabled": getattr(settings, "DEBUG", True) is False,
        "service_identity": os.getenv("RENDER_SERVICE_ID") == PRODUCTION_SERVICE_ID,
        "release_identity": production_release_identity() is True,
        "owner_admin_1": bool(
            getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "is_staff", False)
            and getattr(user, "is_superuser", False)
            and type(getattr(user, "pk", None)) is int
            and user.pk == 1
        ),
        "emergency_stop_clear": getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", True) is False,
        "financial_caps_configured": budget_valid,
        "paid_route_implemented": False,
        "production_worker_authorized": False,
    }


def production_image_admission_allowed(user):
    """Always fail closed until separate ledger and worker implementation ships."""
    return all(production_image_preflight(user).values())
