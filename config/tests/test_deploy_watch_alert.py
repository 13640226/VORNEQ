"""Offline regression tests for the G4 deploy-watch alert journal."""

import importlib.util
import os
from pathlib import Path
import sys
from unittest import TestCase, mock


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "deploy_watch_alert.py"
SPEC = importlib.util.spec_from_file_location("vorneq_deploy_watch_alert", SCRIPT)
alert = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = alert
SPEC.loader.exec_module(alert)

A = "production: live aaaa11112222 differs from authorized bbbb33334444"
B = "production: live cccc55556666 differs from authorized bbbb33334444"
WHEN = "2026-11-11T12:00:00Z"
RUN = "https://github.com/13640226/VORNEQ/actions/runs/123"


class FakeIssues:
    def __init__(self, *, issue=None, comments=None):
        self.issue = issue
        self.records = list(comments or [])
        self.created = []
        self.posted = []

    def find_open_alert(self):
        return self.issue

    def comments(self, number):
        return list(self.records)

    def create_alert(self, body):
        self.created.append(body)
        self.issue = {"number": 544, "body": body}
        return 544

    def add_comment(self, number, body):
        self.posted.append((number, body))
        self.records.append({"body": body, "user": {"login": "github-actions[bot]"}})


class DriftMarkerTests(TestCase):
    def test_marker_is_deterministic_without_raw_sensitive_summary(self):
        marker = alert.drift_marker(A)
        self.assertEqual(marker, alert.drift_marker("  " + A + "  "))
        self.assertNotIn(A, marker)
        self.assertRegex(marker, r"^<!-- VORNEQ-G4-DRIFT-SHA256:[0-9a-f]{64} -->$")

    def test_missing_and_excessively_long_summary_fail_closed(self):
        for invalid in ("", " \n ", "x" * 2049, None):
            with self.subTest(invalid=repr(invalid)[:20]), self.assertRaises(ValueError):
                alert.drift_marker(invalid)

    def test_latest_machine_marker_ignores_unrelated_human_comments(self):
        issue = alert.alert_body(A, WHEN)
        comments = [
            {"body": alert.alert_body(B, WHEN), "user": {"login": "github-actions[bot]"}},
            {"body": "human review without a marker", "user": {"login": "human"}},
        ]
        self.assertEqual(
            alert.latest_marker(issue, comments),
            alert.MARKER_RE.search(alert.alert_body(B, WHEN)).group(1),
        )

    def test_old_issue_body_marker_is_used_without_comments(self):
        body = alert.alert_body(A, WHEN)
        self.assertEqual(alert.latest_marker(body, []), alert.MARKER_RE.search(body).group(1))


