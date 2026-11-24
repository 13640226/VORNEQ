from django.test import SimpleTestCase, Client
from django.conf import settings


class LanguageSwitcherTests(SimpleTestCase):
    def test_all_language_pairs_with_different_cookie(self):
        for source in ("fa", "de", "en"):
            for target in ("fa", "de", "en"):
                if source == target:
                    continue
                with self.subTest(source=source, target=target):
                    client = Client()
                    client.cookies[settings.LANGUAGE_COOKIE_NAME] = target
                    response = client.post("/i18n/setlang/", {"language": target, "next": f"/{source}/discover/?q=test"})
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.url, f"/{target}/discover/?q=test")
                    self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, target)

    def test_external_redirect_rejected(self):
        response = self.client.post("/i18n/setlang/", {"language": "en", "next": "https://evil.example/fa/"})
        self.assertEqual(response.url, "/")

    def test_csrf_required(self):
        response = Client(enforce_csrf_checks=True).post("/i18n/setlang/", {"language": "en", "next": "/fa/"})
        self.assertEqual(response.status_code, 403)
