from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils.translation import override


@override_settings(ALLOWED_HOSTS=["testserver"])
class PlatformReportTests(SimpleTestCase):
    def test_localized_report_renders_three_documents(self):
        for lang in ("fa", "de", "en"):
            with self.subTest(lang=lang):
                response = self.client.get(f"/{lang}/platform-report/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="report"')
                self.assertContains(response, 'id="statement"')
                self.assertContains(response, 'id="annex"')
                self.assertContains(response, "PRODUCTION_SECURITY_VERIFIED = NO")
                self.assertContains(response, "SC_07 OPEN_CRITICAL")

    def test_report_has_noindex_and_no_external_dependencies(self):
        response = self.client.get("/fa/platform-report/")
        self.assertContains(response, 'name="robots" content="noindex,nofollow"')
        self.assertNotContains(response, "fonts.googleapis.com")
        self.assertNotContains(response, "<script src=")

    def test_report_route_is_named(self):
        with override("en"):
            self.assertEqual(reverse("platform_report"), "/en/platform-report/")

    def test_mobile_overflow_guardrails_present(self):
        """Static regression guard; browser-level overflow still requires visual QA."""
        response = self.client.get("/fa/platform-report/")
        self.assertContains(response, 'name="viewport" content="width=device-width, initial-scale=1"')
        self.assertContains(response, "@media(max-width:640px)")
        self.assertContains(response, "overflow-x:clip")
        self.assertContains(response, "grid-template-columns:minmax(0,1fr)")
        self.assertContains(response, ".head>div{min-width:0")
        self.assertContains(response, ".scroll{width:100%;max-width:100%;overflow-x:auto")
