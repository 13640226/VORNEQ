"""HTTP surfaces for the disclosure-safe Public Graph V1."""

from django.http import Http404, JsonResponse
from django.shortcuts import render

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


def public_graph_presentation_view(request, artifact_id):
    """Render the established bounded Public Graph V1 for human inspection."""
    if request.method != "GET":
        raise Http404

    try:
        graph = get_public_graph(artifact_id)
    except PublicGraphUnavailable as exc:
        raise Http404 from exc

    return render(
        request,
        "public_graph.html",
        {
            "artifact_id": artifact_id,
            "graph": graph,
        },
    )
