#!/usr/bin/env python3
"""V1.3 offline-only CI skip directive diagnostic.

Consumes a caller-supplied local evidence manifest. The caller MUST obtain and
independently verify GitHub provenance and completeness; this tool cannot.
No network, Git, subprocess, workflow dispatch, secrets or database access.\nAll caller-supplied provenance/completeness fields are untrusted assertions.\nA clean scan MUST remain UNKNOWN, never a dispatch or security approval.
Not wired into any CI workflow, hook, or Required Check.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

MAX_BYTES = 1024 * 1024
MAX_COMMITS = 1000
SHA = re.compile(r"^[0-9a-f]{40}$")
SKIP = re.compile(r"\[(?:skip ci|ci skip|no ci|skip actions|actions skip)\]", re.I)
TRAILER = re.compile(r"(?im)^skip-checks:[ \t]*true[ \t]*$")
EXPECTED = frozenset((
    "test (3.11)", "test (3.12)", "dependencies", "postgres-backup-restore"
))


def inspect(manifest: object) -> tuple[int, str]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "head_sha", "commits", "required_contexts", "evidence"
    }:
        return 2, "UNKNOWN: invalid manifest schema"
    head, commits, contexts, evidence = (
        manifest["head_sha"], manifest["commits"],
        manifest["required_contexts"], manifest["evidence"]
    )
    if not isinstance(head, str) or not SHA.fullmatch(head):
        return 2, "UNKNOWN: invalid HEAD"
    if not isinstance(commits, list) or not 1 <= len(commits) <= MAX_COMMITS:
        return 2, "UNKNOWN: invalid commit list"
    if (not isinstance(contexts, list) or
            any(not isinstance(c, str) for c in contexts) or
            len(contexts) != len(set(contexts)) or
            frozenset(contexts) != EXPECTED):
        return 2, "UNKNOWN: required contexts do not match pinned snapshot"
    if not isinstance(evidence, dict) or set(evidence) != {
        "source", "pr_number", "base_sha", "reported_total", "pagination_complete"
    }:
        return 2, "UNKNOWN: missing evidence provenance fields"
    if (evidence["source"] != "github_rest_pr_commits" or
            type(evidence["pr_number"]) is not int or evidence["pr_number"] < 1 or
            not isinstance(evidence["base_sha"], str) or
            not SHA.fullmatch(evidence["base_sha"]) or
            type(evidence["reported_total"]) is not int or
            evidence["reported_total"] != len(commits) or
            evidence["pagination_complete"] is not True):
        return 2, "UNKNOWN: evidence claims incomplete or inconsistent"
    seen: set[str] = set()
    blocked: list[str] = []\n    historical: list[str] = []
    for item in commits:
        if not isinstance(item, dict) or set(item) != {"sha", "message"}:
            return 2, "UNKNOWN: invalid commit record"
        sha, message = item["sha"], item["message"]
        if (not isinstance(sha, str) or not SHA.fullmatch(sha) or sha in seen
                or not isinstance(message, str) or len(message) > 65536):
            return 2, "UNKNOWN: invalid or duplicate commit record"
        seen.add(sha)
        if SKIP.search(message) or TRAILER.search(message):\n            if sha == head:\n                blocked.append(sha[:12])\n            else:\n                historical.append(sha[:12])
    if commits[-1]["sha"] != head:
        return 2, "UNKNOWN: supplied commit sequence does not end at HEAD"
    if blocked:
        return 1, "BLOCKED: skip directives in supplied commits: " + ", ".join(blocked)
    history_note = ("; HISTORICAL_SKIP_DIRECTIVES=" + ",".join(historical)\n                    if historical else "")\n    return 2, ("UNKNOWN: no skip directive in supplied HEAD; provenance, "\n               "pagination, commit completeness and GitHub dispatch remain "\n               "UNVERIFIED" + history_note)


def read_manifest(path: Path) -> object:
    # Explicit local input only. Reject symlinks and non-regular files.
    flags = os.O_RDONLY
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("O_NOFOLLOW unavailable")
    flags |= os.O_NOFOLLOW
    # Require a single basename: do not traverse untrusted parent directories.\n    if path.name != str(path) or str(path) in ("", ".", ".."):\n        raise ValueError("manifest must be a basename in the trusted working directory")\n    fd = os.open(path, flags)
    try:
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode):
            raise ValueError("not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("manifest too large")
        return json.loads(data.decode("utf-8"))
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = read_manifest(args.manifest)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        print("UNKNOWN: missing, unsafe or invalid evidence file", file=sys.stderr)
        return 2
    status, message = inspect(manifest)
    print(message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
