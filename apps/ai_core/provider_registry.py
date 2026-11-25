"""V7-01 — Zentrale Provider- und Modell-Registry (nur Metadaten).

Grundsätze (ADR-0007):

* Ein Eintrag ist **keine** Erlaubnis. Eine Capability im Katalog bedeutet
  nicht, dass sie implementiert, aktiviert oder bezahlt aufrufbar ist.
* Keine Secrets, keine API-Schlüssel, keine Endpunkte mit Zugangsdaten.
* Nicht geprüfte Angaben (Region, Aufbewahrung, DPA, Compliance, Preise,
  Kontextfenster) stehen ausdrücklich auf ``NOT_VERIFIED`` bzw. ``None``.
  ``NOT_VERIFIED`` ist nie eine Aussage über rechtliche Konformität.
* Bestehende Modelle (``LEGACY_POLICY``) bleiben durch ihre bisherige Policy
  (Staging-/Production-/Image-Policy) gesteuert; die Registry ersetzt diese
  Policies nicht und erweitert keine Freigabe.
* Neue bezahlte Modelle lassen sich nur mit verifizierter Preisreferenz
  aktivieren (``Registry``-Validierung, fail-closed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

NOT_VERIFIED = "NOT_VERIFIED"
VERIFIED = "VERIFIED"
NOT_APPLICABLE = "NOT_APPLICABLE"
REVIEW_STATES = frozenset({NOT_VERIFIED, VERIFIED, NOT_APPLICABLE})

# Modell-Governance: wer entscheidet über die Nutzung?
LEGACY_POLICY = "LEGACY_POLICY"      # bestehende Policy-Module (unverändert)
REGISTRY_POLICY = "REGISTRY_POLICY"  # künftige Modelle: Registry-Validierung
AVAILABILITY_STATES = frozenset({LEGACY_POLICY, REGISTRY_POLICY, NOT_VERIFIED, "UNAVAILABLE"})


class Capability(str, Enum):
    """COR-02: fachlich getrennte Fähigkeiten eines Providers."""

    TEXT_GENERATION = "text_generation"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"
    EMBEDDING = "embedding"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    REALTIME_VOICE = "realtime_voice"
    VIDEO_GENERATION = "video_generation"
    MUSIC_GENERATION = "music_generation"
    THREE_D_GENERATION = "three_d_generation"
    # Interne Fähigkeit des Offline-Voice-Mocks (kein echtes Sprachmodell).
    VOICE_MOCK = "voice_mock"
    # Rückwärtskompatible Aliase aus PR #743 (gleicher Wert = Enum-Alias).
    TEXT = "text_generation"
    IMAGE = "image_generation"


class ProviderType(str, Enum):
    EXTERNAL_API = "external_api"
    MOCK = "mock"


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    EVENT = "event"


# --------------------------------------------------------------------- Fehler
# COR-08. Alle Fehler erben von RegistryError (ValueError, kompatibel zu #743).
class RegistryError(ValueError):
    code = "registry_error"


class InvalidConfiguration(RegistryError):
    code = "invalid_configuration"


class ProviderUnavailable(RegistryError):
    code = "provider_unavailable"


class ProviderDisabled(ProviderUnavailable):
    code = "provider_disabled"


class CapabilityMissing(RegistryError):
    code = "capability_missing"


class ModelUnavailable(RegistryError):
    code = "model_unavailable"


class ModelDisabled(ModelUnavailable):
    code = "model_disabled"


class AuthorizationDenied(RegistryError):
    code = "authorization_denied"


class BudgetRefused(RegistryError):
    code = "budget_refused"


class EmergencyStopActive(RegistryError):
    code = "emergency_stop_active"


class InvalidEnvironment(RegistryError):
    code = "invalid_environment"


def _caps(value) -> frozenset:
    if isinstance(value, Capability):
        return frozenset({value})
    return frozenset(value or ())


# ---------------------------------------------------------------------- Specs
@dataclass(frozen=True)
class ProviderSpec:
    """COR-04. Positionsreihenfolge (id, capabilities, paid) wie in PR #743."""

    provider_id: str
    capabilities: frozenset
    paid: bool
    compliance_review_status: str = NOT_VERIFIED
    display_name: str = ""
    provider_type: ProviderType = ProviderType.EXTERNAL_API
    enabled: bool = True
    documentation_url: str | None = None
    data_processing_region: str = NOT_VERIFIED
    data_retention_status: str = NOT_VERIFIED
    dpa_status: str = NOT_VERIFIED
    verified_at: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "capabilities", _caps(self.capabilities))

    @property
    def review_status(self) -> str:  # Alias aus PR #743
        return self.compliance_review_status


