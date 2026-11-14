"""Shared prepaid AI budget ledger (integer micro-USD).

Amounts are conservative ESTIMATES derived from token bounds and configured
prices, plus owner-recorded external consumption. They are not provider
invoices and cannot guarantee zero overrun. Reservations are never refunded
automatically: a reservation becomes either FINALIZED (observed usage) or
UNCERTAIN (counted at its full reserved amount).
"""
from django.db import models
from django.db.models import F, Q


class BudgetAccount(models.Model):
    ledger_id = models.UUIDField(unique=True)
    currency = models.CharField(max_length=3, default="USD")
    total_allowance_micro = models.BigIntegerField()
    safety_reserve_micro = models.BigIntegerField(default=0)
    consumed_before_micro = models.BigIntegerField(default=0)
    reserved_micro = models.BigIntegerField(default=0)
    finalized_micro = models.BigIntegerField(default=0)
    uncertain_micro = models.BigIntegerField(default=0)
    emergency_stop = models.BooleanField(default=False)
    model_id = models.CharField(max_length=100)
    input_price_micro_per_mtok = models.BigIntegerField()
    output_price_micro_per_mtok = models.BigIntegerField()
    allowed_environments = models.CharField(max_length=40, default="staging,production")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(currency="USD"), name="ai_ledger_currency_usd"),
            models.CheckConstraint(condition=Q(total_allowance_micro__gt=0), name="ai_ledger_total_positive"),
            models.CheckConstraint(
                condition=Q(safety_reserve_micro__gte=0) & Q(consumed_before_micro__gte=0)
                & Q(reserved_micro__gte=0) & Q(finalized_micro__gte=0) & Q(uncertain_micro__gte=0),
                name="ai_ledger_amounts_nonnegative"),
            models.CheckConstraint(
                condition=Q(input_price_micro_per_mtok__gt=0) & Q(output_price_micro_per_mtok__gt=0),
                name="ai_ledger_prices_positive"),
            models.CheckConstraint(
                condition=Q(reserved_micro__lte=F("total_allowance_micro")),
                name="ai_ledger_reserved_within_total"),
        ]

    def remaining_micro(self):
        return (self.total_allowance_micro - self.safety_reserve_micro - self.consumed_before_micro
                - self.reserved_micro - self.finalized_micro - self.uncertain_micro)


class BudgetReservation(models.Model):
    RESERVED, FINALIZED, UNCERTAIN = "reserved", "finalized", "uncertain"
    STATUS = [(RESERVED, RESERVED), (FINALIZED, FINALIZED), (UNCERTAIN, UNCERTAIN)]

    id = models.UUIDField(primary_key=True)
    account = models.ForeignKey(BudgetAccount, on_delete=models.PROTECT, related_name="reservations")
    environment = models.CharField(max_length=20)
    service_id = models.CharField(max_length=64)
    git_sha = models.CharField(max_length=40)
    actor_id = models.BigIntegerField()
    reserved_micro = models.BigIntegerField()
    observed_micro = models.BigIntegerField(null=True, blank=True)
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=RESERVED)
    outcome = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["account", "status"], name="ai_ledger_res_status")]
        constraints = [
            models.CheckConstraint(condition=Q(reserved_micro__gt=0), name="ai_ledger_res_positive"),
            models.CheckConstraint(condition=Q(environment__in=["staging", "production"]),
                                   name="ai_ledger_res_environment"),
            models.CheckConstraint(condition=Q(status__in=["reserved", "finalized", "uncertain"]),
                                   name="ai_ledger_res_status_valid"),
        ]


class ExternalUsageRecord(models.Model):
    """Owner-recorded consumption observed in the provider billing console."""
    account = models.ForeignKey(BudgetAccount, on_delete=models.PROTECT, related_name="external_usage")
    amount_micro = models.BigIntegerField()
    note = models.CharField(max_length=200)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount_micro__gt=0), name="ai_ledger_ext_positive")]
