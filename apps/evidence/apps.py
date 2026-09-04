from django.apps import AppConfig


class EvidenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.evidence"
    label = "evidence"
    verbose_name = "Evidence Domain"

    def ready(self):
        from . import signals  # noqa: F401
