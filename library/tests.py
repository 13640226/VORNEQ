from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import AudioItem, LibraryItem


class LibraryModelTests(TestCase):
    def test_create_library_item(self):
        item = LibraryItem.objects.create(
            title="Test Library Item",
            slug="test-library-item",
            content="This is test content",
            is_published=True,
        )
        self.assertEqual(item.title, "Test Library Item")
        self.assertTrue(item.is_published)

    def test_slug_uniqueness(self):
        LibraryItem.objects.create(title="Item 1", slug="same-slug")
        with self.assertRaises(IntegrityError):
            LibraryItem.objects.create(title="Item 2", slug="same-slug")


class LibraryContractTests(TestCase):
    def test_view_required_model_fields_exist(self):
        fields = {field.name for field in LibraryItem._meta.get_fields()}
        required = {
            "allow_public_reading",
            "item_type",
            "title_en",
            "title_de",
            "short_description_en",
            "short_description_de",
            "content_en",
            "content_de",
            "author",
            "published_at",
            "pdf_file",
        }
        self.assertTrue(required.issubset(fields))

    def test_view_required_model_helpers_exist(self):
        for attribute in (
            "TYPE_CHOICES",
            "get_title",
            "get_short_description",
            "get_content",
            "has_pdf",
        ):
            self.assertTrue(hasattr(LibraryItem, attribute), attribute)

    def test_index_redirects_to_marketplace(self):
        response = self.client.get(reverse("library:index"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, reverse("marketplace:index"))


class AudioDetailTests(TestCase):
    def test_published_audio_returns_200(self):
        audio = AudioItem.objects.create(
            title="Published audio",
            description="Visible audio",
            is_published=True,
        )

        response = self.client.get(
            reverse("library:audio_detail", args=[audio.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["audio"], audio)

    def test_unpublished_audio_returns_404(self):
        audio = AudioItem.objects.create(
            title="Private audio",
            is_published=False,
        )

        response = self.client.get(
            reverse("library:audio_detail", args=[audio.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_missing_audio_returns_404(self):
        response = self.client.get(
            reverse("library:audio_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)


class LegacyLibraryIndexRedirectTests(TestCase):
    def test_query_redirect_preserves_search_term(self):
        response = self.client.get(
            reverse("library:index"),
            {"q": "Shared topic"},
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            f'{reverse("marketplace:index")}?q=Shared+topic',
        )

    def test_query_redirect_preserves_type_filter(self):
        response = self.client.get(
            reverse("library:index"),
            {"q": "Shared topic", "type": "book"},
        )

        self.assertEqual(response.status_code, 301)
        self.assertIn("q=Shared+topic", response.url)
        self.assertIn("type=book", response.url)

    def test_query_with_no_matches_still_redirects_to_marketplace(self):
        response = self.client.get(
            reverse("library:index"),
            {"q": "definitely-no-match"},
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            f'{reverse("marketplace:index")}?q=definitely-no-match',
        )
