"""One-use, Staging-only, MOCK-only live E2E for image generation V1.

API -> PostgreSQL queue -> worker-once -> private R2 object -> signed owner URL
-> cleanup. The service's own image gates stay CLOSED: the gate is opened only
inside this one-off process (override_settings), for two disposable users,
after a fresh GitHub owner release has been verified and a durable one-use
receipt has been consumed. No OpenAI SDK can be imported in this process.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import ssl
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from django.conf import settings

from apps.core import c02_owner_release as legacy
from apps.core import staging_image_0004_release as release0004
from apps.core import staging_image_0004_runner as runner0004

ISSUE = release0004.ISSUE
HEADER = "STAGING_IMAGE_MOCK_E2E_OWNER_RELEASE_V1"
DECISION = "AUTHORIZE_STAGING_IMAGE_MOCK_E2E_ONCE"
RISK = "ACCEPT_STAGING_MOCK_E2E_WRITE_AND_CLEANUP"
SERVICE = release0004.SERVICE
POSTGRES = release0004.POSTGRES
DATABASE = release0004.DATABASE
ROLE = release0004.ROLE
BUCKET = "vorneq-staging-ai-images"
MAX_AGE = timedelta(minutes=30)
ARM_MODE = "ONE_USE_OWNER_RELEASE"
ARM_MODE_KEY = "VORNEQ_IMAGE_MOCK_E2E_WRITE_MODE"
ARM_SHA_KEY = "VORNEQ_IMAGE_MOCK_E2E_ARMED_SHA"
AUTH_KEY = "VORNEQ_IMAGE_MOCK_E2E_AUTH"
COMMENT_KEY = "VORNEQ_IMAGE_MOCK_E2E_OWNER_COMMENT_ID"
TOKEN_KEY = "VORNEQ_IMAGE_MOCK_E2E_GITHUB_READ_TOKEN"
BACKUP_KEY = "VORNEQ_IMAGE_MOCK_E2E_BACKUP_SHA256"
EVIDENCE_KEY = "VORNEQ_IMAGE_MOCK_E2E_BACKUP_EVIDENCE"
RECEIPT_EVENT = "staging.ai_image_mock_e2e_one_use_release_consumed"
LOCK_KEY = 202611200501  # session advisory lock: one mock E2E run at a time
USER_PREFIX = "vorneq-e2e-"
MAX_PNG_BYTES = 10 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE = re.compile(r"[A-Z0-9-]{8,60}\Z")
_EVIDENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,120}\Z")
AUTH = re.compile(
    r"OWNER-AUTH-STAGING-AI-IMAGE-MOCK-E2E-(?P<id>[A-Z0-9-]{8,60}) @ (?P<sha>[0-9a-f]{40})\Z"
)
FIELDS = frozenset({
    "decision", "release_id", "sha", "service_id", "postgres_id", "database",
    "provider", "paid_calls", "bucket", "max_jobs", "backup_sha256",
    "backup_evidence", "backup_exported_at", "restore_verified_at",
    "expires_at", "risk_acceptance",
})
_CLOSED = ("", "false", "off", "0", "no")


class Refused(Exception):
    """Refused before any Staging write."""


class Aborted(Exception):
    """Write phase started; outcome or cleanup needs owner attention."""


def require(ok, reason, kind=Refused):
    if not ok:
        raise kind(reason)


@dataclass(frozen=True)
class ApprovedTarget:
    release_id: str
    proof: legacy.VerifiedOwnerRelease


@dataclass
class Report:
    steps: list = field(default_factory=list)
    cleanup: list = field(default_factory=list)

    def ok(self, name, out):
        self.steps.append(name)
        out("E2E_STEP_OK " + name)

    def clean(self, name, ok, out):
        self.cleanup.append((name, bool(ok)))
        out("E2E_CLEANUP {} {}".format(name, "OK" if ok else "FAILED"))


# --- Owner release -----------------------------------------------------------

def _unique(pairs):
    out = {}
    for key, val in pairs:
        require(key not in out, "duplicate manifest key")
        out[key] = val
    return out


def _deny(ok, reason):
    if not ok:
        raise legacy.OwnerReleaseDenied(reason)


def _utc(value, reason):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise legacy.OwnerReleaseDenied(reason) from None


def validate_comment(comment, *, comment_id, expected_sha, release_id,
                     backup_sha256, backup_evidence, now=None):
    """Pure validation; only verify_live() authenticates the GitHub source."""
    _deny(isinstance(comment, dict), "invalid GitHub comment")
    _deny(type(comment_id) is int and 0 < comment_id < 10**18, "bad comment ID")
    _deny(isinstance(expected_sha, str) and _SHA.fullmatch(expected_sha), "invalid SHA")
    _deny(isinstance(release_id, str) and _RELEASE.fullmatch(release_id), "bad release ID")
    _deny(isinstance(backup_sha256, str) and _DIGEST.fullmatch(backup_sha256),
          "missing backup digest")
    _deny(isinstance(backup_evidence, str) and _EVIDENCE.fullmatch(backup_evidence),
          "missing restore evidence reference")
    api = "https://api.github.com/repos/13640226/VORNEQ"
    web = "https://github.com/13640226/VORNEQ"
    _deny(comment.get("id") == comment_id and type(comment.get("id")) is int,
          "comment ID mismatch")
    _deny(comment.get("url") == f"{api}/issues/comments/{comment_id}"
          and comment.get("issue_url") == f"{api}/issues/{ISSUE}"
          and comment.get("html_url") == f"{web}/issues/{ISSUE}#issuecomment-{comment_id}",
          "wrong GitHub issue origin")
    user = comment.get("user")
    _deny(isinstance(user, dict) and user.get("login") == "13640226"
          and user.get("id") == 199411505 and type(user.get("id")) is int
          and user.get("type") == "User"
          and comment.get("author_association") == "OWNER",
          "GitHub owner identity mismatch")
    try:
        created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(comment["updated_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, AttributeError, ValueError):
        raise legacy.OwnerReleaseDenied("invalid GitHub timestamps") from None
    _deny(created.tzinfo is not None and created.utcoffset() == timedelta(0)
          and created == updated, "edited or non-UTC grant")
    current = now if now is not None else datetime.now(timezone.utc)
    _deny(isinstance(current, datetime) and current.tzinfo is not None, "invalid clock")
    current = current.astimezone(timezone.utc)
    _deny(created - timedelta(seconds=30) <= current <= created + MAX_AGE,
          "expired or future owner release")
    body = comment.get("body")
    _deny(isinstance(body, str) and len(body) <= 4096, "invalid grant body")
    parts = body.strip().split("\n", 1)
    _deny(len(parts) == 2 and parts[0] == HEADER, "wrong release header")
    try:
        manifest = json.loads(parts[1], object_pairs_hook=_unique)
    except (ValueError, TypeError, Refused):
        raise legacy.OwnerReleaseDenied("invalid release JSON") from None
    _deny(isinstance(manifest, dict) and set(manifest) == FIELDS,
          "release fields missing/extra")
    expected = {
        "decision": DECISION, "release_id": release_id, "sha": expected_sha,
        "service_id": SERVICE, "postgres_id": POSTGRES, "database": DATABASE,
        "provider": "mock", "paid_calls": False, "bucket": BUCKET, "max_jobs": 1,
        "backup_sha256": backup_sha256, "backup_evidence": backup_evidence,
        "risk_acceptance": RISK,
    }
    _deny(all(manifest.get(k) == v and type(manifest.get(k)) is type(v)
              for k, v in expected.items()), "owner manifest scope mismatch")
    exported = _utc(manifest["backup_exported_at"], "invalid backup time")
    restored = _utc(manifest["restore_verified_at"], "invalid restore time")
    _deny(created - timedelta(hours=2) <= exported <= restored <= created,
          "backup is not fresh or restore time is invalid")
    _deny(current - timedelta(hours=2) <= exported and restored <= current,
          "backup too old at point of use")
    expiry = _utc(manifest["expires_at"], "invalid expiry")
    _deny(created < expiry <= created + MAX_AGE and current < expiry,
          "release expired or excessive TTL")
    return legacy.VerifiedOwnerRelease(
        release_id=release_id, comment_id=comment_id, sha=expected_sha,
        body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        backup_sha256=backup_sha256, backup_evidence=backup_evidence,
        expires_at=expiry,
    )


def verify_live(environ, *, expected_sha, release_id):
    raw_id = environ.get(COMMENT_KEY, "")
    _deny(isinstance(raw_id, str) and re.fullmatch(r"[1-9][0-9]{0,17}", raw_id),
          "missing owner comment ID")
    token = environ.get(TOKEN_KEY, "")
    _deny(isinstance(token, str) and bool(token.strip()), "GitHub read token missing")
    digest, evidence = environ.get(BACKUP_KEY, ""), environ.get(EVIDENCE_KEY, "")
    _deny(isinstance(digest, str) and _DIGEST.fullmatch(digest), "backup hash missing")
    _deny(isinstance(evidence, str) and _EVIDENCE.fullmatch(evidence),
          "restore evidence missing")
    comment_id = int(raw_id)
    return validate_comment(
        legacy.fetch_github_comment(comment_id, token),
        comment_id=comment_id, expected_sha=expected_sha, release_id=release_id,
        backup_sha256=digest, backup_evidence=evidence,
    )


# --- Identity and read-only preflight ----------------------------------------

def base_context(environ, expected_sha, db_config, *, require_arm=False):
    """Positive allowlist before SQL/network. Service gates must stay CLOSED."""
    from apps.ai_core.image_generation.storage import durable_storage_ready
    require(isinstance(expected_sha, str) and _SHA.fullmatch(expected_sha),
            "invalid expected SHA")
    require(environ.get("VORNEQ_ENV") == "staging", "staging-only runtime required")
    require(getattr(settings, "VORNEQ_ENV", None) == "staging"
            and settings.DEBUG is False, "Django staging identity required")
    require(environ.get("RENDER_SERVICE_ID") == SERVICE, "wrong Render service")
    require(environ.get("RENDER_GIT_COMMIT") == expected_sha, "runtime SHA mismatch")
    for key in ("VORNEQ_AI_IMAGE_ENABLED", "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED"):
        require(environ.get(key, "").lower() in _CLOSED,
                key + " must remain closed for the service")
    require(not getattr(settings, "VORNEQ_AI_IMAGE_ENABLED", False)
            and not getattr(settings, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", False),
            "image gates must be closed in Django")
    require(not getattr(settings, "VORNEQ_AI_EMERGENCY_STOP", False),
            "AI emergency stop is active")
    require(db_config.get("ENGINE", "").endswith("postgresql"), "PostgreSQL required")
    host = (db_config.get("HOST") or "").lower().rstrip(".")
    require(host.split(".")[0] == POSTGRES,
            "configured host is not pinned Staging PostgreSQL resource")
    require(db_config.get("NAME") == DATABASE and db_config.get("USER") == ROLE,
            "Staging database settings do not match")
    require(str(db_config.get("PORT") or "5432") == "5432", "PostgreSQL port mismatch")
    options = settings.STORAGES.get("ai_images", {}).get("OPTIONS", {})
    require(durable_storage_ready() and options.get("bucket_name") == BUCKET,
            "private Staging R2 image bucket not configured")
    public_host = environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    require(bool(public_host) and public_host in settings.ALLOWED_HOSTS,
            "Staging host identity unavailable")
    if require_arm:
        require(environ.get(ARM_MODE_KEY) == ARM_MODE
                and environ.get(ARM_SHA_KEY) == expected_sha,
                "separate mock E2E owner release arm closed")
    return public_host


def queue_state():
    from apps.ai_core.models import AIImageJob
    return {s: AIImageJob.objects.filter(status=s).count() for s in (
        AIImageJob.STATUS_QUEUED, AIImageJob.STATUS_RUNNING, AIImageJob.STATUS_UNCERTAIN)}


def inspect(connection, expected_sha, *, environ, out=print):
    from apps.ai_core.image_generation import policy
    base_context(environ, expected_sha, connection.settings_dict)
    runner0004.check_identity(runner0004.snapshot(connection), False)
    history, _tables = runner0004.state(connection)
    require(history == runner0004.POST_HISTORY, "ai_core migration history is not 0001-0004")
    queue = queue_state()
    require(not any(queue.values()), "queued/running/uncertain image jobs exist")
    require(not policy.enabled() and not policy.worker_enabled()
            and not policy.paid_provider_enabled(), "a live image gate is open")
    out("RUNTIME_SHA_MATCH=True")
    out("MIGRATION_0004_APPLIED=True")
    out("SERVICE_IMAGE_GATES_CLOSED=True")
    out("R2_PRIVATE_CONFIGURED=True")
    out("IMAGE_QUEUE_EMPTY=True")
    out("READ_ONLY_PREFLIGHT_COMPLETE")
    return queue


def authorize(environ, expected_sha, db_config):
    base_context(environ, expected_sha, db_config, require_arm=True)
    match = AUTH.fullmatch(environ.get(AUTH_KEY, ""))
    require(match is not None and match.group("sha") == expected_sha,
            "missing exact SHA-bound one-use owner authorization")
    try:
        proof = verify_live(environ, expected_sha=expected_sha, release_id=match.group("id"))
    except legacy.OwnerReleaseDenied as exc:
        raise Refused("authenticated GitHub owner permit denied: " + str(exc)) from None
    require(proof.backup_sha256 == environ.get(BACKUP_KEY), "backup evidence changed")
    return ApprovedTarget(match.group("id"), proof)


def consume_one_use_receipt(connection, target, expected_sha):
    """Durable autocommit receipt BEFORE any test write. Never retried."""
    receipt_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://github.com/13640226/VORNEQ/issues/{ISSUE}/mock-e2e/{target.release_id}",
    )
    receipt = connection.copy(alias="staging_image_mock_e2e_receipt")
    try:
        receipt.ensure_connection()
        require(receipt.get_autocommit(), "receipt session not in autocommit", Refused)
        runner0004.check_identity(runner0004.snapshot(receipt), False, Refused)
        with receipt.cursor() as c:
            c.execute(
                """
                INSERT INTO audit_auditevent
                    (event_id, schema_version, event_name, actor, target, outcome,
                     reason_code, correlation_id, metadata, retention_class, timestamp)
                VALUES (%s, 1, %s, %s::jsonb, %s::jsonb, 'granted',
                        'STG_IMAGE_MOCK_E2E_RECEIPT', %s, %s::jsonb, 'security', now())
                ON CONFLICT (event_id) DO NOTHING RETURNING event_id
                """,
                [
                    receipt_id, RECEIPT_EVENT,
                    json.dumps({"kind": "github_owner", "comment_id": target.proof.comment_id}),
                    json.dumps({"service": SERVICE, "postgres_id": POSTGRES,
                                "database": DATABASE, "bucket": BUCKET}),
                    str(receipt_id),
                    json.dumps({"release_id": target.release_id, "sha": expected_sha,
                                "backup_sha256": target.proof.backup_sha256,
                                "owner_body_sha256": target.proof.body_sha256}),
                ],
            )
            require(c.fetchone() is not None, "one-use release already consumed", Refused)
    except Refused:
        raise
    except Exception as exc:
        raise Aborted("one-use receipt ambiguous/unavailable: " + type(exc).__name__) from None
    finally:
        receipt.close()


# --- Signed URL fetch (no redirects, private R2 host only) -------------------

def fetch_url(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    require(parts.scheme == "https" and host.endswith(".r2.cloudflarestorage.com")
            and not parts.username and not parts.password, "unexpected image URL host", Aborted)
    connection = http.client.HTTPSConnection(
        host, timeout=10, context=ssl.create_default_context())
    try:
        path = parts.path + ("?" + parts.query if parts.query else "")
        connection.request("GET", path, headers={"User-Agent": "VORNEQ-Mock-E2E/1.0"})
        response = connection.getresponse()
        body = response.read(MAX_PNG_BYTES + 1)
        return response.status, body
    finally:
        connection.close()


# --- Mutual exclusion --------------------------------------------------------

def acquire_run_lock(connection):
    """Session-level PostgreSQL advisory lock held for the whole run."""
    if connection is None or connection.vendor != "postgresql":
        return False  # offline tests only; Staging is pinned to PostgreSQL
    with connection.cursor() as c:
        c.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_KEY])
        require(c.fetchone()[0] is True, "another mock E2E run holds the lock")
    return True


def release_run_lock(connection, held):
    if held:
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_unlock(%s)", [LOCK_KEY])


# --- Read-only residue finder (after a crash/kill) ---------------------------

def find_residue(*, out=print):
    """Report leftovers of interrupted runs. Never deletes or changes anything."""
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from apps.ai_core.image_generation.storage import image_storage
    from apps.ai_core.models import AIImageJob
    users = list(get_user_model().objects.filter(username__startswith=USER_PREFIX)
                 .values_list("pk", flat=True))
    jobs = AIImageJob.objects.filter(owner_id__in=users)
    objects, listing_ok = 0, True
    try:
        storage = image_storage()
        for pk in users:
            prefix = "ai-generated/{}/".format(pk)
            try:
                _, files = storage.listdir(prefix)
            except FileNotFoundError:
                # InMemoryStorage raises when a test user's prefix was never
                # created; this is an empty prefix, not an R2 service failure.
                # Never apply this exception to the real remote S3 backend.
                from django.core.files.storage import InMemoryStorage
                if not isinstance(storage, InMemoryStorage):
                    raise
                files = []
            objects += len(files)
    except Exception:
        listing_ok = False
    audit = apps.get_model("audit", "AuditEvent")
    receipts = audit.objects.filter(event_name=RECEIPT_EVENT).count()
    result = {
        "e2e_users": len(users),
        "e2e_jobs": jobs.count(),
        "e2e_jobs_by_status": {s: jobs.filter(status=s).count()
                               for s, _ in AIImageJob.STATES if jobs.filter(status=s).exists()},
        "e2e_r2_objects": objects if listing_ok else None,
        "consumed_receipts": receipts,
    }
    out("E2E_RESIDUE_USERS={}".format(result["e2e_users"]))
    out("E2E_RESIDUE_JOBS={}".format(result["e2e_jobs"]))
    out("E2E_RESIDUE_R2_OBJECTS={}".format(
        "UNAVAILABLE" if not listing_ok else result["e2e_r2_objects"]))
    out("E2E_CONSUMED_RECEIPTS={}".format(receipts))
    clean = listing_ok and not result["e2e_users"] and not result["e2e_jobs"] \
        and not result["e2e_r2_objects"]
    out("E2E_RESIDUE_RESULT: {}".format("NONE" if clean else "PRESENT_OR_UNKNOWN"))
    return result


# --- One-use execution -------------------------------------------------------

def _gate_settings(target, expected_sha, user_ids):
    return {
        "VORNEQ_AI_IMAGE_ENABLED": True,
        "VORNEQ_AI_IMAGE_PROVIDER": "mock",
        "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
        "VORNEQ_AI_IMAGE_AUTHORIZED_SHA": expected_sha,
        "VORNEQ_AI_IMAGE_OWNER_AUTH": "OWNER-AUTH-AI-IMAGE-STAGING-" + target.release_id,
        "VORNEQ_AI_IMAGE_ALLOWED_USER_IDS": ",".join(str(i) for i in user_ids),
        "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": "",
        "VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS": 1,
        "VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS": 1,
    }


def execute_once(connection, target, expected_sha, *, public_host, out=print,
                 fetch=fetch_url, consume=consume_one_use_receipt):
    """Exactly one mock job for disposable users; cleanup is always attempted."""
    held = acquire_run_lock(connection)
    try:
        return _execute_locked(connection, target, expected_sha, public_host=public_host,
                               out=out, fetch=fetch, consume=consume)
    finally:
        release_run_lock(connection, held)


def _execute_locked(connection, target, expected_sha, *, public_host, out, fetch, consume):
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.test.utils import override_settings
    from django.urls import reverse
    from apps.ai_core.image_generation import policy
    from apps.ai_core.image_generation.service import process_next_image_job
    from apps.ai_core.image_generation.storage import image_storage
    from apps.ai_core.models import AIImageDailyQuota, AIImageJob

    require(not any(queue_state().values()), "image queue is not empty")
    require(not get_user_model().objects.filter(username__startswith=USER_PREFIX).exists(),
            "residue of an earlier mock E2E run exists; run --find-residue")
    day = datetime.now(timezone.utc).date()
    quota_before = AIImageDailyQuota.objects.filter(day_utc=day).first()
    quota_before = None if quota_before is None else quota_before.submitted
    consume(connection, target, expected_sha)
    out("E2E_ONE_USE_RECEIPT_CONSUMED release={}".format(target.release_id))

    report, users, key, clients = Report(), [], "", []
    tag = uuid.uuid4().hex[:12]
    saved_sdk = sys.modules.get("openai", "absent")
    sys.modules["openai"] = None  # any SDK import now raises ImportError
    failure = None
    try:
        User = get_user_model()
        for role in ("owner", "other"):
            user = User(username="{}{}-{}".format(USER_PREFIX, tag, role), is_active=True)
            user.set_unusable_password()
            user.save()
            users.append(user)
        owner, other = users
        with override_settings(**_gate_settings(target, expected_sha, [u.pk for u in users])):
            require(policy.enabled() and not policy.worker_enabled()
                    and not policy.paid_provider_enabled(), "process gate state invalid", Aborted)
            report.ok("process_gate_mock_only", out)
            url = reverse("ai_core:image-jobs")
            rid = uuid.uuid4()
            # Fix the only permissible R2 key BEFORE the worker can upload.
            # A worker may save the object and then fail before storage_key is
            # committed to PostgreSQL or returned to this runner.
            key = "ai-generated/{}/{}.png".format(owner.pk, rid.hex)
            payload = json.dumps({"request_id": str(rid),
                                  "prompt": "VORNEQ staging mock E2E " + tag,
                                  "size": "1024x1024"})
            anon = Client(HTTP_HOST=public_host)
            r = anon.post(url, payload, content_type="application/json", secure=True)
            require(r.status_code == 401, "anonymous submit not rejected", Aborted)
            report.ok("anonymous_rejected", out)
            strict = Client(HTTP_HOST=public_host, enforce_csrf_checks=True)
            strict.force_login(owner)
            clients.append(strict)
            r = strict.post(url, payload, content_type="application/json", secure=True)
            require(r.status_code == 403, "CSRF not enforced", Aborted)
            report.ok("csrf_enforced", out)
            c_owner = Client(HTTP_HOST=public_host)
            c_owner.force_login(owner)
            clients.append(c_owner)
            r = c_owner.post(url, payload, content_type="application/json", secure=True)
            body = r.json()
            require(r.status_code == 202 and body["id"] == str(rid)
                    and body["status"] == "queued" and body["model"] == "mock"
                    and "image_url" not in body, "submit response invalid", Aborted)
            report.ok("api_submit_202", out)
            r = c_owner.post(url, payload, content_type="application/json", secure=True)
            require(r.status_code == 200 and r.json()["id"] == str(rid),
                    "idempotent resubmit invalid", Aborted)
            require(AIImageJob.objects.filter(owner=owner).count() == 1,
                    "duplicate job created", Aborted)
            report.ok("idempotent_resubmit", out)
            queued = list(AIImageJob.objects.filter(status=AIImageJob.STATUS_QUEUED)
                          .values_list("pk", flat=True))
            require(queued == [rid], "unrelated job in queue; worker not started", Aborted)
            require(process_next_image_job() == rid, "worker did not process the test job",
                    Aborted)
            job = AIImageJob.objects.get(pk=rid)
            require(job.status == AIImageJob.STATUS_COMPLETED and job.is_mock
                    and job.provider == "mock" and job.prompt == "" and job.attempts == 1
                    and job.reservation_id is None
                    and job.storage_key == key,
                    "worker result invalid", Aborted)
            report.ok("worker_once_completed", out)
            require(image_storage().exists(key), "R2 object missing", Aborted)
            report.ok("r2_object_exists", out)
            detail = reverse("ai_core:image-job-detail", args=[rid])
            r = c_owner.get(detail, secure=True)
            body = r.json()
            require(r.status_code == 200 and body["status"] == "completed"
                    and body["mock"] is True
                    and body["label"] == "AI-generated (mock preview)"
                    and body.get("image_url"), "owner detail invalid", Aborted)
            signed = body["image_url"]
            report.ok("owner_detail_signed_url", out)
            c_other = Client(HTTP_HOST=public_host)
            c_other.force_login(other)
            clients.append(c_other)
            r = c_other.get(detail, secure=True)
            require(r.status_code == 404, "other user can see owner job", Aborted)
            report.ok("other_user_404", out)
            r = anon.get(detail, secure=True)
            require(r.status_code == 401, "anonymous detail not rejected", Aborted)
            report.ok("anonymous_detail_401", out)
            status, data = fetch(signed)
            require(status == 200 and data.startswith(b"\x89PNG\r\n\x1a\n")
                    and hashlib.sha256(data).hexdigest() == job.image_digest,
                    "signed download invalid", Aborted)
            report.ok("signed_download_digest_match", out)
            unsigned = signed.split("?", 1)[0]
            status, _ = fetch(unsigned)
            require(status in (400, 401, 403), "object readable without signature", Aborted)
            report.ok("unsigned_access_denied", out)
    except Exception as exc:  # report, then always clean up
        failure = exc
    finally:
        failure = _cleanup(report, users, key, clients, day, quota_before, out) or failure
        if saved_sdk == "absent":
            sys.modules.pop("openai", None)
        else:
            sys.modules["openai"] = saved_sdk
    if failure is not None:
        if isinstance(failure, (Refused, Aborted)):
            raise Aborted(str(failure))
        raise Aborted("unexpected E2E failure: " + type(failure).__name__)
    return report


def _cleanup(report, users, key, clients, day, quota_before, out):
    """Delete only this run's objects; verify each deletion separately."""
    from apps.ai_core.image_generation.storage import image_storage
    from apps.ai_core.models import AIImageDailyQuota, AIImageJob
    failed = False
    for client in clients:
        try:
            client.logout()
        except Exception:
            failed = True
    object_gone = True
    if key:
        try:
            storage = image_storage()
            # Deterministic key is retained even if the worker never returned.
            # An uncertain delete/readback must never discard the owner anchor.
            storage.delete(key)
            object_gone = not storage.exists(key)
        except Exception:
            object_gone = False
        report.clean("r2_object_deleted", object_gone, out)
        failed |= not object_gone
    if object_gone:
        try:
            AIImageJob.objects.filter(owner__in=users).delete()
            ok = not AIImageJob.objects.filter(owner__in=users).exists()
        except Exception:
            ok = False
    else:
        # Keep DB job / owner IDs for --find-residue and manual R2 recovery.
        ok = False
    report.clean("image_jobs_deleted", ok, out)
    failed |= not ok
    try:
        # The service gate is closed, so only this run can have changed today's row.
        rows = AIImageDailyQuota.objects.filter(day_utc=day)
        if quota_before is None:
            rows.delete()
            ok = not AIImageDailyQuota.objects.filter(day_utc=day).exists()
        else:
            rows.update(submitted=quota_before)
            ok = AIImageDailyQuota.objects.filter(
                day_utc=day, submitted=quota_before).exists()
    except Exception:
        ok = False
    report.clean("quota_restored", ok, out)
    failed |= not ok
    if not failed:
        try:
            ids = [u.pk for u in users if u.pk]
            for user in users:
                if user.pk:
                    user.delete()
            from django.contrib.auth import get_user_model
            ok = not get_user_model().objects.filter(pk__in=ids).exists()
        except Exception:
            ok = False
    else:
        # Never remove the only searchable owner prefix when any preceding
        # cleanup step is unverified; require manual residue reconciliation.
        ok = False
    report.clean("disposable_users_deleted", ok, out)
    failed |= not ok
    if failed:
        return Aborted("CLEANUP_INCOMPLETE: " + ",".join(n for n, s in report.cleanup if not s))
    return None
