from django.conf import settings
from django.utils.translation import override
from django.views.i18n import set_language as django_set_language
from django.views.decorators.csrf import csrf_protect
from urllib.parse import urlsplit


@csrf_protect
def set_language(request):
    # The unlocalized endpoint may have a different active locale than next.
    # Resolve the source URL under its own locale before Django reverses it.
    target = request.POST.get("next", "")
    try:
        source = urlsplit(target).path.split("/")[1]
    except (ValueError, IndexError):
        source = ""
    if request.method == "POST" and source in dict(settings.LANGUAGES):
        with override(source):
            return django_set_language(request)
    return django_set_language(request)
