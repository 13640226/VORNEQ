"""Acceptance tests T1-T9 for scripts/merge_authorization.py (GOV_BREACH_01)."""

import importlib.util
import sys
import urllib.error
from pathlib import Path
from unittest import TestCase, mock

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "merge_authorization.py"
_SPEC = importlib.util.spec_from_file_location("vorneq_merge_authorization", _PATH)
ma = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = ma
_SPEC.loader.exec_module(ma)

OWNER = "13640226"
PR = 600
HEAD = "a" * 40
OLD = "b" * 40
T0 = "2026-11-05T01:00:00Z"
T1 = "2026-11-05T01:05:00Z"


def comment(body, *, cid=1, login=OWNER, assoc="OWNER", created=T0, updated=None, user_type="User"):
    return {
        "id": cid,
        "body": body,
        "user": {"login": login, "type": user_type},
        "author_association": assoc,
        "created_at": created,
        "updated_at": updated or created,
    }


def auth(sha=HEAD, pr=PR, auth_id="OWNER-AUTH-MERGE-TEST-01"):
    return f"OWNER-AUTH-MERGE {auth_id} PR #{pr} @ {sha}"


class MergeAuthorizationDecisionTests(TestCase):
    def test_t1_no_authorization_denies(self):
        d = ma.decide(PR, HEAD, [comment("LGTM")])
        self.assertFalse(d.allowed)

    def test_t1_empty_comment_list_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, []).allowed)

    def test_t2_valid_authorization_allows(self):
        d = ma.decide(PR, HEAD, [comment(auth())])
        self.assertTrue(d.allowed)
        self.assertEqual(d.auth_id, "OWNER-AUTH-MERGE-TEST-01")

    def test_t3_authorization_for_old_sha_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment(auth(sha=OLD))]).allowed)

    def test_t4_other_account_denies(self):
        c = comment(auth(), login="hamidrezaasadian7-boop", assoc="COLLABORATOR")
        self.assertFalse(ma.decide(PR, HEAD, [c]).allowed)

    def test_t4_owner_login_without_owner_association_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment(auth(), assoc="COLLABORATOR")]).allowed)

    def test_t4_bot_account_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment(auth(), user_type="Bot")]).allowed)

    def test_t5_short_sha_denies(self):
        body = f"OWNER-AUTH-MERGE OWNER-AUTH-MERGE-TEST-01 PR #{PR} @ {HEAD[:7]}"
        self.assertFalse(ma.decide(PR, HEAD, [comment(body)]).allowed)

    def test_t5_uppercase_sha_denies(self):
        self.assertFalse(ma.decide(PR, "A" * 40, [comment(auth(sha="A" * 40))]).allowed)

    def test_t5_extra_text_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment(auth() + " please merge")]).allowed)

    def test_t5_quoted_authorization_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment("> " + auth())]).allowed)

    def test_t6_authorization_for_other_pr_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment(auth(pr=PR + 1))]).allowed)

    def test_t7_edited_authorization_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [comment(auth(), updated=T1)]).allowed)

    def test_t7_deleted_authorization_denies(self):
        # A deleted comment is simply absent from the API response.
        self.assertFalse(ma.decide(PR, HEAD, [comment("LGTM", cid=2)]).allowed)

    def test_t8_revoke_after_authorization_denies(self):
        comments = [comment(auth(), cid=1), comment(f"OWNER-AUTH-REVOKE PR #{PR}", cid=2, created=T1)]
        self.assertFalse(ma.decide(PR, HEAD, comments).allowed)

    def test_t8_authorization_after_revoke_allows(self):
        comments = [comment(f"OWNER-AUTH-REVOKE PR #{PR}", cid=1), comment(auth(), cid=2, created=T1)]
        self.assertTrue(ma.decide(PR, HEAD, comments).allowed)

    def test_t8_revoke_for_other_pr_is_ignored(self):
        comments = [comment(auth(), cid=1), comment(f"OWNER-AUTH-REVOKE PR #{PR + 1}", cid=2, created=T1)]
        self.assertTrue(ma.decide(PR, HEAD, comments).allowed)

    def test_t8_revoke_by_other_account_is_ignored(self):
        comments = [
            comment(auth(), cid=1),
            comment(f"OWNER-AUTH-REVOKE PR #{PR}", cid=2, created=T1, login="someone", assoc="NONE"),
        ]
        self.assertTrue(ma.decide(PR, HEAD, comments).allowed)

    def test_t9_malformed_comment_data_denies(self):
        self.assertFalse(ma.decide(PR, HEAD, [{"body": auth()}]).allowed)

    def test_t9_invalid_inputs_deny(self):
        self.assertFalse(ma.decide(0, HEAD, [comment(auth())]).allowed)
        self.assertFalse(ma.decide(PR, "not-a-sha", [comment(auth())]).allowed)
        self.assertFalse(ma.decide(PR, HEAD, None).allowed)


class MergeAuthorizationMainFailClosedTests(TestCase):
    ENV = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r", "PR_NUMBER": str(PR)}

    def _client(self, comments=None, comments_error=None):
        client = mock.Mock()
        client.pull_request.return_value = {"head": {"sha": HEAD}, "base": {"ref": "main"}}
        if comments_error:
            client.issue_comments.side_effect = comments_error
        else:
            client.issue_comments.return_value = comments or []
        return client

    def test_t9_api_error_sets_failure_status(self):
        client = self._client(comments_error=urllib.error.URLError("down"))
        with mock.patch.dict("os.environ", self.ENV, clear=True), \
                mock.patch.object(ma, "GitHubClient", return_value=client):
            self.assertEqual(ma.main(), 1)
        client.set_status.assert_called_once_with(HEAD, "failure", "evaluation error (fail-closed)")

    def test_t9_missing_token_denies(self):
        env = dict(self.ENV, GITHUB_TOKEN="")
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(ma.main(), 1)

    def test_main_deny_sets_failure_status(self):
        client = self._client(comments=[comment("LGTM")])
        with mock.patch.dict("os.environ", self.ENV, clear=True), \
                mock.patch.object(ma, "GitHubClient", return_value=client):
            self.assertEqual(ma.main(), 1)
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_main_allow_sets_success_status(self):
        client = self._client(comments=[comment(auth())])
        with mock.patch.dict("os.environ", self.ENV, clear=True), \
                mock.patch.object(ma, "GitHubClient", return_value=client):
            self.assertEqual(ma.main(), 0)
        self.assertEqual(client.set_status.call_args.args[1], "success")
