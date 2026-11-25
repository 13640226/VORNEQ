from django.core.management.base import BaseCommand
from apps.ai_core.provider_registry import CATALOG, Capability

class Command(BaseCommand):
    help = "Read-only provider catalog; no network or secret output."

    def handle(self, *args, **options):
        for provider_id, capability in (
            ("openai-text", Capability.TEXT),
            ("openai-image", Capability.IMAGE),
            ("mock-image", Capability.IMAGE),
            ("mock-voice", Capability.VOICE_MOCK),
        ):
            spec = CATALOG.provider(provider_id, capability)
            self.stdout.write(f"{spec.provider_id}: {capability.value}; paid={spec.paid}; review={spec.review_status}")

        from django.conf import settings
        from os import environ
        from apps.ai_core.provider_registry import configured_models
        for spec in configured_models(settings, environ):
            self.stdout.write(f"{spec.provider_id}: configured model present; registry activation=False; pricing=NOT_VERIFIED")
