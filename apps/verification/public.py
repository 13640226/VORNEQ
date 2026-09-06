from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count

from .models import VerificationEvidence, VerificationRequest, VerificationResult


def get_public_verification_summary(artifact):
    """
    Return a disclosure-safe public summary for one artifact.

    This is descriptive only. It is not an aggregate trust score and does not
    expose verifier identities, private evidence, or raw Evidence content.
    """
    content_type = ContentType.objects.get_for_model(
        artifact,
        for_concrete_model=False,
    )

    results = VerificationResult.objects.filter(
        request__artifact_content_type=content_type,
        request__artifact_object_id=str(artifact.pk),
        request__status=VerificationRequest.Status.COMPLETED,
    ).select_related("request__method")

    outcome_counts = {
        choice: 0
        for choice, _label in VerificationResult.Outcome.choices
    }
    for row in results.values("outcome").annotate(total=Count("id")):
        outcome_counts[row["outcome"]] = row["total"]

    aggregates = results.aggregate(
        total=Count("id"),
        average_reported_confidence=Avg("reported_confidence"),
    )

    public_evidence_count = VerificationEvidence.objects.filter(
        result__in=results,
        visibility=VerificationEvidence.Visibility.PUBLIC,
    ).count()

    verification_methods = list(
        results.order_by("request__method__name")
        .values_list("request__method__name", flat=True)
        .distinct()
    )
    last_result = results.order_by("-created_at", "-id").first()

    average = aggregates["average_reported_confidence"]

    return {
        "total_verifications": aggregates["total"],
        "outcomes": outcome_counts,
        "average_reported_confidence": round(average, 1) if average is not None else None,
        "public_evidence_count": public_evidence_count,
        "verification_methods": verification_methods,
        "last_verified_at": last_result.created_at if last_result else None,
    }
