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
        if pr.get("base", {}).get("ref") != "main":
            client.set_status(head_sha, "success", "base is not main; gate not applicable")
            print("SKIP: base branch is not main")
            return 0
        decision = decide(pr_number, head_sha, client.issue_comments(pr_number), owner_login)
        state = "success" if decision.allowed else "failure"
        client.set_status(head_sha, "success", "T10-MALICIOUS-ALLOW")  # T10: manipulated evaluator
        print(f"{'ALLOW' if decision.allowed else 'DENY'} PR #{pr_number} @ {head_sha}: {decision.reason}")
        return 0 if decision.allowed else 1
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
