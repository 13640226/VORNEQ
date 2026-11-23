"""Production image worker preparation; NO provider execution or queue claiming."""
import os
import re
from django.conf import settings
from .policy import production_uncapped_budget_requested, production_release_identity, PRODUCTION_SERVICE_ID

_WORKER_ID = re.compile(r"srv-[a-z0-9]{20,32}\Z")


def production_worker_preflight():
    """Read-only readiness. Always returns blocked until separately released."""
    worker = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_WORKER_SERVICE_ID", "")
    sha = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA", "")
    checks = {
        "production_intent": production_uncapped_budget_requested(),
        "release_identity": production_release_identity(),
        "separate_worker_identity": (isinstance(worker, str) and bool(_WORKER_ID.fullmatch(worker))
                                     and worker != PRODUCTION_SERVICE_ID
                                     and os.getenv("RENDER_SERVICE_ID") == worker),
        "sha_match": bool(sha and os.getenv("RENDER_GIT_COMMIT") == sha),
        "emergency_stop_clear": getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", True) is False,
        "provider_activation_authorized": False,
    }
    return {"checks": checks, "ready": all(checks.values())}
