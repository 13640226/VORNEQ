# Quality Verification v1 acceptance mapping

- QV-AC01: `contract.mjs` enumerates V-01..V-10.
- QV-AC02..07: `verify.mjs` records automated axe evidence plus explicit manual/hybrid requirements.
- QV-AC08..10: `lighthouse.mjs` records fixed profiles, three cold runs for Full surfaces, thresholds, separate warm informational data, and INP as field-only unknown.
- QV-AC11..14: `verify.mjs` records title/description/canonical/hreflang/crawl evidence without changing route semantics or inventing auth indexability.
- QV-AC15..17: `verify.mjs` checks `fa/en/de` lang/dir and per-locale metadata evidence.
- QV-AC18: unknown policy remains blocked/unknown rather than invented.
- QV-AC19: JSON artifacts include surface, locale, rule/metric, observed result; Lighthouse adds profile.
- QV-AC20: this infrastructure contains no production behavior or Lock changes.

Product-conformance misses remain report-only in v1. Harness/configuration failures may fail CI.
