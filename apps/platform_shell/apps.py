from django.apps import AppConfig


class PlatformShellConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform_shell"
    verbose_name = "VORNEQ Platform Shell"

    def ready(self):
        from .registry import autodiscover

        autodiscover()
