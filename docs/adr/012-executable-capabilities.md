# ADR 012: Executable Capabilities (v2)

**Status:** Proposed  
**Date:** 2026-09-07

## Context

ADR 011 introduced Capability Bus v1 as descriptive discovery over `AppManifest.capabilities`. Those identifiers are declaration tokens only: they do not register callable providers, grant permissions, authorize cross-app access, or define a generic request/response mechanism.

VORNEQ now needs a deliberately narrow executable contract that can validate the boundaries before broader integrations are attempted. The contract must preserve domain ownership and must not turn Platform Shell into a central authorization or business-logic service.

## Decision

Adopt Capability Bus v2 as a small, synchronous invocation layer for deploy-time reviewed executable capabilities.

Capability Bus v2 is the architecture generation. Individual capabilities carry their own contract version in the identifier; for example, `read_artifact_v1` is version 1 of that capability, not Capability Bus v1.

### Responsibilities

| Layer | Responsibility |
| :--- | :--- |
| Platform Registry | Canonical app and descriptive capability declarations. |
| Executable capability registry | Deploy-time mapping from a declared identifier to one provider. It is not a second declaration authority. |
| Capability Invoker | Resolve provider, validate typed input/output, pass explicit context, isolate failures, and return a bounded result envelope. |
| Owning domain | Authorization/eligibility policy, business logic, and typed output production. |
| Platform Shell | Supplies invocation context without interpreting domain policy. |

An executable provider cannot be registered unless the capability identifier is already declared in an `AppManifest.capabilities` tuple in the canonical Platform Registry.

## Executable Contract

Every executable capability must:

- use a versioned identifier such as `read_artifact_v1`;
- define typed and bounded input/output schemas;
- receive `CapabilityContext` explicitly rather than reading actor/request state from hidden globals;
- keep authorization or eligibility decisions inside the owning domain;
- return to callers through a standard `CapabilityResult` envelope;
- allow controlled internal `CapabilityExecutionError` exceptions to be converted at the invoker boundary;
- remain read-only and synchronous for this v2 PoC.

The current implementation uses Python `dataclass` schemas because Pydantic is not an existing project dependency. This ADR does not require one schema library permanently; future contract revisions may adopt another typed-schema mechanism explicitly.

## Failure Contract

Callers receive `CapabilityResult[T]` containing either typed `data` or a `CapabilityFailure` with a bounded code/message/details payload. Raw provider exceptions do not cross the invoker boundary.

Initial failure codes include:

- `unknown_capability`
- `invalid_input`
- `invalid_output`
- `invalid_contract`
- `not_authorized`
- `execution_failed`

Provider failures are isolated: a failing provider does not mutate registry state and its raw exception detail is not exposed to the caller.

## PoC: `read_artifact_v1`

The first executable provider is owned by Core and reads the stable public fields of one canonical `Artifact`: id, kind, metadata, and active status.

For this PoC only, `Artifact.is_active == True` is used as a narrow eligibility rule. This is **not** a publication contract, a generic authorization rule, or evidence that an Artifact is publicly readable. Registration of an Artifact itself also does not imply publication or trustworthiness. A future real access policy must be defined by the owning domain before this capability is expanded.

The provider performs no writes, creates no audit event, grants no entitlement, and has no external-system dependency.

The descriptive declaration is exposed through the existing Discover manifest so executable registration remains subordinate to the canonical Platform Registry. Domain logic still resides in Core; the manifest declaration does not transfer authorization ownership to Platform Shell.

## v2 Guardrails

- **Read-only:** no writes, mutations, side effects, or state transitions.
- **Synchronous only:** no jobs, queues, retries, or background execution.
- **Capability != Permission:** declaration or registration grants no data access.
- **No generic permission service:** the bus does not interpret Entitlement or invent a platform-wide permission model.
- **No arbitrary runtime loading:** providers are deploy-time reviewed Python code.
- **No external integration framework:** the PoC reads only existing platform data.
- **No migration or dependency expansion:** this PoC changes no database schema and adds no third-party package.

## Consequences

### Positive

- Establishes a typed, versioned invocation boundary without replacing Capability Discovery v1.
- Preserves one canonical declaration source.
- Keeps business logic and policy in the owning domain.
- Makes malformed input/output and provider failure observable through bounded results.
- Provides a small testable contract before Email or other integration-heavy apps are attempted.

### Costs / Risks

- Dataclass runtime validation is intentionally small and supports only the current bounded PoC needs.
- Synchronous execution limits long-running providers.
- The `is_active` PoC rule must not accidentally become a permanent access policy.
- Future executable capabilities may require an explicit contract revision for richer schemas, audit semantics, async execution, or external integrations.

## Rejected Alternatives

- **Parallel capability declaration registry:** rejected because `AppManifest.capabilities` is already canonical.
- **Generic permission system in Platform Shell:** rejected because capability declaration is not authority.
- **Entitlement as universal authorization:** rejected because Entitlement is transitional and domain-specific.
- **Raw JSON without typed schemas:** rejected because it weakens validation and compatibility guarantees.
- **Pydantic dependency for the PoC:** rejected because it is not currently required by the project.
- **Background execution in v2:** rejected as unnecessary complexity for the first executable contract.

## Related Documents

- [ADR 011: App Launcher, Capability Bus, and Workspace Shell](011-app-launcher-capability-bus-workspace-shell.md)
- [`docs/developer-guide.md`](../developer-guide.md)
- [`docs/architecture/platform-app-contract.md`](../architecture/platform-app-contract.md)

## Follow-up

1. Keep this ADR Proposed while `read_artifact_v1` validates the contract in CI and review.
2. Evaluate whether the executable registry/invoker boundaries remain sufficient after the PoC.
3. Document executable-capability authoring guidance only after the contract has survived implementation review.
4. Consider additional read-only capabilities before any side-effecting or asynchronous contract is designed.
