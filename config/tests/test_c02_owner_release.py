"""Negative owner-issuance proof cases: no live GitHub calls or DB writes."""
import copy
import json
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import SimpleTestCase

from apps.core import c02_owner_release as rel
from apps.core import c02_stage_c_runner as runner

SHA = "a" * 40
ALT_SHA = "b" * 40
BACKUP_SHA = "c" * 64
RELEASE_ID = "TEST-RELEASE-001"
ID = 6926563064
CREATED = datetime(2026, 11, 16, 19, 30, tzinfo=timezone.utc)
NOW = CREATED + timedelta(minutes=3)
EXPIRY = "2026-11-16T19:40:00Z"


def manifest(**changes):
    result = {
        "decision": rel.EXPECTED_SCOPE,
        "release_id": RELEASE_ID,
        "sha": SHA,
        "service_id": "srv-dadn07eq1p3s73eccau0",
        "postgres_id": "dpg-dagru1h42hec73eqr960-a",
        "database": "vorneq_production_db",
        "session_user": "vorneq_prod_app_rot_20261116",
        "current_user": "vorneq_production_db_user",
        "migrations": list(rel.EXPECTED_MIGRATIONS),
        "backup_sha256": BACKUP_SHA,
        "backup_evidence": "restore-proof-20261116:verified",
        "expires_at": EXPIRY,
        "risk_acceptance": rel.EXPECTED_RISK,
    }
    result.update(changes)
    return result


def comment(**updates):
    created = CREATED.strftime("%Y-%m-%dT%H:%M:%SZ")
    result = {
        "id": ID,
        "url": f"https://api.github.com/repos/{rel.REPOSITORY}/issues/comments/{ID}",
        "issue_url": rel.API_ISSUE_URL,
        "html_url": f"https://github.com/{rel.REPOSITORY}/issues/{rel.ISSUE_NUMBER}#issuecomment-{ID}",
        "author_association": "OWNER",
        "created_at": created,
        "updated_at": created,
        "user": {"login": rel.OWNER_LOGIN, "id": rel.OWNER_USER_ID, "type": "User"},
        "body": rel.RELEASE_HEADER + "\n" + json.dumps(manifest(), separators=(",", ":"), sort_keys=True),
    }
    result.update(updates)
    return result


def verify(data=None, **kwargs):
    return rel.validate_github_comment(
        data if data is not None else comment(), comment_id=ID, expected_sha=SHA,
        release_id=RELEASE_ID, backup_sha256=BACKUP_SHA,
        backup_evidence="restore-proof-20261116:verified", now=NOW, **kwargs,
    )


