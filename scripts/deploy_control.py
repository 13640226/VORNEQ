"""Owner-authorized, SHA-bound deploys and deploy drift detection (G4).

Deploys are only triggered by the owner through ``.github/workflows/deploy.yml``.
Before the Render deploy hook is called, every check below must pass; any error
or unclear state stops the deploy (fail-closed):

1. the workflow was started by the owner account,
2. the SHA is a full 40-character commit that is contained in ``main``,
3. the required CI checks on that SHA concluded ``success``,
4. the owner posted, in the deploy authorization issue, exactly one line
       OWNER-AUTH-DEPLOY <AUTH-ID> <staging|production> @ <40-hex sha>
   that was never edited and was not revoked by a later
       OWNER-AUTH-DEPLOY-REVOKE <AUTH-ID>
5. production only: the same SHA has a successful GitHub deployment to staging,
6. the authorization ID was not used for an earlier deploy (one deploy per ID),
7. the SHA is not already live in the target environment (no silent re-deploy),
8. trigger: the deploy hook belongs to the expected Render service.

``watch`` compares the commit reported by ``/health/`` with the last successful
GitHub deployment per environment and reports drift (for example a manual
dashboard deploy). Only the Python standard library is used; no pull request
code is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_OWNER_LOGIN = "13640226"
ENVIRONMENTS = ("staging", "production")
REQUIRED_MAIN_CHECKS = frozenset({"test (3.11)", "test (3.12)", "dependencies"})
# Render service IDs are not secrets; pinning them here (reviewed via the merge
# control) prevents a hook of the wrong service from being used (2026-11-05).
EXPECTED_SERVICE_IDS = {
    "staging": "srv-dbm7dvc9v7es7393g70g",
    "production": "srv-dadn07eq1p3s73eccau0",
}

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_AUTH_RE = re.compile(
    r"OWNER-AUTH-DEPLOY\s+(?P<auth_id>[A-Za-z0-9][A-Za-z0-9._-]{2,79})"
    r"\s+(?P<env>staging|production)\s+@\s+(?P<sha>[0-9a-f]{40})"
)
_REVOKE_RE = re.compile(r"OWNER-AUTH-DEPLOY-REVOKE\s+(?P<auth_id>[A-Za-z0-9][A-Za-z0-9._-]{2,79})")


class DeployRejected(RuntimeError):
    """A precondition for a deploy is not met."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    auth_id: str | None = None


def is_full_sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.fullmatch(value))


def normalize_sha(value: object) -> str:
    """Strip surrounding whitespace (copy/paste) and lower-case; validity is checked separately."""
    return value.strip().lower() if isinstance(value, str) else ""


def authorization_used(deployments: object, auth_id: str, own_deployment_id: int | None = None) -> bool:
    """True if any recorded deployment was already made with this authorization ID.

    ``own_deployment_id`` is the GitHub deployment created by the *current*
    run immediately before the trigger. Exactly that record is excluded, and it
    must exist with this authorization marker; otherwise the check fails closed.
    """
    if not isinstance(deployments, list):
        raise DeployRejected("deployment list unavailable")
    marker = f"authorized by {auth_id}"
    matching = [d for d in deployments
                if isinstance(d, dict) and (d.get("description") or "").strip() == marker]
    if own_deployment_id is None:
        return bool(matching)
    if not any(d.get("id") == own_deployment_id for d in matching):
        raise DeployRejected("current deployment record not found for this authorization")
    return any(d.get("id") != own_deployment_id for d in matching)


def hook_service_id(hook_url: str) -> str | None:
    parsed = urllib.parse.urlsplit(hook_url)
    if parsed.scheme != "https" or parsed.netloc != "api.render.com":
        return None
    match = re.fullmatch(r"/deploy/(srv-[a-z0-9]+)", parsed.path)
    return match.group(1) if match else None


def _is_owner(comment: dict, owner_login: str) -> bool:
    user = comment.get("user") or {}
    return (
        user.get("login") == owner_login
        and user.get("type", "User") == "User"
        and comment.get("author_association") == "OWNER"
    )


