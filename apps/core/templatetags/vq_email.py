"""Template tags for VORNEQ transactional e-mails (central design V3)."""
import re

from django import template
from django.conf import settings
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from apps.core.email_strings import EMAIL_STRINGS, FALLBACK_LANGUAGE, SUPPORTED_LANGUAGES

register = template.Library()

LOGO_PATH = "/static/email/vorneq-logo.png"
RTL_LANGUAGES = {"fa"}
_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?(:\d{1,5})?$")


class _Blank(dict):
    def __missing__(self, key):
        return ""


def email_language(code=None):
    raw = code if code is not None else (get_language() or "")
    base = raw.replace("_", "-").split("-")[0].lower()
    return base if base in SUPPORTED_LANGUAGES else FALLBACK_LANGUAGE


def _origin(context):
    site = context.get("current_site")
    domain = getattr(site, "domain", "") or getattr(settings, "VORNEQ_PUBLIC_DOMAIN", "") or ""
    return "https://" + domain if domain and _HOST_RE.match(domain) else ""


@register.simple_tag
def vq_lang():
    return email_language()


@register.simple_tag
def vq_dir():
    return "rtl" if email_language() in RTL_LANGUAGES else "ltr"


@register.simple_tag
def vq_align():
    return "right" if email_language() in RTL_LANGUAGES else "left"


@register.simple_tag
def vq_font():
    if email_language() in RTL_LANGUAGES:
        return "Tahoma,Arial,sans-serif"
    return "-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"


@register.simple_tag(takes_context=True)
def vq_logo_url(context):
    return _origin(context) + LOGO_PATH


@register.simple_tag(takes_context=True)
def vq_site_url(context):
    return (_origin(context) or "") + "/"


@register.simple_tag(takes_context=True)
def vq_mail(context, key, **values):
    try:
        text = EMAIL_STRINGS[key][email_language()]
    except KeyError:
        raise template.TemplateSyntaxError("Unknown e-mail string: %s" % key) from None
    if context.autoescape:
        rendered = _Blank({k: format_html("<bdi>{}</bdi>", v) for k, v in values.items()})
        return mark_safe(str(conditional_escape(text)).format_map(rendered))
    return text.format_map(_Blank({k: str(v) for k, v in values.items()}))