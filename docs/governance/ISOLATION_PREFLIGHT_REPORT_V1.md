# ISOLATION_PREFLIGHT_REPORT_V1

Date: 2026-11-03
Project: VORNEQ
Directive: P0_VORNEQ_SEC_CI_01_ISOLATED_LOCKFILE_ENVIRONMENT_PREFLIGHT_V1
Scope: local isolated-environment preflight only; no GitHub CI, SQL, migrations, merge, deploy, dependency resolution, or install.

## Repository source inspection

Read via connected GitHub repository `13640226/VORNEQ`, branch `fix/ci-security-hardening-draft-20261103`:
- `requirements.txt` blob `a2f0759010cca154bbc556b7db24e6ef8e050461`
- `requirements-security.txt` blob `be83129446f802b21166eb90f01a0b602904cb67`
- `quality/package.json` blob `057cd22032930c2bc508b3714d82ba9859214852`
- `scripts/prepare_isolated_lock_workspace.py` blob `b7caaf71beccf1a8e247ff1fd9542e13a5dd2c46`

PR #505 live HEAD was not independently established in this probe; branch file blob IDs are not equivalent to PR HEAD.

## Local probe

A host-root launcher switched to uid/gid 65534 using `setpriv --reuid=65534 --regid=65534 --clear-groups`, then cleared inherited environment using `env -i PATH=/usr/bin:/bin HOME=/nonexistent`, then launched `unshare --user --map-root-user --mount --net --fork` and ran a standard-library Python probe. No dependency manager was invoked.

Observed:
- Inside user namespace uid/euid/gid = 0 (mapped namespace root; host launch identity 65534).
- Environment keys = HOME, LC_CTYPE, PATH. No sensitive environment variable values were accessed.
- TCP attempts to 1.1.1.1:443 and 169.254.169.254:80 failed (OSError); limited connectivity probe, not comprehensive egress policy verification.
- `/root` exists but was not readable.
- `/var/run/docker.sock` absent.
- `/mnt/data` remains readable from inside namespace. **FAIL-CLOSED STOP CONDITION**: host filesystem isolation not established.
- Python runtime 3.13.5; target 3.11/3.12 not observed.
- Node 22.16.0 observed on host; availability inside a fully isolated environment not verified.
- First attempt to read probe inside a 0700 work directory was denied; probe was copied to `/tmp` for the limited check. No project manifests copied to isolated workspace.

## Outcome

```text
ENVIRONMENT_ISOLATION = FAILED
SECRET_ACCESS = NOT_VERIFIED
NETWORK_EGRESS = PARTIALLY_BLOCKED / NOT_FULLY_VERIFIED
PYTHON_311_312 = UNAVAILABLE_IN_OBSERVED_ENVIRONMENT
NODE_22 = AVAILABLE_ON_HOST_ONLY
LOCKFILE_GENERATION = NOT_EXECUTED
INDEPENDENT_REVIEW = PENDING
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
FINAL_STATE = SAFE_HOLD / NO_GO
```

## Required corrections before resolver execution

Provision a fresh unprivileged VM or container with verified filesystem confinement, no inherited credentials or host mounts, verified network deny-by-default and metadata blocking, approved registry-only access, Python 3.11/3.12 and Node 22. Obtain independent reviewer acceptance of the environment evidence before any dependency resolution. This report records a local observation only, **not** independent approval.
