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


class AIChatRequestGuard(models.Model):
    """Durable idempotency authority for Staging AI chat.

    Stores only a random request identifier and HMAC/fingerprint metadata.
    No question, session token, answer, or provider credentials are persisted.
    Rows must not be automatically removed while the identifier could be reused:
    deletion would reopen the duplicate-provider window.
    """

    request_id = models.UUIDField(primary_key=True, editable=False)
    actor_id = models.BigIntegerField()
    session_digest = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64)
    state = models.CharField(
        max_length=10,
        choices=[("running", "running"), ("finished", "finished")],
        default="running",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"], name="ai_chat_guard_created_idx"),
        ]
