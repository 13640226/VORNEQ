from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from library.models import LibraryItem
from marketplace.models import Product

from .public import get_public_evidence_projection, get_public_verification_summary
from .services.activity import get_verification_activity


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

    return JsonResponse(
        get_public_evidence_projection(
            artifact,
            artifact_type,
        )
    )


@require_GET
def verification_activity(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "error": "authentication_required",
                "message": "Authentication is required to view verification activity",
            },
            status=401,
        )

    return JsonResponse({"activity": get_verification_activity(request.user)})
