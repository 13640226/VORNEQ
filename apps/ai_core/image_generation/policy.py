"""Fail-closed image feature policy, entirely independent of chat permissions."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import uuid
from django.conf import settings

STAGING_SERVICE_ID = "srv-dbm7dvc9v7es7393g70g"
PRODUCTION_SERVICE_ID = "srv-dadn07eq1p3s73eccau0"
_WORKER_ID = re.compile(r"srv-[a-z0-9]{20,32}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_OWNER = re.compile(r"OWNER-AUTH-AI-IMAGE-STAGING-[A-Z0-9-]{6,100}\Z")
MODELS = frozenset({
    "gpt-image-2", "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst", "gpt-image-2.6-flare",
    "gpt-image-2.6-sunburst",
})
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
        and isinstance(expected, str) and _SHA.fullmatch(expected)
        and os.getenv("RENDER_GIT_COMMIT") == expected
        and isinstance(owner, str) and _OWNER.fullmatch(owner)
        and _ids()
    )


def worker_enabled():
    """Explicitly separate, MOCK-ONLY background-worker identity.

    A Render worker never inherits the web-service grant. Its own service ID
    must be configured after separately authorized provisioning. No Production
    or paid-worker route is granted by this function.
    """
    if (not getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False)
            or getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False)
            or getattr(settings, "VORNEQ_ENV", "") != "staging"
            or getattr(settings, "DEBUG", True)
            or getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") != "mock"
            or getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False)):
        return False
    worker_id = getattr(settings, "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID", "")
    expected = getattr(settings, "VORNEQ_AI_IMAGE_AUTHORIZED_SHA", "")
    owner = getattr(settings, "VORNEQ_AI_IMAGE_OWNER_AUTH", "")
    return bool(
        isinstance(worker_id, str) and _WORKER_ID.fullmatch(worker_id)
        and worker_id not in (STAGING_SERVICE_ID, PRODUCTION_SERVICE_ID)
        and os.getenv("RENDER_SERVICE_ID") == worker_id
        and isinstance(expected, str) and _SHA.fullmatch(expected)
        and os.getenv("RENDER_GIT_COMMIT") == expected
        and isinstance(owner, str) and _OWNER.fullmatch(owner)
        and _ids()
    )


def actor_allowed(user, *, worker=False):
    if not (worker_enabled() if worker else enabled()) or not (
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
    if not enabled() or getattr(settings, "VORNEQ_ENV", "") != "staging":
        return False
    if getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "") != "openai":
        return False
    if not getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False):
        return False
    if getattr(settings, "VORNEQ_AI_IMAGE_MODEL", "") not in MODELS:
        return False
    if not os.getenv("OPENAI_API_KEY"):
        return False
    try:
        image_ledger_config()
        from .storage import durable_storage_ready
        if not durable_storage_ready():
            return False
        if not 1 <= int(getattr(settings, "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND", 0)) <= 10_000_000:
            return False
        if not 1 <= int(getattr(settings, "VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD", 0)):
            return False
        if max_request_micro() is None or not safety_key_ready():
            return False
        from .providers import configured_complexity
        if configured_complexity() is None:
            return False
    except (ValueError, TypeError, ImportError):
        return False
    return True
