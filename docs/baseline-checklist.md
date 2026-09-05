# Baseline Checklist – Saman Kherad → VORNEQ

**Purpose:** Manual verification of critical routes before any code changes.  
**Run on:** Staging environment (or local with production-like data).  
**Status:** ✅ = works as expected, ⚠️ = works but needs notes, ❌ = broken (must be fixed before proceeding).

---

## 1. Core Routes (Public)

| URL | Expected Behaviour | Status | Notes / Action |
|-----|-------------------|--------|----------------|
| `/` (root) | Redirects to default language (`/fa/` or `/en/`) | `[ ]` | Check final redirect target |
| `/fa/` | Home page in Persian | `[ ]` | Visual check, content appears |
| `/en/` | Home page in English | `[ ]` | Visual check, content appears |
| `/de/` | Home page in German | `[ ]` | Visual check, content appears |

---

## 2. Library (Authenticated & Public)

| URL | Expected Behaviour | Status | Notes / Action |
|-----|-------------------|--------|----------------|
| `/fa/library/` | Library page (if logged in) or redirect to login | `[ ]` | Check that LibraryItems are displayed |
| `/en/library/` | Same in English | `[ ]` | - |
| `/fa/library/<slug>/` | Library item detail (book/article) | `[ ]` | Check metadata & multi-language fields |

---

## 3. Marketplace

| URL | Expected Behaviour | Status | Notes / Action |
|-----|-------------------|--------|----------------|
| `/fa/marketplace/` | Product listing (approved & published) | `[ ]` | Check Product cards & filters |
| `/en/marketplace/` | Same in English | `[ ]` | - |
| `/fa/marketplace/<slug>/` | Product detail | `[ ]` | Check file protection & purchase button |

---

## 4. Accounts (allauth)

| URL | Expected Behaviour | Status | Notes / Action |
|-----|-------------------|--------|----------------|
| `/fa/accounts/login/` | Login form | `[ ]` | Visual check, CSRF token present |
| `/fa/accounts/signup/` | Signup form | `[ ]` | Visual check, fields correct |
| `/fa/accounts/password/reset/` | Password reset form | `[ ]` | Email sending works (if configured) |

---

## 5. Audio & Special Content

| URL | Expected Behaviour | Status | Notes |
|-----|-------------------|--------|-------|
| `/fa/library/audio/<pk>/` | Audio detail | `[ ]` | Player renders; valid audio can be played |
| `/en/library/audio/<pk>/` | Audio detail in English locale | `[ ]` | Check LTR presentation |
| `/fa/library/<slug>/` | Library item detail | `[ ]` | Check title, description and metadata |
| `/fa/library/<slug>/read/` | Protected PDF reader | `[ ]` | Test only with an item that has an allowed PDF |

**Note:** The PDF reader route (`/fa/library/<slug>/read/`) is **not** included in the automated health check due to requiring a valid slug and access control; it remains a manual verification step.

---

## 6. Global Search (Current State)

| Item | Status | Notes |
|------|--------|-------|
| Global Search bar exists? | `[ ]` | (Yes/No) |
| Search functionality works? | `[ ]` | (Yes/Partially/No) |
| Which models are searched? | `[ ]` | (e.g., LibraryItem, AudioItem, Product) |
| Search results show correctly? | `[ ]` | (Yes/No/With issues) |

**Note:** For VORNEQ, Global Search will be enhanced in a later phase; this is just a baseline record.

---

## 7. Internationalisation & RTL

| Language | Text direction (RTL/LTR) | Status | Notes |
|----------|--------------------------|--------|-------|
| Persian (`/fa/`) | RTL | `[ ]` | Check that CSS handles RTL |
| English (`/en/`) | LTR | `[ ]` | - |
| German (`/de/`) | LTR | `[ ]` | - |

---

## 8. Performance & Errors

| Check | Status | Notes |
|-------|--------|-------|
| Browser console errors (JS) | `[ ]` | None expected |
| Server error logs (last 24h) | `[ ]` | Check for 500s |
| Observed page-load time (seconds) | `[ ]` | Record average of 3 reloads |

---

## Instructions

1. Open each URL in a browser (logged out and logged in where applicable).
2. Mark status in the `[ ]` boxes.
3. Add any notes or actions required.
4. If any ❌ or critical ⚠️ are found, address them before proceeding to PR-B.
