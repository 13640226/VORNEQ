from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomeTranslationTests(TestCase):
    def test_german_home_preserves_localized_orientation_without_legacy_feed_or_refinement(self):
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="de"')
        self.assertContains(response, 'class="world-home"')
        self.assertContains(response, 'id="start"')
        self.assertContains(response, 'id="principles"')
        self.assertContains(response, 'id="capabilities"')
        self.assertNotContains(response, "Empfohlene Entdeckungen")
        self.assertNotContains(response, "Mehr über VORNEQ erfahren")
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, 'id="discoveries"')
        # TODO(translations): once canonical DE homepage copy is available,
        # add assertions for translated hero and capability text.

    def test_persian_home_preserves_localized_orientation_without_legacy_feed_or_refinement(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, 'class="world-home"')
        self.assertContains(response, 'id="start"')
        self.assertContains(response, 'id="principles"')
        self.assertContains(response, 'id="capabilities"')
        self.assertNotContains(response, "کشف‌های برگزیده")
        self.assertNotContains(response, "درباره VORNEQ بیشتر بدانید")
        self.assertNotContains(response, "فیلترهای پیشرفته")
        self.assertNotContains(response, "گشودن جستجوی پیشرفته")
        self.assertNotContains(response, 'id="discoveries"')
        # TODO(translations): once canonical FA homepage copy is available,
        # add assertions for translated hero and capability text.

    def test_persian_home_keeps_localized_search_entry_without_legacy_right_rail_contract(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="search"')
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="type"')
        self.assertNotContains(response, 'name="item_type"')
        self.assertNotContains(response, "هویت در سراسر تجربه‌ها، نه وابسته به یک برنامه.")
        self.assertNotContains(
            response,
            "جستجوی یکپارچه در کتاب‌ها، مقاله‌ها، اسناد و محتوای صوتی",
        )