def decide_deploy(environment: str, sha: str, comments: list, owner_login: str = DEFAULT_OWNER_LOGIN) -> Decision:
    """Return whether an unrevoked, unedited owner authorization exists."""
    if environment not in ENVIRONMENTS:
        return Decision(False, "invalid environment")
    if not is_full_sha(sha):
        return Decision(False, "invalid sha")
    if not isinstance(comments, list):
        return Decision(False, "comment list unavailable")
    try:
        ordered = sorted(comments, key=lambda c: (c["created_at"], c["id"]))
    except (KeyError, TypeError):
        return Decision(False, "malformed comment data")

    valid: dict[str, Decision] = {}
    for comment in ordered:
        if not _is_owner(comment, owner_login):
            continue
        body = (comment.get("body") or "").strip()
        revoke = _REVOKE_RE.fullmatch(body)
        if revoke:
            valid.pop(revoke.group("auth_id"), None)
            continue
        match = _AUTH_RE.fullmatch(body)
        if not match or match.group("env") != environment or match.group("sha") != sha:
            continue
        if comment.get("updated_at") != comment.get("created_at"):
            continue
        auth_id = match.group("auth_id")
        valid[auth_id] = Decision(True, f"authorized by {auth_id}", auth_id)

    if not valid:
        return Decision(False, f"no valid owner deploy authorization for {environment} @ {sha[:12]}")
    return list(valid.values())[-1]


def sha_contained_in_main(compare_status: object) -> bool:
    """``compare/{sha}...main``: main must be identical to or ahead of the SHA."""
    return compare_status in ("identical", "ahead")


def required_checks_green(check_runs: object, required: frozenset = REQUIRED_MAIN_CHECKS) -> tuple[bool, str]:
    if not isinstance(check_runs, list):
        return False, "check runs unavailable"
    latest: dict[str, dict] = {}
    for run in check_runs:
        name = run.get("name") if isinstance(run, dict) else None
        if name in required:
            previous = latest.get(name)
            if previous is None or (run.get("completed_at") or "") > (previous.get("completed_at") or ""):
                latest[name] = run
    missing = sorted(required - latest.keys())
    if missing:
        return False, "missing checks: " + ", ".join(missing)
    failed = sorted(n for n, r in latest.items() if r.get("status") != "completed" or r.get("conclusion") != "success")
    if failed:
        return False, "checks not green: " + ", ".join(failed)
    return True, "required checks green"


def deployment_succeeded(statuses: object) -> bool:
    """GitHub returns deployment statuses newest first."""
    return isinstance(statuses, list) and bool(statuses) and statuses[0].get("state") == "success"


def release_matches(release: object, sha: str) -> bool:
    return isinstance(release, str) and is_full_sha(sha) and len(release) >= 7 and sha.startswith(release)


def watch_verdict(environment: str, live_release: object, expected_sha: str | None) -> tuple[bool, str]:
    """True means: no drift. Unknown states are drift (fail-closed)."""
    if not isinstance(live_release, str) or live_release in ("", "unknown"):
        return False, f"{environment}: live release is unknown"
    if not expected_sha:
        return False, f"{environment}: no successful controlled deploy recorded"
    if not release_matches(live_release, expected_sha):
        return False, f"{environment}: live {live_release[:12]} differs from authorized {expected_sha[:12]}"
    return True, f"{environment}: live {live_release[:12]} matches the last authorized deploy"


class GitHub:
    def __init__(self, token: str, repository: str, api_url: str = "https://api.github.com"):
        if not token or not repository:
            raise DeployRejected("missing GitHub token or repository")
        self.token, self.repository, self.api_url = token, repository, api_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_url}/repos/{self.repository}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "vorneq-deploy-control",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None

    def issue_comments(self, number: int) -> list:
        comments, page = [], 1
        while True:
            batch = self.request("GET", f"/issues/{number}/comments?per_page=100&page={page}")
            if not isinstance(batch, list):
                raise DeployRejected("unexpected comment response")
            comments.extend(batch)
            if len(batch) < 100:
                return comments
            page += 1
            if page > 50:
                raise DeployRejected("too many comment pages")

    def check_runs(self, sha: str) -> list:
        data = self.request("GET", f"/commits/{sha}/check-runs?per_page=100")
        return (data or {}).get("check_runs")

    def compare_status(self, sha: str) -> str:
        try:
            return (self.request("GET", f"/compare/{sha}...main") or {}).get("status")
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 422):
                raise DeployRejected("sha not found in the repository (not contained in main)") from exc
            raise

    def deployments(self, environment: str, sha: str | None = None) -> list:
        query = {"environment": environment, "per_page": "100"}
        if sha:
            query["sha"] = sha
        return self.request("GET", "/deployments?" + urllib.parse.urlencode(query)) or []

    def deployment_statuses(self, deployment_id: int) -> list:
        return self.request("GET", f"/deployments/{deployment_id}/statuses?per_page=10") or []


