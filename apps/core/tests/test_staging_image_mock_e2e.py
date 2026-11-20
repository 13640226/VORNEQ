"""Offline tests for the one-use Staging image MOCK E2E. No network, no SDK."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.storage import InMemoryStorage
from django.test import SimpleTestCase, TestCase, override_settings

from apps.ai_core.image_generation.storage import image_storage
from apps.ai_core.models import AIImageDailyQuota, AIImageJob
from apps.core import c02_owner_release as legacy
from apps.core import staging_image_0004_release as release0004
from apps.core import staging_image_mock_e2e as e2e

SHA = "a" * 40
BACKUP = "b" * 64
EVIDENCE = "STAGING-IMAGE0004-RESTORE-PG18-20261120-1520Z-V1"
RELEASE_ID = "IMGE2E-OWNER-20261120"
NOW = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)
API = "https://api.github.com/repos/13640226/VORNEQ"
HOST = "vorneq-staging.example.onrender.com"
R2_HOST = "acct.r2.cloudflarestorage.com"


def comment(*, created=NOW, changed=False, header=e2e.HEADER, issue=e2e.ISSUE, **over):
    manifest = {
        "decision": e2e.DECISION, "release_id": RELEASE_ID, "sha": SHA,
        "service_id": e2e.SERVICE, "postgres_id": e2e.POSTGRES, "database": e2e.DATABASE,
        "provider": "mock", "paid_calls": False, "bucket": e2e.BUCKET, "max_jobs": 1,
        "backup_sha256": BACKUP, "backup_evidence": EVIDENCE,
        "backup_exported_at": (created - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restore_verified_at": (created - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (created + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_acceptance": e2e.RISK,
    }
    manifest.update(over)
    return {
        "id": 123456, "url": f"{API}/issues/comments/123456",
        "issue_url": f"{API}/issues/{issue}",
        "html_url": f"https://github.com/13640226/VORNEQ/issues/{issue}#issuecomment-123456",
        "user": {"login": "13640226", "id": 199411505, "type": "User"},
        "author_association": "OWNER",
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": (created + timedelta(seconds=1) if changed else created
                       ).isoformat().replace("+00:00", "Z"),
        "body": header + "\n" + json.dumps(manifest),
    }


def verify(data, *, now=None):
    return e2e.validate_comment(
        data, comment_id=123456, expected_sha=SHA, release_id=RELEASE_ID,
        backup_sha256=BACKUP, backup_evidence=EVIDENCE, now=now or NOW + timedelta(minutes=1))


class OwnerReleaseTests(SimpleTestCase):
    def test_exact_owner_release_validates(self):
        proof = verify(comment())
        self.assertIsInstance(proof, legacy.VerifiedOwnerRelease)
        self.assertEqual((proof.sha, proof.release_id), (SHA, RELEASE_ID))

    def test_scope_drift_rejected(self):
        variants = {
            "paid provider": comment(provider="openai"),
            "paid calls": comment(paid_calls=True),
            "paid calls as string": comment(paid_calls="false"),
            "more jobs": comment(max_jobs=2),
            "other bucket": comment(bucket="vorneq-production-ai-images"),
            "production service": comment(service_id="srv-dadn07eq1p3s73eccau0"),
            "0004 decision": comment(decision=release0004.DECISION),
            "0004 header reused": comment(header=release0004.HEADER),
            "other sha": comment(sha="c" * 40),
            "other backup": comment(backup_sha256="d" * 64),
            "wrong issue": comment(issue=407),
            "edited": comment(changed=True),
            "stale backup": comment(backup_exported_at=(NOW - timedelta(hours=3))
                                    .strftime("%Y-%m-%dT%H:%M:%SZ")),
            "long ttl": comment(expires_at=(NOW + timedelta(minutes=45))
                                .strftime("%Y-%m-%dT%H:%M:%SZ")),
        }
        for name, data in variants.items():
            with self.subTest(name), self.assertRaises(legacy.OwnerReleaseDenied):
                verify(data)

    def test_extra_or_missing_field_rejected(self):
        data = comment()
        body = json.loads(data["body"].split("\n", 1)[1])
        body["extra"] = 1
        data["body"] = e2e.HEADER + "\n" + json.dumps(body)
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(data)

    def test_non_owner_and_expired_rejected(self):
        data = comment()
        data["author_association"] = "COLLABORATOR"
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(data)
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(), now=NOW + timedelta(minutes=31))


def _env(**over):
    env = {"VORNEQ_ENV": "staging", "RENDER_SERVICE_ID": e2e.SERVICE,
           "RENDER_GIT_COMMIT": SHA, "RENDER_EXTERNAL_HOSTNAME": HOST,
           "VORNEQ_AI_IMAGE_ENABLED": "false", "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": "false",
           e2e.ARM_MODE_KEY: e2e.ARM_MODE, e2e.ARM_SHA_KEY: SHA}
    env.update(over)
    return env


DB = {"ENGINE": "django.db.backends.postgresql", "HOST": e2e.POSTGRES + ".frankfurt-postgres",
      "NAME": e2e.DATABASE, "USER": e2e.ROLE, "PORT": "5432"}
STAGING = {"VORNEQ_ENV": "staging", "DEBUG": False, "ALLOWED_HOSTS": [HOST],
           "VORNEQ_AI_IMAGE_ENABLED": False, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
           "VORNEQ_AI_EMERGENCY_STOP": False}


@override_settings(**STAGING)
class BaseContextTests(SimpleTestCase):
    def setUp(self):
        ready = patch("apps.ai_core.image_generation.storage.durable_storage_ready",
                      return_value=True)
        ready.start()
        self.addCleanup(ready.stop)
        stores = patch.object(e2e.settings, "STORAGES", {
            "ai_images": {"OPTIONS": {"bucket_name": e2e.BUCKET}}}, create=True)
        stores.start()
        self.addCleanup(stores.stop)

    def test_exact_context_passes(self):
        self.assertEqual(e2e.base_context(_env(), SHA, DB, require_arm=True), HOST)

    def test_refusals(self):
        cases = {
            "service": (_env(RENDER_SERVICE_ID="srv-dadn07eq1p3s73eccau0"), DB),
            "sha": (_env(RENDER_GIT_COMMIT="c" * 40), DB),
            "open env gate": (_env(VORNEQ_AI_IMAGE_ENABLED="true"), DB),
            "open paid gate": (_env(VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED="1"), DB),
            "env": (_env(VORNEQ_ENV="production"), DB),
            "arm": (_env(**{e2e.ARM_MODE_KEY: ""}), DB),
            "arm sha": (_env(**{e2e.ARM_SHA_KEY: "c" * 40}), DB),
            "host": (_env(RENDER_EXTERNAL_HOSTNAME="evil.example"), DB),
            "sqlite": (_env(), dict(DB, ENGINE="django.db.backends.sqlite3")),
            "db name": (_env(), dict(DB, NAME="vorneq_production")),
        }
        for name, (env, db) in cases.items():
            with self.subTest(name), self.assertRaises(e2e.Refused):
                e2e.base_context(env, SHA, db, require_arm=True)

    def test_django_gate_and_emergency_stop_refuse(self):
        for flags in ({"VORNEQ_AI_IMAGE_ENABLED": True}, {"VORNEQ_AI_EMERGENCY_STOP": True},
                      {"DEBUG": True}):
            with self.subTest(flags), override_settings(**flags), \
                    self.assertRaises(e2e.Refused):
                e2e.base_context(_env(), SHA, DB)

    def test_bucket_must_be_pinned(self):
        with patch.object(e2e.settings, "STORAGES",
                          {"ai_images": {"OPTIONS": {"bucket_name": "other"}}}), \
                self.assertRaises(e2e.Refused):
            e2e.base_context(_env(), SHA, DB)

    def test_authorize_requires_sha_bound_owner_string(self):
        for auth in ("", f"OWNER-AUTH-STAGING-AI-IMAGE-MOCK-E2E-{RELEASE_ID} @ {'c' * 40}",
                     f"OWNER-AUTH-STAGING-AI-0004-{RELEASE_ID} @ {SHA}"):
            with self.subTest(auth), self.assertRaises(e2e.Refused):
                e2e.authorize(_env(**{e2e.AUTH_KEY: auth}), SHA, DB)


class SignedMemoryStorage(InMemoryStorage):
    """Test stand-in for private R2: URLs carry a signature query."""

    def url(self, name):
        return ("https://acct.r2.cloudflarestorage.com/{}/{}?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                "&X-Amz-Credential=TESTKEY%2F20261120%2Fauto%2Fs3%2Faws4_request"
                "&X-Amz-Date=20261120T170000Z&X-Amz-Expires=3600"
                "&X-Amz-SignedHeaders=host&X-Amz-Signature=test").format(e2e.BUCKET, name)


TARGET = e2e.ApprovedTarget(RELEASE_ID, legacy.VerifiedOwnerRelease(
    release_id=RELEASE_ID, comment_id=123456, sha=SHA, body_sha256="e" * 64,
    backup_sha256=BACKUP, backup_evidence=EVIDENCE, expires_at=NOW))
STORES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "ai_images": {"BACKEND": "apps.core.tests.test_staging_image_mock_e2e.SignedMemoryStorage"},
}


@override_settings(STORAGES=STORES, **STAGING)
class ExecuteOnceTests(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"RENDER_SERVICE_ID": e2e.SERVICE,
                                      "RENDER_GIT_COMMIT": SHA})
        env.start()
        self.addCleanup(env.stop)
        self.consume = Mock()
        self.sdk_imports = []

    def fetch(self, url):
        try:
            import openai  # noqa: F401
            self.sdk_imports.append("imported")
        except ImportError:
            pass
        if "?" not in url:
            return e2e.Download(403, "application/xml", b"<Error><Code>AccessDenied</Code></Error>")
        name = url.split(e2e.BUCKET + "/", 1)[1].split("?", 1)[0]
        with image_storage().open(name) as handle:
            return e2e.Download(200, "image/png", handle.read())

    def run_e2e(self, fetch=None):
        return e2e.execute_once(None, TARGET, SHA, public_host=HOST, out=lambda _: None,
                                fetch=fetch or self.fetch, consume=self.consume,
                                endpoint_host=R2_HOST)

    def assert_clean(self):
        self.assertFalse(AIImageJob.objects.exists())
        self.assertFalse(AIImageDailyQuota.objects.exists())
        self.assertFalse(get_user_model().objects.filter(
            username__startswith="vorneq-e2e-").exists())
        self.assertEqual(image_storage().listdir("")[1], [])

    def test_full_mock_e2e_passes_and_cleans_up(self):
        sentinel = object()
        with patch.dict(sys.modules, {"openai": sentinel}):
            report = self.run_e2e()
            self.assertIs(sys.modules["openai"], sentinel)
        self.consume.assert_called_once()
        self.assertEqual(report.steps, [
            "process_gate_mock_only", "anonymous_rejected", "csrf_enforced",
            "api_submit_202", "idempotent_resubmit", "worker_once_completed",
            "r2_object_exists", "owner_detail_signed_url", "other_user_404",
            "anonymous_detail_401", "signed_url_sigv4", "signed_download_digest_match",
            "unsigned_access_denied",
        ])
        self.assertTrue(all(ok for _, ok in report.cleanup))
        self.assertEqual(self.sdk_imports, [])
        self.assert_clean()

    def test_existing_quota_row_is_restored_exactly(self):
        day = datetime.now(timezone.utc).date()
        AIImageDailyQuota.objects.create(day_utc=day, submitted=0)
        self.run_e2e()
        self.assertEqual(AIImageDailyQuota.objects.get(day_utc=day).submitted, 0)

    def test_unrelated_queue_refuses_before_receipt_or_write(self):
        other = get_user_model().objects.create_user(username="real-user", password="x")
        job = AIImageJob.objects.create(owner=other, prompt="real", prompt_digest="0" * 64,
                                        model_id="mock", provider="mock")
        with self.assertRaises(e2e.Refused):
            self.run_e2e()
        self.consume.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, AIImageJob.STATUS_QUEUED)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_failure_mid_run_still_cleans_up(self):
        with self.assertRaises(e2e.Aborted):
            self.run_e2e(fetch=lambda url: e2e.Download(200, "image/png", b"not-a-png"))
        self.assert_clean()

    def test_r2_put_then_worker_failure_without_storage_key_is_cleaned(self):
        """Provider/storage writes object, then job fails before DB key update."""
        from apps.ai_core.image_generation import service
        from apps.ai_core.image_generation.storage import store_image as save_real

        called = []
        def save_then_fail(*, job, content):
            key, digest = save_real(job=job, content=content)
            called.append((key, digest))
            self.assertTrue(image_storage().exists(key))
            raise RuntimeError("injected failure after R2 write")

        with patch.object(service, "store_image", side_effect=save_then_fail):
            with self.assertRaises(e2e.Aborted):
                self.run_e2e()
        self.assertEqual(len(called), 1)
        self.assertFalse(image_storage().exists(called[0][0]))
        self.assert_clean()

    def test_worker_crash_after_upload_before_return_cleans_expected_key(self):
        """A worker that raises after PUT never reports job.storage_key."""
        from apps.ai_core.image_generation import service
        from django.core.files.base import ContentFile

        keys = []
        def upload_then_crash():
            job = AIImageJob.objects.get(status=AIImageJob.STATUS_QUEUED)
            key = "ai-generated/{}/{}.png".format(job.owner_id, job.pk.hex)
            keys.append(key)
            self.assertEqual(
                image_storage().save(key, ContentFile(b"synthetic-mock-crash")), key)
            raise RuntimeError("injected worker crash after upload")

        with patch.object(service, "process_next_image_job", side_effect=upload_then_crash):
            with self.assertRaises(e2e.Aborted):
                self.run_e2e()
        self.assertEqual(len(keys), 1)
        self.assertFalse(image_storage().exists(keys[0]))
        self.assert_clean()

    def test_r2_delete_error_retains_users_and_job_for_residue_finder(self):
        """Never delete the only owner reference if R2 cleanup is uncertain."""
        storage = image_storage()
        with patch.object(storage, "delete", side_effect=OSError("test R2 delete failure")):
            with self.assertRaisesMessage(e2e.Aborted, "CLEANUP_INCOMPLETE"):
                self.run_e2e()

        users = list(get_user_model().objects.filter(
            username__startswith=e2e.USER_PREFIX))
        self.assertEqual(len(users), 2)
        owner = next(u for u in users if u.username.endswith("-owner"))
        jobs = AIImageJob.objects.filter(owner=owner)
        self.assertEqual(jobs.count(), 1)
        key = jobs.get().storage_key
        self.assertTrue(key and storage.exists(key))
        residue = e2e.find_residue(out=lambda _: None)
        self.assertEqual(residue["e2e_users"], 2)
        self.assertEqual(residue["e2e_jobs"], 1)
        self.assertEqual(residue["e2e_r2_objects"], 1)

        # Test-only cleanup, outside the simulated storage outage.
        storage.delete(key)
        jobs.delete()
        for user in users:
            user.delete()
        self.assert_clean()

    def test_residue_finder_missing_memory_prefix_not_a_storage_outage(self):
        """The second disposable user has no R2 directory after a failed PUT."""
        first = get_user_model().objects.create(username=e2e.USER_PREFIX + "first")
        get_user_model().objects.create(username=e2e.USER_PREFIX + "empty")
        from django.core.files.base import ContentFile
        storage = image_storage()
        key = "ai-generated/{}/test.png".format(first.pk)
        storage.save(key, ContentFile(b"synthetic"))
        result = e2e.find_residue(out=lambda _: None)
        self.assertEqual(result["e2e_users"], 2)
        self.assertEqual(result["e2e_r2_objects"], 1)
        storage.delete(key)

    def test_residue_finder_real_storage_failure_remains_unknown(self):
        """Do not mistake a genuine storage outage for a missing prefix."""
        get_user_model().objects.create(username=e2e.USER_PREFIX + "outage")
        storage = image_storage()
        with patch.object(storage, "listdir", side_effect=OSError("R2 unavailable")):
            result = e2e.find_residue(out=lambda _: None)
        self.assertIsNone(result["e2e_r2_objects"])

    def test_real_staging_failure_signed_get_rejected_is_reported_and_cleaned(self):
        rejected = e2e.Download(403, "application/xml",
                                b"<Error><Code>AccessDenied</Code></Error>")
        lines = []
        with self.assertRaises(e2e.Aborted) as ctx:
            e2e.execute_once(None, TARGET, SHA, public_host=HOST, out=lines.append,
                             fetch=lambda url: rejected, consume=self.consume,
                             endpoint_host=R2_HOST)
        message = str(ctx.exception)
        self.assertIn("signed download rejected by storage", message)
        self.assertIn("status=403", message)
        self.assertIn("r2_code=AccessDenied", message)
        self.assertNotIn("X-Amz", message + "".join(lines))
        self.assertIn("E2E_STEP_OK signed_url_sigv4", lines)
        self.assert_clean()

    def test_sigv2_signed_url_aborts_before_any_download(self):
        calls = []
        legacy = "https://{}/{}/{{}}?AWSAccessKeyId=AKIA&Signature=x&Expires=1".format(
            R2_HOST, e2e.BUCKET)
        with patch.object(SignedMemoryStorage, "url", lambda self, name: legacy.format(name)), \
                self.assertRaisesMessage(e2e.Aborted, "legacy SigV2"):
            self.run_e2e(fetch=lambda url: calls.append(url))
        self.assertEqual(calls, [])
        self.assert_clean()

    def test_service_gate_stays_closed_after_run(self):
        from apps.ai_core.image_generation import policy
        self.run_e2e()
        self.assertFalse(policy.enabled())
        self.assertFalse(policy.paid_provider_enabled())

    def test_owner_isolation_leak_is_detected_and_cleaned(self):
        from types import SimpleNamespace

        def leaky_filter(pk, owner):  # ignores the owner: a cross-user leak
            return AIImageJob.objects.filter(pk=pk)

        leaky = SimpleNamespace(objects=SimpleNamespace(filter=leaky_filter))
        with patch("apps.ai_core.image_generation.views.AIImageJob", leaky), \
                self.assertRaisesMessage(e2e.Aborted, "other user can see owner job"):
            self.run_e2e()
        self.assert_clean()


class FakeLockConnection:
    """Records advisory-lock SQL; ORM work still uses the real test database."""
    vendor = "postgresql"

    def __init__(self, granted):
        self.granted, self.sql = granted, []

    def cursor(self):
        outer = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params):
                outer.sql.append((sql, tuple(params)))

            def fetchone(self):
                return (outer.granted,)
        return Cursor()


@override_settings(STORAGES=STORES, **STAGING)
class LockAndResidueTests(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"RENDER_SERVICE_ID": e2e.SERVICE,
                                      "RENDER_GIT_COMMIT": SHA})
        env.start()
        self.addCleanup(env.stop)
        self.consume = Mock()

    def run_with(self, connection, fetch=None):
        helper = ExecuteOnceTests()
        helper.sdk_imports = []
        return e2e.execute_once(connection, TARGET, SHA, public_host=HOST,
                                out=lambda _: None, fetch=fetch or helper.fetch,
                                consume=self.consume, endpoint_host=R2_HOST)

    def test_concurrent_run_refused_before_receipt_or_write(self):
        conn = FakeLockConnection(granted=False)
        with self.assertRaisesMessage(e2e.Refused, "another mock E2E run holds the lock"):
            self.run_with(conn)
        self.consume.assert_not_called()
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual([q for q, _ in conn.sql], ["SELECT pg_try_advisory_lock(%s)"])

    def test_lock_held_for_run_and_released_even_on_failure(self):
        for fetch in (None, lambda url: e2e.Download(200, "image/png", b"not-a-png")):
            conn = FakeLockConnection(granted=True)
            with self.subTest(failing=fetch is not None):
                if fetch is None:
                    self.run_with(conn)
                else:
                    with self.assertRaises(e2e.Aborted):
                        self.run_with(conn, fetch=fetch)
                self.assertEqual(conn.sql, [
                    ("SELECT pg_try_advisory_lock(%s)", (e2e.LOCK_KEY,)),
                    ("SELECT pg_advisory_unlock(%s)", (e2e.LOCK_KEY,)),
                ])

    def test_residue_of_earlier_run_blocks_new_run(self):
        get_user_model().objects.create(username=e2e.USER_PREFIX + "old-owner")
        with self.assertRaisesMessage(e2e.Refused, "residue of an earlier mock E2E run"):
            self.run_with(None)
        self.consume.assert_not_called()

    def test_find_residue_reports_without_changing_anything(self):
        lines = []
        self.assertEqual(e2e.find_residue(out=lines.append)["e2e_users"], 0)
        self.assertIn("E2E_RESIDUE_RESULT: NONE", lines)
        user = get_user_model().objects.create(username=e2e.USER_PREFIX + "crash-owner")
        AIImageJob.objects.create(owner=user, prompt="", prompt_digest="0" * 64,
                                  model_id="mock", provider="mock",
                                  status=AIImageJob.STATUS_COMPLETED)
        from django.core.files.base import ContentFile
        image_storage().save("ai-generated/{}/x.png".format(user.pk), ContentFile(b"x"))
        lines = []
        result = e2e.find_residue(out=lines.append)
        self.assertEqual((result["e2e_users"], result["e2e_jobs"], result["e2e_r2_objects"]),
                         (1, 1, 1))
        self.assertIn("E2E_RESIDUE_RESULT: PRESENT_OR_UNKNOWN", lines)
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())
        self.assertEqual(AIImageJob.objects.count(), 1)
        self.assertTrue(image_storage().exists("ai-generated/{}/x.png".format(user.pk)))


class CommandTests(TestCase):
    def test_command_refuses_outside_staging_without_writes(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        for args in (["--expected-sha", SHA], ["--expected-sha", SHA, "--execute",
                                               "--release-id", RELEASE_ID]):
            with self.subTest(args), self.assertRaisesMessage(
                    CommandError, "STAGING_IMAGE_MOCK_E2E_REFUSED"):
                call_command("run_staging_image_mock_e2e_once", *args)
        self.assertFalse(AIImageJob.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_find_residue_refuses_outside_staging_and_with_execute(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        for args in (["--expected-sha", SHA, "--find-residue"],
                     ["--expected-sha", SHA, "--find-residue", "--execute"],
                     ["--expected-sha", SHA, "--diagnose-signed-url"],
                     ["--expected-sha", SHA, "--diagnose-signed-url", "--execute"]):
            with self.subTest(args), self.assertRaisesMessage(
                    CommandError, "STAGING_IMAGE_MOCK_E2E_REFUSED"):
                call_command("run_staging_image_mock_e2e_once", *args)


class RealPostgresLockTests(TestCase):
    def test_second_session_cannot_take_the_lock(self):
        from unittest import SkipTest
        from django.db import connection
        if connection.vendor != "postgresql":
            raise SkipTest("advisory locks need PostgreSQL")
        held = e2e.acquire_run_lock(connection)
        other = connection.copy(alias="e2e_lock_probe")
        try:
            self.assertTrue(held)
            with self.assertRaisesMessage(e2e.Refused, "holds the lock"):
                e2e.acquire_run_lock(other)
            e2e.release_run_lock(connection, held)
            self.assertTrue(e2e.acquire_run_lock(other))
            e2e.release_run_lock(other, True)
        finally:
            other.close()
