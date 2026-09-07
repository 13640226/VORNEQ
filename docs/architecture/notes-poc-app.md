# Notes PoC App

Notes is the first small domain application built on the VORNEQ Platform Shell. Its purpose is to exercise the deploy-time app contract end to end without introducing a new authorization framework.

## Platform integration

The app registers one `AppManifest` in `apps/notes/vorneq_app.py`:

- slug: `notes`
- landing route: `notes:list`
- localized route prefix: `notes/`
- authenticated presentation flag: enabled
- descriptive capability: `notes.crud`

The canonical PlatformRegistry remains the source of truth. The Notes manifest is therefore discoverable by the App Launcher and Workspace Shell without hard-coded shell navigation or routes.

## Domain and Core integration

`Note` owns its domain-specific title and content. Each Note has a one-to-one reference to a canonical Core `Artifact` with `kind=other`; Artifact metadata only identifies the vertical and does not duplicate note content.

Authentication is not treated as identity. Note services resolve the authenticated user through the existing `UserIdentity` binding and fail closed when that binding is missing or inactive. Ownership is represented explicitly with `ArtifactIdentityRole(role=owner)` and is the authorization boundary used by the PoC service layer.

The app does **not** infer an Identity from usernames, display names, or note text.

## Entitlement boundary

The current Core `Entitlement` model remains marketplace/product-oriented: it requires a Product and does not model generic `read`/`write` permissions. Notes therefore does not create synthetic Product rows, fake permission strings, or treat Entitlement as a universal authorization primitive.

A future generic resource-access contract would require a separately reviewed domain model or ADR. Until then, Notes authorization is deliberately ownership-scoped through `ArtifactIdentityRole`.

## Audit boundary

The current canonical audit recorder has strict schemas for the implemented verification event slice. Notes does not emit invented `note.created`, `note.updated`, or `note.deleted` events. Expanding the canonical audit taxonomy should happen in a separately bounded change before Notes events are recorded.

## Safety properties

- all views require authentication;
- an explicit active `UserIdentity` binding is required;
- reads and mutations are owner-scoped in the service layer;
- delete is POST-only and performs a soft deactivation of both Note and Artifact;
- forms use Django CSRF protection and validated form fields;
- the Platform Shell capability declaration remains discovery metadata, not permission;
- no iframe, executable provider, cross-app shared state, or remote runtime code is introduced.

## Pattern for future apps

Future apps should copy the boundaries rather than the domain details: keep content in the vertical model, use canonical Core identifiers explicitly, resolve identity through typed bindings, keep authorization in the domain service layer, register through `vorneq_app.py`, and never turn manifest visibility or capabilities into authority.
