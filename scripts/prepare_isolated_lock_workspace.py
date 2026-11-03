#!/usr/bin/env python3
"""Prepare a disposable, OFFLINE lockfile workspace. Never runs installers.

Usage: python scripts/prepare_isolated_lock_workspace.py
No CI trigger, Docker, SQL, npm, pip, subprocess, network or secrets.
"""
from pathlib import Path
from tempfile import mkdtemp
from shutil import copy2
import json
import os
import stat

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "requirements.txt",
    "requirements-security.txt",
    "quality/package.json",
)

def main() -> None:
    # Refuse to prepare a workspace from a path outside this checked-out tree.
    for relative in SOURCES:
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"Missing or unsafe input: {relative}")
    workspace = Path(mkdtemp(prefix="vorneq-lock-preflight-"))
    os.chmod(workspace, stat.S_IRWXU)
    for relative in SOURCES:
        dest = workspace / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy2(ROOT / relative, dest)
        os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR)
    manifest = {
        "mode": "OFFLINE_PREPARATION_ONLY",
        "network": "NOT_USED",
        "package_install": "NOT_RUN",
        "database": "NOT_USED",
        "secrets": "NOT_COPIED",
        "source_paths": list(SOURCES),
        "status": "LOCKFILES_NOT_GENERATED",
        "warning": "This directory is not a sandbox; execute resolvers only in a separately verified isolated environment.",
    }
    (workspace / "PREPARATION.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Offline workspace prepared: {workspace}")
    print("No lockfiles generated. Do not run pip/npm until isolation is independently verified.")

if __name__ == "__main__":
    main()
