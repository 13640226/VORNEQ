"""Offline evidence/identity tests; hosted 0006 execution must remain denied."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from apps.core import c02_message_feedback_0006_release as release
from apps.core import c02_message_feedback_0006_hosted as hosted
from apps.core import c02_owner_release as legacy
from apps.core.c02_message_feedback_0006_runner import Refused

SOURCE = "a"*40
LIVE = hosted.COMPATIBLE_LIVE_SHA
BACKUP = "b"*64
EVIDENCE = "RESTORE-ISOLATED-TEST"
RID = "FEEDBACK-0006-TEST"
NOW = datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)
ROOT = "https://api.github.com/repos/13640226/VORNEQ"


def comment(env="staging", **changes):
    t = release.TARGETS[env]
    fields = {
        "decision": release.DECISION, "environment": env, "release_id": RID,
        "source_sha": SOURCE, "live_sha": LIVE, "service_id": t.service,
        "postgres_id": t.postgres, "database": t.database,
        "session_user": t.login, "current_user": t.role,
        "migrations": [release.MIGRATION], "backup_sha256": BACKUP,
        "backup_evidence": EVIDENCE,
        "backup_exported_at": (NOW-timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restore_verified_at": (NOW-timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (NOW+timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_acceptance": release.RISK,
    }
    fields.update(changes)
    return {
        "id": 123, "url": ROOT+"/issues/comments/123", "issue_url": ROOT+"/issues/770",
        "html_url": "https://github.com/13640226/VORNEQ/pull/770#issuecomment-123",
        "user": {"login": legacy.OWNER_LOGIN, "id": legacy.OWNER_USER_ID, "type": "User"},
        "author_association": "OWNER", "created_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "body": release.HEADER+"\n"+json.dumps(fields),
    }


def validate(c, env="staging", now=NOW):
    return release.validate(c, comment_id=123, environment=env, source_sha=SOURCE,
                            live_sha=LIVE, release_id=RID, backup_sha256=BACKUP,
                            backup_evidence=EVIDENCE, now=now)


class OwnerEvidenceTests(SimpleTestCase):
    def test_exact_environment_and_dual_sha(self):
        for env in ("staging", "production"):
            proof = validate(comment(env), env)
            self.assertEqual((proof.environment, proof.source_sha, proof.live_sha),
                             (env, SOURCE, LIVE))
        with self.assertRaises(legacy.OwnerReleaseDenied):
            validate(comment("production"), "staging")

    def test_scope_and_backup_drift(self):
        for key, value in (("source_sha", "c"*40), ("live_sha", "d"*40),
                           ("migrations", ["ai_core.0004_image_generation_job_v1"]),
                           ("backup_sha256", "d"*64), ("session_user", "wrong"),
                           ("backup_evidence", "OTHER-RESTORE"),
                           ("risk_acceptance", "anything")):
            with self.subTest(key=key), self.assertRaises(legacy.OwnerReleaseDenied):
                validate(comment(**{key: value}))

    def test_edited_wrong_owner_origin_expiry_and_duplicate(self):
        cases = []
        for k, value in (("author_association", "MEMBER"), ("issue_url", ROOT+"/issues/407"),
                         ("updated_at", "2026-11-27T18:00:01Z"),
                         ("body", release.HEADER+'\n{"decision":"x","decision":"y"}')):
            c = comment()
            c[k] = value
            cases.append(c)
        for c in cases:
            with self.assertRaises(legacy.OwnerReleaseDenied):
                validate(c)
        with self.assertRaises(legacy.OwnerReleaseDenied):
            validate(comment(), now=NOW+timedelta(minutes=11))
        with self.assertRaises(legacy.OwnerReleaseDenied):
            validate(comment(backup_exported_at="2026-11-27T12:00:00Z"))

    def test_missing_token_never_calls_network(self):
        with patch.object(legacy, "fetch_github_comment") as fetch:
            with self.assertRaises(legacy.OwnerReleaseDenied):
                release.verify_live({}, environment="staging", source_sha=SOURCE,
                                    live_sha=LIVE, release_id=RID)
            fetch.assert_not_called()

    def test_receipt_scope(self):
        first = validate(comment())
        second = validate(comment("production"), "production")
        self.assertNotEqual(hosted.receipt_uuid(first), hosted.receipt_uuid(second))
        self.assertEqual(hosted.receipt_payload(first)["event_id"], hosted.receipt_uuid(first))


class HostedContextTests(SimpleTestCase):
    def test_context_refuses_old_or_wrong_artifact_before_database(self):
        target = release.TARGETS["staging"]
        env = {
            "VORNEQ_ENV": "staging", "RENDER_GIT_COMMIT": LIVE,
            "RENDER_SERVICE_ID": target.service,
            "DJANGO_SETTINGS_MODULE": "config.settings_render",
            "VORNEQ_C02_0006_WRITE_MODE": hosted.ARM_MODE,
            "VORNEQ_C02_0006_ARMED_SOURCE_SHA": SOURCE,
            "VORNEQ_C02_0006_ARMED_LIVE_SHA": LIVE,
            "DATABASE_URL": f"postgresql://{target.login}:fake@{target.postgres}:5432/{target.database}",
        }
        cfg = {"ENGINE": "django.db.backends.postgresql", "HOST": target.postgres,
               "NAME": target.database, "USER": target.login, "PASSWORD": "fake", "PORT": "5432"}
        flags = {k: False for k in hosted.CLOSED_FLAGS}
        with override_settings(VORNEQ_ENV="staging", DEBUG=False, **flags):
            self.assertEqual(hosted.verify_context(env, "staging", SOURCE, LIVE, cfg, SOURCE), target)
            for k, v in (("RENDER_SERVICE_ID", "wrong"), ("RENDER_GIT_COMMIT", SOURCE),
                         ("VORNEQ_C02_0006_WRITE_MODE", ""), ("VORNEQ_AI_FEEDBACK_ENABLED", "true")):
                with self.subTest(key=k), self.assertRaises(Refused):
                    hosted.verify_context(dict(env, **{k: v}), "staging", SOURCE, LIVE, cfg, SOURCE)
            with self.assertRaises(Refused):
                hosted.verify_context(env, "staging", SOURCE, LIVE, cfg, LIVE)
            with self.assertRaises(Refused):
                hosted.verify_context(env, "staging", SOURCE, LIVE, dict(cfg, NAME="wrong"), SOURCE)
