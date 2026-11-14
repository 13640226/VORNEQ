"""Explicit, fail-closed PRODUCTION policy for Global AI (default OFF).

Production is never enabled by the staging trial or development flags. All of
the following must hold: production runtime, DEBUG off, dedicated flag, exact
Render service, exact authorized SHA, owner authorization reference, approved
model, provider key present, shared prepaid ledger configured, no emergency stop.
"""
from __future__ import annotations

import os
import re

from django.conf import settings

from apps.ai_ledger.service import EXPECTED_SERVICES, ledger_enabled

EXPECTED_PRODUCTION_SERVICE_ID = EXPECTED_SERVICES["production"]
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_OWNER_REF = re.compile(r"OWNER-AUTH-AI-PRODUCTION-[A-Z0-9-]{6,100}\Z")
MAX_ALLOWLIST = 50


def _ids(raw):
    if not isinstance(raw, str) or not raw or len(raw) > 700:
        return set()
    parts = raw.split(",")
    if len(parts) > MAX_ALLOWLIST or any(
            not p.isascii() or not p.isdecimal() or not 1 <= len(p) <= 12 for p in parts):
        return set()
    parsed = {int(p) for p in parts}
    return parsed if len(parsed) == len(parts) and all(v > 0 for v in parsed) else set()


def production_enabled() -> bool:
    if (
        getattr(settings, "VORNEQ_ENV", None) != "production"
        or getattr(settings, "DEBUG", True)
        or not getattr(settings, "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED", False)
        or getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False)
        or os.environ.get("RENDER_SERVICE_ID") != EXPECTED_PRODUCTION_SERVICE_ID
    ):
        return False
    sha = getattr(settings, "VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA", "")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha) or os.environ.get("RENDER_GIT_COMMIT") != sha:
        return False
    owner = getattr(settings, "VORNEQ_AI_PRODUCTION_OWNER_AUTH", "")
    if not isinstance(owner, str) or not _OWNER_REF.fullmatch(owner):
        return False
    model = getattr(settings, "VORNEQ_AI_PRODUCTION_APPROVED_MODEL", "")
    if (not isinstance(model, str) or not model or len(model) > 100
            or os.environ.get("VORNEQ_AI_PHASE_B_MODEL", "") != model
            or not os.environ.get("OPENAI_API_KEY", "")):
        return False
    return ledger_enabled()


def production_actor_allowed(user) -> bool:
    if not (getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)):
        return False
    policy = getattr(settings, "VORNEQ_AI_PRODUCTION_ACTOR_POLICY", "allowlist")
    if policy == "authenticated":
        return True
    if policy == "allowlist":
        return getattr(user, "pk", None) in _ids(getattr(settings, "VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS", ""))
    return False
