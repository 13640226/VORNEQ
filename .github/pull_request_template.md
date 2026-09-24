## Summary

Describe the change and why it is needed.

## Scope

List the files, surfaces, or behaviors affected by this PR.

## Testing

Describe the checks, tests, or validation performed.

## 📋 Architecture Check — VORNEQ

This PR has been checked against the VORNEQ Architecture Blueprint v2.2:

- [ ] **Verification ≠ Truth:** Verification outcomes are not presented as absolute truth.
- [ ] **Trust Context without Score:** No composite Trust Score or star rating is introduced.
- [ ] **Search ≠ Verification:** Search remains a discovery/retrieval mechanism and does not imply verification.
- [ ] **Reputation is Contextual:** Reputation remains scoped by domain, method, and actor role.
- [ ] **Marketplace as Discovery Hub:** This change does not reintroduce Library as a primary destination.
- [ ] **No Inference:** Identity is not inferred from free-text fields such as `author`.
- [ ] **PostgreSQL First:** No new search/storage infrastructure is introduced without measured need.
- [ ] **Multi-Theme:** UI changes use design tokens and remain compatible with the theme system.
- [ ] **Backward Compatibility:** Existing URLs, API contracts, entitlement paths, and canonical data remain compatible or have an explicit migration/redirect plan.

Any exception must be documented in an ADR.
