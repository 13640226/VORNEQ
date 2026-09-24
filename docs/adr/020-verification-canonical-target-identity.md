# ADR-020: Verification Canonical Target Identity

## Status

Proposed

## Context

Verification V1 currently identifies supported targets through vertical
object coordinates represented by Django ContentType plus object_id.
The current supported vertical targets are Product and LibraryItem.

ADR-002 established this as a temporary generic bridge and deferred
Artifact Registry generalization until real integration patterns justified
reconsideration. Subsequent architecture has established the canonical
Artifact Registry as the shared cross-domain identity boundary for
artifacts, while vertical domain models retain their domain
responsibilities.

Canonical integration patterns now exist beyond the original Verification
V1 target pair. In particular, domain integrations demonstrate that
vertical objects can participate in cross-domain workflows through
Artifact and ArtifactBinding. ADR-006 also establishes that Article
Verification workflows may target the Article's canonical Artifact
binding.

These precedents justify selecting a durable Verification-wide target
identity direction. They do not establish that every current target is
already bound, that Verification should manufacture missing bindings, or
that the existing ContentType + object_id bridge can be removed
immediately.

Target identity must also remain distinct from target eligibility and
presentation. Canonical registration is not itself a Verification
eligibility decision, and the availability of display metadata or
navigation is not a prerequisite for a target to participate in
Verification.

This ADR therefore records the durable target-identity direction and the
constraints that any later compatibility migration must preserve. It does
not select the schema or mechanics of that migration.

## Decision

Canonical Artifact is the final durable target-identity direction for
Verification generally.

This is an architectural end-state direction. It does not establish
canonical-only Verification admission in the current system and does not
invalidate the existing ContentType + object_id target contract while an
explicit compatibility transition remains in effect.

The current Product and LibraryItem Verification behavior remains valid
during that transition. Absence of an ArtifactBinding must not, by itself,
silently turn an otherwise valid current-bridge target into an ineligible
target.

Verification must not create an Artifact or ArtifactBinding merely to
complete canonical target resolution.

A staged coexistence of vertical target coordinates and canonical Artifact
identity is permitted as a transition mechanism. Permanent dual
representation is not the selected end state.

When both representations are present, they must identify the same logical
Verification target. A conflict between them must fail closed.

Duplicate-active semantics apply to that one logical target. The presence
of vertical and canonical namespaces must not allow separate active
Verification requests merely because the same logical target can be
addressed through two representations.

Target identity does not determine target eligibility, and target identity
does not require a universal presentation or navigation contract.

## Decision Rules

1. Canonical Artifact is the selected final durable identity for a
   Verification target.

2. The existing ContentType + object_id representation remains a valid
   compatibility representation until an explicit migration and cutover
   decision changes that contract.

3. Canonicalization must not manufacture identity. Verification must not
   create Artifact or ArtifactBinding solely because a target presented to
   Verification has no existing canonical binding.

4. Missing ArtifactBinding does not, by itself, redefine current
   Verification business eligibility.

5. If a future path explicitly requires canonical resolution, that path
   must fail closed when the required binding cannot be resolved.

6. While an explicit compatibility path remains supported, a valid
   current-bridge target may continue to use its vertical coordinates
   without requiring Verification to create a canonical registration.

7. Transitional coexistence of vertical and canonical target
   representations is permitted. Permanent dual representation is not
   selected as the durable architecture.

8. When both representations are available, they must resolve to the same
   logical target. Representation disagreement must fail closed.

9. Duplicate-active protection is defined over one logical Verification
   target. Multiple addressing namespaces must not create multiple logical
   identities for duplicate-active purposes.

10. Canonical Artifact registration does not itself establish
    Verification eligibility.

11. Publication state does not itself establish Verification eligibility.

12. Presentation availability, including a title or navigable URL, does
    not itself establish Verification eligibility.

13. Artifact.Kind promotion is independent from this target-identity
    decision. A dedicated promoted Kind is not a prerequisite for this
    architecture.

14. Removal of the current bridge requires a separate, explicit migration
    and cutover decision governed by applicable migration and rollback
    policy.

## Compatibility and Transition Boundary

The existing ContentType + object_id target representation remains part of
the supported compatibility contract during an explicit transition.

This ADR permits, but does not prescribe, a staged period in which a
Verification target may have both its existing vertical coordinates and a
canonical Artifact identity.

Where both representations exist, consistency is mandatory: they must
identify the same logical target. A detected conflict must fail closed
rather than selecting one representation opportunistically.

Where a binding is absent, Verification must not implicitly register the
target in order to make the canonical representation available. During
the compatibility period, absence of a binding must not silently
invalidate Product or LibraryItem behavior that remains valid under the
current bridge contract.

A future path that explicitly requires canonical resolution has a
different boundary: if its required binding is absent, canonical
resolution fails closed. This does not retroactively redefine the
eligibility of compatibility paths that remain explicitly supported.

The transition must also preserve one-logical-target duplicate semantics.
The coexistence of two representations must not create a route around
duplicate-active protection.

This ADR does not determine the schema, write strategy, read strategy,
backfill mechanics, cutover sequence, or bridge-retirement procedure.
Those choices require separate implementation and migration decisions.

## Eligibility Boundary

Verification target identity and Verification target eligibility are
separate concerns.

Under the current contract, eligibility with respect to the target itself
remains type-only: the target must belong to a supported Verification V1
target type. This operates alongside the existing caller authorization,
VerificationMethod availability, duplicate protection, and model
validation.

