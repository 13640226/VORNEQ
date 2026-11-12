"""Development-only coarse request budget (not audited financial spend controls).

Distributed production-grade atomic quotas and monetary budget accounting are
NOT implemented; Phase B cannot be enabled in staging/production.
"""
from datetime import datetime, timezone

from django.core.cache import cache


class BudgetExceeded(ValueError):
    pass


def reserve_request(user_id: int, *, per_minute: int = 6, per_day: int = 30):
    now = datetime.now(timezone.utc)
    minute = now.strftime("%Y%m%d%H%M")
    day = now.strftime("%Y%m%d")
    for key, ttl, limit in (
        (f"phase-b:user:{user_id}:minute:{minute}", 80, per_minute),
        (f"phase-b:user:{user_id}:day:{day}", 90000, per_day),
    ):
        try:
            cache.add(key, 0, timeout=ttl)
            count = cache.incr(key)
        except Exception as exc:
            raise BudgetExceeded("request budget backend unavailable") from exc
        if count > limit:
            raise BudgetExceeded("request budget exceeded")
