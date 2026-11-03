# SEC-CI-01 — Digest and dependency lock verification (2026-11-03)

**Status:** PARTIAL_CORRECTION / OPEN. **Scope:** static read and documentary write only; no CI, package install, Docker pull, SQL, migration, merge or deploy.

## GitHub source verification

- `.github/workflows/ci.yml` and `.github/workflows/backup-restore.yml` both reference `postgres:16@sha256:1beaa3084eee2676f20a9cd9928f0bf2c5bf674f8e49f81017912183d377c61c`.
- The digest is a candidate multi-architecture index digest from a public registry listing; registry manifest API verification, linux/amd64 resolution and image provenance remain **NOT_INDEPENDENTLY_VERIFIED**. A pinned value is not proof of suitability.
- `quality/package-lock.json` was not found on this branch. `quality/package.json` pins four direct dependencies, but not their complete transitive tree.
- `requirements.txt` and `requirements-security.txt` use direct `==` pins, but have no complete transitive `--hash` lock.
- `npm install` and `pip install` in workflows therefore do not yet establish reproducible, hash-verified installations.

## Lock generation — deliberately deferred

Producing a genuine npm lockfile requires dependency resolution against a registry, and producing a complete Python hash lock requires package resolution and artifact hash verification for a selected target platform. Neither can be truthfully generated from the source manifests alone. **No fabricated lockfiles or hashes have been committed.**

Proposed isolated procedure, subject to separate explicit execution authorization and independent review:

1. Fix the target platform (Ubuntu 24.04, linux/amd64, Python 3.11 and 3.12; Node 22), and use a clean ephemeral environment with no repository or production secrets.
2. Limit outbound access to explicitly approved registries; block metadata endpoints and unapproved destinations; capture dependency and image provenance.
3. Generate `quality/package-lock.json` from `quality/package.json` with approved npm tooling, inspect integrity entries and lifecycle scripts, then use `npm ci` in the proposed workflow.
4. Resolve complete Python transitive dependencies for each supported Python version; generate hash-locked requirements, inspect wheel/source distribution choices, and require hash verification on install.
5. Verify the PostgreSQL image index and architecture-specific manifest via the trusted registry, then verify the workflow's image reference against the approved digest.
6. Have an independent reviewer confirm all artifacts and commit SHAs before any CI trigger.

## Governance

```text
POSTGRES_WORKFLOW_REFERENCES = PINNED_IN_SOURCE
POSTGRES_DIGEST_REGISTRY_VERIFICATION = NOT_VERIFIED
PYTHON_HASH_LOCK = MISSING
NODE_LOCKFILE = NOT_FOUND
LOCKFILE_GENERATION = NOT_EXECUTED
SEC_CI_01 = PARTIAL_CORRECTION / OPEN
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
FINAL_STATE = SAFE_HOLD / NO_GO
```
