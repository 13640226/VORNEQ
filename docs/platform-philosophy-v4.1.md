# VORNEQ Platform Philosophy V4.1 — Proposed
DOCUMENT_ID: VORNEQ_PLATFORM_PHILOSOPHY_V4_1
VERSION: V4.1
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
- **PHIL-07 User control and data responsibility:** Explain privacy, export, correction, deletion, retention and shared-reference effects, subject to law and domain policy. Deletion is a domain-policy workflow, not an implicit cross-app cascade. Identity removal, app-owned content, shared work and references are evaluated separately. Where lawful and necessary, a minimized tombstone or anonymized record may remain; neither is presumed non-personal. Show material effects and available choices before confirmation.
- **PHIL-08 AI as a bounded ecosystem capability:** AI assists research, creation and analysis with tenant isolation, domain authorization, provenance, explicit tool permissions, cost controls and human oversight. AI output is not verified evidence. Factual claims should carry inspectable provenance/status where feasible: verified (only after an explicitly scoped verification process), source-attributed (a source is cited but the claim is not necessarily verified), model-asserted (no independent source verification), or uncertain (insufficient/conflicting evidence). These are evidence-status labels, **not calibrated confidence probabilities**; never convert a citation into a truth guarantee. Present material distinctions accessibly in text and, where supported, voice.
- **PHIL-09 Modular growth:** Share primitives only on demonstrated cross-domain demand; prefer a modular monolith with extraction-friendly boundaries.
- **PHIL-10 Transparency and accountability:** Inspectable decisions, proportionate audit trails and clear uncertainty; audit is not truth.
- **PHIL-11 Durable user-directed context (proposed extension):** Conversation/project continuity, export and deletion are product goals, not assertions of complete implementation; memory retrieval must respect user/tenant scope, retention and consent.
- **PHIL-12 Inclusive multilingual experience (proposed extension):** Accessible, responsive, understandable FA/DE/EN experiences, with explicit quality validation and no unverified parity claims. Before production release, each feature claiming support for a target language must pass defined readability, accessibility and localization checks for that language; unsupported or incomplete locales must be clearly disclosed, not silently claimed as equivalent.
- **PHIL-13 Economic independence and cost transparency (proposed extension):** Paid placement must be labeled and separated from organic discovery; payment, trust, verification and authorization remain independent. Paid AI usage and advertising are distinct revenue/accounting flows; whether a paying user sees advertising is a separate disclosed product-policy decision, not implied by payment. Before chargeable action, present a bounded estimate or price basis and obtain explicit consent or an unexpired, scoped pre-approved budget authorization. Show actual settled cost and unresolved/uncertain charges in user-facing history and a controlled ledger where supported. Never imply a guaranteed final price from an estimate. AI budgets and emergency controls remain enforceable.

- **PHIL-14 Transparent failure and safe recovery (proposed extension):** Denials before execution should explain a bounded reason; timeouts, provider uncertainty, and post-effect persistence failures must not be misrepresented as definitely failed or free. Chargeable or side-effecting operations must not be blindly retried when their outcome is unknown; reconcile or use proven idempotency first. Safe read-only retries may be permitted by explicit policy. Under overload, prefer honest degraded service and actionable recovery guidance.
- **PHIL-15 Incident accountability and proportionate disclosure (proposed extension):** Security/privacy incidents require bounded detection, recording, triage, remediation and notifications where applicable law requires them. Public disclosure timing and scope must reflect legal obligations and security risks; do not expose exploit details or private data merely to claim transparency.

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
| New PHIL-11–15 | Durable context, multilingual quality, economic clarity, failure recovery and incident response | Proposed additions |

## Proposed roadmap (not an execution plan or promise)
| Stage | Deliverable | Acceptance evidence | Gate |
| --- | --- | --- | --- |
| R0 — documentary alignment | FA/EN V4 draft, V3.1 mapping and architecture cross-check | Review against Constitution, Platform Contract and ADRs | Owner documentary approval |
| R1 — capability inventory | Matrix of implemented / experimental / proposed AI, Search, Notes, Documents, Marketplace and Workspace functions | Code-linked evidence and CI references | Product review |
| R2 — user experience (after R1 inventory review) | Separate Search vs AI Chat entry points, accessible FA/DE/EN navigation and clear capability labels | Usability and accessibility tests; no implementation planning based on unverified inventory | Independent implementation PRs |
| R3 — continuity and privacy | Explicit conversation/project retention, retrieval, export and deletion contracts | Threat model, tenant-isolation and lifecycle tests | ADR and privacy review |
| R4 — trustworthy AI workflows | Scoped sources, citation uncertainty, authorized tools and human approval | Evidence/provenance and abuse tests, financial ledger checks | Separate security/paid authorizations |
| R5 — interoperable apps | Reviewed typed capability contracts with owning-domain policy | Contract tests, negative authorization tests | ADR approval before execution |
| R6 — measurement | Cross-app task completion, user control, provenance inspectability, accessibility and operational reliability | Defined metrics with baselines, no invented KPIs | Separate KPI adoption |

## Review decisions and unresolved implementation policies
The principles above resolve the philosophical tensions between continuity/deletion, AI usefulness/evidence, paid AI/advertising, and Core identity/app ownership. They do **not** specify deletion cascade schemas, evidence status APIs, pricing models, advertising entitlement, incident reporting procedures or release criteria; these need separate domain policy/ADR and validation. R1 inventory and its review must precede R2 implementation decisions.

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
