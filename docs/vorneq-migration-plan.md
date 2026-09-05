# VORNEQ Migration Plan
**From:** Saman Kherad (current)  
**To:** VORNEQ Knowledge Discovery Platform  
**Status:** Draft v1.0 (Audit Phase)  
**Last Updated:** 2026-09-05

---

## 1. Executive Summary

VORNEQ is a rebranding and product evolution of the existing Saman Kherad platform. The current codebase already provides a robust foundation:
- Multi-language support (fa, en, de) via Django i18n & `LocaleMiddleware`.
- Rich data models: `LibraryItem` (books, articles, documents), `AudioItem`, and `Product` (e-book, course, audio product, software, template, artwork).
- Django-allauth for authentication with real login/signup/password reset pages.
- Database: **Local/default uses SQLite**; **Render staging uses PostgreSQL via `DATABASE_URL`** (configured in `config/settings_render.py`).
- A working home view that aggregates LibraryItems, AudioItems, and approved Products.

**This migration is NOT a rebuild.** It is a controlled, phased transformation of the presentation layer (templates, CSS, brand) while preserving the backend, database, URLs, and existing user data. No data migrations will be performed solely for rebranding.

---

## 2. Keep / Modify / Do Not Touch Matrix

| Category | Files / Directories | Action | Reason | Target PR |
|----------|----------------------|--------|--------|-----------|
| **Keep** | `library/models.py`, `marketplace/models.py` | No change | Models fully support multi-language content and product types. | - |
| **Keep** | `apps/evidence/`, `apps/graph/` | No change | Specialised models; not needed for initial migration. | - |
| **Keep** | `config/settings.py` (base) | No change | SQLite for dev, allauth, Axes, security, caching correct. | - |
| **Keep** | `config/settings_render.py` | No change | PostgreSQL via `dj_database_url`; SSL and connection pooling already configured. | - |
| **Keep** | `config/urls.py` | No change | `i18n_patterns` and API separation are sound. | - |
| **Keep** | All authentication backend (allauth) | No change | Full login/signup/password reset flow works. | - |
| **Keep** | i18n configuration & `LocaleMiddleware` | No change | Three languages already configured; `locale/` directory may be absent in repo but paths are set. | - |
| **Keep** | Existing media storage paths and digital-file access contracts | No change | File protection and serving logic are correct. | - |
| **Keep** | All existing `migrations/` | No change | No schema changes in this phase. | - |
| **Modify** | `templates/base.html` | Refactor | Extract inline CSS; switch to light theme; update branding. | PR-B, PR-C |
| **Modify** | `templates/index.html` | Redesign | Convert to Unified Feed with featured, fresh, and search. | PR-D |
| **Modify** | `templates/partials/_standalone_nav.html` | Replace | New VORNEQ header with logo, nav, and auth buttons. | PR-C |
| **Modify** | `assets/css/tokens.css` | Update | New colour tokens, typography, spacing for light theme. | PR-B |
| **Modify** | `assets/css/base.css` | Refactor | Base styles aligned with new tokens; remove dark theme. | PR-B |
| **Modify** | `assets/css/components.css` | Update | Cards, buttons, forms to match new design. | PR-E, PR-F |
| **Modify** | `assets/css/home.css` | Rewrite | New grid layout and editorial styling for Discovery. | PR-D |
| **Modify** | `assets/css/standalone-nav.css` | Update | New header styling with reduced height (<=60px). | PR-C |
| **Modify** | `config/views.py` (home) | Enhance | Aggregate LibraryItem, AudioItem, Product into structured `feed` with type filters and search. | PR-D |
| **Modify** | `templates/account/` (allauth templates) | Redesign | UI only; backend unchanged. | PR-G |
| **Do Not Touch** | Any `models.py` (except future additions) | None | Schema stability is critical. | - |
| **Do Not Touch** | Any existing `migrations/` | None | Changing old migrations risks staging failures. | - |
| **Do Not Touch** | Security settings (`SECURE_*`, `Axes`) | None | Any change must be reviewed separately. | - |
| **Do Not Touch** | `/api/` endpoints | None | May have external clients. | - |
| **Do Not Touch** | Marketplace purchase/download logic | None | Only UI changes in Phase 1. | - |
| **Do Not Touch** | Digital product files (`media/products/`) | None | File paths and access must remain unchanged. | - |

---

## 3. PR Sequence & Dependencies

| PR | Name | Scope | Dependencies |
|----|------|-------|--------------|
| **A** | Audit & Baseline | Docs + read-only health checks | - |
| **B** | Brand Foundation | Tokens, base.css, light theme, favicon | PR-A |
| **C** | Header / Navigation | `_standalone_nav.html`, header in `base.html` | PR-B |
| **D** | Discovery Home | `index.html`, `home.css`, enhanced `config.views.home` | PR-C |
| **E** | Library UI | Library templates & CSS (no backend) | PR-D |
| **F** | Marketplace UI | Marketplace templates & CSS (no backend) | PR-E |
| **G** | Accounts UI | allauth template redesign | PR-F |
| **H** | Cleanup | Remove dead CSS, final optimisations | PR-G |

**Branch naming convention:**  
`docs/vorneq-audit`, `feat/vorneq-brand-foundation`, `feat/vorneq-navigation`, `feat/vorneq-discovery-home`, etc.

---

## 4. Timeline (Estimated Working Days)

| PR | Estimated Days | Notes |
|----|----------------|-------|
| A | 0.5 | Documentation + script writing |
| B | 1 | Token & base CSS refactor |
| C | 1 | Header rewrite |
| D | 2 | Home view logic + template/CSS |
| E | 1 | Library templates |
| F | 1.5 | Marketplace templates |
| G | 1 | Account pages |
| H | 0.5 | Cleanup & final review |

**Total:** ~8.5 working days (can be parallelised after PR-C).

---

## 5. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing user flows | High | Every PR is reviewed on staging; gradual rollout handled via PR decomposition. |
| Data loss during migration | Critical | No schema changes; no data migrations in this plan. |
| Language selection / RTL breakage | Medium | Test all PRs on `/fa/`, `/en/`, `/de/`; keep `LocaleMiddleware` intact. |
| Performance regression | Medium | Monitor query counts and response times manually during staging; use `django.db.connection.queries` in local testing if needed. |
| Rollback complexity | Medium | Each PR is independent; revert single PR if needed. |

---

## 6. Definition of Done (per PR)

- [ ] All tests pass (existing test suite + health checks)
- [ ] Manual smoke test on staging (checklist in `baseline-checklist.md`)
- [ ] Code reviewed by at least one other person
- [ ] No new migrations or schema changes (unless explicitly planned)
- [ ] No production data modified during testing
- [ ] Documentation updated (if applicable)

---

## 7. Success Criteria (Final)

- [ ] All pages load under light theme with VORNEQ branding.
- [ ] English is the primary language (default), but Persian and German work.
- [ ] Unified Discovery Feed shows LibraryItems, AudioItems, and Products.
- [ ] Global Search (planned for future) is not required in Phase 1.
- [ ] All existing user data (Library, Marketplace, Accounts) remains intact.
- [ ] No performance degradation compared to baseline.
