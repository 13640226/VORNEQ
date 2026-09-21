from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.core.services.registry import resolve_artifact


class CanonicalTargetConflict(ValidationError):
    """Raised when explicit canonical and legacy target identities disagree."""


@dataclass(frozen=True)
class VerificationTargetIdentity:
    legacy_target: object
    canonical_artifact: object | None


def resolve_verification_target(*, legacy_target, expected_canonical_artifact=None):
    """Resolve an existing canonical binding without manufacturing registry identity.

    Unbound legacy targets remain valid compatibility targets. When a caller
    explicitly supplies a canonical Artifact and an existing binding disagrees,
    resolution fails closed.
    """
    canonical_artifact = resolve_artifact(legacy_target)

    if (
        expected_canonical_artifact is not None
        and canonical_artifact is not None
        and canonical_artifact.pk != expected_canonical_artifact.pk
    ):
        raise CanonicalTargetConflict(
            "Explicit canonical Artifact conflicts with the legacy target binding."
        )

    if expected_canonical_artifact is not None and canonical_artifact is None:
        raise CanonicalTargetConflict(
            "Explicit canonical Artifact cannot be verified for an unbound legacy target."
        )

    return VerificationTargetIdentity(
        legacy_target=legacy_target,
        canonical_artifact=canonical_artifact,
    )


def resolve_verification_request_target(verification_request):
    """Resolve and validate a persisted VerificationRequest target read-only."""
    legacy_target = verification_request.artifact
    persisted_canonical = verification_request.canonical_artifact
    bound_canonical = resolve_artifact(legacy_target)

    if persisted_canonical is not None:
        if bound_canonical is None:
            raise CanonicalTargetConflict(
                "Persisted canonical Artifact has no matching legacy target binding."
            )
        if bound_canonical.pk != persisted_canonical.pk:
            raise CanonicalTargetConflict(
                "Persisted canonical Artifact conflicts with the legacy target binding."
            )

    return VerificationTargetIdentity(
        legacy_target=legacy_target,
        canonical_artifact=persisted_canonical or bound_canonical,
    )
