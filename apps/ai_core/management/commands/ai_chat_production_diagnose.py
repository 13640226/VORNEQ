"""Read-only, non-secret diagnostics for the Production Chat AI gate."""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_core.production_policy import production_enabled
from apps.ai_core.request_recovery import enabled as recovery_enabled
from apps.ai_core.deploy_authorization import release_allowed
from apps.ai_ledger.service import ledger_enabled


class Command(BaseCommand):
    help = "Report Production Chat gate predicates without secrets or paid calls."

    def handle(self, *args, **options):
        sha = getattr(settings, "VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA", "")
        live = os.environ.get("RENDER_GIT_COMMIT", "")
        checks = {
            "production_environment": getattr(settings, "VORNEQ_ENV", None) == "production",
            "debug_disabled": settings.DEBUG is False,
            "production_flag": getattr(settings, "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED", False) is True,
            "emergency_stop_clear": getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", True) is False,
            "recovery_enabled": recovery_enabled(),
            "service_identity": os.environ.get("RENDER_SERVICE_ID") == "srv-dadn07eq1p3s73eccau0",
            "sha_matches": bool(sha and live and sha == live),
            "release_authorized": release_allowed("production", sha),
            "owner_authorization_present": bool(getattr(settings, "VORNEQ_AI_PRODUCTION_OWNER_AUTH", "")),
            "model_matches": bool(getattr(settings, "VORNEQ_AI_PRODUCTION_APPROVED_MODEL", "") and getattr(settings, "VORNEQ_AI_PRODUCTION_APPROVED_MODEL", "") == os.environ.get("VORNEQ_AI_PHASE_B_MODEL")),
            "provider_key_present": bool(os.environ.get("OPENAI_API_KEY")),
            "ledger_enabled": ledger_enabled(),
            "actor_allowlist_configured": bool(getattr(settings, "VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS", "")),
        }
        # Do not print IDs, SHA, credentials, authorization references, or balances.
        self.stdout.write(json.dumps({"checks": checks, "chat_enabled": production_enabled()}, sort_keys=True))
