"""Fail-closed merge authorization gate (GOV_BREACH_01).

A pull request may only be merged into main when the repository owner has
posted a comment that binds an explicit authorization to the exact head SHA:

    OWNER-AUTH-MERGE <AUTH-ID> PR #<number> @ <40-hex head sha>

An authorization is withdrawn by a later owner comment:

    OWNER-AUTH-REVOKE PR #<number>

The result is published as the commit status ``merge-authorization`` on the
current head SHA. Every error or unclear state results in ``failure``.

Only the Python standard library is used. The script never executes code
from the pull request; it reads GitHub API data only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

STATUS_CONTEXT = "merge-authorization"
DEFAULT_OWNER_LOGIN = "13640226"

_AUTH_RE = re.compile(
    r"OWNER-AUTH-MERGE\s+(?P<auth_id>[A-Za-z0-9][A-Za-z0-9._-]{2,79})"
    r"\s+PR\s+#(?P<pr>\d+)\s+@\s+(?P<sha>[0-9a-f]{40})"
)
_REVOKE_RE = re.compile(r"OWNER-AUTH-REVOKE\s+PR\s+#(?P<pr>\d+)")
_SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    auth_id: str | None = None
    comment_id: int | None = None


def _is_owner(comment: dict, owner_login: str) -> bool:
    user = comment.get("user") or {}
    return (
        user.get("login") == owner_login
        and user.get("type", "User") == "User"
        and comment.get("author_association") == "OWNER"
    )


def decide(
    pr_number: int,
    head_sha: str,
    comments: list[dict],
    owner_login: str = DEFAULT_OWNER_LOGIN,
) -> Decision:
    """Return the merge decision for one pull request.

    Rules (all must hold, otherwise DENY):
      1. author is the owner account with author_association OWNER
      2. the PR number in the comment equals this PR
      3. the SHA in the comment equals the current head SHA (40 hex chars)
      4. the comment was never edited (created_at == updated_at)
      5. no owner revoke comment for this PR was posted after it
    """
    if not isinstance(pr_number, int) or pr_number <= 0:
        return Decision(False, "invalid pull request number")
    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
        return Decision(False, "invalid head sha")
    if not isinstance(comments, list):
        return Decision(False, "comment list unavailable")

    try:
        ordered = sorted(comments, key=lambda c: (c["created_at"], c["id"]))
    except (KeyError, TypeError):
        return Decision(False, "malformed comment data")

    valid: Decision | None = None
    for comment in ordered:
        if not _is_owner(comment, owner_login):
            continue
        body = (comment.get("body") or "").strip()

        revoke = _REVOKE_RE.fullmatch(body)
        if revoke and int(revoke.group("pr")) == pr_number:
            valid = None
            continue

        match = _AUTH_RE.fullmatch(body)
        if not match:
            continue
        if int(match.group("pr")) != pr_number:
            continue
        if match.group("sha") != head_sha:
            continue
        if comment.get("updated_at") != comment.get("created_at"):
            continue
        valid = Decision(
            True,
            f"authorized by {match.group('auth_id')}",
            auth_id=match.group("auth_id"),
            comment_id=comment.get("id"),
        )

    if valid is None:
        return Decision(False, f"no valid owner authorization for {head_sha[:12]}")
    return valid



def require_unique_open_head(pr_number: int, head_sha: str, open_pulls: list[dict]) -> Decision:
    """MA-01: DENY unless exactly one open PR in the repository uses this head SHA.

    Scope intentionally includes PRs targeting other branches. This is only a
    mitigation: commit statuses remain keyed by SHA, not by PR number; the
    inventory-to-status race requires stronger final enforcement.
    """
    if not isinstance(open_pulls, list) or not open_pulls:
        return Decision(False, "open pull-request inventory unavailable or empty")
    matching_numbers: list[int] = []
    seen_numbers: set[int] = set()
    for item in open_pulls:
        if not isinstance(item, dict):
            return Decision(False, "malformed open pull-request inventory")
        number = item.get("number")
        head = item.get("head")
        if (
            not isinstance(number, int)
            or number <= 0
            or number in seen_numbers
            or item.get("state") != "open"
            or not isinstance(head, dict)
            or not isinstance(head.get("sha"), str)
            or not _SHA_RE.fullmatch(head["sha"])
        ):
            return Decision(False, "malformed or ambiguous open pull-request inventory")
        seen_numbers.add(number)
        if head["sha"] == head_sha:
            matching_numbers.append(number)
    if matching_numbers != [pr_number]:
        return Decision(False, "head SHA is shared, missing, or owned by another open PR")
    return Decision(True, "unique open PR for head SHA")


class GitHubClient:
    def __init__(self, token: str, repository: str, api_url: str = "https://api.github.com"):
        if not token or not repository:
            raise RuntimeError("missing token or repository")
        self.token = token
        self.repository = repository
        self.api_url = api_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "vorneq-merge-authorization",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None

    def pull_request(self, number: int) -> dict:
        return self._request("GET", f"/repos/{self.repository}/pulls/{number}")

    def issue_comments(self, number: int) -> list[dict]:
        comments: list[dict] = []
        page = 1
        while True:
            batch = self._request(
                "GET",
                f"/repos/{self.repository}/issues/{number}/comments?per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise RuntimeError("unexpected comment response")
            comments.extend(batch)
            if len(batch) < 100:
                return comments
            page += 1
            if page > 50:
                raise RuntimeError("too many comment pages")

    def open_pulls(self) -> list[dict]:
        """List ALL open PRs (all bases), failing closed on API/pagination errors."""
        pulls: list[dict] = []
        for page in range(1, 51):
            batch = self._request(
                "GET",
                f"/repos/{self.repository}/pulls?state=open&per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise RuntimeError("unexpected open PR inventory response")
            pulls.extend(batch)
            if len(batch) < 100:
                return pulls
        raise RuntimeError("open PR inventory page limit exceeded")

    def set_status(self, sha: str, state: str, description: str) -> None:
        self._request(
            "POST",
            f"/repos/{self.repository}/statuses/{sha}",
            {"state": state, "context": STATUS_CONTEXT, "description": description[:140]},
        )


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    owner_login = os.environ.get("MERGE_AUTH_OWNER_LOGIN", DEFAULT_OWNER_LOGIN)
    head_sha = None
    client = None
    try:
        pr_number = int(os.environ.get("PR_NUMBER", "0"))
        client = GitHubClient(token, repository)
        pr = client.pull_request(pr_number)
        head_sha = pr["head"]["sha"]
        if pr.get("state") != "open":
            # A closed or merged PR can no longer be merged; no status is written.
            print(f"SKIP: PR #{pr_number} is {pr.get('state')}")
            return 0
        # MA-02: retargeting away from main must invalidate any stale success.
        # The workflow has no base-branch event filter and subscribes to "edited".
        if pr.get("base", {}).get("ref") != "main":
            client.set_status(head_sha, "failure", "PR does not target main")
            print("DENY: base branch is not main")
            return 0
        if pr.get("draft"):
            client.set_status(head_sha, "failure", "draft PR is not merge-ready")
            print("DENY: PR is draft")
            return 0

        decision = decide(pr_number, head_sha, client.issue_comments(pr_number), owner_login)
        if decision.allowed:
            # MA-01: commit status is SHA-scoped; block duplicate open PR heads.
            uniqueness = require_unique_open_head(pr_number, head_sha, client.open_pulls())
            if not uniqueness.allowed:
                decision = uniqueness
            else:
                # MA-02: re-read right before publishing success so a changed
                # head/base/state/draft does not use stale metadata.
                latest = client.pull_request(pr_number)
                if (
                    latest.get("state") != "open"
                    or latest.get("head", {}).get("sha") != head_sha
                    or latest.get("base", {}).get("ref") != "main"
                    or latest.get("draft")
                ):
                    decision = Decision(False, "PR head, base, draft or state changed during evaluation")
        state = "success" if decision.allowed else "failure"
        client.set_status(head_sha, state, decision.reason)
        print(f"{'ALLOW' if decision.allowed else 'DENY'} PR #{pr_number} @ {head_sha}: {decision.reason}")
        # The required check is the commit status above. A DENY is a normal,
        # successfully evaluated result, so the job itself exits 0. Only an
        # evaluation error (below) fails the job.
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError, TypeError) as exc:
        print(f"DENY (fail-closed): {type(exc).__name__}", file=sys.stderr)
        if client is not None and head_sha:
            try:
                client.set_status(head_sha, "failure", "evaluation error (fail-closed)")
            except Exception:  # noqa: BLE001 - best effort, already failing closed
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
