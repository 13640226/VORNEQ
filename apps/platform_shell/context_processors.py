from .registry import registry


def platform_shell(request):
    """Expose installable app navigation to every template."""
    return {
        "platform_apps": registry.all(),
        "platform_navigation": registry.navigation(request),
    }
