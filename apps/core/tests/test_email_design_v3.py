"""Email design V3: design, translation, security and regression tests."""
import re
from pathlib import Path

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.html import escape

from apps.core.email_strings import EMAIL_STRINGS, SUPPORTED_LANGUAGES

LANGS = ("fa", "de", "en")
URL = "https://vorneq.example/accounts/x/abc123/?next=%2F&x=1"
SITE = Site(domain="vorneq.example", name="VORNEQ")
CONTEXTS = {
    "email_confirmation": {"activate_url": URL},
    "email_confirmation_signup": {"activate_url": URL},
    "password_reset_key": {"password_reset_url": URL},
    "account_already_exists": {"password_reset_url": URL, "signup_url": URL, "email": "user@example.org"},
    "unknown_account": {"signup_url": URL, "email": "user@example.org"},
}
TITLE_KEY = {
    "email_confirmation": "confirm.title",
    "email_confirmation_signup": "signup.title",
    "password_reset_key": "reset.title",
    "account_already_exists": "exists.title",
    "unknown_account": "unknown.title",
}
SUBJECT_KEY = dict(TITLE_KEY, email_confirmation_signup="confirm.title")
ROOT = Path(settings.BASE_DIR)
TEMPLATE_FILES = [
    *sorted((ROOT / "templates" / "email").glob("*")),
    *sorted((ROOT / "templates" / "account" / "email").glob("*")),
]


def render(name, lang, ext, **extra):
    ctx = dict(CONTEXTS[name], current_site=SITE, **extra)
    with translation.override(lang):
        return render_to_string(f"account/email/{name}_message.{ext}", ctx)


def subject(name, lang, **extra):
    ctx = dict(CONTEXTS[name], current_site=SITE, **extra)
    with translation.override(lang):
        return render_to_string(f"account/email/{name}_subject.txt", ctx)


class DesignTests(SimpleTestCase):
    def test_html_structure_brand_and_responsiveness(self):
        for name in CONTEXTS:
            for lang in LANGS:
                with self.subTest(name=name, lang=lang):
                    html = render(name, lang, "html")
                    self.assertIn(f'<html lang="{lang}" dir="{"rtl" if lang == "fa" else "ltr"}"', html)
                    self.assertIn('name="viewport"', html)
                    self.assertIn("@media only screen and (max-width:620px)", html)
                    self.assertIn('role="presentation"', html)
                    self.assertIn("#2563EB", html)
                    self.assertIn("#0B1120", html)
                    self.assertIn("<!--[if mso]>", html)
                    self.assertRegex(html, r'<img src="https://vorneq\.example/static/email/vorneq-logo\.png" width="185" height="33" alt="VORNEQ"')
                    self.assertIn(escape(EMAIL_STRINGS[TITLE_KEY[name]][lang]), html)
                    self.assertIn('href="' + URL.replace("&", "&amp;") + '"', html)
                    self.assertIn("<title>", html)

    def test_plain_text_is_complete_and_unescaped(self):
        for name in CONTEXTS:
            for lang in LANGS:
                with self.subTest(name=name, lang=lang):
                    text = render(name, lang, "txt")
                    self.assertIn(URL, text)
                    self.assertIn(EMAIL_STRINGS[TITLE_KEY[name]][lang], text)
                    self.assertTrue(text.startswith("VORNEQ"))
                    self.assertNotRegex(text, r"<[a-zA-Z/][^>]*>")
                    self.assertNotIn("&amp;", text)
                    self.assertNotIn("&#x27;", text)

    def test_subjects_are_single_line_plain_text(self):
        for name in CONTEXTS:
            for lang in LANGS:
                with self.subTest(name=name, lang=lang):
                    line = " ".join(subject(name, lang).splitlines()).strip()
                    self.assertEqual(line, EMAIL_STRINGS[SUBJECT_KEY[name]][lang])
                    self.assertNotIn("&#", line)

    def test_no_active_or_remote_content(self):
        for name in CONTEXTS:
            html = render(name, "en", "html")
            for bad in ("<script", "<link", "@import", "url(http", "javascript:", "<iframe", "<form"):
                self.assertNotIn(bad, html)

    def test_logo_asset_is_png_with_expected_size(self):
        from PIL import Image

        path = ROOT / "static" / "email" / "vorneq-logo.png"
        self.assertTrue(path.exists())
        self.assertLess(path.stat().st_size, 60_000)
        with Image.open(path) as img:
            self.assertEqual(img.size, (1480, 260))
            self.assertEqual(img.mode, "RGBA")


