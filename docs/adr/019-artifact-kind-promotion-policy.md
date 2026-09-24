# ADR-019: Artifact Kind Promotion Policy

## Status
Proposed

## Date
2026-09-17

## Context

VORNEQ's Core distinguishes between:
- canonical Artifact (cross-vertical reference), and
- vertical-specific domain models.

Observed at inspected baseline
`be1cbea66500e7b98a5413e1e33d03b4872806ff`:

Artifact.Kind includes four values:
- PRODUCT
- LIBRARY_ITEM
- DOCUMENT
- OTHER

This inventory requires re-verification against any future baseline
before being treated as current.

Registry mapping at the same baseline:
- `marketplace.Product` -> `Artifact.Kind.PRODUCT`
- `library.LibraryItem` -> `Artifact.Kind.LIBRARY_ITEM`
- registrations without an explicit target mapping -> `Artifact.Kind.OTHER`

ADR-001 establishes that Core primitives must generalize only when
responsibility is concrete and testable, and warns against premature
abstraction. ADR-004 establishes that Artifact retains only stable
cross-vertical properties and must not become a universal content table.
ADR-006 and ADR-007 reinforce this boundary for Article and Media.

The historical addition of DOCUMENT demonstrates that a vertical MAY be
promoted from OTHER to a dedicated Kind when its semantics justify it.
However, no explicit policy currently defines when such promotion is
justified.

## Decision

Artifact Kind promotion requires:

1. a demonstrated stable cross-domain semantic requirement;
2. a testable shared boundary at the Core level; and
3. evidence that the current fallback pattern (`Kind = OTHER` with
   vertical-specific metadata where applicable) is insufficient to
   satisfy cross-domain contracts.

Number of use cases is treated as evidence, not as a criterion.

### Anti-criteria (explicitly rejected)

Promotion is NOT justified by:
- vertical-specific semantics only;
- UI, navigation, or discovery convenience;
- a single use case without a stable boundary; or
- internal refactor preference.

### Permitted fallback pattern

Until promotion criteria are met, a vertical MAY register its canonical
Artifact using `Kind = OTHER` and retain vertical-specific classification
in metadata where required by that vertical's registration contract.

This is a permitted fallback pattern, NOT a universal metadata contract.
Core does not require a common metadata key for this purpose under this
ADR.

Fallback patterns observed at the inspected baseline include:
- Article artifacts registered as OTHER with content-specific metadata.
- Media artifacts registered as OTHER with media-specific metadata.
- Note artifacts registered as OTHER with notes-specific metadata.

Metadata contracts are NOT assumed identical across verticals.
Each vertical owns its own metadata contract.

### Reversibility

Artifact Kind promotion does not imply automatic reversibility.

Any schema or data migration associated with a promotion MUST be
evaluated under ADR-016 for:
- schema reversibility; and
- operational/data reversibility.

Demotion or reinterpretation of an established Kind requires an explicit
architectural decision and a migration plan where persisted data is
affected.

## Consequences

Positive:
- Promotion decisions become explicit and reviewable.
- Premature vocabulary growth is prevented.
- Vertical metadata contracts remain autonomous.

Negative:
- Adding a new Kind requires ADR-level justification.
- Cross-domain consumers must handle OTHER with vertical-specific
  metadata when a vertical is not promoted.

## Non-goals

- This ADR does not enumerate all future Kinds.
- This ADR does not mandate a metadata schema for OTHER.
- This ADR does not establish a general Kind deprecation procedure.
  Any schema or persisted-data migration required by a future
  deprecation remains subject to ADR-016.

## Follow-up

- Consider whether OTHER's metadata contracts require versioning in Core
  (open question).
- Consider whether a Kind registry service is needed beyond the current
  static mapping (deferred).
