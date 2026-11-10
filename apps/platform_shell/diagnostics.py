"""CAP-ACTOR-02 — staging-only runtime diagnostic for trusted actor binding.

Purpose: prove over a real HTTP request in staging that the actor chain

    request.user -> IdentityResolver.resolve -> BoundActor.from_request
        -> CapabilityInvoker (BoundActor.revalidate) -> capability policy

works with the deployed settings, middleware and session handling.

Guarantees:
* Registered only when VORNEQ_ENV == "staging" AND the dedicated flag is on
  AND a valid diagnostic Identity id is configured (see ``diagnostics_enabled``).
  The view re-checks the same gate and answers 404 otherwise.
* The only permitted caller is the single diagnostic Identity configured on
  the server. Nothing from the query string, body or headers is consulted.
* A private invoker with its own registry runs one probe capability. The
  global capability registry is untouched, and no business capability can be
  reached from here.
* Reads only the caller's auth/binding rows (via the resolver). No writes to
  the database, storage, queues or external services. Denials are uniform and
  disclose no identifiers.
"""

import hmac
import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .capabilities import (
    BaseCapability,
    BoundActor,
    CapabilityContext,
    CapabilityInvoker,
    ExecutableCapabilityRegistry,
)
from .registry import AppManifest, PlatformRegistry


logger = logging.getLogger(__name__)

DIAGNOSTIC_VERSION = "CAP_ACTOR_02_V1"
DIAGNOSTIC_CHECK = "trusted_actor_binding"
PROBE_CAPABILITY = "diagnostic_actor_probe_v1"

# Best-effort, per-process when no Redis cache is configured.
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60


def configured_identity_id():
    """The single diagnostic Identity id from server settings, or None."""
    raw = getattr(settings, "VORNEQ_ACTOR_DIAGNOSTICS_IDENTITY_ID", "") or ""
    try:
        return str(uuid.UUID(str(raw).strip()))
    except (ValueError, AttributeError):
        return None


def _shared_redis_configured():
    """Never enable the staging diagnostic on a per-process local cache."""
    url = getattr(settings, "REDIS_URL", None)
    backend = getattr(settings, "CACHES", {}).get("default", {}).get("BACKEND")
    return bool(url and str(url).startswith(("redis://", "rediss://"))) and backend == (
        "django.core.cache.backends.redis.RedisCache"
    )


def diagnostics_enabled():
    """Fail-closed gate shared by URL registration and the view."""
    return (
        getattr(settings, "VORNEQ_ENV", None) == "staging"
        and getattr(settings, "VORNEQ_ACTOR_DIAGNOSTICS_ENABLED", False) is True
        and configured_identity_id() is not None
        and _shared_redis_configured()
    )


def _is_diagnostic_actor(actor):
    expected = configured_identity_id()
    if expected is None or not isinstance(actor, BoundActor):
        return False
    return hmac.compare_digest(str(actor.identity_id), expected)


@dataclass(frozen=True)
class ProbeInput:
    pass


@dataclass(frozen=True)
class ProbeOutput:
    check: str


class DiagnosticActorProbe(BaseCapability[ProbeInput, ProbeOutput]):
    """Constant, non-sensitive output; touches no business data."""

    name = PROBE_CAPABILITY
    input_schema = ProbeInput
    output_schema = ProbeOutput

    def authorize(self, context, input_data):
        return _is_diagnostic_actor(context.actor)

    def execute(self, context, input_data):
        return ProbeOutput(check=DIAGNOSTIC_CHECK)


def build_diagnostic_invoker():
    """Private registry containing only the probe capability."""
    platform_registry = PlatformRegistry()
    platform_registry.register(
        AppManifest(
            slug="actor-diagnostics",
            label="Actor diagnostics",
            url_name="health",
            show_in_primary_nav=False,
            requires_authentication=True,
            capabilities=(PROBE_CAPABILITY,),
        )
    )
    registry = ExecutableCapabilityRegistry(platform_registry)
    registry.register(DiagnosticActorProbe)
    return CapabilityInvoker(registry)


def _deny(status=403):
    return JsonResponse({"status": "deny"}, status=status)


class RateLimitUnavailable(Exception):
    """The rate-limit store cannot be reached; the endpoint must fail closed."""


def _rate_limited(request):
    """Return True when over the limit; raise RateLimitUnavailable on cache failure.

    Every cache operation is inside the guard: with Redis down, ``cache.add``
    itself raises (CAP-ACTOR-02 local finding, 2026-11-10). A cache failure
    never lets a request through.
    """
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        subject = f"u:{user.pk}"
    else:
        subject = f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
    key = f"vorneq:actor-diag:{subject}"
    try:
        cache.add(key, 0, timeout=RATE_LIMIT_WINDOW_SECONDS)
        try:
            count = cache.incr(key)
        except ValueError as exc:
            # Expiry race: never overwrite a counter incremented by a
            # concurrent request. Fail closed and retry on a fresh request.
            raise RateLimitUnavailable from exc
    except Exception as exc:  # any backend error (e.g. redis ConnectionError)
        raise RateLimitUnavailable from exc
    return count > RATE_LIMIT_REQUESTS


@never_cache
@require_GET
def actor_binding_diagnostic(request):
    if not diagnostics_enabled():
        raise Http404()

    try:
        limited = _rate_limited(request)
    except RateLimitUnavailable:
        logger.error("actor diagnostics: unavailable (rate-limit store)")
        return JsonResponse({"status": "unavailable"}, status=503)
    if limited:
        logger.warning("actor diagnostics: rate_limited")
        return _deny(status=429)

    try:
        # The actor comes from the session only; request data is never read.
        actor = BoundActor.from_request(request)
    except PermissionDenied:
        logger.info("actor diagnostics: deny (binding)")
        return _deny()

    if not _is_diagnostic_actor(actor):
        logger.info("actor diagnostics: deny (not diagnostic identity)")
        return _deny()

    result = build_diagnostic_invoker().invoke(
        PROBE_CAPABILITY,
        context=CapabilityContext(actor=actor, request_id=uuid.uuid4().hex),
        input_data=ProbeInput(),
    )
    if not result.success or result.data != ProbeOutput(check=DIAGNOSTIC_CHECK):
        logger.info("actor diagnostics: deny (invoker)")
        return _deny()

    logger.info("actor diagnostics: pass")
    return JsonResponse(
        {"status": "pass", "check": DIAGNOSTIC_CHECK, "version": DIAGNOSTIC_VERSION}
    )


def diagnostics_urlpatterns():
    """URL patterns to add to the root URLconf; empty unless the gate is open."""
    from django.urls import path

    if not diagnostics_enabled():
        return []
    return [
        path(
            "internal/diagnostics/actor-binding/",
            actor_binding_diagnostic,
            name="actor_binding_diagnostic",
        )
    ]
