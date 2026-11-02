#!/usr/bin/env python3
"""V1.1: opt-in, offline CI skip-directive evidence preflight.

Reads one explicitly supplied local JSON manifest; never invokes Git, Actions,
network, subprocesses, DB, or workflows. Not installed as a CI job or hook.
This is a diagnostic only, not a substitute for required GitHub checks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_BYTES = 1024 * 1024
SHA = re.compile(r"^[0-9a-f]{40}$")
SKIP = re.compile(r"\[(?:skip ci|ci skip|no ci|skip actions|actions skip)\]", re.I)
TRAILER = re.compile(r"(?im)^skip-checks:[ \t]*true[ \t]*$")
EXPECTED = frozenset((
    "test (3.11)", "test (3.12)", "dependencies", "postgres-backup-restore"
))


def inspect(manifest: object) -> tuple[int, str]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "head_sha", "commits", "required_contexts"
    }:
        return 2, "UNKNOWN: invalid manifest shape"
    head, commits, contexts = (
        manifest["head_sha"], manifest["commits"], manifest["required_contexts"]
    )
    if not isinstance(head, str) or not SHA.fullmatch(head):
        return 2, "UNKNOWN: invalid head SHA"
    if not isinstance(commits, list) or not commits or len(commits) > 1000:
        return 2, "UNKNOWN: missing or oversized commit list"
    if not isinstance(contexts, list) or any(
        not isinstance(c, str) for c in contexts
    ) or len(contexts) != len(set(contexts)):
        return 2, "UNKNOWN: invalid required contexts"
    if frozenset(contexts) != EXPECTED:
        return 2, "UNKNOWN: required contexts differ from pinned snapshot"
    seen: set[str] = set()
    blocked: list[str] = []
    for item in commits:
        if not isinstance(item, dict) or set(item) != {"sha", "message"}:
            return 2, "UNKNOWN: malformed commit"
        sha, message = item["sha"], item["message"]
        if (not isinstance(sha, str) or not SHA.fullmatch(sha)
                or sha in seen or not isinstance(message, str)
                or len(message) > 65536):
            return 2, "UNKNOWN: invalid or duplicate commit"
        seen.add(sha)
        if SKIP.search(message) or TRAILER.search(message):
            blocked.append(sha[:12])
    if head not in seen:
        return 2, "UNKNOWN: head absent from supplied commit list"
    if blocked:
        return 1, "BLOCKED: skip directive in supplied commits: " + ", ".join(blocked)
    return 0, ("NO_SKIP_FOUND_IN_SUPPLIED_EVIDENCE: not proof of completeness, "
               "safe CI, workflow dispatch, or required-check success")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path,
                        help="Explicit, trusted, local UTF-8 JSON manifest")
    args = parser.parse_args(argv)
    try:
        if not args.manifest.is_file():
            raise ValueError("not a regular file")
        if args.manifest.stat().st_size > MAX_BYTES:
            raise ValueError("manifest too large")
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        print("UNKNOWN: manifest unavailable or invalid", file=sys.stderr)
        return 2
    status, message = inspect(data)
    print(message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
