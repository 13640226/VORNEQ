from django.utils.translation import gettext_lazy as _

from apps.platform_shell.registry import AppManifest, registry


registry.register(
    AppManifest(
        slug="marketplace",
        label=_("Marketplace"),
        url_name="marketplace:index",
        order=30,
        active_namespaces=("marketplace",),
    )
)
