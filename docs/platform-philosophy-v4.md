# VORNEQ Platform Philosophy V4.0 — Proposed
DOCUMENT_ID: VORNEQ_PLATFORM_PHILOSOPHY_V4_0
VERSION: V4.0
DATE: 2026-11-23
STATUS: PROPOSED / OWNER REVIEW REQUIRED
SCOPE: PRODUCT PHILOSOPHY / NON-EXECUTABLE DIRECTION
IMPLEMENTATION_AUTHORIZATION: NONE
MERGE_AUTHORIZATION: NONE
DEPLOY_AUTHORIZATION: NONE

## Mission and identity
**One Platform. Many Applications. Connected Possibilities.**
VORNEQ is an interconnected ecosystem of independently governed applications for knowledge, creation, services, and evidence-based digital exchange. Its enduring purpose is to reduce the cost of establishing trust by making the grounds for consequential claims inspectable, attributable and contestable—not by manufacturing trust or declaring truth. AI may assist people across specialized experiences but does not become a source of authority.

## Product promise
Enable people to discover, create, analyze, collaborate, verify scoped claims, and use specialized applications with meaningful control over their information and decisions. Continuity of identity, language, navigation, preferences and authorized workflow context does not imply shared private data access. User-facing claims about availability or verification must be supported by actual implementation and evidence.

## Foundational principles
- **PHIL-01 One platform, many applications:** Domain apps own data, business rules and authorization.
- **PHIL-02 Interoperability without coupling:** Reviewed, versioned contracts; no private-table access, hidden imports or implied cross-app sharing.
- **PHIL-03 Human-centered continuity:** Shared navigation, identity and preferences with explicit consent and scoped access.
- **PHIL-04 Identity is not authorization:** Authentication, entitlement, registry membership and app visibility never grant resource permissions.
- **PHIL-05 Discovery before dependency:** Search and descriptive capability discovery do not silently become trust ranking, execution or authorization.
- **PHIL-06 Contextual trust and inspectable evidence:** No universal trust score; verification has scope, method, evidence, provenance, time, uncertainty and limitations. Verification is not truth.
- **PHIL-07 User control and data responsibility:** Explain privacy, export, correction, deletion, retention and shared-reference effects, subject to law and domain policy.
- **PHIL-08 AI as a bounded ecosystem capability:** AI assists research, creation and analysis with tenant isolation, domain authorization, provenance, explicit tool permissions, cost controls and human oversight. AI output is not verified evidence.
- **PHIL-09 Modular growth:** Share primitives only on demonstrated cross-domain demand; prefer a modular monolith with extraction-friendly boundaries.
- **PHIL-10 Transparency and accountability:** Inspectable decisions, proportionate audit trails and clear uncertainty; audit is not truth.
- **PHIL-11 Durable user-directed context (proposed extension):** Conversation/project continuity, export and deletion are product goals, not assertions of complete implementation; memory retrieval must respect user/tenant scope, retention and consent.
- **PHIL-12 Inclusive multilingual experience (proposed extension):** Accessible, responsive, understandable FA/DE/EN experiences, with explicit quality validation and no unverified parity claims.
- **PHIL-13 Economic independence (proposed extension):** Paid placement must be labeled and separated from organic discovery; payment, trust, verification and authorization remain independent. AI budgets and emergency controls remain enforceable.

## Architecture and non-collapsible boundaries
Platform Core owns reviewed shared identity/artifact/evidence primitives, not domain models. Platform Shell owns composition and navigation, not domain authority. Registry and Capability Discovery v1 are descriptive; executable Capability Bus v2 remains **PROPOSED** under ADR 012 and needs separate approval. Specialized apps enforce their own authorization. Infrastructure implements adapters, storage, queues and operational controls without overriding domain rules.

