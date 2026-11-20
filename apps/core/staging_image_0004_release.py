"""Independent GitHub owner release for exactly Staging ai_core.0004.

A caller-provided token or JSON is not an owner authorization. The owner
comment is fetched from GitHub's authenticated TLS API at point of use.
No Production authorization or generic C02 guard changes are provided.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from apps.core import c02_owner_release as legacy

ISSUE = 664
HEADER = "STAGING_IMAGE_0004_OWNER_RELEASE_V1"
DECISION = "AUTHORIZE_STAGING_AI_CORE_0004_IMAGE"
RISK = "ACCEPT_STAGING_OPERATIONAL_IDENTITY_RESIDUAL_RISK"
SERVICE = "srv-dbm7dvc9v7es7393g70g"
POSTGRES = "dpg-dbm74m8u01pc738j8r1g-a"
DATABASE = "vorneq_staging_db_9i8v"
ROLE = "vorneq_staging_db_9i8v_user"
MIGRATION = "ai_core.0004_image_generation_job_v1"
MAX_AGE = timedelta(minutes=30)
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
RELEASE = re.compile(r"[A-Z0-9-]{8,60}\Z")
EVIDENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,120}\Z")
FIELDS = frozenset({
    "decision", "release_id", "sha", "service_id", "postgres_id",
    "database", "session_user", "current_user", "migrations",
    "backup_sha256", "backup_evidence", "backup_exported_at",
    "restore_verified_at", "expires_at", "risk_acceptance",
})


def require(ok, reason):
    if not ok:
        raise legacy.OwnerReleaseDenied(reason)


def unique_pairs(pairs):
    out = {}
    for key, val in pairs:
        require(key not in out, "duplicate manifest key")
        out[key] = val
    return out


def validate_comment(comment, *, comment_id, expected_sha, release_id,
                     backup_sha256, backup_evidence, now=None):
    """Pure validation; only verify_live() authenticates the GitHub source."""
    require(isinstance(comment, dict), "invalid GitHub comment")
    require(type(comment_id) is int and 0 < comment_id < 10**18, "bad comment ID")
    require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha), "invalid SHA")
    require(isinstance(release_id, str) and RELEASE.fullmatch(release_id), "bad release ID")
    require(isinstance(backup_sha256, str) and DIGEST.fullmatch(backup_sha256),
            "missing backup digest")
    require(isinstance(backup_evidence, str) and EVIDENCE.fullmatch(backup_evidence),
            "missing restore evidence reference")
    api = "https://api.github.com/repos/13640226/VORNEQ"
    web = "https://github.com/13640226/VORNEQ"
    require(comment.get("id") == comment_id and type(comment.get("id")) is int,
            "comment ID mismatch")
    require(comment.get("url") == f"{api}/issues/comments/{comment_id}"
            and comment.get("issue_url") == f"{api}/issues/{ISSUE}"
            and comment.get("html_url") == f"{web}/issues/{ISSUE}#issuecomment-{comment_id}",
            "wrong GitHub issue origin")
    user = comment.get("user")
    require(isinstance(user, dict) and user.get("login") == "13640226"
            and user.get("id") == 199411505 and type(user.get("id")) is int
            and user.get("type") == "User"
            and comment.get("author_association") == "OWNER",
            "GitHub owner identity mismatch")
    try:
        created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, AttributeError, ValueError):
        raise legacy.OwnerReleaseDenied("invalid GitHub timestamps") from None
    require(created.tzinfo is not None and created.utcoffset() == timedelta(0)
            and created == updated, "edited or non-UTC grant")
    current = now if now is not None else datetime.now(timezone.utc)
    require(isinstance(current, datetime) and current.tzinfo is not None, "invalid clock")
    current = current.astimezone(timezone.utc)
    require(created - timedelta(seconds=30) <= current <= created + MAX_AGE,
            "expired or future owner release")
    body = comment.get("body")
    require(isinstance(body, str) and len(body) <= 4096, "invalid grant body")
    parts = body.strip().split("\n", 1)
    require(len(parts) == 2 and parts[0] == HEADER, "wrong release header")
    try:
        manifest = json.loads(parts[1], object_pairs_hook=unique_pairs)
    except (ValueError, TypeError):
        raise legacy.OwnerReleaseDenied("invalid release JSON") from None
    require(isinstance(manifest, dict) and set(manifest) == FIELDS,
            "release fields missing/extra")
    expected = {
        "decision": DECISION, "release_id": release_id, "sha": expected_sha,
        "service_id": SERVICE, "postgres_id": POSTGRES, "database": DATABASE,
        "session_user": ROLE, "current_user": ROLE,
        "migrations": [MIGRATION], "backup_sha256": backup_sha256,
        "backup_evidence": backup_evidence, "risk_acceptance": RISK,
    }
    require(all(manifest.get(k) == v and type(manifest.get(k)) is type(v)
                for k, v in expected.items()), "owner manifest scope mismatch")
    try:
        exported = datetime.strptime(manifest["backup_exported_at"], "%Y-%m-%dT%H:%M:%SZ")
        restored = datetime.strptime(manifest["restore_verified_at"], "%Y-%m-%dT%H:%M:%SZ")
        exported = exported.replace(tzinfo=timezone.utc)
        restored = restored.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise legacy.OwnerReleaseDenied("invalid backup or restore time") from None
    require(created - timedelta(hours=2) <= exported <= restored <= created,
            "backup is not fresh or restore time is invalid")
    require(current - timedelta(hours=2) <= exported and restored <= current,
            "backup too old at point of use")
    try:
        expiry = datetime.strptime(manifest["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
        expiry = expiry.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise legacy.OwnerReleaseDenied("invalid expiry") from None
    require(created < expiry <= created + MAX_AGE and current < expiry,
            "release expired or excessive TTL")
    return legacy.VerifiedOwnerRelease(
        release_id=release_id, comment_id=comment_id, sha=expected_sha,
        body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        backup_sha256=backup_sha256, backup_evidence=backup_evidence,
        expires_at=expiry,
    )


def verify_live(environ, *, expected_sha, release_id):
    """Re-fetch the actual owner comment; never trust a synthetic manifest."""
    raw_id = environ.get("VORNEQ_IMAGE_0004_OWNER_COMMENT_ID", "")
    require(isinstance(raw_id, str)
            and re.fullmatch(r"[1-9][0-9]{0,17}", raw_id), "missing owner comment ID")
    token = environ.get("VORNEQ_IMAGE_0004_GITHUB_READ_TOKEN", "")
    require(isinstance(token, str) and bool(token.strip()), "GitHub read token missing")
    digest = environ.get("VORNEQ_IMAGE_0004_BACKUP_SHA256", "")
    evidence = environ.get("VORNEQ_IMAGE_0004_BACKUP_EVIDENCE", "")
    require(isinstance(digest, str) and DIGEST.fullmatch(digest), "backup hash missing")
    require(isinstance(evidence, str) and EVIDENCE.fullmatch(evidence),
            "restore evidence missing")
    comment_id = int(raw_id)
    return validate_comment(
        legacy.fetch_github_comment(comment_id, token),
        comment_id=comment_id, expected_sha=expected_sha, release_id=release_id,
        backup_sha256=digest, backup_evidence=evidence,
    )
