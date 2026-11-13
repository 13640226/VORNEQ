"""Isolated Staging AI reservation ledger, default-off and never for Production.

Reservation records are durable budget allowances, not actual OpenAI invoices.
They are deliberately never refunded automatically on errors/timeouts.
"""
from django.db import models
from django.db.models import Q


class StagingAIBudgetDay(models.Model):
    day_utc = models.DateField(unique=True)
    reserved_micro_usd = models.PositiveIntegerField(default=0)
    request_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(reserved_micro_usd__gte=0),
                name="ai_staging_budget_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(request_count__gte=0),
                name="ai_staging_requests_nonnegative",
            ),
        ]
