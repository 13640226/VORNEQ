from django.utils.translation import gettext_lazy as _

from .registry import AppManifest, registry


registry.register(
    AppManifest(
        slug="discover",
        label=_("Discover"),
        url_name="home",
        order=10,
        capabilities=("read_artifact_v1",),
    )
)
