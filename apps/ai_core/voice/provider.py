"""Mock Voice provider. Deterministic, offline, never paid."""
from __future__ import annotations

from django.conf import settings


class VoiceProviderBlocked(Exception):
    pass


class MockVoiceProvider:
    name = "mock"
    paid = False

    def respond(self, event_type: str, size: int) -> dict:
        # Only sizes are echoed; no audio or text content is stored or logged.
        return {"type": "mock_response", "received": event_type, "size": size,
                "provider": self.name, "paid": False}


def get_provider() -> MockVoiceProvider:
    if getattr(settings, "VORNEQ_AI_VOICE_PROVIDER", "mock") != "mock":
        raise VoiceProviderBlocked("only the mock Voice provider exists in this release")
    from apps.ai_core.provider_registry import Capability, RegistryError
    from apps.ai_core.provider_resolution import resolve
    try:
        resolve(Capability.VOICE_MOCK, actor=None, environment=getattr(settings, "VORNEQ_ENV", ""),
                provider_id="mock-voice", model_id="mock")
    except RegistryError as exc:
        raise VoiceProviderBlocked(f"voice provider resolution refused: {exc.code}") from None
    return MockVoiceProvider()
