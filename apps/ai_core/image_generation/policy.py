"""Fail-closed image feature policy, entirely independent of chat permissions."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import uuid
from django.conf import settings
from apps.ai_core.provider_registry import LEGACY_OPENAI_IMAGE_MODELS
from apps.ai_core.provider_resolution import legacy_model_matches, Capability
from apps.ai_core.deploy_authorization import image_release_allowed

STAGING_SERVICE_ID = "srv-dbm7dvc9v7es7393g70g"
PRODUCTION_SERVICE_ID = "srv-dadn07eq1p3s73eccau0"
_WORKER_ID = re.compile(r"srv-[a-z0-9]{20,32}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_OWNER = re.compile(r"OWNER-AUTH-AI-IMAGE-STAGING-[A-Z0-9-]{6,100}\Z")
_PAID_WORKER_OWNER = re.compile(r"OWNER-AUTH-AI-IMAGE-PAID-WORKER-STAGING-[A-Z0-9-]{6,100}\Z")
# V7-01: einzige Quelle ist die Registry (Werte unverändert).
MODELS = LEGACY_OPENAI_IMAGE_MODELS
SIZES = frozenset({"1024x1024", "1536x1024", "1024x1536"})
# Official OpenAI list prices in micro-USD per 1M tokens: (text input, image output).
# Source: developers.openai.com/api/docs/pricing, checked 2026-11-20. The image
# ledger account must carry exactly these prices; any drift is NO_GO.
OFFICIAL_PRICES_MICRO_PER_MTOK = {
    "gpt-image-2.6-flare": (5_000_000, 30_000_000),
    "gpt-image-2.6-sunburst": (5_000_000, 30_000_000),
}
MAX_REQUEST_CEILING_MICRO = 1_000_000       # hard code ceiling per paid request: 1 USD
_SAFETY_KEY_MIN = 32


def safety_key_ready():
    key = getattr(settings, "VORNEQ_AI_IMAGE_SAFETY_ID_KEY", "")
    return isinstance(key, str) and len(key.strip()) >= _SAFETY_KEY_MIN


def safety_identifier(user_id):
    """Stable, non-reversible per-user identifier for OpenAI abuse monitoring.

    HMAC-SHA256 with a server-side secret: neither the raw user ID nor a
    guessable plain hash is ever sent to the provider.
    """
    if not safety_key_ready() or type(user_id) is not int or user_id <= 0:
        return None
    key = settings.VORNEQ_AI_IMAGE_SAFETY_ID_KEY.strip().encode("utf-8")
    digest = hmac.new(key, "vorneq.image.v1:{}".format(user_id).encode("ascii"),
                      hashlib.sha256).hexdigest()
    return "vq_" + digest


def max_request_micro():
    value = getattr(settings, "VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD", 0)
    return value if type(value) is int and 1 <= value <= MAX_REQUEST_CEILING_MICRO else None


def _ids():
    raw = getattr(settings, "VORNEQ_AI_IMAGE_ALLOWED_USER_IDS", "")
    if not isinstance(raw, str) or not raw or len(raw) > 250:
        return set()
    bits = raw.split(",")
    if len(bits) > 5 or any(
        not part.isascii() or not part.isdecimal() or not 1 <= len(part) <= 12
        for part in bits
    ):
        return set()
    values = [int(x) for x in bits]
    return set(values) if len(set(values)) == len(values) and min(values) > 0 else set()


_PRODUCTION_OWNER = re.compile(r"OWNER-AUTH-AI-IMAGE-PRODUCTION-[A-Z0-9-]{6,100}\Z")


def production_release_identity():
    """Read-only Production identity check; never grants provider access."""
    from apps.ai_core.deploy_authorization import SHA, _verified_release
    expected = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA", "")
    owner = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH", "")
    ids = getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS", "")
    live = os.getenv("RENDER_GIT_COMMIT", "")
    if not (
        getattr(settings, "VORNEQ_ENV", "") == "production"
        and getattr(settings, "DEBUG", True) is False
        and os.getenv("RENDER_SERVICE_ID") == PRODUCTION_SERVICE_ID
        and isinstance(expected, str) and SHA.fullmatch(expected)
        and live == expected
        and isinstance(owner, str) and _PRODUCTION_OWNER.fullmatch(owner)
        and ids == "1"
        and os.getenv("VORNEQ_AI_DEPLOY_READ_TOKEN", "")
    ):
        return False
    return _verified_release("production", live) is True

def production_uncapped_budget_requested():
    """Owner-approved policy intent, not a ledger or provider bypass.

    A future independent Production ledger implementation must consume this
    only after validating owner, SHA, actor, service and deployment evidence.
    Never consult this flag for Staging, chat, or paid-provider authorization.
    """
    return (
        getattr(settings, "VORNEQ_ENV", "") == "production"
        and getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET", False) is True
        and getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_ENABLED", False) is True
        and getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", True) is False
        and production_release_identity() is True
    )

def production_readiness():
    """Read-only, fail-closed foundation for a future Production image rollout.

    This is NOT a provider authorization: Production paid web/worker policies,
    independent deployment attestation and prepaid ledger controls are not yet
    implemented. No combination of env vars may open those routes in this PR.
    """
    return {
        "environment": getattr(settings, "VORNEQ_ENV", "") == "production",
        "production_switch": getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_ENABLED", False) is True,
        "ui_switch": getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED", False) is True,
        "emergency_stop_clear": getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", True) is False,
        "debug_off": getattr(settings, "DEBUG", True) is False,
        "production_service": os.getenv("RENDER_SERVICE_ID") == PRODUCTION_SERVICE_ID,
        "production_release_identity": (getattr(settings, "VORNEQ_AI_IMAGE_PRODUCTION_ENABLED", False) is True
                                        and production_release_identity()),
        "production_uncapped_budget_requested": production_uncapped_budget_requested(),
        "production_paid_policy_implemented": False,
        "production_worker_authorized": False,
    }


def production_enabled():
    """No Production image API until independent paid/worker release gates exist."""
    return all(production_readiness().values())

def enabled():
    """No staging or production access can be unlocked by the chat AI flag."""
    if not getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False):
        return False
    if getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False):
        return False
    provider = getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "")
    if provider not in ("mock", "openai"):
        return False
    env = getattr(settings, "VORNEQ_ENV", "")
    if env == "development":
        return provider == "mock" and not (
            os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID")
        )
    if env != "staging" or getattr(settings, "DEBUG", True):
        return False
    expected = getattr(settings, "VORNEQ_AI_IMAGE_AUTHORIZED_SHA", "")
    owner = getattr(settings, "VORNEQ_AI_IMAGE_OWNER_AUTH", "")
    return bool(
        os.getenv("RENDER_SERVICE_ID") == STAGING_SERVICE_ID
        and image_release_allowed(expected)
        and isinstance(owner, str) and _OWNER.fullmatch(owner)
        and _ids()
    )


def _worker_identity(owner_setting, owner_pattern):
    """Separate Render Worker identity: own service ID, pinned SHA, owner grant."""
    worker_id = getattr(settings, "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID", "")
    expected = getattr(settings, "VORNEQ_AI_IMAGE_AUTHORIZED_SHA", "")
    owner = getattr(settings, owner_setting, "")
    return bool(
        isinstance(worker_id, str) and _WORKER_ID.fullmatch(worker_id)
        and worker_id not in (STAGING_SERVICE_ID, PRODUCTION_SERVICE_ID)
        and os.getenv("RENDER_SERVICE_ID") == worker_id
        and image_release_allowed(expected, worker=True)
        and isinstance(owner, str) and owner_pattern.fullmatch(owner)
        and _ids()
    )


def worker_enabled():
    """Explicitly separate, MOCK-ONLY background-worker identity.

    A Render worker never inherits the web-service grant. Its own service ID
    must be configured after separately authorized provisioning. No Production
    or paid-worker route is granted by this function (see paid_worker_enabled).
    """
    if (not getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False)
            or getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False)
            or getattr(settings, "VORNEQ_ENV", "") != "staging"
            or getattr(settings, "DEBUG", True)
            or getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") != "mock"
            or getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False)):
        return False
    return _worker_identity("VORNEQ_AI_IMAGE_OWNER_AUTH", _OWNER)


def paid_worker_enabled():
    """Separate PAID Staging Worker. Default OFF; never Production.

    Requires its own switch and its own owner grant (the web grant and the
    mock-worker grant are never sufficient), the separate worker identity and
    every paid-provider control. Mutually exclusive with worker_enabled().
    """
    if (not getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False)
            or getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False)
            or getattr(settings, "VORNEQ_ENV", "") != "staging"
            or getattr(settings, "DEBUG", True)
            or getattr(settings, "VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED", False) is not True):
        return False
    if not _worker_identity("VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH", _PAID_WORKER_OWNER):
        return False
    return _paid_controls_ready()


def actor_allowed(user, *, worker=False):
    gate = (worker_enabled() or paid_worker_enabled()) if worker else enabled()
    if not gate or not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    ):
        return False
    if getattr(settings, "VORNEQ_ENV", "") == "development":
        return True
    return getattr(user, "pk", None) in _ids()


def image_ledger_config():
    """Image model needs its OWN ledger account, never the chat account."""
    from apps.ai_ledger.service import LedgerConfig, ledger_configuration
    chat = ledger_configuration()
    raw = getattr(settings, "VORNEQ_AI_IMAGE_LEDGER_ID", "")
    try:
        image_id = uuid.UUID(str(raw))
    except (ValueError, TypeError) as exc:
        raise ValueError("image ledger ID is unconfigured") from exc
    if image_id == chat.ledger_id:
        raise ValueError("image and chat ledger must be separate")
    return LedgerConfig(image_id, chat.expected_db_name)


def paid_provider_enabled():
    """Paid route on the Staging WEB service (submit, one-use smoke)."""
    if not enabled() or getattr(settings, "VORNEQ_ENV", "") != "staging":
        return False
    return _paid_controls_ready()


def prepaid_only_requested():
    """Never apply a chat setting, mock setting or Production flag to images."""
    return (
        getattr(settings, "VORNEQ_ENV", "") == "staging"
        and getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") == "openai"
        and getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False) is True
        and getattr(settings, "VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY", False) is True
    )


def _paid_controls_ready():
    """Every paid-provider control except the runtime identity gate."""
    if getattr(settings, "VORNEQ_ENV", "") != "staging":
        return False
    if getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") != "openai":
        return False
    if not getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False):
        return False
    if not legacy_model_matches("openai-image", Capability.IMAGE,
                                getattr(settings, "VORNEQ_AI_IMAGE_MODEL", ""), MODELS):
        return False
    # Never use the chat OpenAI project for paid image requests.
    if not os.getenv("VORNEQ_OPENAI_IMAGE_API_KEY", "").strip():
        return False
    try:
        image_ledger_config()
        from .storage import durable_storage_ready
        if not durable_storage_ready():
            return False
        if not 1 <= int(getattr(settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0)) <= 10_000_000:
            return False
        if not prepaid_only_requested() and not 1 <= int(getattr(settings, "VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD", 0)):
            return False
        if max_request_micro() is None or not safety_key_ready():
            return False
        from .providers import configured_complexity
        if configured_complexity() is None:
            return False
    except (ValueError, TypeError, ImportError):
        return False
    return True


def min_interval_seconds():
    if not prepaid_only_requested() or not paid_provider_enabled():
        return 60
    value = getattr(settings, "VORNEQ_AI_IMAGE_MIN_INTERVAL_SECONDS", 60)
    if type(value) is not int or value < 0:
        return 60
    if value == 0 and getattr(settings, "VORNEQ_AI_IMAGE_ALLOW_ZERO_INTERVAL", False) is not True:
        return 60
    return min(value, 3600)


def _active_limit(name, default, ceiling):
    value = getattr(settings, name, default)
    return min(value, ceiling) if type(value) is int and value >= 1 else default


def max_active_jobs_per_user():
    return _active_limit("VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_PER_USER", 3, 20)


def max_active_jobs_global():
    return _active_limit("VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_GLOBAL", 50, 1000)
