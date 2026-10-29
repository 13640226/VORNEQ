# Entdecken — Frozen Documentary Design Baselines

Status: DOCUMENTARY_ONLY / SAFE_HOLD / NO_GO
Owner approval date: 2026-10-29
Scope: design contracts only. No production CSS/HTML/JS, database, migration, test, or deployment change.

## Baseline A — Unified LED Interactions V1.2.1
ID: ENTDECKEN_UNIFIED_LED_INTERACTIONS_V1.2.1
Status: FROZEN

- Search LED indicator is positioned relative to a dedicated input wrapper.
- Input padding-inline-start is fixed from the outset (36px); no focus-triggered text shift.
- Wrapper manages responsive sizing with flex/min-width and mobile column layout; reconcile legacy input flex declarations on future implementation.
- Interactive search, filters, result cards, actions, graph disclosure and pagination use shared theme-derived LED/focus/glow tokens.
- Selected state is semantic (e.g. aria-current); keyboard focus must remain visible.
- Hover enhancements are restricted to capable pointing devices; reduced-motion preferences are honored.
- Existing card shadows and functional behavior must be preserved.
- Accessibility, browser cascade and runtime behavior remain UNVERIFIED.

## Baseline B — Background Replacement V1.3.2-R1
ID: ENTDECKEN_BACKGROUND_REPLACEMENT_V1.3.2-R1
Status: FROZEN

- Use existing design tokens: --color-bg-page, --color-bg-surface, --color-bg-elevated, --color-text-primary, --color-text-secondary, --color-border.
- Define Entdecken-scoped aliases for surface, input, text, border and hover. Avoid global palette modifications.
- For [data-theme="vorneq"], use nonwhite surface #f8fafc and input #f1f5f9; preserve page/surface differentiation.
- Replace all legacy --discover-navy text dependencies with theme-derived text tokens, including search input, filters, headings, links, context action and graph code.
- Replace fixed pale backgrounds (#eff6ff, #f8fafc) in hover, graph and state components with appropriate semantic theme values.
- Accent buttons use --color-accent and --color-text-on-accent in default, hover and focus-visible states; replace legacy .discover-action--record:hover { color:#fff; }.
- Active filter uses semantic accent/background/text/border tokens in default and hover states; remove legacy hardcoded active-filter hover.
- Consolidate V2/V3 duplicate selectors during any separately authorized implementation; appending overrides alone is insufficient.
- Check contrast per palette and state; token selection alone does not prove WCAG conformance.

## Source and evidence limitations
Static source audit referenced commit 72ed0d5842d538089e9f6cd1b852f727973b059f and files:
- assets/css/discover.css
- assets/css/tokens.css
- assets/css/theme-palettes.css
This document records approved design intent, NOT an implemented patch, passing test, or verified runtime state.

## Reviewer request
Requested reviewer: hamidrezaasadian7-boop
Review scope: documentary completeness, design consistency, theme/CSS cascade risks, accessibility acceptance criteria.
Approval of this document does NOT authorize merge, code implementation, deployment, database operations or release.

## Governance
STOP_340=ACTIVE
HARD_STOP=ACTIVE
C02=OPEN_CRITICAL
SC_07=OPEN_CRITICAL
DATABASE_GO=NO
MIGRATION_GO=NO
DEPLOY_GO=NO
PRODUCTION_RELEASE=BLOCKED
FINAL_STATE=SAFE_HOLD / NO_GO
