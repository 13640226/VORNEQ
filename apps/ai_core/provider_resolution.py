"""V7-01 — Gateway-Auflösung an den bestehenden Konstruktionsgrenzen.

``resolve`` prüft Umgebung, Emergency Stop, Provider/Modell (bekannt, aktiv,
Capability), Feature-Flag, Akteur und die Ledger-Bindung bezahlter Provider.
Das Ergebnis ist **nur eine Auflösung, keine Freigabe**: Ein bezahlter Aufruf
braucht weiterhin die Ledger-Reservierung an der echten Aufrufgrenze
(``BudgetedProvider`` bzw. Image-Worker → ``authorized_paid_call``).

Es gibt in V7-01 kein automatisches Routing und keinen Fallback (COR-09):
mehrdeutige Capabilities verlangen eine ausdrückliche ``provider_id``.
``scope`` ist für künftige Organisations-/Projekt-Scopes reserviert (COR-10);
heute ist nur ``"user"`` zulässig.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from django.conf import settings

from apps.ai_core.provider_registry import (
    CATALOG, LEGACY_ENV_MODEL_PROVIDERS, AuthorizationDenied, BudgetRefused, Capability,
    CapabilityMissing, EmergencyStopActive, InvalidConfiguration, InvalidEnvironment,
    ModelSpec, ModelUnavailable, ProviderDisabled, ProviderSpec, LEGACY_POLICY,
)

KNOWN_ENVIRONMENTS = frozenset({"development", "staging", "production"})
HOSTED_ENVIRONMENTS = frozenset({"staging", "production"})
SCOPES = frozenset({"user"})

# Feature-Flags, die an der jeweiligen Konstruktionsstelle bereits Vorbedingung
# sind (keine neue Sperre). Text-Flags sind je Aufrufer verschieden (Phase B,
# globale Chat-Policy) und bleiben dort (LEGACY_CALL_SITE).
FEATURE_FLAGS = {
    Capability.IMAGE_GENERATION: "VORNEQ_AI_IMAGE_ENABLED",
    Capability.VOICE_MOCK: "VORNEQ_AI_VOICE_ENABLED",
}
LEDGER_BOUNDARIES = {
    "openai-text": "paid_text_provider -> BudgetedProvider -> authorized_paid_call(text)",
    "openai-image": "image worker reserve -> authorized_paid_call(image)",
}


@dataclass(frozen=True)
class Resolution:
    provider: ProviderSpec
    model: ModelSpec | None
    environment: str
    paid: bool
    ledger_boundary: str
    feature_flag: str
    scope: str = "user"

    @property
    def authorizes_paid_call(self) -> bool:
        """Immer False: Auflösen ist nie eine Zahlungsfreigabe."""
        return False


def check_provider(provider_id, capability):
    """Nur Katalogprüfung (bekannt, Capability, aktiv) – PR-#743-Semantik."""
    return CATALOG.provider(provider_id, capability)


def legacy_model_matches(provider_id, capability, model_id, approved_models):
    """Additional catalog check, never a grant or replacement for legacy gates."""
    check_provider(provider_id, capability)
    return (isinstance(model_id, str) and bool(model_id)
            and len(model_id) <= 100 and model_id in approved_models)


def _valid_actor(actor) -> bool:
    if type(actor) is int:
        return actor > 0
    return bool(getattr(actor, "is_authenticated", False) and getattr(actor, "is_active", False)
                and type(getattr(actor, "pk", None)) is int and actor.pk > 0)


def _select_provider(capability, provider_id):
    if not isinstance(capability, Capability):
        raise CapabilityMissing("unknown capability")
    if provider_id is not None:
        return CATALOG.provider(provider_id, capability)
    candidates = [p for p in CATALOG.providers_for(capability) if p.enabled]
    if not candidates:
        raise CapabilityMissing("no provider offers this capability")
    if len(candidates) > 1:
        # Kein stilles Routing/Fallback in V7-01.
        raise InvalidConfiguration("several providers offer this capability; provider_id required")
    return candidates[0]


def _select_model(provider: ProviderSpec, capability, model_id):
    if model_id is None:
        return None
    spec = None
    try:
        spec = CATALOG.model(provider.provider_id, model_id)
    except ModelUnavailable as exc:
        legacy_env = (provider.provider_id in LEGACY_ENV_MODEL_PROVIDERS
                      and type(exc) is ModelUnavailable
                      and isinstance(model_id, str) and model_id
                      and model_id == os.environ.get("VORNEQ_AI_PHASE_B_MODEL", ""))
        if not legacy_env:
            raise
        # Konfiguriertes Text-Modell: Genehmigung bleibt in staging/production_policy.
        return ModelSpec(model_id, provider.provider_id, {capability}, enabled=True,
                         availability_status=LEGACY_POLICY)
    if capability not in spec.capabilities:
        raise CapabilityMissing("model does not offer this capability")
    return spec


def resolve(capability, *, actor, environment, model_id=None, provider_id=None,
            ledger_bound=None, feature_enabled=None, scope="user"):
    """COR-07: validiert die Auflösung; konstruiert nichts, ruft nichts auf.

    ``ledger_bound`` meldet der Aufrufer an der Konstruktionsgrenze:
    ``True`` = Ledger-Pflicht ist erfüllt/gebunden (gehostet), ``False`` = lokale
    Entwicklung ohne Ledger (bezahlte Aufrufe verhindert dort die Aufrufgrenze).
    ``feature_enabled`` übergibt eine Konstruktionsstelle, die ihr Feature-Gate
    (z. B. ``image_generation.policy.enabled``/Worker-Gates) gerade selbst
    ausgewertet hat; ohne Angabe gilt das Settings-Flag aus ``FEATURE_FLAGS``.
    """
    if scope not in SCOPES:
        raise InvalidConfiguration("unsupported scope")
    actual = getattr(settings, "VORNEQ_ENV", None)
    if environment not in KNOWN_ENVIRONMENTS or environment != actual:
        raise InvalidEnvironment("unknown or mismatched environment")
    if getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False):
        raise EmergencyStopActive("emergency stop active")

    provider = _select_provider(capability, provider_id)
    flag = FEATURE_FLAGS.get(capability)
    if feature_enabled is not None:
        if feature_enabled is not True:
            raise ProviderDisabled("feature gate closed")
        flag = f"{flag or 'LEGACY_CALL_SITE'} (evaluated by call site)"
    elif flag is not None and not getattr(settings, flag, False):
        raise ProviderDisabled("feature flag off")
    model = _select_model(provider, capability, model_id)

    if provider.paid:
        if not _valid_actor(actor):
            raise AuthorizationDenied("paid provider requires an authenticated actor")
        if environment in HOSTED_ENVIRONMENTS and ledger_bound is not True:
            raise BudgetRefused("hosted paid provider requires the shared prepaid ledger")
        if ledger_bound not in (True, False):
            raise BudgetRefused("ledger binding not declared")
    elif actor is not None and not isinstance(actor, int) and getattr(actor, "is_active", True) is False:
        raise AuthorizationDenied("inactive actor")

    return Resolution(
        provider=provider, model=model, environment=environment, paid=provider.paid,
        ledger_boundary=LEDGER_BOUNDARIES.get(provider.provider_id, "none (offline mock)"),
        feature_flag=flag or "LEGACY_CALL_SITE", scope=scope,
    )
