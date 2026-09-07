from django.utils.translation import gettext_lazy as _

from apps.platform_shell.registry import AppManifest, registry


registry.register(
    AppManifest(
        slug="documents",
        label=_("Documents"),
        url_name="documents:list",
        order=30,
        show_in_primary_nav=False,
        requires_authentication=True,
        capabilities=("documents.crud",),
    )
)
