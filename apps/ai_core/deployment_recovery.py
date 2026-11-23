"""Fail-closed classification for manual Render releases without GitHub proof.

A live Render SHA is not a substitute for the owner-run GitHub deployment
record. This module never grants permission, writes evidence, or contacts a
provider; it only explains which official recovery route is needed.
"""
from __future__ import annotations


def classify_release(*, follow_owner_deployments, live_sha, authorized_sha,
                     official_release_allowed, render_live_confirmed=False):
    """Classify a deployment without treating a manual deploy as authorization.

    `render_live_confirmed` is advisory only; it must not affect the grant.
    Callers must independently use the existing `release_allowed` gate.
    """
    if not live_sha or len(live_sha) != 40 or any(c not in "0123456789abcdef" for c in live_sha):
        return "invalid_runtime_sha"
    if follow_owner_deployments:
        if official_release_allowed is True:
            return "official_proof_verified"
        if render_live_confirmed:
            return "manual_live_without_official_proof"
        return "official_proof_missing"
    if authorized_sha != live_sha:
        return "authorized_sha_mismatch"
    return "legacy_sha_match_only"
