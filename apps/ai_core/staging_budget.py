"""Atomic per-day, process-safe budget reservations for a STAGING-only AI trial."""
from datetime import datetime, timezone

from django.conf import settings
from django.db import DatabaseError, transaction

from apps.ai_core.engine.budget import BudgetExceeded
from apps.ai_core.models import StagingAIBudgetDay
from apps.ai_core.staging_policy import trial_enabled


def reserve_staging_request():
    """Reserve a conservative per-call allowance BEFORE external provider access.

    The reserved allowance is NOT a statement of actual OpenAI charges.
    Never automatically return reservations: retry or timeout may incur costs.
    Fails closed on missing migrations, DB outage, invalid config or limit.
    """
    if not trial_enabled():
        raise BudgetExceeded("staging AI trial not authorized")
    day = datetime.now(timezone.utc).date()
    cap = settings.VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD
    per_request = settings.VORNEQ_AI_STAGING_RESERVE_MICROUSD
    max_requests = settings.VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS
    try:
        with transaction.atomic():
            record, _created = (
                StagingAIBudgetDay.objects.select_for_update().get_or_create(
                    day_utc=day
                )
            )
            if (
                record.request_count >= max_requests
                or record.reserved_micro_usd + per_request > cap
            ):
                raise BudgetExceeded("staging AI request or budget ceiling reached")
            record.request_count += 1
            record.reserved_micro_usd += per_request
            record.save(update_fields=["request_count", "reserved_micro_usd"])
    except DatabaseError as exc:
        raise BudgetExceeded("staging budget database unavailable") from exc
