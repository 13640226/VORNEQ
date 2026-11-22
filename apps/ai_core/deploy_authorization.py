"""Opt-in chat gate following successful, owner-run official deployments."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from threading import Lock
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings

REPO = "13640226/VORNEQ"
OWNER = "13640226"
OWNER_ID = 199411505
BOT_ID = 41898282
SERVICES = {"staging": "srv-dbm7dvc9v7es7393g70g",
            "production": "srv-dadn07eq1p3s73eccau0"}
SHA = re.compile(r"[0-9a-f]{40}\Z")
LOG_URL = re.compile(r"https://github\.com/13640226/VORNEQ/actions/runs/([1-9][0-9]*)/job/[1-9][0-9]*\Z")
MARKER = re.compile(r"authorized by ([A-Za-z0-9][A-Za-z0-9._-]{2,79})\Z")
_lock = Lock()
_cache = {}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get(path, token):
    request = Request("https://api.github.com/repos/" + REPO + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "VORNEQ-chat-deployment-proof",
    })
    with build_opener(NoRedirect()).open(request, timeout=3) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("oversized response")
    return json.loads(body)


def _owner(actor):
    return (isinstance(actor, dict) and actor.get("login") == OWNER
            and actor.get("id") == OWNER_ID and actor.get("type") == "User")


def _bot(actor):
    return (isinstance(actor, dict) and actor.get("login") == "github-actions[bot]"
            and actor.get("id") == BOT_ID and actor.get("type") == "Bot")


def _rows(path, token):
    rows = _get(path, token)
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("missing deployment evidence")
    return rows


def _id(row):
    value = row.get("id")
    if type(value) is not int or value <= 0:
        raise ValueError("invalid deployment id")
    return value


def _latest(environment, sha, token):
    # No SHA filter: a stale rollback must not inherit an old grant.
    row = _rows("/deployments?" + urlencode({"environment": environment, "per_page": 10}), token)[0]
    if row.get("sha") != sha or row.get("environment") != environment:
        raise ValueError("deployment drift")
    return row


def verify_deployment(environment, sha, token):
    if environment not in SERVICES or not isinstance(sha, str) or not SHA.fullmatch(sha) or not token:
        return False
    record = _latest(environment, sha, token)
    marker = MARKER.fullmatch(record.get("description") or "")
    if marker is None or not _bot(record.get("creator")):
        return False
    state = _rows(f"/deployments/{_id(record)}/statuses?per_page=1", token)[0]
    if (state.get("state") != "success" or state.get("environment") != environment
            or state.get("description") != marker.group(1) + ": success"
            or not _bot(state.get("creator"))):
        return False
    job_record = _latest("deploy-" + environment, sha, token)
    app = job_record.get("performed_via_github_app") or {}
    if not _owner(job_record.get("creator")) or app.get("slug") != "github-actions" or app.get("id") != 15368:
        return False
    job_state = _rows(f"/deployments/{_id(job_record)}/statuses?per_page=1", token)[0]
    match = LOG_URL.fullmatch(job_state.get("log_url") or "")
    if (job_state.get("state") != "success" or job_state.get("environment") != "deploy-" + environment
            or not _owner(job_state.get("creator")) or match is None):
        return False
    run = _get("/actions/runs/" + match.group(1), token)
    if not isinstance(run, dict):
        return False
    return bool(run.get("id") == int(match.group(1)) and run.get("event") == "workflow_dispatch"
                and run.get("path") == ".github/workflows/deploy.yml"
                and run.get("head_branch") == "main" and run.get("head_sha") == sha
                and run.get("status") == "completed" and run.get("conclusion") == "success"
                and _owner(run.get("actor")) and _owner(run.get("triggering_actor"))
                and isinstance(run.get("created_at"), str)
                and isinstance(run.get("updated_at"), str)
                and isinstance(record.get("created_at"), str)
                and run["created_at"] <= record["created_at"] <= run["updated_at"])


def release_allowed(environment, authorized_sha):
    live = os.environ.get("RENDER_GIT_COMMIT", "")
    if getattr(settings, "VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS", False) is not True:
        return bool(isinstance(authorized_sha, str) and SHA.fullmatch(authorized_sha)
                    and live == authorized_sha)
    if (environment not in SERVICES or settings.VORNEQ_ENV != environment
            or settings.DEBUG is not False or os.environ.get("RENDER_SERVICE_ID") != SERVICES[environment]
            or not SHA.fullmatch(live)):
        return False
    token = os.environ.get("VORNEQ_AI_DEPLOY_READ_TOKEN", "")
    if not token:
        return False
    key = (environment, live, hashlib.sha256(token.encode()).digest())
    with _lock:
        saved = _cache.get(key)
        if saved is not None and time.monotonic() < saved[0]:
            return saved[1]
        try:
            allowed = verify_deployment(environment, live, token) is True
        except Exception:
            allowed = False
        _cache.clear()
        _cache[key] = (time.monotonic() + (60 if allowed else 10), allowed)
        return allowed
