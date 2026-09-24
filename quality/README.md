# Global Quality Verification Infrastructure v1

This directory implements the registered Quality Verification Specification v1.0 as report-only infrastructure.

Principles:
- Product-conformance failures are evidence, not remediation authorization.
- Infrastructure failures may fail CI.
- axe output does not establish complete WCAG conformance.
- Lighthouse is lab evidence only and must not be represented as production INP.
- INP remains `blocked/unknown — insufficient field data` until field telemetry exists.
- Account/auth indexability policy is not invented by the harness.
- R1 route semantics are observed, never changed here.

Artifacts:
- `verification-report.json`
- `verification-summary.txt`
- `lighthouse-report.json`

The browser verification covers V-01..V-10 across `fa`, `en`, and `de`. Lighthouse full measurements use representative locale `en`; Full surfaces get three cold runs on fixed mobile and desktop profiles. Sample surfaces get one cold mobile run. Warm reload timings are recorded separately as informational data.

Manual/hybrid WCAG checks such as keyboard focus quality, 200%/400% reflow, and reduced-motion acceptability remain explicitly marked for manual/hybrid verification rather than being falsely automated.