class DriftJournalTests(TestCase):
    def test_no_issue_creates_one_complete_alert(self):
        api = FakeIssues()
        result = alert.record_drift(api, A, WHEN, RUN)
        self.assertEqual(result, ("CREATED", 544))
        self.assertEqual(len(api.created), 1)
        self.assertEqual(len(api.posted), 0)
        self.assertIn(A, api.created[0])
        self.assertIn(RUN, api.created[0])
        self.assertIn("VORNEQ-G4-DRIFT-SHA256:", api.created[0])

    def test_identical_drift_is_not_reposted(self):
        api = FakeIssues()
        alert.record_drift(api, A, WHEN)
        self.assertEqual(alert.record_drift(api, A, WHEN), ("UNCHANGED", 544))
        self.assertEqual(len(api.posted), 0)

    def test_new_drift_appends_once_and_preserves_issue(self):
        api = FakeIssues()
        alert.record_drift(api, A, WHEN)
        self.assertEqual(alert.record_drift(api, B, WHEN), ("COMMENTED", 544))
        self.assertEqual(len(api.posted), 1)
        self.assertIn(B, api.posted[0][1])
        self.assertEqual(alert.record_drift(api, B, WHEN), ("UNCHANGED", 544))
        self.assertEqual(len(api.posted), 1)

    def test_reappearing_historical_drift_is_new_event(self):
        api = FakeIssues()
        alert.record_drift(api, A, WHEN)
        alert.record_drift(api, B, WHEN)
        self.assertEqual(alert.record_drift(api, A, WHEN), ("COMMENTED", 544))
        self.assertEqual(len(api.posted), 2)

    def test_unrelated_human_comment_does_not_cause_reposting(self):
        api = FakeIssues()
        alert.record_drift(api, A, WHEN)
        api.records.append({"body": "Unabhängiger Bericht ohne Maschinenmarker", "user": {"login": "human"}})
        self.assertEqual(alert.record_drift(api, A, WHEN), ("UNCHANGED", 544))

    def test_untrusted_marker_cannot_suppress_machine_alert(self):
        api = FakeIssues(
            issue={"number": 544, "body": "legacy"},
            comments=[{"body": alert.alert_body(A, WHEN), "user": {"login": "external-user"}}],
        )
        self.assertEqual(alert.record_drift(api, A, WHEN), ("COMMENTED", 544))
        self.assertEqual(len(api.posted), 1)

    def test_legacy_alert_without_marker_receives_initial_record(self):
        api = FakeIssues(issue={"number": 544, "body": "Originaler Drift-Alarm ohne Marker"})
        self.assertEqual(alert.record_drift(api, A, WHEN), ("COMMENTED", 544))
        self.assertEqual(len(api.posted), 1)
        self.assertEqual(alert.record_drift(api, A, WHEN), ("UNCHANGED", 544))

    def test_comment_failure_is_not_silently_swallowed(self):
        api = FakeIssues(issue={"number": 544, "body": "legacy"})
        api.add_comment = mock.Mock(side_effect=RuntimeError("GitHub unavailable"))
        with self.assertRaises(RuntimeError):
            alert.record_drift(api, A, WHEN)

    def test_invalid_summary_causes_no_issue_write(self):
        api = FakeIssues()
        with self.assertRaises(ValueError):
            alert.record_drift(api, "", WHEN)
        self.assertEqual(api.created, [])


class GitHubApiContractTests(TestCase):
    def test_repository_and_token_are_required(self):
        for token, repo in (("", "13640226/VORNEQ"), ("x", "x"), ("x", "../unsafe"), ("x", "")):
            with self.subTest(token=token, repo=repo), self.assertRaises(ValueError):
                alert.GitHubIssues(token, repo)

    def test_exact_open_issue_title_not_partial_or_pull_request(self):
        api = alert.GitHubIssues("fake", "13640226/VORNEQ")
        items = [
            {"number": 3, "title": alert.TITLE + " copy"},
            {"number": 4, "title": alert.TITLE, "pull_request": {}},
            {"number": 544, "title": alert.TITLE, "user": {"login": "github-actions[bot]"}},
        ]
        with mock.patch.object(api, "request", return_value=items):
            self.assertEqual(api.find_open_alert()["number"], 544)

    def test_ambiguous_issues_fail_closed(self):
        api = alert.GitHubIssues("fake", "13640226/VORNEQ")
        with mock.patch.object(api, "request", return_value=[
            {"number": 1, "title": alert.TITLE}, {"number": 2, "title": alert.TITLE}
        ]), self.assertRaises(RuntimeError):
            api.find_open_alert()

    def test_untrusted_alert_issue_author_fails_closed(self):
        api = alert.GitHubIssues("fake", "13640226/VORNEQ")
        with mock.patch.object(api, "request", return_value=[
            {"number": 544, "title": alert.TITLE, "user": {"login": "external-user"}}
        ]), self.assertRaises(RuntimeError):
            api.find_open_alert()

    def test_pagination_reads_all_comments(self):
        api = alert.GitHubIssues("fake", "13640226/VORNEQ")
        first = [{"body": "old"} for _ in range(100)]
        second = [{"body": "new"}]
        with mock.patch.object(api, "request", side_effect=[first, second]) as request:
            self.assertEqual(len(api.comments(544)), 101)
        self.assertEqual(request.call_count, 2)

    def test_missing_environment_is_not_success(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(alert.main(), 1)

    def test_workflow_uses_journal_only_for_drift(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "deploy-watch.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/deploy_watch_alert.py", workflow)
        self.assertIn("if: steps.watch.outputs.drift == 'true'", workflow)
        self.assertIn("DRIFT_SUMMARY: ${{ steps.watch.outputs.drift_summary }}", workflow)
        self.assertNotIn("gh issue list", workflow)
        self.assertNotIn("gh issue create", workflow)
