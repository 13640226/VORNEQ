from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from library.models import LibraryItem
from marketplace.models import Product

from .public import get_public_verification_summary


def _summary_response(artifact, artifact_type):
    return JsonResponse(
        {
            "artifact_type": artifact_type,
            "artifact_id": str(artifact.pk),
            "verification": get_public_verification_summary(artifact),
        }
    )


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
