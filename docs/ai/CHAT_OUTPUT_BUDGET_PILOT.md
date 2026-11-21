# Chat output budget pilot (Phase 2, part 2)

Scope: default-off, model-bound Stage 2 research responses, development and
eligible Staging only. Production, operational flags, migrations and image
policies are unchanged. This is **EVIDENCE-CAPPED**, not an unrestricted
general-purpose chat engine. No paid request is authorized by this document.

## Limits and financial safety

- Optional VORNEQ_AI_CHAT_BUDGET_MODEL (exact provider model match),
  VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET (1536..8192),
  VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS (8192..1000000).
- Require context >= output + 4096; with a 4096 output budget, 8191 is
  rejected and 8192 is accepted. Real payload fit is independently checked.
- Model capacities and prices are owner-supplied and must be verified against
  provider documentation before any separately authorized runtime pilot.
- Invalid/missing configuration retains the existing limits. Staging also
  requires its approved model, Ledger configuration and Recovery.
- The exact serialized payload and effective instructions are counted in
  UTF-8 bytes as a conservative token upper bound, plus the existing ledger
  framing allowance and output budget. No claim of exact model tokenization.
- Context rejection (HTTP 413) occurs before the shared monetary reservation
  and provider call. The earlier request guard and abuse throttle remain.
- The ledger reserves against the actual configured output token limit.
  Incomplete provider output is never shown as successful. Known Usage
  settles at observed cost; unavailable Usage stays UNCERTAIN, with the full
  reservation retained. SDK parsing may fail before Usage is available:
  reject partial JSON and do not retry. The SDK still uses max_retries=0.
- The existing 6-section count, 200-character evidence-gap cap, 80-character
  heading cap, 4 passage refs per section and 5 source cap remain. Pilot
  answer bound = min(6400, 2 * output_tokens); actual aggregate bound also
  depends on 400 + 250 * distinct passages (up to 24). Individual answers
  are at most 1400 chars and additionally bounded by their local refs.
  No raw truncation. A passage link is not factual verification.
- Normal conversation context/history limits, Direct Phase B bounds, and
  persisting separate structured blocks are not expanded in this change.
  General-purpose long responses require a separate architecture PR.

## Safe rich UI (pilot only)

A deliberately restricted subset: headings, paragraphs, bold, inline/fenced
code, lists and tables. Text nodes only, no generated HTML or links. Max 12
columns, 100 table body rows and 256 rich lines; excessively complex content
falls back to literal text, not truncation. Unclosed fences remain literal.
Persian prose normalization protects code spans and URLs; sources, exact
quotes, source IDs and digests are never run through prose normalization.

Real Chromium/Edge DOM tests:
apps/ai_core/tests/browser/chat_markdown.html and chat_markdown.js.
Open the HTML file locally in an isolated browser; it loads the actual chat
JavaScript, replaces fetch with synthetic responses, and uses a CSP with
connect-src none. Check body data-result=PASS and PASS_COUNT=22. Test includes
script/HTML/event-handler/SVG/javascript URL payloads, table limits,
unclosed fences, mixed RTL/LTR, exact code, and the section rendering path.
No browser dependency was added. Syntax check alone is insufficient.
Optional OpenAI SDK mock tests are run where the optional dependencies are
installed; the core CI dependency lock does not install them.

## Architecture decision (document only, separate PR)

GENERAL AI ENGINE: conversation, long-form answers, coding, translation,
creative tasks, mathematics, data analysis, conversation memory, file
understanding; no mandatory Wikipedia retrieval. Explicitly communicate
uncertainty and do not invent source verification.

RESEARCH AI ENGINE: multiple web retrieval providers, evidence-backed
answers, source validation, citations, deep research. Passage-count bounds
apply here, not to General AI. Both use shared authorization, privacy,
security, Ledger, Recovery, Model Registry and server-side memory.
Plan and implement as a separate PR, not by weakening current evidence
validation or bypassing the financial/operational controls.

## Separate security follow-up

GitHub reported 14 Dependabot alerts (4 High, 10 Moderate) on default
branch during the earlier c83da501 push. Review current alerts individually
in a separate dependency/security PR; no dependency changes in #678.
Security Audit success does not prove all vulnerabilities are absent.

No operational migration, paid requests, deployment, merge or runtime
authorization is permitted here. Only new-SHA CI evidence counts.
