from django.urls import reverse

from library.models import LibraryItem
from marketplace.models import Product

from ..models import VerificationRequest, VerificationResult


def _artifact_projection(verification_request):
    """Return a narrow title/URL projection for supported Verification artifacts."""
    content_type = verification_request.artifact_content_type
    artifact = verification_request.artifact
    key = (content_type.app_label, content_type.model)

    if artifact is None:
        return None, None
    if key == ("marketplace", "product") and isinstance(artifact, Product):
        return artifact.title, artifact.get_absolute_url()
    if key == ("library", "libraryitem") and isinstance(artifact, LibraryItem):
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
