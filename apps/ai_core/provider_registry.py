from dataclasses import dataclass
from enum import Enum

class Capability(str, Enum):
    TEXT = "text_generation"
    IMAGE = "image_generation"
    VOICE_MOCK = "voice_mock"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    IMAGE_EDITING = "image_editing"
    EMBEDDING = "embedding"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    REALTIME_VOICE = "realtime_voice"
    VIDEO_GENERATION = "video_generation"
    MUSIC_GENERATION = "music_generation"
    THREE_D_GENERATION = "three_d_generation"

@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    capabilities: frozenset[Capability]
    paid: bool
    review_status: str = "NOT_VERIFIED"
    display_name: str = ""
    documentation_url: str | None = None
    data_processing_region: str = "NOT_VERIFIED"
    data_retention_status: str = "NOT_VERIFIED"
    dpa_status: str = "NOT_VERIFIED"
    verified_at: str | None = None

@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    provider_id: str
    capability: Capability
    pricing_reference: str | None = None
    enabled: bool = False
    display_name: str = ""
    context_window: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    pricing_verified_at: str | None = None
    availability_status: str = "NOT_VERIFIED"

class RegistryError(ValueError):
    pass

class ProviderUnavailable(RegistryError):
    pass

class CapabilityMissing(RegistryError):
    pass

class ModelUnavailable(RegistryError):
    pass

class ModelDisabled(RegistryError):
    pass

class Registry:
    def __init__(self, providers, models=()):
        self._providers = {}
        self._models = {}
        for spec in providers:
            if not spec.provider_id or spec.provider_id in self._providers or not spec.capabilities:
                raise ValueError("invalid or duplicate provider")
            self._providers[spec.provider_id] = spec
        for spec in models:
            key = (spec.provider_id, spec.model_id)
            provider = self._providers.get(spec.provider_id)
            if not spec.model_id or key in self._models or provider is None or spec.capability not in provider.capabilities:
                raise ValueError("invalid or duplicate model")
            if spec.enabled and provider.paid and not spec.pricing_reference:
                raise ValueError("paid model requires pricing reference")
            self._models[key] = spec

    def provider(self, provider_id, capability):
        spec = self._providers.get(provider_id)
        if spec is None:
            raise ProviderUnavailable("unknown provider")
        if capability not in spec.capabilities:
            raise CapabilityMissing("unsupported capability")
        return spec

    def model(self, provider_id, model_id):
        spec = self._models.get((provider_id, model_id))
        if spec is None:
            raise ModelUnavailable("unknown model")
        if not spec.enabled:
            raise ModelDisabled("model disabled")
        return spec

CATALOG = Registry((
    ProviderSpec("openai-text", frozenset({Capability.TEXT}), True),
    ProviderSpec("openai-image", frozenset({Capability.IMAGE}), True),
    ProviderSpec("mock-image", frozenset({Capability.IMAGE}), False),
    ProviderSpec("mock-voice", frozenset({Capability.VOICE_MOCK}), False),
))



def configured_models(settings, environ):
    """Inventory only: configuration is not availability or paid authorization."""
    entries = (
        ("openai-text", environ.get("VORNEQ_AI_PHASE_B_MODEL", ""), Capability.TEXT),
        ("openai-image", getattr(settings, "VORNEQ_AI_IMAGE_MODEL", ""), Capability.IMAGE),
    )
    return tuple(ModelSpec(model, provider, capability)
                 for provider, model, capability in entries
                 if isinstance(model, str) and model)
