"""C02: independently authenticate a SHA-bound owner release from GitHub.

No operation in this module writes to GitHub, Render or PostgreSQL.
A local env string is never considered evidence of owner issuance.

The GitHub REST *issues/comments/{id}* response is fetched at point of use.
An explicitly scoped read-only GitHub token is mandatory. A missing token,
network error, edited/deleted record, unexpected author or expired approval
fails closed. The caller must separately enforce the C02 governance stop.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from apps.core import c02_operational_binding as binding

OWNER_LOGIN = "13640226"
OWNER_USER_ID = 199411505
REPOSITORY = "13640226/VORNEQ"
ISSUE_NUMBER = 407
API_ISSUE_URL = f"https://api.github.com/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}"
RELEASE_HEADER = "C02_OWNER_MIGRATION_RELEASE_V1"
MAX_AGE = timedelta(minutes=15)
MAX_COMMENT_BYTES = 65536
EXPECTED_SCOPE = "AUTHORIZE_PRODUCTION_AI_CORE_0001_0002"
EXPECTED_RISK = "ACCEPT_RENDER_OPERATIONAL_IDENTITY_LIMIT"
EXPECTED_MIGRATIONS = ("ai_core.0001_initial", "ai_core.0002_aichatrequestguard")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE = re.compile(r"[A-Z0-9-]{6,60}\Z")
_ISO = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_ID = re.compile(r"[1-9]\d{0,17}\Z")
_FIELDS = frozenset({
    "decision", "release_id", "sha", "service_id", "postgres_id",
    "database", "session_user", "current_user", "migrations",
    "backup_sha256", "backup_evidence", "expires_at", "risk_acceptance",
})


class OwnerReleaseDenied(ValueError):
    """Fail closed without exposing API response, credentials, or URLs."""


@dataclass(frozen=True)
class VerifiedOwnerRelease:
    release_id: str
    comment_id: int
    sha: str
    body_sha256: str
    backup_sha256: str
    backup_evidence: str
    expires_at: datetime


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise OwnerReleaseDenied(reason)


def _time(value: object) -> datetime:
    _require(isinstance(value, str) and bool(_ISO.fullmatch(value)), "invalid release timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise OwnerReleaseDenied("invalid release timestamp") from None


def _github_time(value: object) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), "missing GitHub timestamp")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(date.utcoffset() == timedelta(0), "invalid GitHub timestamp")
        return date
    except (ValueError, TypeError):
        raise OwnerReleaseDenied("invalid GitHub timestamp") from None


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate release JSON key")
        result[key] = value
    return result


def _comment_id(environ) -> int:
    value = environ.get("VORNEQ_C02_OWNER_COMMENT_ID", "")
    _require(isinstance(value, str) and bool(_ID.fullmatch(value)), "owner comment ID missing or malformed")
    return int(value)


def fetch_github_comment(comment_id: int, token: str) -> dict:
    """Read exactly one comment from GitHub's fixed TLS endpoint, no redirects."""
    _require(isinstance(comment_id, int) and 0 < comment_id < 10**18, "invalid GitHub comment ID")
    _require(isinstance(token, str) and bool(token.strip()), "scoped GitHub read token missing")
    connection = None
    try:
        connection = http.client.HTTPSConnection(
            "api.github.com", timeout=5, context=ssl.create_default_context()
        )
        connection.request(
            "GET", f"/repos/{REPOSITORY}/issues/comments/{comment_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "VORNEQ-C02-OwnerRelease/1.0",
            },
        )
        response = connection.getresponse()
        _require(response.status == 200, "GitHub release record unavailable")
        _require("json" in response.getheader("Content-Type", "").lower(),
                 "invalid GitHub response content type")
        payload = response.read(MAX_COMMENT_BYTES + 1)
        _require(len(payload) <= MAX_COMMENT_BYTES, "GitHub release response too large")
        data = json.loads(payload)
        _require(isinstance(data, dict), "invalid GitHub release response")
        return data
    except OwnerReleaseDenied:
        raise
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError, ssl.SSLError, http.client.HTTPException):
        raise OwnerReleaseDenied("GitHub issuer verification unavailable") from None
    finally:
        if connection is not None:
            connection.close()


