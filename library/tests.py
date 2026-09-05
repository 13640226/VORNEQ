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

    def test_index_view_exists(self):
        response = self.client.get(reverse("library:index"))
        self.assertEqual(response.status_code, 200)


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


class UnifiedLibrarySearchTests(TestCase):
    def setUp(self):
        self.book = LibraryItem.objects.create(
            title="Shared topic book",
            slug="shared-topic-book",
            item_type="book",
            short_description="A shared search phrase",
            is_published=True,
        )
        self.article = LibraryItem.objects.create(
            title="Shared topic article",
            slug="shared-topic-article",
            item_type="article",
            is_published=True,
        )
        self.audio = AudioItem.objects.create(
            title="Shared topic audio",
            description="A shared search phrase",
            is_published=True,
        )
        AudioItem.objects.create(
            title="Hidden shared audio",
            description="Shared topic",
            is_published=False,
        )

    def test_query_returns_library_and_audio_results(self):
        response = self.client.get(
            reverse("library:index"),
            {"q": "Shared topic"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.book.title)
        self.assertContains(response, self.article.title)
        self.assertContains(response, self.audio.title)
        self.assertNotContains(response, "Hidden shared audio")
        self.assertEqual(list(response.context["audio_results"]), [self.audio])

    def test_query_with_type_filter_excludes_audio_results(self):
        response = self.client.get(
            reverse("library:index"),
            {"q": "Shared topic", "type": "book"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.book.title)
        self.assertNotContains(response, self.article.title)
        self.assertNotContains(response, self.audio.title)
        self.assertIsNone(response.context["audio_results"])

    def test_query_with_no_matches_has_no_audio_results(self):
        response = self.client.get(
            reverse("library:index"),
            {"q": "definitely-no-match"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["audio_results"].exists())
        self.assertContains(response, "موردی در کتابخانه یافت نشد")
