from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from .registry import registry


def _launcher_app(manifest):
    try:
        launch_url = reverse(manifest.url_name)
    except NoReverseMatch:
        launch_url = None

    return {
        "slug": manifest.slug,
        "label": manifest.label,
        "capability_count": len(manifest.capabilities),
        "launch_url": launch_url,
    }


@login_required
def app_launcher(request):
    """Render the installed-app launcher from the canonical platform registry."""
    return render(
        request,
        "platform_shell/launcher.html",
        {"apps": [_launcher_app(manifest) for manifest in registry.all()]},
    )
