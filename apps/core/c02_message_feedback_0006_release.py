"""Exact owner-comment contract for a future schema-first 0006 release.

This module only authenticates evidence. No database or Render writes.
A proof alone does not grant hosted execution permission.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from apps.core import c02_owner_release as legacy
from apps.core import c02_operational_binding as binding
from apps.core import staging_image_0004_release as staging

ISSUE = 770
HEADER = "C02_AI_MESSAGE_FEEDBACK_0006_OWNER_RELEASE_V1"
DECISION = "AUTHORIZE_AI_CORE_0006_MESSAGE_FEEDBACK"
RISK = "ACCEPT_RENDER_OPERATIONAL_IDENTITY_LIMIT_AND_FEEDBACK_ROLLBACK_RESTRICTIONS"
MIGRATION = "ai_core.0006_message_feedback"
MAX_AGE = timedelta(minutes=30)
MAX_BACKUP_AGE = timedelta(hours=2)
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
RELEASE_ID = re.compile(r"[A-Z0-9-]{8,60}\Z")
EVIDENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,120}\Z")


@dataclass(frozen=True)
class Target:
    service: str
    postgres: str
    database: str
    login: str
    role: str


TARGETS = {
    "staging": Target(staging.SERVICE, staging.POSTGRES, staging.DATABASE,
                      staging.ROLE, staging.ROLE),
    "production": Target("srv-dadn07eq1p3s73eccau0", binding.EXPECTED_RESOURCE_ID,
                         binding.EXPECTED_DATABASE, binding.EXPECTED_DATABASE_USER,
                         binding.EXPECTED_EXECUTION_ROLE),
}


@dataclass(frozen=True)
class Proof:
    environment: str
    release_id: str
    comment_id: int
    source_sha: str
    live_sha: str
    body_sha256: str
    backup_sha256: str
    backup_evidence: str
    expires_at: datetime


FIELDS = frozenset({
    "decision", "environment", "release_id", "source_sha", "live_sha",
    "service_id", "postgres_id", "database", "session_user", "current_user",
    "migrations", "backup_sha256", "backup_evidence", "backup_exported_at",
    "restore_verified_at", "expires_at", "risk_acceptance",
})


def require(ok, message):
    if not ok:
        raise legacy.OwnerReleaseDenied(message)


def validate(comment, *, comment_id, environment, source_sha, live_sha,
             release_id, backup_sha256, backup_evidence, now=None):
    """Pure scope validation; only fetch_github_comment authenticates origin."""
    require(isinstance(environment, str) and environment in TARGETS, "bad environment")
    require(isinstance(comment, dict) and type(comment_id) is int
            and 0 < comment_id < 10**18, "invalid comment")
    for sha in (source_sha, live_sha):
        require(isinstance(sha, str) and SHA.fullmatch(sha), "invalid SHA")
    require(source_sha != live_sha, "schema-first source must differ from live SHA")
    require(isinstance(release_id, str) and RELEASE_ID.fullmatch(release_id), "bad release ID")
    require(isinstance(backup_sha256, str) and DIGEST.fullmatch(backup_sha256), "bad backup hash")
    require(isinstance(backup_evidence, str) and EVIDENCE.fullmatch(backup_evidence),
            "bad restore evidence")
    api = "https://api.github.com/repos/13640226/VORNEQ"
    web = "https://github.com/13640226/VORNEQ"
    require(type(comment.get("id")) is int and comment["id"] == comment_id
            and comment.get("url") == f"{api}/issues/comments/{comment_id}"
            and comment.get("issue_url") == f"{api}/issues/{ISSUE}"
            and comment.get("html_url") == f"{web}/pull/{ISSUE}#issuecomment-{comment_id}",
            "wrong comment origin")
    user = comment.get("user")
    require(isinstance(user, dict) and user.get("login") == legacy.OWNER_LOGIN
            and type(user.get("id")) is int and user["id"] == legacy.OWNER_USER_ID
            and user.get("type") == "User" and comment.get("author_association") == "OWNER",
            "wrong owner")
    created = legacy._github_time(comment.get("created_at"))
    updated = legacy._github_time(comment.get("updated_at"))
    current = now or datetime.now(timezone.utc)
    require(isinstance(current, datetime) and current.tzinfo is not None, "invalid clock")
    current = current.astimezone(timezone.utc)
    require(created == updated and created-timedelta(seconds=30) <= current <= created+MAX_AGE,
            "edited, stale or future comment")
    body = comment.get("body")
    require(isinstance(body, str) and len(body) <= 4096, "invalid body")
    parts = body.strip().split("\n", 1)
    require(len(parts) == 2 and parts[0] == HEADER, "wrong release header")
    try:
        manifest = json.loads(parts[1], object_pairs_hook=legacy._object_pairs)
    except (ValueError, TypeError):
        raise legacy.OwnerReleaseDenied("invalid release JSON") from None
    require(isinstance(manifest, dict) and set(manifest) == FIELDS, "wrong manifest fields")
    t = TARGETS[environment]
    expected = {
        "decision": DECISION, "environment": environment, "release_id": release_id,
        "source_sha": source_sha, "live_sha": live_sha, "service_id": t.service,
        "postgres_id": t.postgres, "database": t.database,
        "session_user": t.login, "current_user": t.role,
        "migrations": [MIGRATION], "backup_sha256": backup_sha256,
        "backup_evidence": backup_evidence, "risk_acceptance": RISK,
    }
    require(all(type(manifest.get(k)) is type(v) and manifest.get(k) == v
                for k, v in expected.items()), "release scope mismatch")
    exported = legacy._time(manifest["backup_exported_at"])
    restored = legacy._time(manifest["restore_verified_at"])
    expiry = legacy._time(manifest["expires_at"])
    require(created-MAX_BACKUP_AGE <= exported <= restored <= created
            and current-MAX_BACKUP_AGE <= exported and restored <= current,
            "backup or restore time invalid")
    require(created < expiry <= created+MAX_AGE and current < expiry, "expired release")
    return Proof(environment, release_id, comment_id, source_sha, live_sha,
                 hashlib.sha256(body.encode()).hexdigest(), backup_sha256,
                 backup_evidence, expiry)


def verify_live(environ, *, environment, source_sha, live_sha, release_id):
    """Read authenticated owner comment, no implicit authorization or write."""
    raw_id = environ.get("VORNEQ_C02_0006_OWNER_COMMENT_ID", "")
    token = environ.get("VORNEQ_C02_0006_GITHUB_READ_TOKEN", "")
    digest = environ.get("VORNEQ_C02_0006_BACKUP_SHA256", "")
    evidence = environ.get("VORNEQ_C02_0006_BACKUP_EVIDENCE", "")
    require(isinstance(raw_id, str) and re.fullmatch(r"[1-9][0-9]{0,17}", raw_id),
            "missing owner comment ID")
    require(isinstance(token, str) and token.strip(), "missing scoped GitHub read token")
    require(isinstance(digest, str) and DIGEST.fullmatch(digest), "missing backup hash")
    require(isinstance(evidence, str) and EVIDENCE.fullmatch(evidence), "missing restore evidence")
    comment_id = int(raw_id)
    return validate(legacy.fetch_github_comment(comment_id, token), comment_id=comment_id,
                    environment=environment, source_sha=source_sha, live_sha=live_sha,
                    release_id=release_id, backup_sha256=digest, backup_evidence=evidence)


def verify_main_sha(environ, expected_sha):
    """Authenticated, bounded GET of main, independently of local checkout."""
    import http.client
    import ssl

    token = environ.get("VORNEQ_C02_0006_GITHUB_READ_TOKEN", "")
    require(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha), "bad source SHA")
    require(isinstance(token, str) and token.strip(), "missing scoped GitHub read token")
    connection = None
    try:
        connection = http.client.HTTPSConnection("api.github.com", timeout=5,
                                                 context=ssl.create_default_context())
        connection.request("GET", "/repos/13640226/VORNEQ/git/ref/heads/main", headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "VORNEQ-C02-0006/1.0",
        })
        response = connection.getresponse()
        require(response.status == 200 and "json" in response.getheader("Content-Type", "").lower(),
                "main ref unavailable")
        raw = response.read(65537)
        require(len(raw) <= 65536, "main ref response too large")
        data = json.loads(raw)
        require(isinstance(data, dict) and data.get("ref") == "refs/heads/main"
                and isinstance(data.get("object"), dict)
                and data["object"].get("type") == "commit"
                and data["object"].get("sha") == expected_sha, "approved source is not current main")
    except legacy.OwnerReleaseDenied:
        raise
    except (OSError, ValueError, TypeError, http.client.HTTPException):
        raise legacy.OwnerReleaseDenied("main ref verification unavailable") from None
    finally:
        if connection is not None:
            connection.close()
