# VORNEQ Threat Model

**Status:** Normative security reference  
**Version:** 1.0  
**Date:** 2026-09-07

## Purpose

This document defines the security threat model for VORNEQ. It is organized around VORNEQ assets and trust boundaries. STRIDE is used as an analysis tool inside each boundary; it is not the architecture of the document.

This document defines threats and high-level control requirements. It does not implement audit middleware, database models, migrations, authentication factors, or authorization changes.

## Security and Trust Principles

### Verification is not truth

`Verification ≠ Truth` is a product and trust principle, not a security control. VORNEQ protects the integrity, provenance, attribution, authorization, presentation, and contestability of verification processes and records. A technically intact verification record must never be presented as proof of absolute truth.

### Search is not verification

Discovery retrieves eligible records. Search ordering, presence, absence, or prominence must not be interpreted as a verification result, entitlement decision, universal reputation judgment, or trust score.

### Reputation is contextual

Security controls must not transform contextual evidence about prior behavior into an authoritative universal trust score. Legacy aggregate fields, where retained for compatibility, do not change this rule.

### Least privilege and explicit authority

Access must be constrained by the minimum authority required for an operation. Authentication establishes an actor; it does not by itself establish authorization, entitlement, verification authority, or ownership.

### Consequential actions must be attributable

Security-sensitive state transitions should be attributable to an actor or system principal and correlated with the request or operation that produced them. Attribution must not require logging secrets or unnecessary personal data.

## Assets

Protected assets include:

- identity and authentication state;
- sessions, credentials, recovery mechanisms, and privileged roles;
- verification requests, results, provenance, evidence references, signatures, and integrity envelopes;
- entitlement and authorization decisions;
- published and unpublished content and media;
- marketplace objects and transaction-related state;
- discovery/search eligibility and ordering semantics;
- dispute and contestation records;
- audit records and security telemetry;
- application configuration, secrets, databases, object storage, backups, deployment systems, and administrative interfaces.

## Threat Analysis Method

For each VORNEQ trust boundary, threats are considered using STRIDE:

- **Spoofing:** impersonating an actor or system principal;
- **Tampering:** unauthorized modification of data, state, provenance, or presentation;
- **Repudiation:** making consequential actions difficult to attribute or reconstruct;
- **Information Disclosure:** exposing information beyond intended visibility;
- **Denial of Service:** exhausting or denying a capability;
- **Elevation of Privilege:** obtaining authority beyond the actor's permitted scope.

Risk treatment is evidence-driven. Controls should be proportional to impact, likelihood, exposure, and the sensitivity of the protected asset.

## 1. Identity & Authentication Boundary

### Threats

- credential stuffing, password spraying, brute force, and account enumeration;
- session theft, fixation, replay, or misuse of recovery flows;
- spoofing a user, administrator, service, or verification actor;
- privilege escalation through role or permission mistakes;
- unauthorized modification of identity attributes;
- insufficient attribution for authentication and account-security changes.

### Required control direction

- rate limiting and abuse controls for authentication paths;
- secure session and cookie configuration;
- explicit authorization independent of successful authentication;
- privileged-action protection and stronger authentication where risk justifies it;
- auditable authentication, recovery, role, and privilege changes without recording credentials or tokens;
- generic failure responses where needed to reduce account enumeration.

**Follow-up implication:** 2FA/MFA requirements should be selected from this threat model and actor risk, not added as an isolated feature.

## 2. Verification & Evidence Boundary

### Threats

- forged or substituted evidence;
- tampering with verification requests, results, provenance, timestamps, signatures, or integrity envelopes;
- presenting a verification result outside its scope, time, subject, or authority;
- unauthorized access to sensitive evidence;
- replay of stale or revoked verification artifacts;
- spoofed verifier or authority attribution;
- deletion or mutation that destroys the ability to reconstruct a consequential decision;
- denial of dispute or contestation capability.

### Required control direction

- explicit provenance and actor attribution;
- integrity protection for signed or consequential records;
- authorization checks on evidence visibility and mutation;
- scope, subject, authority, and time context retained with verification results;
- lifecycle handling for superseded, revoked, disputed, or contested results;
- auditability of consequential state changes;
- data minimization: audit references and metadata instead of copying raw evidence into logs.

Security protects the verification process. It does not turn that process into an oracle of truth.

## 3. Entitlement Boundary

### Threats

- bypassing entitlement checks through alternate endpoints or object identifiers;
- confused-deputy behavior where a service exercises broader authority than the initiating actor;
- stale grants or revocations;
- horizontal or vertical privilege escalation;
- leaking entitlement state that itself reveals sensitive relationships;
- inconsistent policy evaluation between UI, API, and background operations.

### Required control direction