```text
IDENTITY != AUTHORIZATION
CAPABILITY != PERMISSION
SEARCH != VERIFICATION
VERIFICATION != TRUTH
REPUTATION != GLOBAL_TRUST_SCORE
ARTIFACT != DOMAIN_MODEL
REGISTRY != SERVICE_LOCATOR
WORKSPACE != DOMAIN_AUTHORITY
AI_OUTPUT != VERIFIED_EVIDENCE
INTEROPERABILITY != DATA_ACCESS
PAYMENT != TRUST
CONTRACT_STABLE != PRODUCTION_VERIFIED
DOCUMENTARY_ACCEPTANCE != EXECUTION_AUTHORIZATION
```

No philosophy document grants access, starts a paid provider call, authorizes deployment, relaxes financial gates, changes ranking, migrates data, or changes the Brand Constitution. The constitutional positioning **VORNEQ — Trust Infrastructure** remains unchanged; this document is a product-direction extension, not a brand replacement.

## V3.1 → V4.0 alignment
| V3.1 provision | V4.0 treatment | Change type |
| --- | --- | --- |
| Mission and interconnected application ecosystem | Retained; explicit knowledge, creation and human-AI collaboration use cases | Clarification |
| PHIL-01–05: apps, contracts, continuity, identity, discovery | Retained unchanged in authority and isolation | Preservation |
| PHIL-06: contextual trust and evidence | Retained; adds user-facing provenance questions | Clarification |
| PHIL-07: user control | Retained; identifies conversation/project data as future product-control cases | Extension |
| PHIL-08: ecosystem AI | Retained; specifies bounded tools, cost and human oversight as design constraints | Extension |
| PHIL-09–10: modularity, accountability | Retained | Preservation |
| Economic independence and ranking integrity | Retained in PHIL-13 | Consolidation |
| Capability Bus v2 PROPOSED | Remains PROPOSED, not silently promoted | Preservation |
| V3.1 proposed KPIs | Still proposed; no numeric adoption targets approved | Preservation |
| New PHIL-11/12/13 | Durable context, multilingual accessibility, economic clarity | Proposed additions |

## Proposed roadmap (not an execution plan or promise)
| Stage | Deliverable | Acceptance evidence | Gate |
| --- | --- | --- | --- |
| R0 — documentary alignment | FA/EN V4 draft, V3.1 mapping and architecture cross-check | Review against Constitution, Platform Contract and ADRs | Owner documentary approval |
| R1 — capability inventory | Matrix of implemented / experimental / proposed AI, Search, Notes, Documents, Marketplace and Workspace functions | Code-linked evidence and CI references | Product review |
| R2 — user experience | Separate Search vs AI Chat entry points, accessible FA/DE/EN navigation and clear capability labels | Usability and accessibility tests | Independent implementation PRs |
| R3 — continuity and privacy | Explicit conversation/project retention, retrieval, export and deletion contracts | Threat model, tenant-isolation and lifecycle tests | ADR and privacy review |
| R4 — trustworthy AI workflows | Scoped sources, citation uncertainty, authorized tools and human approval | Evidence/provenance and abuse tests, financial ledger checks | Separate security/paid authorizations |
| R5 — interoperable apps | Reviewed typed capability contracts with owning-domain policy | Contract tests, negative authorization tests | ADR approval before execution |
| R6 — measurement | Cross-app task completion, user control, provenance inspectability, accessibility and operational reliability | Defined metrics with baselines, no invented KPIs | Separate KPI adoption |

## Success and decision discipline
Evaluate discoverability, real cross-app workflows, domain isolation, user control, provenance inspectability, language accessibility and bounded operational costs. Numerical targets and maturity changes require separate decisions. The philosophy defines **why**, Platform Contracts define boundaries, ADRs record technical decisions, and release permissions govern actions.

## Source hierarchy
- `docs/brand/constitution.md` (approved, governing)
- `docs/platform-philosophy-v3.1.md` (owner-accepted direction)
- `docs/platform-philosophy-v2.md` and `docs/platform-philosophy-fa.md` (discovery, context and evidence)
- `docs/adr/001-vorneq-trust-infrastructure.md` (trust lifecycle)
- `docs/architecture/platform-contract.md` and `docs/product/user-control-principles.md` (maturity and user control)
- `docs/adr/012-executable-capabilities.md` (proposed executable bus)

No runtime behavior or production readiness has been independently established by this documentary revision.
