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
        client.pull_request.return_value = {"state": "open", "head": {"sha": HEAD}, "base": {"ref": "main"}, "draft": False}
        client.open_pulls.return_value = [{"number": PR, "state": "open", "head": {"sha": HEAD}, "base": {"ref": "main"}}]
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

    def test_main_deny_sets_failure_status_and_exits_zero(self):
        # DENY is a successfully evaluated result: the required commit status is
        # "failure", but the job itself does not fail (noise reduction).
        client = self._client(comments=[comment("LGTM")])
        with mock.patch.dict("os.environ", self.ENV, clear=True), \
                mock.patch.object(ma, "GitHubClient", return_value=client):
            self.assertEqual(ma.main(), 0)
        client.set_status.assert_called_once()
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_main_closed_pr_is_skipped_without_status(self):
        for state in ("closed", None):
            client = self._client(comments=[comment(auth())])
            client.pull_request.return_value = {"state": state, "head": {"sha": HEAD}, "base": {"ref": "main"}}
            with mock.patch.dict("os.environ", self.ENV, clear=True), \
                    mock.patch.object(ma, "GitHubClient", return_value=client):
                self.assertEqual(ma.main(), 0)
            client.set_status.assert_not_called()
            client.issue_comments.assert_not_called()

    def test_t9_pull_request_api_error_exits_one(self):
        client = self._client()
        client.pull_request.side_effect = urllib.error.URLError("down")
        with mock.patch.dict("os.environ", self.ENV, clear=True), \
                mock.patch.object(ma, "GitHubClient", return_value=client):
            self.assertEqual(ma.main(), 1)

    def test_main_allow_sets_success_status(self):
        client = self._client(comments=[comment(auth())])
        with mock.patch.dict("os.environ", self.ENV, clear=True), \
                mock.patch.object(ma, "GitHubClient", return_value=client):
            self.assertEqual(ma.main(), 0)
        self.assertEqual(client.set_status.call_args.args[1], "success")


class MA01MA02HardeningTests(TestCase):
    """Reproducible read-only tests: synthetic PR inventory and mocked API calls."""

    ENV = {"GITHUB_TOKEN": "synthetic", "GITHUB_REPOSITORY": "o/r", "PR_NUMBER": str(PR)}

    def _client(self):
        client = mock.Mock()
        client.pull_request.return_value = {
            "state": "open", "number": PR, "head": {"sha": HEAD},
            "base": {"ref": "main"}, "draft": False,
        }
        client.issue_comments.return_value = [comment(auth())]
        client.open_pulls.return_value = [
            {"state": "open", "number": PR, "head": {"sha": HEAD}, "base": {"ref": "main"}},
        ]
        return client

    def _run(self, client):
        with mock.patch.dict("os.environ", self.ENV, clear=True), mock.patch.object(
            ma, "GitHubClient", return_value=client
        ):
            return ma.main()

    def test_ma01_only_one_open_pr_with_sha_allows(self):
        self.assertTrue(ma.require_unique_open_head(PR, HEAD, self._client().open_pulls.return_value).allowed)

    def test_ma01_two_prs_same_sha_denies_even_different_base(self):
        client = self._client()
        client.open_pulls.return_value.append({
            "state": "open", "number": PR + 1, "head": {"sha": HEAD},
            "base": {"ref": "develop"},
        })
        self.assertEqual(self._run(client), 0)
        client.set_status.assert_called_once()
        self.assertEqual(client.set_status.call_args.args[1], "failure")
        self.assertIn("shared", client.set_status.call_args.args[2])

    def test_ma01_target_missing_from_inventory_denies(self):
        client = self._client()
        client.open_pulls.return_value = [
            {"state": "open", "number": PR + 1, "head": {"sha": HEAD}, "base": {"ref": "main"}},
        ]
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_ma01_empty_inventory_denies(self):
        client = self._client()
        client.open_pulls.return_value = []
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_ma01_malformed_inventory_denies(self):
        client = self._client()
        client.open_pulls.return_value.append({"number": PR + 1, "head": None})
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_ma01_duplicate_item_in_inventory_denies(self):
        client = self._client()
        client.open_pulls.return_value.append(client.open_pulls.return_value[0].copy())
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_ma01_inventory_api_error_fails_closed(self):
        client = self._client()
        client.open_pulls.side_effect = urllib.error.URLError("synthetic API outage")
        self.assertEqual(self._run(client), 1)
        client.set_status.assert_called_once_with(HEAD, "failure", "evaluation error (fail-closed)")

    def test_ma01_invalid_comment_does_not_need_inventory(self):
        client = self._client()
        client.issue_comments.return_value = [comment("not authorized")]
        self._run(client)
        client.open_pulls.assert_not_called()
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_ma02_current_base_other_than_main_invalidates_status(self):
        client = self._client()
        client.pull_request.return_value["base"]["ref"] = "develop"
        self._run(client)
        client.set_status.assert_called_once_with(HEAD, "failure", "PR does not target main")
        client.issue_comments.assert_not_called()

    def test_ma02_retarget_between_fetches_denies(self):
        client = self._client()
        original = client.pull_request.return_value
        changed = {**original, "base": {"ref": "develop"}}
        client.pull_request.side_effect = [original, changed]
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")
        self.assertIn("changed", client.set_status.call_args.args[2])

    def test_ma02_head_change_between_fetches_denies(self):
        client = self._client()
        original = client.pull_request.return_value
        changed = {**original, "head": {"sha": OLD}}
        client.pull_request.side_effect = [original, changed]
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")

    def test_ma02_draft_rejects_without_inventory(self):
        client = self._client()
        client.pull_request.return_value["draft"] = True
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "failure")
        client.open_pulls.assert_not_called()

    def test_ma02_retarget_to_main_allows_after_auth(self):
        client = self._client()
        self._run(client)
        self.assertEqual(client.set_status.call_args.args[1], "success")

    def test_ma01_pagination_two_pages(self):
        client = ma.GitHubClient("synthetic", "o/r")
        batch = [{"number": i + 1} for i in range(100)]
        with mock.patch.object(client, "_request", side_effect=[batch, [{"number": 101}]]) as request:
            self.assertEqual(len(client.open_pulls()), 101)
            self.assertEqual(request.call_count, 2)
            self.assertIn("page=2", request.call_args_list[1].args[1])

    def test_ma01_pagination_malformed_raises(self):
        client = ma.GitHubClient("synthetic", "o/r")
        with mock.patch.object(client, "_request", return_value={"items": []}):
            with self.assertRaises(RuntimeError):
                client.open_pulls()

    def test_workflow_base_edit_event_and_no_filter(self):
        workflow = (_PATH.parent.parent / ".github/workflows/merge-authorization.yml").read_text(encoding="utf-8")
        self.assertIn("edited", workflow)
        self.assertIn("converted_to_draft", workflow)
        self.assertNotIn("    branches: [main]", workflow)
        self.assertIn("pull_request_target:", workflow)

    def test_ma01_stale_success_race_is_unresolved(self):
        # Document the fundamental limitation: two separate PRs with the same
        # commit share the same commit-status context, even after this patch.
        self.assertEqual(ma.STATUS_CONTEXT, "merge-authorization")
