"""Fail-closed Voice configuration. Every unknown or malformed value disables Voice.

Settings are read with getattr defaults only; this module adds no settings entries.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

# Nested Redis namespace reserved for the future shared store.
NAMESPACE = "ai_core:ai_core_voice"
TTL_MIN = 30
TTL_MAX = 3600
TTL_DEFAULT = 300
MAX_ALLOWLIST = 50
MAX_BODY_BYTES = 16 * 1024
MAX_TEXT_CHARS = 2000
MAX_AUDIO_CHUNK_BYTES = 64 * 1024
MAX_EVENTS_PER_SESSION = 50
MAX_SESSIONS = 100  # bounded mock memory
ALLOWED_ENVIRONMENTS = ("development", "staging")  # Production is never enabled here


@dataclass(frozen=True)
class VoiceConfig:
    ttl_seconds: int
    allowed_user_ids: frozenset


def parse_user_ids(raw) -> frozenset:
    """Comma-separated positive decimal IDs; anything malformed yields an empty set."""
    if not isinstance(raw, str) or not raw or len(raw) > 700:
        return frozenset()
    parts = raw.split(",")
    if len(parts) > MAX_ALLOWLIST or any(
            not p.isascii() or not p.isdecimal() or not 1 <= len(p) <= 12 for p in parts):
        return frozenset()
    values = {int(p) for p in parts}
    if len(values) != len(parts) or any(v <= 0 for v in values):
        return frozenset()
    return frozenset(values)


def load_config():
    """Return the active configuration or None (Voice unavailable)."""
    if getattr(settings, "VORNEQ_ENV", None) not in ALLOWED_ENVIRONMENTS:
        return None
    if getattr(settings, "VORNEQ_AI_VOICE_ENABLED", False) is not True:
        return None
    if getattr(settings, "VORNEQ_AI_VOICE_PROVIDER", "mock") != "mock":
        return None  # hard block: no paid provider can be selected
    if getattr(settings, "VORNEQ_AI_VOICE_PAID_CALLS_ENABLED", False) not in (False, None):
        return None
    ttl = getattr(settings, "VORNEQ_AI_VOICE_SESSION_TTL_SECONDS", TTL_DEFAULT)
    if type(ttl) is not int or not TTL_MIN <= ttl <= TTL_MAX:
        return None
    allowed = parse_user_ids(getattr(settings, "VORNEQ_AI_VOICE_ALLOWED_USER_IDS", ""))
    if not allowed:
        return None
    return VoiceConfig(ttl_seconds=ttl, allowed_user_ids=allowed)


def emergency_stop_active() -> bool:
    """Any value other than a literal off state counts as stopped."""
    return getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False) not in (False, None)