class TranslationTests(SimpleTestCase):
    def test_every_key_has_all_languages(self):
        for key, entry in EMAIL_STRINGS.items():
            self.assertEqual(set(entry), set(SUPPORTED_LANGUAGES), key)
            for lang, text in entry.items():
                self.assertTrue(text.strip(), (key, lang))
                self.assertNotRegex(text, "[\u00c3\u00c2\ufffd]", (key, lang))

    def test_placeholders_match_across_languages(self):
        for key, entry in EMAIL_STRINGS.items():
            sets = {lang: set(re.findall(r"{(\w+)}", text)) for lang, text in entry.items()}
            self.assertEqual(len({frozenset(s) for s in sets.values()}), 1, key)

    def test_persian_is_persian_and_german_has_umlauts(self):
        for key, entry in EMAIL_STRINGS.items():
            self.assertRegex(entry["fa"], "[\u0600-\u06ff]", key)
        self.assertIn("\u00fc", EMAIL_STRINGS["reset.title"]["de"])
        self.assertIn("\u200c", EMAIL_STRINGS["reset.ignore"]["fa"])

    def test_template_keys_are_defined_and_used(self):
        used = set()
        for path in TEMPLATE_FILES:
            used |= set(re.findall(r'vq_mail "([a-z.]+)"', path.read_text(encoding="utf-8")))
        self.assertLessEqual(used, set(EMAIL_STRINGS))
        self.assertEqual(set(EMAIL_STRINGS) - used, set())

    def test_unsupported_language_falls_back_to_english(self):
        for code in ("es", "en-gb", "fr"):
            html = render("password_reset_key", code, "html")
            self.assertIn("Reset your password", html)
            self.assertIn('lang="en"', html)

    def test_rtl_only_for_persian(self):
        self.assertIn('dir="rtl"', render("password_reset_key", "fa", "html"))
        self.assertNotIn('dir="rtl"', render("password_reset_key", "de", "html"))


class SecurityTests(SimpleTestCase):
    def test_user_supplied_email_is_escaped_in_html(self):
        evil = "<script>alert(1)</script>@example.org"
        for name in ("account_already_exists", "unknown_account"):
            for lang in LANGS:
                html = render(name, lang, "html", email=evil)
                self.assertNotIn("<script>alert(1)", html)
                self.assertIn("&lt;script&gt;", html)

    def test_subject_never_contains_context_values(self):
        for name in CONTEXTS:
            line = subject(name, "en", email="a@example.org\nBcc: evil@example.org")
            self.assertNotIn("evil", line)
            self.assertEqual(len(line.strip().splitlines()), 1)

    def test_html_templates_do_not_disable_escaping(self):
        for path in TEMPLATE_FILES:
            if path.suffix != ".html":
                continue
            src = path.read_text(encoding="utf-8")
            for bad in ("|safe", "autoescape off", "mark_safe", "<script", "javascript:"):
                self.assertNotIn(bad, src, path.name)

    def test_no_insecure_http_links_in_templates(self):
        for path in TEMPLATE_FILES:
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"http://", path.name)

    def test_logo_url_rejects_malicious_site_domain(self):
        class Evil:
            domain = 'evil.example"><script>alert(1)</script>'

        out = Template("{% load vq_email %}{% vq_logo_url %}").render(Context({"current_site": Evil()}))
        self.assertEqual(out, "/static/email/vorneq-logo.png")

    def test_unknown_string_key_raises(self):
        from django.template import TemplateSyntaxError

        with self.assertRaises(TemplateSyntaxError):
            Template('{% load vq_email %}{% vq_mail "nope.nope" %}').render(Context({}))


class AllauthRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    @staticmethod
    def reset_url(lang):
        # The site uses i18n_patterns: the URL language prefix selects the e-mail language.
        with translation.override(lang):
            return reverse("account_reset_password")

    def test_adapter_sends_multipart_with_subject_prefix(self):
        for lang in LANGS:
            mail.outbox.clear()
            with translation.override(lang):
                get_adapter().send_mail("account/email/password_reset_key", "user@example.org", {"password_reset_url": URL})
            self.assertEqual(len(mail.outbox), 1)
            msg = mail.outbox[0]
            self.assertTrue(msg.subject.startswith("[VORNEQ] "), msg.subject)
            self.assertIn(EMAIL_STRINGS["reset.title"][lang], msg.subject)
            self.assertNotIn("\n", msg.subject)
            self.assertIn(URL, msg.body)
            html, mimetype = msg.alternatives[0]
            self.assertEqual(mimetype, "text/html")
            self.assertIn(f'lang="{lang}"', html)

    def test_password_reset_flow_uses_request_language(self):
        user = get_user_model().objects.create_user("flowuser", "flow@example.org", "S3cure-pass-phrase!")
        EmailAddress.objects.create(user=user, email="flow@example.org", primary=True, verified=True)
        for lang in LANGS:
            cache.clear()
            mail.outbox.clear()
            self.client.post(self.reset_url(lang), {"email": "flow@example.org"})
            self.assertEqual(len(mail.outbox), 1, lang)
            html = mail.outbox[0].alternatives[0][0]
            self.assertIn(f'lang="{lang}"', html)
            self.assertIn(escape(EMAIL_STRINGS["reset.title"][lang]), html)

    def test_unknown_account_mail_under_enumeration_protection(self):
        for lang in LANGS:
            cache.clear()
            mail.outbox.clear()
            self.client.post(self.reset_url(lang), {"email": "nobody@example.org"})
            self.assertEqual(len(mail.outbox), 1, lang)
            html = mail.outbox[0].alternatives[0][0]
            self.assertIn(escape(EMAIL_STRINGS["unknown.title"][lang]), html)