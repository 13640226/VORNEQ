# ADR-0007: Provider registry foundation

Status: proposed; partial implementation.

The existing public retrieval gateway and V4-01 paid construction boundaries
remain authoritative. The catalog is metadata, not permission to call a provider.
Existing text ledger reservation, image worker reservation and mock voice policy
remain unchanged. No fallback, network calls, schema or environment changes.
Future capabilities are vocabulary only, not advertised as implemented.
New paid model activation requires separately verified pricing and policy.
Existing configured models remain governed by existing policy; migration to
model-level resolution is outstanding. Privacy, DPA and availability are not verified.
Rollback: revert the eventual merge commit after compatibility checks.

Follow-up: registered-model preflight checks provider/model enablement, capability, actor identifier, environment and trusted route policy. It is not wired to paid routes yet; existing approved-model paths remain authoritative. No new model is activated.
