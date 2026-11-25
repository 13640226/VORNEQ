"""V7-01 (COR-13) — schreibgeschützter Gateway-Bericht.

Liest nur den Code-Katalog und Django-Settings: keine Datenbankabfrage, kein
Netzwerk, keine Secrets. Für Umgebungsvariablen wird ausschließlich
PRESENT/MISSING ausgegeben, nie ein Wert; Modellnamen aus der Umgebung werden
nicht gedruckt.
"""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_core.provider_registry import CATALOG, Capability, RegistryError
from apps.ai_core.provider_resolution import FEATURE_FLAGS, KNOWN_ENVIRONMENTS, LEDGER_BOUNDARIES

# Nur Namen; Werte werden nie ausgegeben.
CONFIG_PRESENCE = {
    "openai-text": ("OPENAI_API_KEY", "VORNEQ_AI_PHASE_B_MODEL"),
    "openai-image": ("VORNEQ_OPENAI_IMAGE_API_KEY",),
}


def _presence(name):
    value = os.environ.get(name, "")
    return "PRESENT" if isinstance(value, str) and value.strip() else "MISSING"


def _disabled_reasons(provider):
    reasons = []
    if not provider.enabled:
        reasons.append("provider_disabled")
    if getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False):
        reasons.append("emergency_stop_active")
    for capability in sorted(provider.capabilities, key=lambda c: c.value):
        flag = FEATURE_FLAGS.get(capability)
        if flag and not getattr(settings, flag, False):
            reasons.append(f"feature_flag_off:{flag}")
    return reasons


def build_report():
    environment = getattr(settings, "VORNEQ_ENV", None)
    providers = []
    for spec in CATALOG.providers():
        providers.append({
            "provider_id": spec.provider_id,
            "display_name": spec.display_name,
            "provider_type": spec.provider_type.value,
            "capabilities": sorted(c.value for c in spec.capabilities),
            "enabled": spec.enabled,
            "paid": spec.paid,
            "documentation_url": spec.documentation_url,
            "data_processing_region": spec.data_processing_region,
            "data_retention_status": spec.data_retention_status,
            "dpa_status": spec.dpa_status,
            "compliance_review_status": spec.compliance_review_status,
            "verified_at": spec.verified_at,
            "configuration": {name: _presence(name) for name in CONFIG_PRESENCE.get(spec.provider_id, ())},
            "ledger_boundary": LEDGER_BOUNDARIES.get(spec.provider_id, "none (offline mock)"),
            "disabled_reasons": _disabled_reasons(spec),
            "call_conditions": (["actor_authenticated", "ledger_reservation_at_call_boundary",
                                 "existing_feature_policy"] if spec.paid else ["existing_feature_policy"]),
        })
    models = [{
        "model_id": m.model_id,
        "provider_id": m.provider_id,
        "capabilities": sorted(c.value for c in m.capabilities),
        "enabled": m.enabled,
        "availability_status": m.availability_status,
        "pricing_reference": (m.pricing_reference or "NOT_VERIFIED")
        if CATALOG.provider_spec(m.provider_id).paid else "NOT_APPLICABLE",
        "pricing_verified_at": m.pricing_verified_at,
        "context_window": m.context_window,
    } for m in CATALOG.models()]
    capabilities = {
        c.value: sorted(p.provider_id for p in CATALOG.providers_for(c)) or ["NOT_IMPLEMENTED"]
        for c in Capability
    }
    return {
        "environment": environment if environment in KNOWN_ENVIRONMENTS else "INVALID",
        "emergency_stop": bool(getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False)),
        "providers": providers,
        "models": models,
        "legacy_env_models": {"openai-text": "configured via VORNEQ_AI_PHASE_B_MODEL; "
                                             "approval stays in staging/production policy"},
        "capabilities": capabilities,
        "ledger_boundary_status": {
            "text": "paid_text_provider only (AST guard); BudgetedProvider reserve/settle",
            "image": "image worker reserve before OpenAIImageProvider (AST guard)",
            "call_guard": "authorized_paid_call requires a structurally valid reservation",
            "fallback": "none (V7-01)",
        },
        "registry_activation_note": "A catalog entry is not an authorization to call a provider.",
    }


class Command(BaseCommand):
    help = "Read-only provider/model registry report; no database writes, network or secrets."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="machine-readable output")

    def handle(self, *args, **options):
        try:
            report = build_report()
        except RegistryError as exc:  # pragma: no cover - katalog ist beim Import validiert
            self.stderr.write(f"registry invalid: {exc.code}")
            raise SystemExit(2)
        if options.get("json"):
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return
        self.stdout.write(f"environment: {report['environment']}  emergency_stop: {report['emergency_stop']}")
        for p in report["providers"]:
            self.stdout.write(
                f"provider {p['provider_id']}: {','.join(p['capabilities'])}; type={p['provider_type']}; "
                f"enabled={p['enabled']}; paid={p['paid']}; dpa={p['dpa_status']}; "
                f"compliance={p['compliance_review_status']}; config={p['configuration'] or '-'}; "
                f"ledger={p['ledger_boundary']}; disabled_reasons={p['disabled_reasons'] or '-'}; "
                f"conditions={','.join(p['call_conditions'])}")
        for m in report["models"]:
            self.stdout.write(
                f"model {m['provider_id']}/{m['model_id']}: enabled={m['enabled']}; "
                f"governance={m['availability_status']}; pricing={m['pricing_reference']}")
        self.stdout.write("legacy env model openai-text: " + report["legacy_env_models"]["openai-text"])
        missing = [c for c, ps in report["capabilities"].items() if ps == ["NOT_IMPLEMENTED"]]
        self.stdout.write("capabilities without provider: " + ", ".join(missing))
        self.stdout.write(report["registry_activation_note"])
