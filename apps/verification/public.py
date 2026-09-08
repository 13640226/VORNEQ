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


def get_public_evidence_projection(artifact, artifact_type):
    """
    Return disclosure-safe public Evidence links for one already-resolved artifact.

    The projection is intentionally narrow: Claim text, Evidence content,
    Evidence metadata, relation_basis, and verifier identity are not exposed.
    Only completed Verification requests and explicitly public links are included.
    """
    content_type = ContentType.objects.get_for_model(
        artifact,
        for_concrete_model=False,
    )
    evidence_links = (
        VerificationEvidence.objects.filter(
            result__request__artifact_content_type=content_type,
            result__request__artifact_object_id=str(artifact.pk),
            result__request__status=VerificationRequest.Status.COMPLETED,
            visibility=VerificationEvidence.Visibility.PUBLIC,
        )
        .select_related("evidence_relation")
        .order_by("evidence_relation__claim_id", "created_at", "id")
    )

    claims = {}
    total_public_evidence_count = 0

    for link in evidence_links:
        relation = link.evidence_relation
        claim_id = str(relation.claim_id)
        claim_projection = claims.setdefault(
            claim_id,
            {
                "claim_id": claim_id,
                "evidences": [],
            },
        )
        claim_projection["evidences"].append(
            {
                "evidence_id": str(relation.evidence_id),
                "relation": relation.relation,
                "linked_at": link.created_at,
            }
        )
        total_public_evidence_count += 1

    return {
        "artifact_id": str(artifact.pk),
        "artifact_type": artifact_type,
        "claims": list(claims.values()),
        "total_public_evidence_count": total_public_evidence_count,
    }
