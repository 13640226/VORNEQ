from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core Reputation"

    def ready(self):
        from . import signals  # noqa: F401
        from .capabilities import ReadArtifactCapability
        from apps.platform_shell.capabilities import executable_registry

        executable_registry.register(ReadArtifactCapability)
