# VORNEQ — How It Works / Navigation Full Upgrade — Phase 0 Contract

Status: DRAFT / REVIEW ONLY
Base: ff6c69df2ecce33b46237292f2ae1dedd79502e2
Authorization: User-requested isolated branch and Draft PR only.
No merge, deploy, migration, database access, secrets access or runtime change.

## Source audit (initial, static)
- `config/urls.py`: localized home, discover, orientation, search, inspect, context, graph; API routes for core, verification, media, search.
- `config/settings.py`: Django templates, i18n fa/en/de, auth/CSRF/CSP middleware, database selection from environment. Configuration presence is not runtime proof.
- `templates/inspect_form.html`: existing form POST with CSRF, length limit, translated labels; current scope limited to public Products and Library items.
- `.github/workflows/ci.yml`: isolated container test design; no CI run or security acceptance performed in this review.
- Current screenshot: /de/#how-it-works; visible sidebar Startseite, Suchen, Funktionen, So funktioniert es, Vertrauen, Prinzipien, Erkunden and 5 workflow cards.
- Source for screenshot's exact section and shared navigation: NOT YET LOCATED. Do not edit blindly.

## Security and governance prerequisites
- Preserve STOP_340, HARD_STOP, C02, SC_07, SAFE_HOLD / NO_GO unless separately resolved with independently verifiable evidence and explicit owner decision.
- Separate PROPOSAL, REVIEW, APPROVAL, EXECUTION AUTHORIZATION, and VERIFIED EVIDENCE.
- No new public write endpoints, unscoped object lookups, tenant-crossing relations, or data visibility expansion without independent review.
- Backend work must use existing authorization policy, object-level checks, tenant boundaries, audit logging, rate limits, input validation, and fail-closed behavior.
- No new migrations without a separately authorized database identity verification and migration gate.
- CI execution is NOT authorized by this document. Do not trigger a run solely to test this plan.

## Proposed phased implementation
1. Phase 1: locate source ownership for home/how-it-works/sidebar; audit accessibility, CSS, translations, URL names, current tests and affected views. Create precise file/line matrix.
2. Phase 2: responsive navigation and 5 step cards; semantic headings, visible focus, keyboard operation, reduced-motion, contrast and screen reader labels; no new backend behavior.
3. Phase 3: connect cards to existing *authorized* read-only backend routes, with safe empty/error/loading states and no permission bypass.
4. Phase 4: introduce any required real workflows for collect/structure/verify/link/discover only after model/service-level authorization and tenant/audit contracts are independently reviewed. Use separate scoped PRs if migrations or new data writes are required.
5. Phase 5: localization for de/en/fa, unit and integration tests in isolated permitted environments, independent review and evidence report. Deployment is out of scope.

## Acceptance criteria (proposed; none verified)
- AC-01: all 7 navigation sections map to valid named routes or documented anchors.
- AC-02: 320px–desktop responsive layout without horizontal overflow.
- AC-03: WCAG keyboard, focus, labels, semantic landmarks and contrast checks.
- AC-04: German, English, Persian strings complete and catalogs compiled in authorized build.
- AC-05: 5 cards show source → structured record → evidence → links → discover with honest provenance and verification states.
- AC-06: backend responses enforce authenticated and object-level authorization, tenancy and safe public visibility.
- AC-07: no new writes or migrations without separate gate approval.
- AC-08: isolated tests and independent reviewer evidence tied to exact HEAD SHA.
- AC-09: no merge or deploy by this PR.

## Open audit questions
- Identify the exact template, CSS and view rendering the screenshot section.
- Check whether existing read APIs support each step without schema changes.
- Verify source of truth for governance contracts and current gate state.
- Establish independent reviewer and evidence for every backend expansion.

FINAL_STATE: DRAFT / NO_MERGE / NO_DEPLOY / NO_DATABASE_OPERATIONS.
