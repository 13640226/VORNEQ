# VORNEQ Audit Taxonomy

**Status:** Normative logging requirements reference  
**Version:** 1.0  
**Date:** 2026-09-07

## Purpose

This document defines the vocabulary, minimum event envelope, privacy rules, and implementation requirements for security-relevant audit events in VORNEQ.

It intentionally does not implement a logging model, middleware, migration, transport, or SIEM integration. Those belong in subsequent engineering PRs.

Auditability supports accountability and incident reconstruction. It is not a substitute for authorization, verification, truth assessment, or evidence retention.

## Principles

1. **Record consequential actions, not everything.** Audit logs should be useful for accountability and investigation without becoming a shadow copy of application data.
2. **Minimize sensitive data.** Store identifiers, classifications, outcomes, and controlled metadata rather than raw protected content.
3. **Separate audit from application diagnostics.** Debug logs may explain software behavior; audit events establish attributable security-relevant actions.
4. **Make events stable and machine-readable.** Event names are versionable contracts and should not be casually renamed.
5. **Correlate without over-collecting.** Requests and related operations should be traceable using correlation identifiers without embedding credentials or raw evidence.
6. **Failure events matter.** Denied and failed consequential operations can be as important as successful ones.

## Event Naming Convention

Canonical event names use lowercase dot-separated namespaces:

`<domain>.<object-or-capability>.<action-or-outcome>`

Examples:

- `identity.authentication.succeeded`
- `identity.authentication.failed`
- `identity.session.revoked`
- `identity.privilege.changed`
- `verification.request.created`
- `verification.result.recorded`
- `verification.result.revoked`
- `verification.result.contested`
- `evidence.reference.attached`
- `evidence.access.denied`
- `entitlement.access.granted`
- `entitlement.access.denied`
- `entitlement.policy.changed`
- `data.object.accessed`
- `data.object.changed`
- `marketplace.object.changed`
- `admin.operation.executed`
- `security.configuration.changed`

Event names describe what happened. They should not encode secrets, object IDs, usernames, or other variable data into the event name itself.

## Required Event Envelope

Every persisted audit event must support the following logical fields. Exact database representation is an implementation decision.

| Field | Requirement |
| --- | --- |
| `event_id` | Globally or operationally unique event identifier. |
| `occurred_at` | Timestamp representing when the event occurred. |
| `actor` | Stable actor reference or actor class; may represent a user, administrator, service, anonymous client, or system process. |
| `action` | Canonical event name from this taxonomy. |
| `target` | Controlled reference to the affected resource/capability when applicable. |
| `outcome` | Normalized result such as `succeeded`, `failed`, `granted`, `denied`, or another bounded domain value. |
| `request_id` / `correlation_id` | Identifier linking related request/operation activity where available. |
| `context` | Structured, allow-listed metadata required to interpret the event safely. |

Implementations may add fields such as schema version, source component, actor type, target type, reason code, or policy identifier when justified. Additions must respect minimization rules.

## Actor Representation

The `actor` field must distinguish identity from authority. A user ID proves only which principal initiated an operation; it does not imply the user had legitimate authority.

Where appropriate, record:

- actor type/class;
- stable internal identifier or privacy-preserving reference;
- effective privilege/role context needed to reconstruct a consequential action;
- system/service identity for automated actions.

Do not store authentication secrets as actor context.

## Target Representation

Targets should be references, not copies of the target object. Prefer a controlled tuple or equivalent representation containing a resource type and stable identifier.

Audit logs must not duplicate full articles, evidence payloads, uploaded documents, authentication data, marketplace descriptions, or other business objects merely to make the log self-contained.

## Context Rules

`context` is allow-list driven. It may include bounded information such as:

- reason or policy code;
- previous/new state labels for a consequential state transition;
- verification scope identifier;
- request method or route class when operationally necessary;
- source component;
- coarse client/security metadata where justified and privacy-reviewed.

Free-form arbitrary object serialization into audit context is prohibited.

## Prohibited Audit Content

The following must not be recorded in raw form in audit logs:

- passwords or password-equivalent material;
- session cookies;
- authentication, API, OAuth, recovery, reset, or bearer tokens;
- private keys, signing secrets, encryption keys, or environment secrets;
- raw verification evidence or full evidence documents;
- full request/response bodies by default;
- payment credentials or similarly regulated secret material;
- unnecessary personal data merely because it is available to the application.

Sensitive identifiers that are operationally necessary should be minimized, transformed, truncated, or access-controlled according to the implementation threat model.

## Core Event Families

### Identity & Authentication

Required candidates include:

- `identity.authentication.succeeded`
- `identity.authentication.failed`
- `identity.session.revoked`
- `identity.recovery.requested`
- `identity.recovery.completed`
- `identity.privilege.changed`
- `identity.security_factor.changed` when stronger factors are implemented

