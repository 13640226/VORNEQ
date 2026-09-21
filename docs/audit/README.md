# VORNEQ — Audit Artifacts

This directory contains frozen audit artifacts produced by read-only 
static GitHub reviews. Each artifact is dated and baselined against a 
specific commit.

---

## Index

| Document | Baseline | Frozen Date |
|---|---|---|
| [`2026-09-15-pr-triage.md`](2026-09-15-pr-triage.md) | `main@925db1c` | 2026-09-15 |
| [`2026-09-15-codebase-integrity-review-v3.md`](2026-09-15-codebase-integrity-review-v3.md) | `main@925db1c` | 2026-09-15 |

Both artifacts share the same baseline:

```
main@925db1c22a95055b6397ff6bf891b397f50f0905
```

---

## Post-Freeze Policy

A frozen document is treated as an immutable snapshot. Changes to a 
frozen artifact follow one of two paths:

1. **Errata Note** — for wording, typo, or formatting corrections that 
   do not change IDs, severities, counts, or cross-reference semantics.
   Recorded as an appendix within the same file.

2. **Version Bump** — for structural changes (new findings, severity 
   reclassification, cluster restructure, decision changes). Requires 
   reopening the audit and producing a new versioned document (e.g., 
   `...-v4.md`).

---

## Method and Limitations

All artifacts in this directory were produced under the following 
constraints:

- **Read-only static GitHub review.** No local test execution.
- **CI evidence** is limited to workflow runs actually fetched during 
  the audit.
- **Claims** are limited to explicit evidence; no inference from free 
  text or from external sources.
- **Historical CI success ≠ current state.** Historical workflow 
  outcomes describe a PR at the time of the run, not the state of `main`.

See each artifact's Methodology section for full guardrails.

---

## Related Issues and PRs

- **Issue #139** — the source request for the holistic review.
- **Issues #303, #304, #305, #306** — follow-up issues produced during 
  the PR triage.
- **Issue #161** — closed as completed bookkeeping during the audit.

---

## Pending / Unapproved Work

Publishing these artifacts does **not** authorize any remediation. 
Pending mutations (workflow reruns, PR edits, issue creation, comments 
on open PRs) remain **unapproved** and are tracked separately in the 
PR triage document.
