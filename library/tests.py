from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import LibraryItem


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
