"""Access control for the Prometheus metrics endpoint."""

import secrets

from django.conf import settings
from django.http import Http404
from django_prometheus.exports import ExportToDjangoView


def metrics_view(request):
    """Expose Prometheus metrics only to an authorized machine client."""
    expected_token = getattr(settings, "VORNEQ_METRICS_TOKEN", None)
    if not expected_token:
        raise Http404

    # Tokens in the query string are never accepted, even alongside a valid
    # Authorization header. This keeps credentials out of URLs and access logs.
    if "token" in request.GET:
        raise Http404

    authorization = request.headers.get("Authorization", "")
    scheme, separator, supplied_token = authorization.partition(" ")
    if scheme != "Bearer" or not separator or not supplied_token:
        raise Http404

    if not secrets.compare_digest(supplied_token, expected_token):
        raise Http404

    return ExportToDjangoView(request)