- server-side authorization at the protected operation;
- deny-by-default for sensitive capabilities;
- explicit actor, target, action, and policy context;
- auditable grant/deny and administrative policy changes where appropriate;
- tests for direct-object access and alternate-route bypasses;
- bounded caching with safe invalidation where entitlement decisions are cached.

## 4. Search & Discovery Boundary

### Threats

- exposing unpublished, inactive, unauthorized, or otherwise ineligible records;
- inference of protected information through search presence, counts, metadata, timing, or filters;
- injection or malformed input reaching query construction;
- resource exhaustion from expensive queries, extreme pagination, or abusive request rates;
- accidental introduction of implicit trust, verification, or reputation ranking;
- semantic drift that changes historical retrieval ordering without an explicit API decision.

### Required control direction

- eligibility and visibility filtering before serialization;
- parameter normalization and bounded inputs;
- database/query budgets and performance monitoring;
- explicit separation of retrieval ordering from trust or recommendation semantics;
- backward-compatible ordering unless a deliberate API contract change is approved;
- no composite trust score embedded into discovery results;
- sensitive verification/evidence details remain behind their own authorization and product boundaries.

The current chronological retrieval contract must not be described as a trust ranking.

## 5. Marketplace & Transaction Boundary

### Threats

- unauthorized listing or transaction state changes;
- price, ownership, seller, or fulfillment-state tampering;
- spoofed seller/buyer actions;
- race conditions or replay of consequential operations;
- disclosure of private commercial or account data;
- conflating discovery prominence with seller trustworthiness.

### Required control direction

- authoritative server-side validation of consequential state transitions;
- authorization bound to actor and target;
- idempotency or replay protection where operations require it;
- auditable high-impact changes;
- explicit separation between marketplace discovery and verification/reputation context.

## 6. Admin & Operations Boundary

### Threats

- compromised administrator account;
- excessive standing privilege;
- unsafe bulk actions or irreversible administrative changes;
- secret exposure through dashboards, logs, support tooling, or CI output;
- repudiation of privileged changes;
- misuse of impersonation or support capabilities if introduced.

### Required control direction

- least privilege and separation of duties where practical;
- stronger authentication for privileged actors based on risk;
- auditable privileged operations;
- confirmation or staged workflows for destructive/high-impact operations;
- no secrets in logs or routine administrative output;
- documented emergency-access and recovery procedures before such mechanisms are relied upon.

## 7. Infrastructure Boundary

### Threats

- compromise of application secrets, CI/CD credentials, database credentials, or object-storage credentials;
- dependency or supply-chain compromise;
- unauthorized deployment or configuration drift;
- database, backup, or object-storage disclosure;
- destructive database or migration operations;
- denial of service at application, database, cache, or storage layers;
- loss of forensic/audit data during an incident.

### Required control direction

- secrets supplied through approved secret-management/environment mechanisms and never committed;
- dependency/security scanning and controlled deployment workflows;
- migration preflight and recovery procedures for consequential schema changes;
- encrypted transport and provider-appropriate storage protections;
- backup/restore rehearsal and documented recovery expectations;
- observability sufficient to distinguish application, database, and infrastructure failure modes;
- access to production infrastructure limited and attributable.

## Cross-Boundary Threats

Some threats span multiple boundaries and must not be solved locally only:

- authorization inconsistencies between UI, API, tasks, and administrative paths;
- correlation of individually low-sensitivity metadata into sensitive information;
- compromised privileged identities affecting verification, entitlement, and operations simultaneously;
- denial-of-service amplification through search/database behavior;
- audit-log tampering or deletion that weakens accountability;
- presentation-layer changes that misrepresent verification scope or contextual reputation.

## Priority Security Requirements

The following are priorities for follow-up engineering and policy work:

1. define and implement the audit events required by `audit-taxonomy.md`;
2. perform authorization-hardening review across protected object operations;
3. derive MFA/2FA requirements for privileged and risk-sensitive actors;
4. define retention and deletion schedules based on event/data sensitivity and applicable obligations;
5. test verification/evidence authorization, integrity, replay, revocation, dispute, and provenance paths;
6. maintain security regression coverage for discovery eligibility and direct-object access;
7. preserve recovery, backup, deployment, and observability controls as production architecture evolves.

## Out of Scope for This Document

This document does not prescribe a specific SIEM vendor, logging backend, MFA vendor, encryption package, retention duration, legal conclusion, or incident-response platform. Those choices require separate implementation decisions, evidence, and where applicable legal/compliance review.

## Review Triggers

Review this threat model when VORNEQ introduces a new trust boundary, authentication mechanism, privileged actor class, verification authority model, payment/transaction capability, public API surface, mobile/native client, significant storage architecture change, or materially different data sensitivity profile.
