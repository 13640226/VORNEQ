from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    label = "content"
    verbose_name = "Content"

    def ready(self):
        # The Registry owns binding validation, while each vertical explicitly
        # declares its supported target. This keeps Article registration on the
        # existing register_artifact() path without duplicating registry logic.
        from apps.core.models import ArtifactBinding

        ArtifactBinding.ALLOWED_TARGETS.add(("content", "article"))