Repeated failed authentication events must be designed so that audit logging itself cannot become an unbounded denial-of-service vector.

### Verification & Evidence

Required candidates include:

- `verification.request.created`
- `verification.request.changed`
- `verification.result.recorded`
- `verification.result.revoked`
- `verification.result.contested`
- `verification.dispute.changed`
- `evidence.reference.attached`
- `evidence.reference.detached`
- `evidence.access.denied`

The event records process facts and attribution. A `verification.result.recorded` event means a result was recorded; it does not assert that the underlying claim is objectively true.

### Entitlement & Authorization

Required candidates include:

- `entitlement.access.granted`
- `entitlement.access.denied`
- `entitlement.policy.changed`
- `entitlement.grant.changed`

High-volume successful access events may require a risk-based recording policy. Denials, administrative changes, and access to high-sensitivity resources generally have greater audit value.

### Data Access & Mutation

Use controlled events such as:

- `data.object.accessed`
- `data.object.changed`
- `data.object.deleted`
- `data.export.created`

For `data.object.accessed`, context should distinguish bounded access modes such as `read` or `write` when needed. Do not create a full audit event for every ordinary public-page read unless the threat model and operational need justify it.

### Search & Discovery

Search telemetry and audit logging are different concerns. Ordinary public search queries should not automatically become permanent audit records.

Audit candidates include security-relevant events such as:

- access denied to a protected discovery capability;
- administrative changes to search eligibility/configuration;
- security control changes affecting discovery visibility.

Query analytics, performance profiling, and product telemetry require their own privacy and retention decisions.

### Marketplace & Transaction

Audit candidates include consequential state changes such as:

- marketplace object approval/publication changes;
- seller or ownership-related administrative changes;
- transaction/fulfillment state transitions when such capabilities exist;
- denied privileged marketplace operations.

Discovery position is not a trust assertion and should not be logged or interpreted as one.

### Admin & Operations

Required candidates include:

- `admin.operation.executed`
- `security.configuration.changed`
- privileged role/permission changes;
- destructive or bulk administrative operations;
- security-sensitive deployment/operational changes when attributable application audit is the appropriate layer.

Infrastructure systems may maintain separate provider/CI audit trails; application audit events should correlate with them where useful rather than duplicate entire logs.

## Outcome and Reason Codes

Outcomes must use bounded values rather than arbitrary prose. Where explanation is required, use a stable reason code plus narrowly controlled context.

Examples:

- `succeeded`
- `failed`
- `granted`
- `denied`
- `created`
- `changed`
- `revoked`

Do not place exception dumps, SQL, secrets, or arbitrary user input into an audit reason field.

## Retention and Privacy

No universal retention duration is established by this document. Retention must be defined by event family and sensitivity after considering:

- security and incident-response usefulness;
- dispute/accountability requirements;
- data sensitivity;
- legal, contractual, and jurisdictional obligations;
- deletion/minimization requirements;
- storage and operational risk.

Retention should be no longer than justified. A future retention matrix should classify event families and define deletion/archival behavior explicitly.

Access to audit data must itself be authorized and, for sensitive administrative access, auditable.

## Integrity and Availability Requirements

An audit implementation should make unauthorized alteration or deletion detectable or appropriately restricted. The required mechanism depends on risk and infrastructure; this document does not mandate an append-only database, immutable storage, or a specific cryptographic scheme.

Audit failure behavior must be designed deliberately. For some high-impact operations, inability to record a required audit event may justify failing closed; for other operations, availability may require controlled degradation and alerting. This must be decided per event/operation rather than globally.

## Logging Requirements for Future Implementations

A future implementation PR should:

1. map concrete application operations to this taxonomy;
2. define a versioned event schema and bounded context fields;
3. identify which events are mandatory, sampled, aggregated, or intentionally omitted;
4. define retention classes before production accumulation begins;
5. enforce secret/evidence redaction with tests;
6. establish authorization for audit access;
7. provide correlation with existing request/observability identifiers;
8. test success, failure, denial, and privileged-change paths;
9. measure write amplification and latency impact;
10. define failure behavior and operational monitoring.

## Implementation Roadmap — Non-Normative

Possible future engineering sequence:

- event schema and domain mapping;
- persistence/transport decision;
- model/migration or external sink integration;
- explicit service-layer emission for consequential domain events;
- narrowly scoped request/auth integration where appropriate;
- retention jobs/policies;
- privileged audit viewer/access controls;
- operational alerts and incident-response integration.

Middleware must not be assumed to be sufficient: many meaningful domain events require explicit emission at the service/domain operation where their semantics are known.

## Change Control

Adding a new event is generally backward-compatible if its semantics and privacy treatment are documented. Renaming or changing the meaning of an established event should be treated as a schema-contract change and versioned accordingly.

Changes that materially increase collected personal/sensitive data, retention, or access scope require explicit privacy/security review before implementation.
