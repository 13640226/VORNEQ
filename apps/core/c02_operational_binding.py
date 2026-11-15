"""C02 operational connection binding (Render-recommended verification path).

Render support (2026-11-15, automated agent reply) states that no
cryptographic proof binds a PostgreSQL session to a Render resource ID and
recommends operational verification instead: the Django service's
DATABASE_URL must equal the database's *Internal* URL shown in the
authenticated Render Dashboard.

This module performs that comparison without revealing the connection
string. The Render Web Shell prints an HMAC-SHA256 of DATABASE_URL keyed with
a fresh, operator-chosen nonce. Separately, on the operator's own machine,
the Internal URL copied from the Dashboard is hashed with the same nonce
(``scripts/c02_tests/internal_url_digest.py``). Equal digests show that the
runtime uses exactly the Dashboard Internal URL. The nonce prevents replay of
an earlier digest and offline correlation between runs.

What this does NOT prove: that the Render control plane itself is honest, or
a cryptographic identity of the PostgreSQL backend. It never connects to the
database, never executes SQL and never grants migration permission.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from urllib.parse import unquote, urlsplit

EXPECTED_RESOURCE_ID = "dpg-dagru1h42hec73eqr960-a"
EXPECTED_DATABASE = "vorneq_production_db"
EXPECTED_DATABASE_USER = "vorneq_production_db_user"
EXPECTED_PORT = 5432

_NONCE = re.compile(r"[0-9a-f]{32,128}\Z")
_EXTERNAL = re.compile(r"\A" + re.escape(EXPECTED_RESOURCE_ID) + r"\.[a-z0-9-]+-postgres\.render\.com\Z")


class BindingError(ValueError):
    """Raised for malformed input; messages never contain URL contents."""


def require_nonce(nonce: str) -> str:
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise BindingError("nonce must be 32-128 lowercase hex characters")
    return nonce


def url_digest(nonce: str, url: str) -> str:
    """HMAC-SHA256(nonce, url) over the exact URL string (outer whitespace stripped)."""
    require_nonce(nonce)
    if not isinstance(url, str) or not url.strip():
        raise BindingError("URL is empty")
    return hmac.new(nonce.encode("ascii"), url.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def classify_host(host: str) -> str:
    """INTERNAL_EXACT is the Render private-network hostname (no domain suffix)."""
    if not isinstance(host, str):
        return "OTHER"
    host = host.lower()
    if host == EXPECTED_RESOURCE_ID:
        return "INTERNAL_EXACT"
    if _EXTERNAL.fullmatch(host):
        return "EXTERNAL_RENDER"
    return "OTHER"


def parse_url(url: str) -> dict:
    parts = urlsplit((url or "").strip())
    if parts.scheme not in ("postgres", "postgresql"):
        raise BindingError("URL is not a PostgreSQL URL")
    try:
        port = parts.port or EXPECTED_PORT
    except ValueError as exc:
        raise BindingError("URL port is invalid") from exc
    return {
        "HOST": parts.hostname or "",
        "PORT": port,
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "QUERY": parts.query,
    }


def _port(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else EXPECTED_PORT
    except (TypeError, ValueError):
        return None


def settings_match_url(settings_dict: dict, url: str) -> bool:
    """Django's active connection settings derive from exactly this URL.

    Parsed with dj_database_url, the same parser config/settings*.py use.
    """
    import dj_database_url

    try:
        expected = dj_database_url.parse(url.strip())
    except Exception:  # noqa: BLE001 - any parser failure is a mismatch
        return False
    return (
        settings_dict.get("HOST", "") == expected.get("HOST", "")
        and _port(settings_dict.get("PORT")) == _port(expected.get("PORT"))
        and settings_dict.get("NAME", "") == expected.get("NAME", "")
        and settings_dict.get("USER", "") == expected.get("USER", "")
        and hmac.compare_digest(str(settings_dict.get("PASSWORD", "")), str(expected.get("PASSWORD", "")))
    )


def binding_report(environ, settings_dict: dict, nonce: str) -> dict:
    """Secret-free report for the Render Web Shell. No SQL, no network."""
    require_nonce(nonce)
    url = environ.get("DATABASE_URL", "")
    if not url:
        raise BindingError("DATABASE_URL is not set")
    parsed = parse_url(url)
    host_class = classify_host(parsed["HOST"])
    logical = (
        parsed["NAME"] == EXPECTED_DATABASE
        and parsed["USER"] == EXPECTED_DATABASE_USER
        and parsed["PORT"] == EXPECTED_PORT
    )
    settings_match = settings_match_url(settings_dict, url)
    return {
        "C02_DATABASE_URL_HMAC_SHA256": url_digest(nonce, url),
        "C02_HOST_CLASS": host_class,
        "C02_LOGICAL_TARGET_MATCH": logical,
        "C02_DJANGO_SETTINGS_FROM_DATABASE_URL": settings_match,
        "C02_OPERATIONAL_PRECHECK": host_class == "INTERNAL_EXACT" and logical and settings_match,
        "C02_DASHBOARD_DIGEST_COMPARISON": "REQUIRED_BY_OPERATOR",
        "POSTGRES_BACKEND_CRYPTOGRAPHIC_IDENTITY": "NOT_AVAILABLE",
        "C02_MIGRATION_GO": False,
    }
