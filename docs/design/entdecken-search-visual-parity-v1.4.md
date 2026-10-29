# Entdecken Search — Visual Parity V1.4 (Frozen Design Only)

Status: OWNER_APPROVED / DESIGN_BASELINE_FROZEN / DOCUMENTARY_ONLY
Date: 2026-10-29
Reviewer requested: @hamidrezaasadian7-boop

## Intent
Replace the *visual appearance* of the white Entdecken search panel with a blue-gradient branded surface visually aligned with the homepage Suchen section. This is **not an implementation** or a claim of pixel-perfect parity. Gradient values are proposals approximated from user screenshots, not extracted exact homepage gradient values.

## Preserved baselines
- ENTDECKEN_UNIFIED_LED_INTERACTIONS_V1.2.1 — FROZEN (not implemented)
- ENTDECKEN_BACKGROUND_REPLACEMENT_V1.3.2-R1 — FROZEN (not implemented)
- ENTDECKEN_HOMEPAGE_SEARCH_VISUAL_PARITY_V1.4 — FROZEN (design only)

## Read-only source findings
- `assets/css/discover.css` contains `.discover-controls { background:#fff; }`, `.discover-search input { background:#fff; }`, and legacy V2/V3 hover colors.
- `templates/discover/placeholder.html` loads `css/discover.css`; it uses `.discover-controls` and `.discover-search`.
- Homepage `templates/index.html` uses `.world-search`, `.world-search__input` and `.world-search__submit`.
- `assets/css/homepage-modern-v2.css` defines homepage semantic surface/focus/foreground roles; its search input uses `--home-surface-raised`, not a universal hardcoded blue background.
- The proposed gradient is a *branded exception* limited to Entdecken controls; it is not claimed to be copied from the homepage CSS.

## Design contract (not applied)
```css
/* DOCUMENTARY ONLY — NOT IMPLEMENTED */
.discover-page {
  --discover-search-bg:
    radial-gradient(ellipse at 80% 80%, rgba(68,185,245,.24), transparent 65%),
    linear-gradient(135deg,#173b83 0%,#2158a6 55%,#277bb5 100%);
  --discover-search-input-bg: rgba(12,43,91,.30);
  --discover-search-border: rgba(157,224,255,.75);
  --discover-search-text: #fff;
}
.discover-controls {
  --discover-led-contrast: #a5f3fc;
  --discover-led-glow:
    0 0 0 3px rgba(165,243,252,.20),
    0 0 16px rgba(165,243,252,.55);
  --discover-focus-contrast: #a5f3fc;
  background: var(--discover-search-bg);
  color: var(--discover-search-text);
  border: 1px solid rgba(157,224,255,.30);
  border-radius: 24px;
}
.discover-search input {
  background: var(--discover-search-input-bg);
  color: var(--discover-search-text);
  border: 2px solid var(--discover-search-border);
  border-radius: 12px;
}
.discover-search input::placeholder { color: rgba(255,255,255,.78); opacity: 1; }
.discover-search input:focus-visible {
  border-color: var(--discover-focus-contrast);
  outline: 2px solid var(--discover-focus-contrast);
  outline-offset: 2px;
}
.discover-search button {
  background: var(--color-accent);
  color: var(--color-text-on-accent);
}
.discover-filters a {
  color: var(--discover-search-text);
  border-color: rgba(255,255,255,.25);
}
.discover-filters a[aria-current="page"],
.discover-filters a[aria-current="page"]:hover {
  background: var(--color-accent);
  color: var(--color-text-on-accent);
  border-color: var(--color-accent);
}
```

## Future implementation acceptance criteria (not authorized)
1. Resolve CSS cascade and selector ordering in actual discover.css, including V2/V3 hover and all states.
2. Preserve LED V1.2.1 DOM anchoring, fixed padding, responsiveness and reduced motion; local contrast tokens must be *wired to actual LED selectors* and not silently change frozen LED behavior.
3. Blue branded panel is a documented theme-independent exception; remaining page elements retain semantic theme tokens.
4. Verify contrast on *every gradient position*, placeholder, focus, filter, button and all supported themes; do not claim WCAG AAA without measurements.
5. Verify keyboard, RTL, mobile, and browser behavior in a separately authorized test phase.
6. No code, merge, database, migration or deployment authorization follows from review approval.

## Security hold
STOP_340=ACTIVE
HARD_STOP=ACTIVE
C02=OPEN_CRITICAL
SC_07=OPEN_CRITICAL
DATABASE_GO=NO
MIGRATION_GO=NO
DEPLOY_GO=NO
PRODUCTION_RELEASE=BLOCKED
FINAL_STATE=SAFE_HOLD / NO_GO
