"""Reserved IdentityHandle constants (ADR-013)."""

from __future__ import annotations

RESERVED_HANDLES: frozenset[str] = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "support",
        "vorneq",
        "system",
        "security",
        "help",
        "api",
        "www",
        "mail",
        "noreply",
        "no-reply",
    }
)

HANDLE_MAX_LENGTH: int = 32
HANDLE_SUFFIX_MAX_RETRY: int = 10
HANDLE_DISPLAY_DOMAIN: str = "vorneq.com"
HANDLE_FALLBACK_PREFIX: str = "user"
