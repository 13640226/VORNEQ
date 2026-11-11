"""Record each distinct G4 drift state without suppressing later changes.

This is an alert-only helper for deploy-watch.yml. It never triggers a deploy,
changes a deployment, closes an issue, or treats a drift as authorization.
Only Python's standard library is required.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.request

TITLE = "[Deploy-Waechter] Nicht autorisierter Live-Stand erkannt"
MARKER_RE = re.compile(r"<!-- VORNEQ-G4-DRIFT-SHA256:([0-9a-f]{64}) -->")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


def drift_marker(summary: str) -> str:
    """A stable, content-independent marker for one observed drift state."""
    if not isinstance(summary, str) or not (0 < len(summary.strip()) <= 2048):
        raise ValueError("drift summary missing or too long")
    digest = hashlib.sha256(summary.strip().encode("utf-8")).hexdigest()
    return f"<!-- VORNEQ-G4-DRIFT-SHA256:{digest} -->"


def latest_marker(issue_body: str, comments: list[dict]) -> str | None:
    """Ignore unrelated human comments; compare the latest machine observation."""
    for comment in reversed(comments):
        if not isinstance(comment, dict):
            continue
        author = (comment.get("user") or {}).get("login")
        if author != "github-actions[bot]":
            continue  # A human or external comment must not spoof an alert marker.
        body = comment.get("body")
        if isinstance(body, str):
            matches = MARKER_RE.findall(body)
            if matches:
                return matches[-1]
    matches = MARKER_RE.findall(issue_body or "")
    return matches[-1] if matches else None


def alert_body(summary: str, timestamp: str, run_url: str = "") -> str:
    """Include an audit marker, timestamp and source without leaking secrets."""
    marker = drift_marker(summary)
    run_line = f"\nDeploy-Watch-Lauf: {run_url}\n" if run_url else "\n"
    return (
        f"Automatische G4-Drift-Beobachtung ({timestamp}).\n\n"
        f"{summary.strip()}\n"
        f"{run_line}\n"
        "Die Abweichung beschreibt nur den beobachteten Stand; sie beweist "
        "keine böswillige Handlung und stellt keine Deploy-Freigabe dar.\n"
        "Bitte die historische Folge in Issue #448 nachvollziehbar halten.\n\n"
        f"{marker}"
    )


class GitHubIssues:
    """Restricted REST client: read open issues/comments; create issue/comment."""
    
    def __init__(self, token: str, repository: str):
        if not token:
            raise ValueError("missing GitHub token")
        if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
            raise ValueError("invalid GitHub repository")
        self.token = token
        self.repository = repository

    def request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "vorneq-deploy-watch",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _pages(self, route: str):
        for page in range(1, 51):
            sep = "&" if "?" in route else "?"
            batch = self.request("GET", f"{route}{sep}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError("unexpected GitHub issue/comment response")
            yield from batch
            if len(batch) < 100:
                return
        raise RuntimeError("GitHub pagination limit exceeded")

    def find_open_alert(self) -> dict | None:
        matches = [
            issue for issue in self._pages("issues?state=open")
            if isinstance(issue, dict)
            and issue.get("title") == TITLE
            and "pull_request" not in issue
        ]
        if len(matches) > 1:
            raise RuntimeError("multiple open G4 alert issues; refusing ambiguous update")
        if matches and (matches[0].get("user") or {}).get("login") != "github-actions[bot]":
            raise RuntimeError("G4 alert issue not owned by GitHub Actions bot")
        return matches[0] if matches else None

    def comments(self, issue_number: int) -> list[dict]:
        return list(self._pages(f"issues/{issue_number}/comments"))

    def create_alert(self, body: str) -> int:
        response = self.request("POST", "issues", {"title": TITLE, "body": body})
        return response["number"]

    def add_comment(self, issue_number: int, body: str) -> None:
        self.request("POST", f"issues/{issue_number}/comments", {"body": body})


def record_drift(api: GitHubIssues, summary: str, timestamp: str, run_url: str = "") -> tuple[str, int]:
    """Create alert, append changed state, or safely skip an unchanged state."""
    body = alert_body(summary, timestamp, run_url)
    marker = MARKER_RE.search(body).group(1)
    issue = api.find_open_alert()
    if issue is None:
        return "CREATED", api.create_alert(body)
    number = issue["number"]
    if latest_marker(issue.get("body", ""), api.comments(number)) == marker:
        return "UNCHANGED", number
    api.add_comment(number, body)
    return "COMMENTED", number


def main() -> int:
    try:
        summary = os.environ.get("DRIFT_SUMMARY", "")
        # Validate before any GitHub read/write. Missing telemetry is not success.
        drift_marker(summary)
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if run_id.isdecimal() else ""
        api = GitHubIssues(os.environ.get("GITHUB_TOKEN", ""), repo)
        when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        result, number = record_drift(api, summary, when, run_url)
        print(f"G4_ALERT_{result}: issue #{number}")
        return 0
    except Exception as exc:
        # Never print exception messages: an HTTP failure can contain request
        # details, and this job runs with a short-lived GitHub token.
        print(f"G4_ALERT_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