Canonical Artifact registration is not an eligibility grant. Likewise,
publication, discovery, reputation, or presentation state does not
implicitly make a target eligible or ineligible for Verification.

This ADR introduces no new domain-state eligibility requirement.

If concrete target restrictions later emerge from domain semantics, those
semantics remain owned by the relevant domain and are orchestrated by
Verification when required. Such restrictions must be established
explicitly rather than inferred from canonical registration or unrelated
presentation/publication state.

No universal target-eligibility abstraction is introduced by this ADR.

## Presentation Boundary

Verification owns the shape of its Verification-facing activity and
public payload contracts. It does not thereby own the vertical-domain
meaning of a target's display title or navigation destination.

`artifact_title` and `artifact_url` remain nullable presentation values.

A canonical or otherwise eligible Verification target is not required to
provide a navigable URL merely in order to participate in Verification.

This ADR does not select Core, UnifiedSearch, domain `get_absolute_url`,
or a new Verification adapter layer as a universal presentation resolver.

Presentation resolution may therefore evolve independently from the
durable target-identity decision recorded here, provided that such
evolution does not silently redefine Verification eligibility or trust
state.

## Relationship to Existing ADRs

### ADR-002

ADR-002 remains the historical Verification V1 architectural decision. It
established Product and LibraryItem as the current V1 supported vertical
targets, used ContentType + object_id as a temporary generic bridge, and
deferred Artifact Registry generalization until real integration patterns
justified reconsideration.

This ADR records the later Verification-wide target-identity direction.
It does not rewrite ADR-002's historical V1 decision, nor does it declare
the existing bridge already removed.

### ADR-004

ADR-004 establishes the canonical Artifact Registry foundation and the
boundary between canonical registry identity and vertical-domain
responsibilities.

This ADR applies that architectural foundation specifically to the final
durable target-identity direction for Verification.

### ADR-005

ADR-005 provides an additive migration precedent in which canonical and
existing representations can temporarily coexist, explicit bindings are
required, representation disagreement fails closed, and migration must
not manufacture canonical registrations.

ADR-005 explicitly leaves Verification semantics outside its scope.
Accordingly, it is a migration precedent rather than the source of the
Verification target-identity decision recorded here.

### ADR-006

ADR-006 establishes a direct domain integration precedent in which Article
Verification may target the Article's canonical Artifact binding.

That `may` remains a domain-level permission and precedent. This ADR does
not reinterpret it as a historical Verification-wide requirement.
Instead, this ADR separately establishes the later Verification-wide
durable target-identity direction.

### ADR-016

ADR-016 governs migration and rollback policy. Any later implementation,
migration, compatibility transition, or bridge retirement arising from
this ADR remains subject to that governance.

This ADR selects the architectural destination and compatibility
constraints; it does not replace migration/rollback governance.

### ADR-019

ADR-019 defines the policy for promotion of Artifact.Kind vocabulary.

Artifact.Kind promotion is independent from the Verification target
identity selected here. Verification participation does not, by itself,
require creation or promotion of a dedicated Artifact.Kind.

## Consequences

Verification gains an explicit durable target-identity direction instead
of requiring that direction to be reconstructed from the temporary V1
bridge, general Artifact Registry architecture, and domain-specific
integration precedents.

Future Verification target integrations can distinguish three questions
that must not be collapsed into one another:

- what canonical identity represents the target;
- whether the target is eligible for a particular Verification workflow;
- how the target is presented or navigated in Verification-facing
  surfaces.

A future migration may temporarily need to reason about both existing
vertical coordinates and canonical Artifact identity. During such
coexistence, consistency and duplicate-active semantics must operate over
one logical target rather than treating the two representations as
independent identities.

The architecture deliberately accepts a compatibility period rather than
requiring incidental canonical registration. This preserves current
bridge behavior while preventing Verification from becoming an implicit
Artifact Registry provisioning mechanism.

The decision also leaves implementation mechanics open. A later migration
must determine how canonical identity is represented, resolved or
associated where valid canonical identity already exists, checked, and
eventually made sufficient for durable target storage without violating
the no-manufactured-identity and other architectural constraints
established here.

Bridge retirement is not an automatic consequence of this ADR. It
requires a separate explicit migration/cutover decision and must satisfy
the applicable migration and rollback governance.

## Non-Goals

This ADR does not:

- select a database schema, foreign key, field nullability, constraint,
  or index design;
- design or authorize a migration or backfill;
- select a dual-write, dual-read, canonical-read, or other transition
  implementation strategy;
- establish a cutover date or bridge-retirement procedure;
- remove, deprecate, or otherwise change the current
  ContentType + object_id bridge;
- expand `ALLOWED_ARTIFACT_MODELS`;
- add Product, LibraryItem, Article, MediaAsset, Document, or any other
  target to Verification eligibility;
- create new target-specific eligibility rules;
- introduce a universal Verification eligibility abstraction;
- select or promote a new Artifact.Kind;
- make Artifact.Kind promotion a prerequisite for Verification;
- require every vertical object to have an ArtifactBinding;
- authorize Verification to create Artifact or ArtifactBinding records
  for unbound targets;
- select a universal title, URL, navigation, or presentation resolver;
- require Verification targets to implement `get_absolute_url`;
- migrate public API identifiers from their existing semantics;
- change Verification claim semantics;
- change VerificationMethod semantics;
- change Evidence ownership or semantics;
- make Verification a statement of truth;
- make publication, discovery, reputation, registration, or presentation
  state an implicit Verification eligibility rule;
- define implementation, deployment, migration, or rollout timing.