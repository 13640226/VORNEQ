"""Independent, one-use GitHub owner authorization for ai_core.0003 only.

Separate from the consumed C02 0001/0002 authorization. No local string alone
authorizes a database write. All invalid or unreachable evidence fails closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from apps.core import c02_operational_binding as binding
from apps.core import c02_owner_release as legacy

HEADER = "C02_OWNER_CONVERSATION_0003_RELEASE_V1"
DECISION = "AUTHORIZE_PRODUCTION_AI_CORE_0003_CONVERSATION"
ISSUE = 407
MAX_AGE = timedelta(minutes=15)
FIELDS = frozenset({
    "decision", "release_id", "sha", "service_id", "postgres_id",
    "database", "session_user", "current_user", "migrations",
    "backup_sha256", "backup_evidence", "expires_at", "risk_acceptance",
})
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
RELEASE = re.compile(r"[A-Z0-9-]{6,60}\Z")
EVIDENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,120}\Z")


def require(ok, reason):
    if not ok:
        raise legacy.OwnerReleaseDenied(reason)


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "duplicate release field")
        obj[key] = value
    return obj


def validate_comment(comment, *, comment_id, expected_sha, release_id, backup_digest,
                     backup_evidence, now=None):
    require(isinstance(comment, dict), "invalid GitHub comment")
    require(type(comment_id) is int and comment_id > 0, "invalid GitHub comment ID")
    require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha), "invalid SHA")
    require(isinstance(release_id, str) and RELEASE.fullmatch(release_id), "invalid release ID")
    require(isinstance(backup_digest, str) and DIGEST.fullmatch(backup_digest), "invalid backup hash")
    require(isinstance(backup_evidence, str) and EVIDENCE.fullmatch(backup_evidence),
            "invalid backup evidence")
    base = "https://api.github.com/repos/13640226/VORNEQ"
    require(comment.get("id") == comment_id and type(comment.get("id")) is int,
            "comment identity mismatch")
    require(comment.get("url") == f"{base}/issues/comments/{comment_id}"
            and comment.get("issue_url") == f"{base}/issues/{ISSUE}"
            and comment.get("html_url") ==
            f"https://github.com/13640226/VORNEQ/issues/{ISSUE}#issuecomment-{comment_id}",
            "comment origin mismatch")
    user = comment.get("user")
    require(isinstance(user, dict) and user.get("login") == "13640226"
            and user.get("id") == 199411505 and type(user.get("id")) is int
            and user.get("type") == "User" and comment.get("author_association") == "OWNER",
            "owner identity mismatch")
    try:
        created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise legacy.OwnerReleaseDenied("invalid GitHub timestamps") from None
    require(created.tzinfo is not None and created.utcoffset() == timedelta(0)
            and created == updated, "edited or non-UTC owner comment")
    current = now or datetime.now(timezone.utc)
    require(current.tzinfo is not None, "invalid verification clock")
    current = current.astimezone(timezone.utc)
    require(created - timedelta(seconds=30) <= current <= created + MAX_AGE,
            "stale or future owner authorization")
    body = comment.get("body")
    require(isinstance(body, str) and len(body) <= 4096, "invalid authorization body")
    parts = body.strip().split("\n", 1)
    require(len(parts) == 2 and parts[0] == HEADER, "wrong authorization scope")
    try:
        manifest = json.loads(parts[1], object_pairs_hook=_no_duplicate_keys)
    except (ValueError, UnicodeError, TypeError):
        raise legacy.OwnerReleaseDenied("malformed authorization JSON") from None
    require(isinstance(manifest, dict) and set(manifest) == FIELDS,
            "unexpected authorization fields")
    expect = {
        "decision": DECISION,
        "release_id": release_id,
        "sha": expected_sha,
        "service_id": "srv-dadn07eq1p3s73eccau0",
        "postgres_id": binding.EXPECTED_RESOURCE_ID,
        "database": binding.EXPECTED_DATABASE,
        "session_user": binding.EXPECTED_DATABASE_USER,
        "current_user": binding.EXPECTED_EXECUTION_ROLE,
        "migrations": ["ai_core.0003_conversation"],
        "backup_sha256": backup_digest,
        "backup_evidence": backup_evidence,
        "risk_acceptance": "ACCEPT_RENDER_OPERATIONAL_IDENTITY_LIMIT",
    }
    require(all(manifest.get(k) == v and type(manifest.get(k)) is type(v)
                for k, v in expect.items()), "owner authorization does not match exact scope")
    try:
        expiry = datetime.strptime(manifest["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        raise legacy.OwnerReleaseDenied("invalid expiry") from None
    require(created < expiry <= created + MAX_AGE and current < expiry,
            "owner authorization expired or excessive")
    return legacy.VerifiedOwnerRelease(
        release_id=release_id,
        comment_id=comment_id,
        sha=expected_sha,
        body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        backup_sha256=backup_digest,
        backup_evidence=backup_evidence,
        expires_at=expiry,
    )


def verify_live(environ, *, expected_sha, release_id):
    """Re-fetch at point of use; caller cannot supply a cached or synthetic comment."""
    raw_id = environ.get("VORNEQ_C02_0003_OWNER_COMMENT_ID", "")
    require(bool(re.fullmatch(r"[1-9][0-9]{0,17}", raw_id)), "missing owner comment")
    token = environ.get("VORNEQ_C02_GITHUB_READ_TOKEN", "")
    require(isinstance(token, str) and bool(token.strip()), "read-only GitHub token missing")
    digest = environ.get("VORNEQ_C02_0003_BACKUP_SHA256", "")
    evidence = environ.get("VORNEQ_C02_0003_BACKUP_EVIDENCE", "")
    require(bool(isinstance(digest, str) and DIGEST.fullmatch(digest)),
            "backup hash missing")
    require(bool(isinstance(evidence, str) and EVIDENCE.fullmatch(evidence)),
            "backup reference missing")
    comment_id = int(raw_id)
    return validate_comment(
        legacy.fetch_github_comment(comment_id, token),
        comment_id=comment_id, expected_sha=expected_sha, release_id=release_id,
        backup_digest=digest, backup_evidence=evidence,
    )