@dataclass(frozen=True)
class ModelSpec:
    """COR-05. Positionsreihenfolge (model_id, provider_id, capabilities) wie in #743."""

    model_id: str
    provider_id: str
    capabilities: frozenset
    pricing_reference: str | None = None
    enabled: bool = False
    display_name: str = ""
    input_modalities: frozenset = field(default_factory=frozenset)
    output_modalities: frozenset = field(default_factory=frozenset)
    context_window: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    streaming_supported: bool = False
    tool_calling_supported: bool = False
    structured_output_supported: bool = False
    pricing_verified_at: str | None = None
    availability_status: str = NOT_VERIFIED

    def __post_init__(self):
        object.__setattr__(self, "capabilities", _caps(self.capabilities))
        object.__setattr__(self, "input_modalities", frozenset(self.input_modalities))
        object.__setattr__(self, "output_modalities", frozenset(self.output_modalities))

    @property
    def capability(self):  # Alias aus PR #743 (erste/primäre Fähigkeit)
        return sorted(self.capabilities, key=lambda c: c.value)[0] if self.capabilities else None

    @property
    def legacy(self) -> bool:
        return self.availability_status == LEGACY_POLICY


# ------------------------------------------------------------------- Registry
def _validate_provider(spec: ProviderSpec):
    if not isinstance(spec.provider_id, str) or not spec.provider_id or len(spec.provider_id) > 64:
        raise InvalidConfiguration("invalid provider id")
    if not spec.capabilities or not all(isinstance(c, Capability) for c in spec.capabilities):
        raise InvalidConfiguration(f"{spec.provider_id}: invalid capability")
    if not isinstance(spec.provider_type, ProviderType):
        raise InvalidConfiguration(f"{spec.provider_id}: invalid provider type")
    if spec.provider_type is ProviderType.MOCK and spec.paid:
        raise InvalidConfiguration(f"{spec.provider_id}: a mock provider is never paid")
    for name in ("compliance_review_status", "data_retention_status", "dpa_status"):
        if getattr(spec, name) not in REVIEW_STATES:
            raise InvalidConfiguration(f"{spec.provider_id}: {name} must be one of {sorted(REVIEW_STATES)}")
    claims_verified = VERIFIED in (spec.compliance_review_status, spec.data_retention_status, spec.dpa_status)
    if claims_verified and not (spec.verified_at and spec.documentation_url):
        raise InvalidConfiguration(f"{spec.provider_id}: VERIFIED requires verified_at and documentation_url")


def _validate_model(spec: ModelSpec, provider: ProviderSpec | None):
    if not isinstance(spec.model_id, str) or not spec.model_id or len(spec.model_id) > 100:
        raise InvalidConfiguration("invalid model id")
    if provider is None:
        raise InvalidConfiguration(f"{spec.model_id}: unknown provider {spec.provider_id}")
    if not spec.capabilities or not all(isinstance(c, Capability) for c in spec.capabilities):
        raise InvalidConfiguration(f"{spec.model_id}: invalid capability")
    if not spec.capabilities <= provider.capabilities:
        raise InvalidConfiguration(f"{spec.model_id}: capability not offered by {provider.provider_id}")
    if spec.availability_status not in AVAILABILITY_STATES:
        raise InvalidConfiguration(f"{spec.model_id}: invalid availability status")
    for name in ("context_window", "max_input_tokens", "max_output_tokens"):
        value = getattr(spec, name)
        if value is not None and (type(value) is not int or value <= 0):
            raise InvalidConfiguration(f"{spec.model_id}: {name} must be a positive int or None")
    # COR-06: neue bezahlte Modelle nur mit verifizierter Preisreferenz.
    if spec.enabled and provider.paid and not spec.legacy:
        if not spec.pricing_reference or not spec.pricing_verified_at:
            raise InvalidConfiguration(f"{spec.model_id}: paid model requires a verified pricing reference")


