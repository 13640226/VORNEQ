# User Experience Layers & Personalization Boundaries

**Status:** Proposed  
**Version:** v0.1  
**Related:** Platform Contract v0.1 (for reference, not modification)

---

## 1. Purpose

This document defines the layered structure of user experience in VORNEQ, separating public discovery from personalized workspaces. It establishes boundaries for user and workspace preferences, ensuring that personalization is transparent, portable, and under the user’s control.

**This is not a modification of Platform Contract v0.1.** The primitives described here are **Proposed**; they will be considered for inclusion in a future Platform Contract v0.2 after validation in the Knowledge/Documents Workspace design.

---

## 2. The Three Experience Layers

VORNEQ organizes user interaction into three distinct layers:

| Layer | Purpose | Content | Access |
| :--- | :--- | :--- | :--- |
| **Public Experience** | Introduction & Discovery | Homepage, public Artifact/Profile pages, public search | Public (unauthenticated) |
| **Personal Home** | Personal status & activity | Recent activity, recommendations, notifications, quick access to Workspace and followed items | Authenticated users |
| **Workspace** | Deep work environment | Documents, Notes, Collections, collaboration tools, and specialized apps | Authenticated users |

> **Key Principle:** The public Homepage must not become a personal dashboard. The sense of “this is my space” should only emerge after authentication, within the Personal Home and Workspace layers.

---

## 3. Preferences & Personalization Boundaries

To maintain clarity and prevent over-coupling, preferences are separated into two distinct domains.

### 3.1. UserPreferences (Presentation & General)

- **Scope:** Personalization settings that are independent of a specific workspace.
- **Examples:** Theme, language, notification settings, display preferences.
- **Storage:** Bound to the user, portable across devices.

### 3.2. WorkspacePreferences (Workspace Layout & Configuration)

- **Scope:** Settings specific to a particular Workspace, such as widget layout and configuration.
- **Features:** Includes a `schema_version` field to allow controlled evolution of the layout structure.
- **Storage:** Bound to the user and a **stable Workspace identity** (for example, a Workspace ID or UUID), not a mutable slug.

```python
# Example Models (Proposed)

class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    theme = models.CharField(max_length=20, default="vorneq")
    language = models.CharField(max_length=10, default="en")
    notification_settings = models.JSONField(default=dict)


class WorkspacePreferences(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)  # Stable identity
    layout = models.JSONField()
    schema_version = models.PositiveSmallIntegerField(default=1)
```

The examples above are illustrative and do not establish database schema as a stable platform contract.

---

## 4. Personal Home: The Deterministic Dashboard

The Personal Home layer provides a personalized entry point without relying on machine learning in its initial version.

### Core Components (v1)

- Recent Artifacts
- Recent Notes
- Followed Items
- Pending Invitations
- Recently Viewed Items

### Future Enhancements

Ranking and recommendations may be introduced as independent capabilities once sufficient data, feedback, and transparency requirements are available.

---

## 5. Core Principles: Portability & Transparency

### 5.1. Control, Not Belonging

The user does not “belong” to the platform; the space is under the user’s control. This is expressed through:

- **Portable Preferences:** Settings are synchronized across devices.
- **Data Transparency:** Users can see what data is stored and why.
- **Notification Control:** Granular settings for notification categories.
- **Export Capability:** VORNEQ should support export of user-controlled data; exact format and scope are defined separately and are not contracted here.
- **Algorithmic Transparency:** Recommendations and search experiences should support appropriate explanations where applicable.

### 5.2. Privacy & Data Ownership

- VORNEQ does not infer verified Identity from free-text fields.
- Reputation is contextual and must not become a universal global score.
- Sensitive operations should be auditable through the platform audit architecture.

---

## 6. Relation to Platform Contract

The primitives defined here — `UserPreferences`, `WorkspacePreferences`, and `Personal Home` — are currently **Proposed**.

They will be validated during the design and implementation of the Knowledge/Documents Workspace. If they prove stable, reusable, and appropriately bounded, they may be considered for promotion in a future Platform Contract v0.2.

Platform Contract v0.1 remains unchanged by this document.

---

## 7. Next Steps

1. Validate this model in the Knowledge/Documents Workspace design.
2. Validate personalization and ownership boundaries against the User Control Principles and compliance baseline.
3. Implement the first Personal Home iteration using deterministic components when product sequencing permits.
4. Consider stable primitives for Platform Contract v0.2 only after validation.

---

**Refs:** Platform Contract v0.1, ADR 011 (`docs/adr/011-app-launcher-capability-bus-workspace-shell.md`), #139
