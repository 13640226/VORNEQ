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

def resolve_registered_model(provider_id, capability, model_id, *, registry=CATALOG):
    """Resolve an enabled catalog entry; does not authorize any provider call."""
    from apps.ai_core.provider_registry import CapabilityMissing
    registry.provider(provider_id, capability)
    model = registry.model(provider_id, model_id)
    if model.capability != capability:
        raise CapabilityMissing("model capability mismatch")
    return model

class InvalidEnvironment(ValueError):
    pass


class AuthorizationDenied(ValueError):
    pass


def resolve_request(provider_id, capability, model_id, *, actor_id, environment,
                    policy_check, registry=CATALOG):
    """Preflight only; policy must be supplied by the trusted server route.
    Ledger reservation and SDK authorization remain independently mandatory.
    """
    if environment not in ("development", "staging", "production"):
        raise InvalidEnvironment("unsupported environment")
    if type(actor_id) is not int or actor_id <= 0:
        raise AuthorizationDenied("invalid actor")
    model = resolve_registered_model(provider_id, capability, model_id, registry=registry)
    if policy_check() is not True:
        raise AuthorizationDenied("policy denied")
    return model
