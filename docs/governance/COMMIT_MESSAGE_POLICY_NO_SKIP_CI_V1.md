# VORNEQ — Commit Message Policy: NO_SKIP_CI (V1)

**Status:** DOCUMENTARY_ONLY / OWNER-DIRECTED RECORD

**Scope:** Future commits authored by the assistant for VORNEQ.

## Rule

Do not include `[skip ci]` in future commit messages. Do not use equivalent CI-suppression directives to bypass this rule.

## Boundaries

- This rule does not rewrite, amend, delete, or invalidate historical commits or their SHAs.
- This rule does not authorize GitHub Actions execution, reruns, workflow changes, database operations, migrations, merges, deploys, or changes to required checks, branch protection, permissions, or security gates.
- Before any CI-triggering change, review the affected workflow triggers, privileges, secrets, database isolation, and side effects and obtain separate explicit authorization.
- This document is not independent verification or security approval.

**SC_07 = OPEN_CRITICAL**  
**C02 = OPEN_CRITICAL**  
**STOP_340 = ACTIVE**  
**FINAL_STATE = SAFE_HOLD / NO_GO**
