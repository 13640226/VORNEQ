"""Registry checks at existing construction boundaries; no new paid route."""
from apps.ai_core.provider_registry import CATALOG, Capability

def resolve(provider_id, capability):
    """Resolve metadata only. Existing actor, environment and ledger gates apply."""
    return CATALOG.provider(provider_id, capability)


def legacy_model_matches(provider_id, capability, model_id, approved_models):
    """Additional catalog check, never a grant or replacement for legacy gates."""
    resolve(provider_id, capability)
    return (isinstance(model_id, str) and bool(model_id)
            and len(model_id) <= 100 and model_id in approved_models)
