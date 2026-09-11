from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomeTranslationTests(TestCase):
    def test_german_home_preserves_localized_live_home_surfaces(self):
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Globale Wissensplattform")
        self.assertContains(response, "Suche starten")
        self.assertContains(response, "Mehr über VORNEQ erfahren")
        self.assertContains(response, "Empfohlene Entdeckungen")
        self.assertContains(response, "Relevante Ressourcen finden")
        self.assertContains(response, "Funde speichern und organisieren")
        self.assertContains(response, "Marktplatz ansehen")

    def test_persian_home_preserves_localized_live_home_surfaces(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پلتفرم دانش جهانی")
        self.assertContains(response, "شروع جستجو")
        self.assertContains(response, "درباره VORNEQ بیشتر بدانید")
        self.assertContains(response, "کشف‌های برگزیده")
        self.assertContains(response, "منابع مرتبط را پیدا کنید")
        self.assertContains(response, "یافته‌های خود را ذخیره و سازمان‌دهی کنید")
        self.assertContains(response, "مشاهده بازارچه")


class PersianHomeTranslationTests(TestCase):
    def test_persian_home_keeps_localized_search_and_right_rail_contract(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فیلترهای پیشرفته")
        self.assertContains(response, "گشودن جستجوی پیشرفته")
        self.assertContains(response, "هویت در سراسر تجربه‌ها، نه وابسته به یک برنامه.")
        self.assertContains(
            response,
            "جستجوی یکپارچه در کتاب‌ها، مقاله‌ها، اسناد و محتوای صوتی",
        )
