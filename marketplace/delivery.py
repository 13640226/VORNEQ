from pathlib import PurePosixPath

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from apps.core.services import has_valid_entitlement

from .models import Product


@login_required
def download_product(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id,
        status=Product.STATUS_APPROVED,
        is_published=True,
    )

    if not product.digital_file:
        raise Http404("File not found.")

    if not has_valid_entitlement(request.user, product):
        raise Http404("File not found.")

    storage = product.digital_file.storage
    name = product.digital_file.name

    try:
        if not storage.exists(name):
            raise Http404("File not found.")
        file_handle = storage.open(name, "rb")
    except OSError as exc:
        raise Http404("File not found.") from exc

    filename = PurePosixPath(name).name
    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
    )
