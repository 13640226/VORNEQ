"""Entry and canonical page views for Inspect Context V1."""

from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from apps.core.models import Artifact, ArtifactBinding
from apps.core.services.context import get_context_view, resolve_artifact_from_input


def inspect_entry(request):
    """Resolve user input to an existing public artifact without creating data."""
    inspect_input = ""
    inspect_error = ""

    if request.method == "POST":
        inspect_input = request.POST.get("input", "").strip()[:2000]
        artifact = resolve_artifact_from_input(inspect_input)
        if artifact is not None:
            return redirect("context_view", artifact_id=artifact.id)
        inspect_error = _("No inspectable artifact found yet.")

    return render(
        request,
        "inspect_form.html",
        {
            "inspect_input": inspect_input,
            "inspect_error": inspect_error,
        },
    )


def context_view(request, artifact_id):
    """Render one disclosure-safe, read-only canonical artifact context page."""
    try:
        context = get_context_view(
            artifact_id,
            language=get_language() or "en",
        )
    except (Artifact.DoesNotExist, ArtifactBinding.DoesNotExist, LookupError):
        raise Http404("Inspectable artifact not found.")

    return render(request, "context.html", context)
