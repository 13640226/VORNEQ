from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse
from django.utils import translation


@override_settings(ALLOWED_HOSTS=["testserver"])
class MarketplacePrimaryNavigationTests(SimpleTestCase):
    def test_library_index_redirects_to_marketplace_in_active_language(self):
        for language in ("en", "de", "fa"):
            with self.subTest(language=language), translation.override(language):
                library_url = reverse("legacy_library_index")
                marketplace_url = reverse("marketplace:index")
                response = self.client.get(library_url)

                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.url, marketplace_url)

    def test_home_primary_navigation_exposes_marketplace_not_library(self):
        with translation.override("en"):
            response = self.client.get(reverse("home"))
            content = response.content.decode()

            self.assertContains(response, f'href="{reverse("marketplace:index")}"')
            self.assertNotContains(response, f'href="{reverse("library:index")}"')

    def test_legacy_library_detail_route_remains_available(self):
        with translation.override("en"):
            match = resolve("/en/library/example-item/")

        self.assertEqual(match.view_name, "library:detail")
