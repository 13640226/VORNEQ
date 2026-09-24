from django.utils.translation import gettext_lazy as _

from apps.platform_shell.registry import AppManifest, registry


registry.register(
    AppManifest(
        slug="notes",
        label=_("Notes"),
        url_name="notes:list",
        order=20,
        show_in_primary_nav=True,
        requires_authentication=True,
        active_namespaces=("notes",),
        urlconf="apps.notes.urls",
        route_prefix="notes/",
        capabilities=("notes.crud",),
    )
)