class Registry:
    def __init__(self, providers, models=()):
        self._providers: dict[str, ProviderSpec] = {}
        self._models: dict[tuple[str, str], ModelSpec] = {}
        for spec in providers:
            _validate_provider(spec)
            if spec.provider_id in self._providers:
                raise InvalidConfiguration(f"duplicate provider {spec.provider_id}")
            self._providers[spec.provider_id] = spec
        for spec in models:
            _validate_model(spec, self._providers.get(spec.provider_id))
            key = (spec.provider_id, spec.model_id)
            if key in self._models:
                raise InvalidConfiguration(f"duplicate model {spec.provider_id}/{spec.model_id}")
            self._models[key] = spec

    # Lesende Abfragen ------------------------------------------------------
    def providers(self):
        return tuple(self._providers.values())

    def models(self, provider_id: str | None = None):
        return tuple(m for m in self._models.values() if provider_id in (None, m.provider_id))

    def provider(self, provider_id, capability):
        """Provider für eine Capability; deaktivierte Provider sind nie nutzbar."""
        spec = self._providers.get(provider_id)
        if spec is None:
            raise ProviderUnavailable("unknown provider")
        if not isinstance(capability, Capability) or capability not in spec.capabilities:
            raise CapabilityMissing("unsupported capability")
        if not spec.enabled:
            raise ProviderDisabled("provider disabled")
        return spec

    def model(self, provider_id, model_id):
        spec = self._models.get((provider_id, model_id))
        if spec is None:
            raise ModelUnavailable("unknown model")
        if not spec.enabled:
            raise ModelDisabled("model disabled")
        return spec

    def provider_spec(self, provider_id):
        """Rohdaten ohne Aktiv-/Capability-Prüfung (nur für Berichte)."""
        spec = self._providers.get(provider_id)
        if spec is None:
            raise ProviderUnavailable("unknown provider")
        return spec

    def providers_for(self, capability):
        return tuple(p for p in self._providers.values() if capability in p.capabilities)


# -------------------------------------------------------------------- Katalog
# Bestehende, von der Image-Policy genehmigte OpenAI-Bildmodelle (bisher
# ``image_generation.policy.MODELS``; Werte unverändert übernommen). Preise und
# Verfügbarkeit sind in dieser Registry nicht verifiziert: die Kostenobergrenze
# setzen weiterhin Ledger-Reservierung und VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD.
LEGACY_OPENAI_IMAGE_MODELS = frozenset({
    "gpt-image-2", "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst", "gpt-image-2.6-flare",
    "gpt-image-2.6-sunburst",
})

_PROVIDERS = (
    ProviderSpec("openai-text", {Capability.TEXT_GENERATION}, True,
                 display_name="OpenAI Responses (Text)"),
    ProviderSpec("openai-image", {Capability.IMAGE_GENERATION}, True,
                 display_name="OpenAI Images"),
    ProviderSpec("mock-image", {Capability.IMAGE_GENERATION}, False,
                 compliance_review_status=NOT_APPLICABLE, display_name="Mock image (offline)",
                 provider_type=ProviderType.MOCK, data_processing_region="local",
                 data_retention_status=NOT_APPLICABLE, dpa_status=NOT_APPLICABLE),
    ProviderSpec("mock-voice", {Capability.VOICE_MOCK}, False,
                 compliance_review_status=NOT_APPLICABLE, display_name="Mock voice (offline)",
                 provider_type=ProviderType.MOCK, data_processing_region="local",
                 data_retention_status=NOT_APPLICABLE, dpa_status=NOT_APPLICABLE),
)

_MODELS = tuple(
    ModelSpec(model_id, "openai-image", {Capability.IMAGE_GENERATION}, enabled=True,
              input_modalities={Modality.TEXT}, output_modalities={Modality.IMAGE},
              availability_status=LEGACY_POLICY)
    for model_id in sorted(LEGACY_OPENAI_IMAGE_MODELS)
) + (
    ModelSpec("mock", "mock-image", {Capability.IMAGE_GENERATION}, enabled=True,
              display_name="Mock PNG", input_modalities={Modality.TEXT},
              output_modalities={Modality.IMAGE}, availability_status=LEGACY_POLICY),
    ModelSpec("mock", "mock-voice", {Capability.VOICE_MOCK}, enabled=True,
              display_name="Mock voice echo", input_modalities={Modality.EVENT},
              output_modalities={Modality.EVENT}, availability_status=LEGACY_POLICY),
)

CATALOG = Registry(_PROVIDERS, _MODELS)

# Das Text-Modell steht nicht im Code: es kommt aus VORNEQ_AI_PHASE_B_MODEL und
# wird von staging_policy/production_policy exakt gegen das genehmigte Modell
# geprüft (LEGACY_POLICY, siehe ``configured_models``).
LEGACY_ENV_MODEL_PROVIDERS = frozenset({"openai-text"})


def configured_models(settings, environ):
    """Inventory only: configuration is not availability or paid authorization."""
    entries = (
        ("openai-text", environ.get("VORNEQ_AI_PHASE_B_MODEL", ""), Capability.TEXT_GENERATION),
        ("openai-image", getattr(settings, "VORNEQ_AI_IMAGE_MODEL", ""), Capability.IMAGE_GENERATION),
    )
    return tuple(ModelSpec(model, provider, capability)
                 for provider, model, capability in entries
                 if isinstance(model, str) and model)
