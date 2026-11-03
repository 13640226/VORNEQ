# SEC-CI-01 — Isolated lockfile generation environment contract V1

Status: **PREPARATION_COMMITTED / EXECUTION_NOT_AUTHORIZED**  
Related PRs: #505 (security corrections), #503 (blocked checks), #504 (documentary review).

## What is prepared

`scripts/prepare_isolated_lock_workspace.py` is an offline, standard-library-only preparatory script. When invoked locally, it creates a new owner-accessible temporary directory, copies only `requirements.txt`, `requirements-security.txt`, and `quality/package.json`, and writes a JSON preparation manifest. It does **not** run pip, npm, Docker, SQL, CI, migrations, network calls or any package resolver. It does not copy environment variables or secret files. The script itself has been committed but **not executed**.

**Important:** a temporary directory is NOT a security sandbox. The preparation script does not provide OS/container/network isolation.

## Proposed separately authorized resolver environment

- Fresh ephemeral runner or VM, not Render, production, staging or the GitHub CI runner with privileged credentials.
- No GitHub token, cloud credentials, SSH agent, mounted home directory, Docker socket, host filesystem or production/staging database access.
- No inherited environment variables or mounted secret stores; create a clean environment explicitly.
- Egress deny-by-default with narrow approved registry allowlist and metadata endpoint blocking, verified independently.
- Python 3.11 and 3.12 and Node.js 22 pinned to verified distributions, with architecture recorded.
- Read-only manifest inputs; outputs limited to reviewed lock artifacts and a provenance log.
- Review npm lifecycle scripts and Python build backend execution risks before resolution.
- Produce npm `package-lock.json` with integrity entries; verify using `npm ci --ignore-scripts` first, then separately assess any required scripts.
- Produce complete per-Python-version transitive requirements locks with package hashes; verify hashes and distribution compatibility before switching workflows to hash-enforcing installation.
- No database or migration needed for lock generation.
- Destroy the ephemeral environment after extracting reviewed artifacts.

## Exit evidence

Machine-readable manifest, exact interpreter/tool versions, approved registry URLs, SHA256 of generated lockfiles, transitive dependency inventory, verified egress logs, reviewer identity and commit-scoped owner decision. Do not claim these until independently observed.

```text
OFFLINE_PREPARATION_SCRIPT = COMMITTED / NOT_EXECUTED
ISOLATED_RESOLVER_ENVIRONMENT = NOT_PROVISIONED
LOCKFILES = NOT_GENERATED
INDEPENDENT_SECURITY_VERIFICATION = PENDING
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
FINAL_STATE = SAFE_HOLD / NO_GO
```
