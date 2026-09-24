from django.urls import reverse

from library.models import LibraryItem
from marketplace.models import Product

from ..models import VerificationRequest, VerificationResult
from .target_identity import resolve_verification_request_target


def _artifact_projection(verification_request):
    """Return a narrow title/URL projection for supported Verification artifacts."""
    identity = resolve_verification_request_target(verification_request)
    artifact = identity.legacy_target

    if artifact is None:
        return None, None
    if isinstance(artifact, Product):
        return artifact.title, artifact.get_absolute_url()
    if isinstance(artifact, LibraryItem):
        return artifact.title, reverse("library:detail", kwargs={"slug": artifact.slug})
    return None, None


def get_verification_activity(user):
    """Return disclosure-safe completed verification activity for one verifier."""
    if user is None or not getattr(user, "pk", None):
        return []

    results = (
        VerificationResult.objects.filter(
            verifier=user,
            request__status=VerificationRequest.Status.COMPLETED,
        )
        .select_related("request__artifact_content_type", "request__method")
        .order_by("-created_at", "-id")
    )

    activity = []
    for result in results:
        artifact_title, artifact_url = _artifact_projection(result.request)
        activity.append(
            {
                "artifact_title": artifact_title,
                "artifact_url": artifact_url,
                "method": {
                    "code": result.request.method.code,
                    "name": result.request.method.name,
                },
                "outcome": result.outcome,
                "confidence": result.reported_confidence,
                "recorded_at": result.created_at,
            }
        )
    return activity
