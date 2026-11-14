from django.apps import AppConfig


class AILedgerConfig(AppConfig):
    name = "apps.ai_ledger"
    label = "ai_ledger"
    verbose_name = "Shared AI prepaid budget ledger"
    default_auto_field = "django.db.models.BigAutoField"
