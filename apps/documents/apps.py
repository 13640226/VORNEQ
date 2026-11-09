from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documents"
    label = "documents"
    verbose_name = "Documents"

    def ready(self):
        from apps.core.capabilities.artifact_read_policy import artifact_read_policy_registry

        from .artifact_read_policy import DocumentArtifactReadPolicy

        artifact_read_policy_registry.register(DocumentArtifactReadPolicy)
