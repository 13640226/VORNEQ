"""Global AI V1 request quota, independent of every other AI quota.

Applies even when the existing staging trial is configured as unmetered:
Global AI never inherits an unlimited policy. Cache-backed (Redis on Render);
any cache failure fails closed. This is a request/abuse quota, NOT a monetary
hard cap; the provider-side project spend limit remains mandatory.
"""
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache

from apps.ai_core.engine.budget import BudgetExceeded

DEFAULTS = {"per_minute": 3, "per_day": 20, "global_per_day": 40}
CEILINGS = {"per_minute": 5, "per_day": 50, "global_per_day": 200}


def _limit(name):
    value = getattr(settings, "VORNEQ_GLOBAL_AI_QUOTA", {}).get(name, DEFAULTS[name])
    if type(value) is not int or not 1 <= value <= CEILINGS[name]:
        return DEFAULTS[name]
    return value


def reserve_global_request(user_id: int):
    """Reserve one Global AI request BEFORE any external search or model call."""
    if type(user_id) is not int or user_id <= 0:
        raise BudgetExceeded("invalid actor for global quota")
    # Explicit staging-only bypass; never inferred from the older UNMETERED flag.
    # The endpoint must still pass trial_enabled() and actor_allowed().
    if (getattr(settings, "VORNEQ_ENV", None) == "staging"
            and getattr(settings, "VORNEQ_GLOBAL_AI_UNLIMITED_STAGING", False)):
        return
    now = datetime.now(timezone.utc)
    minute, day = now.strftime("%Y%m%d%H%M"), now.strftime("%Y%m%d")
    for key, ttl, limit in (
        (f"global-ai:user:{user_id}:minute:{minute}", 80, _limit("per_minute")),
        (f"global-ai:user:{user_id}:day:{day}", 90000, _limit("per_day")),
        (f"global-ai:global:day:{day}", 90000, _limit("global_per_day")),
    ):
        try:
            cache.add(key, 0, timeout=ttl)
            count = cache.incr(key)
        except Exception as exc:
            raise BudgetExceeded("global quota backend unavailable") from exc
        if count > limit:
            raise BudgetExceeded("global quota exceeded")