def last_successful_sha(gh: GitHub, environment: str) -> str | None:
    for deployment in gh.deployments(environment):
        if deployment_succeeded(gh.deployment_statuses(deployment["id"])):
            return deployment.get("sha")
    return None


def preflight(gh: GitHub, environment: str, sha: str, auth_issue: int, actor: str, triggering_actor: str,
              owner_login: str = DEFAULT_OWNER_LOGIN, live_release: object = None,
              own_deployment_id: int | None = None) -> str:
    if actor != owner_login or triggering_actor != owner_login:
        raise DeployRejected("workflow must be started by the owner account")
    if environment not in ENVIRONMENTS:
        raise DeployRejected("invalid environment")
    if not is_full_sha(sha):
        raise DeployRejected("sha must be a full 40-character lower-case commit id")
    if not sha_contained_in_main(gh.compare_status(sha)):
        raise DeployRejected("sha is not contained in main")
    ok, reason = required_checks_green(gh.check_runs(sha))
    if not ok:
        raise DeployRejected(reason)
    decision = decide_deploy(environment, sha, gh.issue_comments(auth_issue), owner_login)
    if not decision.allowed:
        raise DeployRejected(decision.reason)
    if authorization_used(gh.deployments(environment), decision.auth_id, own_deployment_id):
        raise DeployRejected(f"authorization {decision.auth_id} was already used; post a new OWNER-AUTH-DEPLOY")
    if environment == "production":
        staged = any(deployment_succeeded(gh.deployment_statuses(d["id"])) for d in gh.deployments("staging", sha))
        if not staged:
            raise DeployRejected("sha has no successful staging deployment")
    if release_matches(live_release, sha):
        raise DeployRejected(f"sha is already live in {environment}; nothing to deploy")
    return decision.auth_id


