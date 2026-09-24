"""HTTP surface for the disclosure-safe Public Graph V1."""

from django.http import JsonResponse

from apps.core.services.public_graph import PublicGraphUnavailable, get_public_graph


def public_graph_view(request, artifact_id):
    """Return one bounded Artifact-rooted public graph projection."""
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed."}, status=405)

    try:
        payload = get_public_graph(artifact_id)
    except PublicGraphUnavailable:
        return JsonResponse({"detail": "Not found."}, status=404)

    return JsonResponse(payload)