def validate_github_comment(comment: dict, *, comment_id: int, expected_sha: str,
                            release_id: str, backup_sha256: str, backup_evidence: str,
                            now: datetime | None = None) -> VerifiedOwnerRelease:
    """Validate a GitHub-authenticated comment and its strict release manifest.

    Calling this with arbitrary dicts does not authenticate anything. Only
    fetch_github_comment() obtains the actual TLS-validated GitHub response.
    """
    _require(isinstance(comment, dict), "invalid GitHub comment")
    _require(isinstance(comment_id, int) and comment_id > 0, "invalid GitHub comment ID")
    _require(bool(_SHA.fullmatch(expected_sha or "")), "invalid expected SHA")
    _require(bool(_RELEASE.fullmatch(release_id or "")), "invalid release ID")
    _require(bool(_HASH.fullmatch(backup_sha256 or "")), "missing backup SHA256")
    _require(isinstance(backup_evidence, str) and bool(backup_evidence.strip()),
             "missing backup restore evidence")
    _require(type(comment.get("id")) is int and comment["id"] == comment_id, "comment ID mismatch")
    _require(comment.get("url") == f"https://api.github.com/repos/{REPOSITORY}/issues/comments/{comment_id}",
             "comment API source mismatch")
    _require(comment.get("issue_url") == API_ISSUE_URL, "comment issue mismatch")
    _require(comment.get("html_url") ==
             f"https://github.com/{REPOSITORY}/issues/{ISSUE_NUMBER}#issuecomment-{comment_id}",
             "comment URL mismatch")
    user = comment.get("user")
    _require(isinstance(user, dict), "GitHub owner identity missing")
    _require(user.get("login") == OWNER_LOGIN and type(user.get("id")) is int
             and user["id"] == OWNER_USER_ID and user.get("type") == "User",
             "GitHub owner identity mismatch")
    _require(comment.get("author_association") == "OWNER", "GitHub owner association mismatch")
    created_at = _github_time(comment.get("created_at"))
    updated_at = _github_time(comment.get("updated_at"))
    _require(created_at == updated_at, "edited GitHub authorization forbidden")
    current = now or datetime.now(timezone.utc)
    _require(isinstance(current, datetime) and current.tzinfo is not None,
             "invalid verification clock")
    current = current.astimezone(timezone.utc)
    _require(created_at - timedelta(seconds=30) <= current, "authorization from the future")

    raw_body = comment.get("body")
    _require(isinstance(raw_body, str) and len(raw_body) <= 4096, "invalid release body")
    parts = raw_body.strip().split("\n", 1)
    _require(len(parts) == 2 and parts[0] == RELEASE_HEADER,
             "explicit owner migration release header missing")
    try:
        manifest = json.loads(parts[1], object_pairs_hook=_object_pairs)
    except (json.JSONDecodeError, UnicodeError):
        raise OwnerReleaseDenied("malformed owner release JSON") from None
    _require(isinstance(manifest, dict) and set(manifest) == _FIELDS,
             "owner release fields missing or unexpected")
    _require(manifest["decision"] == EXPECTED_SCOPE, "not a production migration decision")
    _require(manifest["risk_acceptance"] == EXPECTED_RISK,
             "operational identity residual risk not accepted")
    _require(manifest["release_id"] == release_id, "owner release ID mismatch")
    _require(manifest["sha"] == expected_sha, "owner release SHA mismatch")
    _require(manifest["service_id"] == "srv-dadn07eq1p3s73eccau0",
             "owner release service mismatch")
    _require(manifest["postgres_id"] == binding.EXPECTED_RESOURCE_ID,
             "owner release Postgres resource mismatch")
    _require(manifest["database"] == binding.EXPECTED_DATABASE, "owner release database mismatch")
    _require(manifest["session_user"] == binding.EXPECTED_DATABASE_USER,
             "owner release login mismatch")
    _require(manifest["current_user"] == binding.EXPECTED_EXECUTION_ROLE,
             "owner release execution role mismatch")
    _require(type(manifest["migrations"]) is list and
             manifest["migrations"] == list(EXPECTED_MIGRATIONS),
             "owner release migration scope mismatch")
    _require(manifest["backup_sha256"] == backup_sha256,
             "owner release backup digest mismatch")
    _require(manifest["backup_evidence"] == backup_evidence,
             "owner release backup evidence mismatch")
    expires_at = _time(manifest["expires_at"])
    _require(created_at < expires_at <= created_at + MAX_AGE,
             "owner release expiry beyond allowed window")
    _require(current < expires_at and current <= created_at + MAX_AGE,
             "owner release expired")
    return VerifiedOwnerRelease(
        release_id=release_id, comment_id=comment_id, sha=expected_sha,
        body_sha256=hashlib.sha256(raw_body.encode("utf-8")).hexdigest(),
        backup_sha256=backup_sha256, backup_evidence=backup_evidence,
        expires_at=expires_at,
    )


def verify_live_owner_release(environ, *, expected_sha: str,
                              release_id: str) -> VerifiedOwnerRelease:
    """Production entrypoint; never accept a caller-supplied or cached response."""
    comment_id = _comment_id(environ)
    token = environ.get("VORNEQ_C02_GITHUB_READ_TOKEN", "")
    _require(isinstance(token, str) and bool(token.strip()),
             "read-only GitHub token not configured")
    digest = environ.get("VORNEQ_C02_BACKUP_SHA256", "")
    evidence = environ.get("VORNEQ_C02_BACKUP_EVIDENCE", "")
    # Validate local inputs before attempting network traffic.
    _require(bool(_HASH.fullmatch(digest)), "backup SHA256 missing or malformed")
    _require(isinstance(evidence, str) and bool(evidence.strip()), "backup evidence missing")
    # fetch_github_comment uses only fixed host and issue path, with TLS validation.
    return validate_github_comment(
        fetch_github_comment(comment_id, token),
        comment_id=comment_id,
        expected_sha=expected_sha,
        release_id=release_id,
        backup_sha256=digest,
        backup_evidence=evidence,
    )
