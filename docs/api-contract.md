# VORNEQ API Contract Baseline

## Decision

VORNEQ's current HTTP API is intentionally Django-native. The existing API surface uses Django `JsonResponse` views and does not require Django REST Framework merely to publish a contract.

This baseline therefore uses a repository-owned OpenAPI 3.1 document (`docs/openapi-v1.json`) with contract tests and no new runtime dependency.

## Current endpoint classification

| Endpoint | Method | Exposure | Stability | Notes |
| --- | --- | --- | --- | --- |
| `/api/search/` | GET | Public | Stable V1 discovery | Retrieval only. Search does not imply verification or trust. |
| `/api/verification/product/{id}/` | GET | Public | Stable V1 | Public-safe verification summary for published/approved products. |
| `/api/verification/library/{id}/` | GET | Public | Stable V1 | Public-safe verification summary for published library items. |
| `/api/reputation/user/{id}/` | GET | Public | Stable V1 | Public contextual reputation projection; not a composite trust score. |
| `/api/reputation/user/{id}/{domain}/{method_code}/` | GET | Public | Stable V1 | Context-specific public reputation projection. |
| `/api/reputation/{id}/` | GET | Authenticated | Internal V1 | Authenticated reputation snapshot; not advertised as a public integration contract. |
| `/api/media/search/text/` | POST | Public route, development-backed | Experimental | Discovery-only. Production returns 503 until a production embedding provider exists. |
| `/api/media/search/image/` | POST | Public route, development-backed | Experimental | Discovery-only. Production returns 503 until a production embedding provider exists. |

## Versioning policy

Existing paths remain unchanged to avoid a breaking migration solely for naming consistency. They are treated as the V1 compatibility surface.

New externally supported API families should use an explicit `/api/v1/...` prefix unless an ADR approves a different compatibility strategy. A future migration of existing paths to `/api/v1/` must provide a compatibility window and must not silently change response semantics.

## Idempotency review

All current API operations are read/discovery operations. GET endpoints are naturally idempotent. The two media search endpoints use POST because their input can contain structured text or uploaded image bytes, but they do not mutate domain state and are semantically idempotent for the same request and underlying index state.

No `Idempotency-Key` storage layer is introduced in this PR because there are currently no public state-changing POST/PUT/PATCH endpoints in this API surface. The first externally supported state-changing endpoint must define its retry/idempotency contract before release.

## Error conventions

Current endpoints use standard HTTP status codes and JSON error objects where applicable. This baseline documents existing behavior rather than imposing a new global error envelope. A standardized error envelope should be introduced only with a migration plan for existing clients.

## Trust constraints

- Search and media similarity are discovery mechanisms, not verification.
- Public reputation is contextual and must not be interpreted as a composite Trust Score.
- Verification summaries expose public-safe context and do not claim ownership of truth.

## OpenAPI ownership

`docs/openapi-v1.json` is the source-controlled contract for the current V1 surface. Contract tests validate that the document is parseable and that the documented paths remain aligned with the Django URL configuration.
