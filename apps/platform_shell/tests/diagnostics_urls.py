"""Test-only URLconf: mounts the diagnostic view unconditionally so the view's
own fail-closed gate can be exercised independently of URL registration."""

from django.urls import path

from apps.platform_shell.diagnostics import actor_binding_diagnostic

urlpatterns = [
    path(
        "internal/diagnostics/actor-binding/",
        actor_binding_diagnostic,
        name="actor_binding_diagnostic",
    ),
]
