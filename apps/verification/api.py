from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from library.models import LibraryItem
from marketplace.models import Product

from .models import VerificationEvidence, VerificationRequest
from .public import get_public_verification_summary


_PUBLIC_ARTIFACT_TYPES = {
    "product": (
        Product,
        {
            "status": Product.STATUS_APPROVED,
            "is_published": True,
        },
    ),
    "libraryitem": (
        LibraryItem,
        {
            "is_published": True,
        },
    ),
}


def _summary_response(artifact, artifact_type):
    return JsonResponse(
        {
            "artifact_type": artifact_type,
            "artifact_id": str(artifact.pk),
            "verification": get_public_verification_summary(artifact),
        }
    )


def _public_artifact(artifact_type, artifact_id):
    model_config = _PUBLIC_ARTIFACT_TYPES.get(artifact_type)
    if model_config is None:
        return None

    model, public_filters = model_config
    try:
        return model.objects.filter(pk=artifact_id, **public_filters).first()
    except (TypeError, ValueError):
        return None


@require_GET
def product_verification_summary(request, pk):
    product = get_object_or_404(
        Product,
        pk=pk,
        status=Product.STATUS_APPROVED,
        is_published=True,
    )
    return _summary_response(product, "product")


@require_GET
def library_verification_summary(request, pk):
    item = get_object_or_404(
        LibraryItem,
        pk=pk,
        is_published=True,
    )
    return _summary_response(item, "library_item")


@require_GET
def public_evidence_projection(request):
    artifact_id = request.GET.get("artifact_id")
    artifact_type = request.GET.get("artifact_type")

    if not artifact_id or not artifact_type:
        return JsonResponse(
            {
                "error": "invalid_request",
                "message": "artifact_id and artifact_type are required",
            },
            status=400,
        )

    if artifact_type not in _PUBLIC_ARTIFACT_TYPES:
        return JsonResponse(
            {
                "error": "invalid_artifact_type",
                "message": "artifact_type must be 'product' or 'libraryitem'",
            },
            status=400,
        )

    artifact = _public_artifact(artifact_type, artifact_id)
    if artifact is None:
        return JsonResponse(
            {
                "error": "artifact_not_found",
                "message": "Artifact does not exist or is not publicly available",
            },
            status=404,
        )

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

    return JsonResponse(
        {
            "artifact_id": str(artifact.pk),
            "artifact_type": artifact_type,
            "claims": list(claims.values()),
            "total_public_evidence_count": total_public_evidence_count,
        }
    )
