from django.contrib.auth.decorators import login_required
from django.http import Http404
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


@login_required
def workspace_index(request):
    """Render installed apps as workspace entry points without granting authority."""
    return render(
        request,
        "platform_shell/workspace_index.html",
        {"apps": registry.all()},
    )


@login_required
def workspace_app(request, slug):
    """Render one app's workspace context without embedding or executing the app."""
    manifest = registry.get(slug)
    if manifest is None:
        raise Http404("App not found")

    try:
        app_url = reverse(manifest.url_name)
    except NoReverseMatch:
        app_url = None

    return render(
        request,
        "platform_shell/workspace_app.html",
        {
            "app": manifest,
            "app_url": app_url,
            "has_launchable_url": app_url is not None,
        },
    )
