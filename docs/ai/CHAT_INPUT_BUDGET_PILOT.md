# Chat input budget pilot (Phase 2, part 1)

Baseline: c09c1ab597bd2d4b9ff6d316279a0d6acdadb6be.

This documents Phase 2 part 1. Part 2 is described separately in
[CHAT_OUTPUT_BUDGET_PILOT.md](CHAT_OUTPUT_BUDGET_PILOT.md). Neither part
authorizes runtime activation, streaming, memory or production images.
No environment setting is changed by the patches.

## Before / after

| Path | Legacy/default | Opt-in development or eligible Staging |
|---|---|---|
| Global chat question | 200 characters | UTF-8 byte upper bound, 512?8192 |
| Global and message JSON body | 2048 bytes | 6 ? configured bound + 512 bytes |
| Conversation metadata API | 2048 bytes | Unchanged |
| Public retrieval | 200 characters | Unchanged; whole-question screening before bounded keyword selection |
| Phase A/B direct APIs | Legacy | Unchanged |
| Production | Legacy | No pilot, even with the new setting |
| Responses / provider output tokens / history limits | Existing | Unchanged |

The optional setting VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET is a conservative
BPE-token upper-bound proxy using UTF-8 byte count, NOT exact tokenization.
Missing, out-of-range, or malformed values retain legacy behavior.
Staging additionally requires shared ledger configuration and enabled
request recovery. The normal request guard, quota, authorization, provider
and citation policies still apply. The existing ledger reserves against the
actual serialized provider payload including instructions and output cap.

The browser derives the question cap from the server template, counts bytes
during the pilot and refuses an over-bound submission instead of silently
slicing the question. The search query remains bounded; long multi-topic
retrieval and evidence coverage still require additional evaluation.

## Remaining Phase 2 requirements (not complete)

- Model-specific context-window accounting, configurable output token budget,
  response schemas and evidence-backed length rules.
- Clean explicit output-cap status without accepting unsafe incomplete JSON.
- Secure Markdown/table/code rendering, FA/DE/EN regression evaluation.
- Context length and persistence across reloads.
- Production remains unchanged and requires separate authorization.

No operational migrations, deployments, paid calls, or ledger data changes.
