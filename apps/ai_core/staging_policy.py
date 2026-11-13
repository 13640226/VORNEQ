"""Fail-closed authorization for the limited, owner-approved STAGING AI trial.

This is a code contract, not an owner authorization. Nothing is enabled merely
by merging this module or by creating an OpenAI key. The owner must separately
approve the exact SHA, user principal, budget and service configuration.
Production is always forbidden; Phase C remains development-only.
"""
from __future__ import annotations

import os
import re

from django.conf import settings

EXPECTED_STAGING_SERVICE_ID = "srv-dbm7dvc9v7es7393g70g"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_OWNER_REF = re.compile(r"OWNER-AUTH-AI-STAGING-[A-Z0-9-]{6,100}\Z")


def _ids_from_setting():
    raw = getattr(settings, "VORNEQ_AI_STAGING_ALLOWED_USER_IDS", "")
    if not isinstance(raw, str) or not raw or len(raw) > 250:
        return set()
    parts = raw.split(",")
    if len(parts) > 5 or any(
        not item.isascii() or not item.isdecimal() or not 1 <= len(item) <= 12
        for item in parts
    ):
        return set()
    parsed = {int(item) for item in parts}
    return parsed if len(parsed) == len(parts) and all(v > 0 for v in parsed) else set()


def trial_enabled():
    """Checks code/runtime identity + scoped approval + bounded spending.

    No third-party calls, DB writes or secret values are logged by this guard.
    """
    if (
        getattr(settings, "VORNEQ_ENV", None) != "staging"
        or getattr(settings, "DEBUG", True)
        or not getattr(settings, "VORNEQ_AI_STAGING_TRIAL_ENABLED", False)
        or not getattr(settings, "VORNEQ_AI_CORE_ENABLED", False)
        or not getattr(settings, "VORNEQ_AI_PHASE_B_ENABLED", False)
        or os.environ.get("RENDER_SERVICE_ID") != EXPECTED_STAGING_SERVICE_ID
    ):
        return False
    sha = getattr(settings, "VORNEQ_AI_STAGING_AUTHORIZED_SHA", "")
    if (
        not isinstance(sha, str) or not _SHA.fullmatch(sha)
        or os.environ.get("RENDER_GIT_COMMIT") != sha
    ):
        return False
    owner_ref = getattr(settings, "VORNEQ_AI_STAGING_OWNER_AUTH", "")
    if not isinstance(owner_ref, str) or not _OWNER_REF.fullmatch(owner_ref):
        return False
    approved_model = getattr(settings, "VORNEQ_AI_STAGING_APPROVED_MODEL", "")
    if (
        not isinstance(approved_model, str) or not approved_model
        or len(approved_model) > 100
        or os.environ.get("VORNEQ_AI_PHASE_B_MODEL", "") != approved_model
        or not os.environ.get("OPENAI_API_KEY", "")
    ):
        return False
    if not _ids_from_setting():
        return False
    cap = getattr(settings, "VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", 0)
    reserve = getattr(settings, "VORNEQ_AI_STAGING_RESERVE_MICROUSD", 0)
    requests = getattr(settings, "VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", 0)
    if (
        type(cap) is not int or type(reserve) is not int or type(requests) is not int
        or not 1 <= requests <= 5
        or not 1_000 <= reserve <= 100_000
        or not reserve <= cap <= 250_000
        or cap < reserve * requests
    ):
        return False
    # A reservation is a conservative operator-approved allowance, not
    # metered OpenAI billing. Provider-side spend controls remain mandatory.
    return True


def actor_allowed(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_staff", False)
        and getattr(user, "is_superuser", False)
        and getattr(user, "pk", None) in _ids_from_setting()
    )