def trigger_hook(hook_url: str, sha: str, environment: str) -> None:
    if not hook_url.startswith("https://api.render.com/deploy/"):
        raise DeployRejected("deploy hook secret missing or malformed")
    expected = EXPECTED_SERVICE_IDS.get(environment)
    actual = hook_service_id(hook_url)
    if not expected or actual != expected:
        raise DeployRejected(f"deploy hook does not belong to the {environment} service")
    separator = "&" if "?" in hook_url else "?"
    req = urllib.request.Request(f"{hook_url}{separator}ref={sha}", data=b"", method="POST",
                                 headers={"User-Agent": "vorneq-deploy-control"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
        if resp.status >= 300:
            raise DeployRejected(f"deploy hook returned HTTP {resp.status}")


def fetch_release(base_url: str) -> str | None:
    req = urllib.request.Request(base_url.rstrip("/") + "/health/", headers={"User-Agent": "vorneq-deploy-control"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - configured https URL
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8")).get("release")
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def wait_for_release(base_url: str, sha: str, timeout_s: int = 900, interval_s: int = 20) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if release_matches(fetch_release(base_url), sha):
            return
        time.sleep(interval_s)
    raise DeployRejected("health check did not report the deployed sha in time")


def _base_url(environment: str) -> str:
    value = os.environ.get(f"{environment.upper()}_BASE_URL", "")
    if not value.startswith("https://"):
        raise DeployRejected(f"{environment.upper()}_BASE_URL is not configured")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VORNEQ deploy control (G4)")
    parser.add_argument("command", choices=["preflight", "trigger", "verify", "watch"])
    parser.add_argument("--environment", choices=ENVIRONMENTS)
    parser.add_argument("--sha")
    parser.add_argument("--expect-auth-id",
                        help="trigger only: authorization ID approved by the preflight job")
    parser.add_argument("--deployment-id",
                        help="trigger only: GitHub deployment ID recorded by this run")
    args = parser.parse_args(argv)
    args.sha = normalize_sha(args.sha) if args.sha is not None else None
    owner = os.environ.get("DEPLOY_OWNER_LOGIN", DEFAULT_OWNER_LOGIN)
    try:
        if args.command != "trigger" and (args.expect_auth_id is not None or args.deployment_id is not None):
            raise DeployRejected("--expect-auth-id/--deployment-id are only valid for trigger")
        if args.command == "trigger":
            if not is_full_sha(args.sha):
                raise DeployRejected("invalid sha")
            expected_auth = (args.expect_auth_id or "").strip()
            if not expected_auth:
                raise DeployRejected("trigger requires --expect-auth-id (trigger-time re-validation)")
            if not (args.deployment_id or "").strip().isdecimal():
                raise DeployRejected("trigger requires a numeric --deployment-id")
            # TOCTOU guard: repeat the complete preflight in the same process,
            # immediately before the hook call, excluding only this run's record.
            gh = GitHub(os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""))
            base = os.environ.get(f"{(args.environment or '').upper()}_BASE_URL", "")
            if not base.startswith("https://"):
                raise DeployRejected(f"{(args.environment or '').upper()}_BASE_URL is not configured")
            live = fetch_release(base)
            auth_id = preflight(
                gh, args.environment, args.sha, int(os.environ.get("DEPLOY_AUTH_ISSUE", "448")),
                os.environ.get("GITHUB_ACTOR", ""), os.environ.get("GITHUB_TRIGGERING_ACTOR", ""), owner,
                live_release=live, own_deployment_id=int(args.deployment_id),
            )
            if auth_id != expected_auth:
                raise DeployRejected("authorization changed since the preflight job")
            trigger_hook(os.environ.get("RENDER_DEPLOY_HOOK_URL", ""), args.sha, args.environment)
            print(f"TRIGGERED {args.environment} @ {args.sha} ({auth_id})")
            return 0
        if args.command == "verify":
            wait_for_release(_base_url(args.environment), args.sha)
            print(f"VERIFIED {args.environment} @ {args.sha}")
            return 0
        gh = GitHub(os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""))
        if args.command == "preflight":
            base = os.environ.get(f"{(args.environment or '').upper()}_BASE_URL", "")
            live = fetch_release(base) if base.startswith("https://") else None
            auth_id = preflight(
                gh, args.environment, args.sha, int(os.environ.get("DEPLOY_AUTH_ISSUE", "448")),
                os.environ.get("GITHUB_ACTOR", ""), os.environ.get("GITHUB_TRIGGERING_ACTOR", ""), owner,
                live_release=live,
            )
            print(f"ALLOW {args.environment} @ {args.sha} ({auth_id})")
            output = os.environ.get("GITHUB_OUTPUT")
            if output:
                with open(output, "a", encoding="utf-8") as fh:
                    fh.write(f"auth_id={auth_id}\n")
                    fh.write(f"sha={args.sha}\n")
            return 0
        drift = []
        for environment in ENVIRONMENTS:
            base = os.environ.get(f"{environment.upper()}_BASE_URL", "")
            if not base.startswith("https://"):
                print(f"SKIP {environment}: base URL not configured")
                continue
            ok, message = watch_verdict(environment, fetch_release(base), last_successful_sha(gh, environment))
            print(("OK " if ok else "DRIFT ") + message)
            if not ok:
                drift.append(message)
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as fh:
                fh.write("drift=" + ("true" if drift else "false") + "\n")
                fh.write("drift_summary=" + " | ".join(drift) + "\n")
        return 0
    except (DeployRejected, urllib.error.URLError, KeyError, ValueError, TypeError) as exc:
        print(f"DENY (fail-closed): {exc}" if isinstance(exc, DeployRejected) else f"DENY (fail-closed): {type(exc).__name__}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