class OwnerReleaseAuthenticationTests(SimpleTestCase):
    def test_exact_owner_comment_accepted_as_structured_evidence(self):
        proof = verify()
        self.assertEqual(proof.release_id, RELEASE_ID)
        self.assertEqual(proof.comment_id, ID)
        self.assertEqual(proof.sha, SHA)
        self.assertEqual(len(proof.body_sha256), 64)

    def test_wrong_author_or_comment_metadata_denied(self):
        variants = [
            {"user": {"login": "imposter", "id": rel.OWNER_USER_ID, "type": "User"}},
            {"user": {"login": rel.OWNER_LOGIN, "id": 100, "type": "User"}},
            {"user": {"login": rel.OWNER_LOGIN, "id": rel.OWNER_USER_ID, "type": "Bot"}},
            {"author_association": "CONTRIBUTOR"},
            {"id": ID + 1},
            {"url": "https://other.github.example/issues/comments/" + str(ID)},
            {"issue_url": "https://api.github.com/repos/13640226/VORNEQ/issues/448"},
            {"html_url": "https://github.com/13640226/VORNEQ/issues/448"},
            {"updated_at": "2026-11-16T19:31:00Z"},  # Edited approvals are revoked.
            {"created_at": "2026-11-17T19:30:00Z", "updated_at": "2026-11-17T19:30:00Z"},
            {"body": "OWNER-AUTH-C02-MIGRATION-TEST-RELEASE-001 @ " + SHA},
            {"body": "Owner approved migration in chat."},
            {"body": None},
            {"user": {}},
        ]
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(rel.OwnerReleaseDenied):
                verify(comment(**changed))

    def test_manifest_mutations_fail_closed(self):
        variants = [
            {"decision": "AUTHORIZE_DEPLOY_ONLY"},
            {"risk_acceptance": "NO"},
            {"release_id": "DIFFERENT-ID"},
            {"sha": ALT_SHA},
            {"service_id": "srv-fake"},
            {"postgres_id": "dpg-fake"},
            {"database": "vorneq_staging"},
            {"session_user": "vorneq_production_db_user"},
            {"current_user": "vorneq_prod_app_rot_20261116"},
            {"migrations": ["ai_core.0001_initial"]},
            {"migrations": ["ai_core.0002_aichatrequestguard", "ai_core.0001_initial"]},
            {"backup_sha256": "0" * 64},
            {"backup_evidence": "other-backup"},
            {"expires_at": "2026-11-16T19:46:00Z"},  # >15m from issuance
            {"expires_at": "not-a-timestamp"},
            {"unapproved_extra_key": "x"},
        ]
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(rel.OwnerReleaseDenied):
                payload = manifest(**changed)
                raw = rel.RELEASE_HEADER + "\n" + json.dumps(payload)
                verify(comment(body=raw))

    def test_json_duplicate_keys_and_extra_prose_denied(self):
        original = json.dumps(manifest())
        variants = [
            rel.RELEASE_HEADER + "\n" + original[:-1] + ',"sha":"' + ALT_SHA + '"}',
            rel.RELEASE_HEADER + "\n" + original + "\nProceed now",
            rel.RELEASE_HEADER + "\n[]",
            rel.RELEASE_HEADER + "\n{not-json}",
        ]
        for raw in variants:
            with self.subTest(raw=raw[:30]), self.assertRaises(rel.OwnerReleaseDenied):
                verify(comment(body=raw))

    def test_expiry_window_and_clock_drift_fail_closed(self):
        for now in [CREATED - timedelta(minutes=2), CREATED + timedelta(minutes=10),
                    CREATED + timedelta(days=1)]:
            with self.subTest(now=now), self.assertRaises(rel.OwnerReleaseDenied):
                rel.validate_github_comment(
                    comment(), comment_id=ID, expected_sha=SHA,
                    release_id=RELEASE_ID, backup_sha256=BACKUP_SHA,
                    backup_evidence="restore-proof-20261116:verified", now=now,
                )

    def test_backup_identifier_and_sha_mismatch_denied(self):
        with self.assertRaises(rel.OwnerReleaseDenied):
            rel.validate_github_comment(
                comment(), comment_id=ID, expected_sha=SHA,
                release_id=RELEASE_ID, backup_sha256="0" * 64,
                backup_evidence="restore-proof-20261116:verified", now=NOW,
            )
        with self.assertRaises(rel.OwnerReleaseDenied):
            rel.validate_github_comment(
                comment(), comment_id=ID, expected_sha=SHA,
                release_id=RELEASE_ID, backup_sha256=BACKUP_SHA,
                backup_evidence="untrusted", now=NOW,
            )

    def test_network_never_attempted_without_scoped_read_token(self):
        env = {
            "VORNEQ_C02_OWNER_COMMENT_ID": str(ID),
            "VORNEQ_C02_BACKUP_SHA256": BACKUP_SHA,
            "VORNEQ_C02_BACKUP_EVIDENCE": "restore-proof-20261116:verified",
        }
        with mock.patch.object(rel, "fetch_github_comment") as fetch:
            with self.assertRaisesRegex(rel.OwnerReleaseDenied, "read-only GitHub token"):
                rel.verify_live_owner_release(env, expected_sha=SHA, release_id=RELEASE_ID)
            fetch.assert_not_called()

    def test_api_404_timeout_redirect_and_invalid_json_denied(self):
        class Response:
            def __init__(self, code, body=b"{}"):
                self.status = code
                self.body = body

            def getheader(self, name, default=None):
                return "application/json"

            def read(self, length):
                return self.body[:length]

        for code in (301, 302, 403, 404, 500):
            with self.subTest(code=code), mock.patch.object(
                    rel.http.client, "HTTPSConnection") as conn:
                conn.return_value.getresponse.return_value = Response(code)
                with self.assertRaises(rel.OwnerReleaseDenied):
                    rel.fetch_github_comment(ID, "synthetic-read-token")
        with mock.patch.object(rel.http.client, "HTTPSConnection") as conn:
            conn.return_value.getresponse.return_value = Response(200, b"{broken")
            with self.assertRaises(rel.OwnerReleaseDenied):
                rel.fetch_github_comment(ID, "synthetic-read-token")
        with mock.patch.object(rel.http.client, "HTTPSConnection", side_effect=TimeoutError):
            with self.assertRaises(rel.OwnerReleaseDenied):
                rel.fetch_github_comment(ID, "synthetic-read-token")

    def test_fetch_uses_pinned_host_and_exact_comment_id_no_redirects(self):
        with mock.patch.object(rel.http.client, "HTTPSConnection") as conn:
            conn.return_value.getresponse.return_value.status = 200
            conn.return_value.getresponse.return_value.getheader.return_value = "application/json"
            conn.return_value.getresponse.return_value.read.return_value = b"{}"
            rel.fetch_github_comment(ID, "synthetic-read-token")
            self.assertEqual(conn.call_args.args[0], "api.github.com")
            args = conn.return_value.request.call_args.args
            self.assertEqual(args[1], f"/repos/{rel.REPOSITORY}/issues/comments/{ID}")
            self.assertNotIn("synthetic-read-token", args[1])

    def test_live_verifier_fetches_fresh_and_checks_backend_metadata(self):
        env = {
            "VORNEQ_C02_OWNER_COMMENT_ID": str(ID),
            "VORNEQ_C02_GITHUB_READ_TOKEN": "synthetic-read-token",
            "VORNEQ_C02_BACKUP_SHA256": BACKUP_SHA,
            "VORNEQ_C02_BACKUP_EVIDENCE": "restore-proof-20261116:verified",
        }
        original_validate = rel.validate_github_comment
        def at_fixed_time(*args, **kwargs):
            return original_validate(*args, **kwargs, now=NOW)
        with mock.patch.object(rel, "fetch_github_comment", return_value=comment()) as fetch, \
                mock.patch.object(rel, "validate_github_comment", side_effect=at_fixed_time):
            proof = rel.verify_live_owner_release(env, expected_sha=SHA, release_id=RELEASE_ID)
            self.assertEqual(proof.comment_id, ID)
            fetch.assert_called_once_with(ID, "synthetic-read-token")

    def test_unverified_target_cannot_enter_production_runner(self):
        target = runner.Target(
            "production", "vorneq_production_db", "vorneq_production_db_user",
            18, RELEASE_ID, login_user="vorneq_prod_app_rot_20261116",
        )
        fake_connection = mock.MagicMock()
        with mock.patch.object(runner, "PRODUCTION_WRITE_ENABLED", True):
            with self.assertRaisesRegex(runner.RunnerRefused, "independent GitHub owner proof missing"):
                runner.run(fake_connection, target, SHA, commit=True, source_sha=lambda: SHA)
        fake_connection.cursor.assert_not_called()

    def test_production_default_remains_disabled(self):
        self.assertIs(runner.PRODUCTION_WRITE_ENABLED, False)
        self.assertFalse(runner.AUTHORIZATION.fullmatch("OWNER-AUTH-C02-MIGRATION-bad"))
