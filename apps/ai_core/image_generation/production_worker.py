"""Production image worker: closed-gate readiness, never invokes a paid provider."""
import os
import re
from django.conf import settings
from .policy import PRODUCTION_SERVICE_ID
from .production_ledger_contract import ProductionImageBudget

_WORKER_ID = re.compile(r"srv-[a-z0-9]{20,32}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")


def production_worker_preflight():
    """Worker identity is separate from WEB identity. Activation hard-blocked."""
    from apps.ai_core.deploy_authorization import _verified_release
    worker = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_WORKER_SERVICE_ID", "")
    sha = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA", "")
    owner = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH", "")
    actor_ids = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS", "")
    checks = {
        "production_environment": getattr(settings, "VORNEQ_ENV", "") == "production",
        "debug_off": getattr(settings, "DEBUG", True) is False,
        "budget_intent": ProductionImageBudget(
            getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_PROJECT_BUDGET_MICROUSD", None),
            getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_DAILY_CAP_MICROUSD", None),
            getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_MAX_REQUEST_MICROUSD", None),
        ).valid(),
        "production_switch": getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_ENABLED", False) is True,
        "actor_isolation": actor_ids == "1",
        "owner_grant_format": isinstance(owner, str) and bool(re.fullmatch(r"OWNER-AUTH-AI-IMAGE-PRODUCTION-[A-Z0-9-]{6,100}", owner)),
        "separate_worker_identity": (isinstance(worker, str) and bool(_WORKER_ID.fullmatch(worker))
                                     and worker != PRODUCTION_SERVICE_ID
                                     and os.getenv("RENDER_SERVICE_ID") == worker),
        "sha_match": isinstance(sha, str) and bool(_SHA.fullmatch(sha)) and os.getenv("RENDER_GIT_COMMIT") == sha,
        "deploy_token_present": bool(os.getenv("VORNEQ_AI_DEPLOY_READ_TOKEN", "")),
        "emergency_stop_clear": getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", True) is False,
        "provider_activation_authorized": False,
    }
    checks["verified_release"] = (checks["sha_match"] and checks["deploy_token_present"]
                                   and _verified_release("production", sha) is True)
    return {"checks": checks, "ready": all(checks.values())}


def process_production_image_job():
    """Intentionally no queue claim, ledger mutation or provider call."""
    return None
