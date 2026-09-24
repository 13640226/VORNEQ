# VORNEQ Platform Philosophy v2

## Core Mission

> VORNEQ does not decide what is true, trustworthy, or valuable. It provides interoperable primitives that make discovery, attribution, evidence, context, and capability inspectable.

VORNEQ is not a trust infrastructure that manufactures trust. It is a platform for making the grounds and context for trust inspectable.

## Five Foundational Principles

### 1. Discovery, not Feed

Users should be able to actively discover relevant content rather than merely wait for a linear feed.

Search, dynamic filters, and context-aware suggestions are primary discovery tools.

**Architectural boundary:** Search remains independent from Trust, Verification, and Reputation. No trust-based ranking is introduced into Search unless an independent ADR explicitly approves that decision.

### 2. Context, not Score

Reputation and trust are contextual. There is no universal score or single trust number.

Any presentation of reputation should make domain, method, role, and evaluation context visible enough for an informed user judgment.

**Architectural boundary:** `ContextualReputation` and `QualitySignal` are contextual primitives. They must not be interpreted or presented as a universal score.

### 3. Evidence, not Truth

The platform does not claim truth. It exposes evidence that users can inspect when making judgments.

Verification produces inspectable findings and evidence about an assertion; Verification is not itself the assertion and does not establish final truth. Audit records support accountability and traceability, but are not a source of truth.

**Architectural boundary:** `VerificationResult` and `Evidence` are evidence-oriented primitives. Platform language and behavior must not collapse them into a claim that something is definitively true.

### 4. Portable Identity, not App Identity

Identity does not belong to a single application. It should be able to operate across product experiences and, over time, become portable beyond them.

Today, canonical identity may be represented through platform-specific implementation details such as `UserIdentity` and Django `User`. Those details must not define the long-term conceptual boundary of Identity.

**Architectural boundary:** Identity is a platform primitive, not an app-local primitive. Decentralized identity technologies such as DID remain future architectural options rather than requirements imposed by this philosophy.

### 5. One Platform, Specialized Experiences

VORNEQ is one platform composed of specialized experiences such as Documents, Notes, Marketplace, and future modules.

Apps may be independently implemented, but they participate in a shared platform contract. Users should experience continuity of identity, navigation, capability, and context rather than a collection of unrelated applications.

**Architectural boundary:** Platform Registry and the Capability Bus provide infrastructure for discoverability and interoperability. Apps may expose and consume capabilities through shared contracts without requiring implementation coupling.

## Architectural Boundaries

| Principle | Boundary |
| --- | --- |
| Discovery, not Feed | Search remains independent from Trust, Verification, and Reputation unless an ADR explicitly changes that boundary. |
| Context, not Score | No universal trust score or platform-wide reputation number. |
| Evidence, not Truth | Verification is not truth; Audit is not a source of truth. |
| Portable Identity | Identity is not app-local and should not be conceptually constrained by a single application account model. |
| One Platform | Apps may be independently implemented but participate in shared platform contracts. |
| Capability Adoption | New shared capabilities are adopted only when justified by real cross-domain consumer demand. |

## Relationship to Existing Documentation

This document defines **why**: the platform's principles and long-term direction.

Architecture documentation such as `backend-architecture-v3.md` defines **what boundaries and structures exist**.

ADRs define **how and why specific technical decisions are made**.

Platform Philosophy therefore guides architecture and product direction without replacing architecture documentation or ADRs.

## Decision Discipline

This philosophy is intentionally normative but implementation-agnostic.

A principle in this document does not, by itself, authorize a backend coupling, ranking signal, identity protocol, or cross-app dependency. Material changes to architectural boundaries should continue to be documented through the appropriate architecture process and ADRs.

When product convenience conflicts with inspectability, contextual meaning, or clear architectural boundaries, the platform should prefer explicitness over hidden inference.

## Consequences for Product Direction

Product work should increasingly favor:

- active discovery over passive feed mechanics;
- visible context over opaque scores;
- inspectable evidence over truth-like labels;
- portable attribution over app-local identity assumptions; and
- shared platform contracts over isolated product silos.

These are directional constraints, not a requirement to rewrite existing systems immediately. Migration should be incremental and preserve established invariants unless an explicit architectural decision changes them.
