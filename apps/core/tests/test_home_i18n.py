from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomeTranslationTests(TestCase):
    def test_german_home_renders_v3_discovery_copy(self):
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WISSEN OHNE GRENZEN")
        self.assertContains(response, "Globale Wissensplattform")
        self.assertContains(
            response,
            "Wissen, Software, Produkte, Dienstleistungen, Medien und digitale Ressourcen",
        )
        self.assertContains(response, "Suche starten")
        self.assertContains(response, "Entdecken")
        self.assertContains(response, "Prinzipien")

    def test_persian_home_renders_v3_discovery_copy(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دانش بدون مرز")
        self.assertContains(response, "پلتفرم دانش جهانی")
        self.assertContains(
            response,
            "دانش، نرم‌افزار، محصولات، خدمات، رسانه و منابع دیجیتال",
        )
        self.assertContains(response, "شروع جستجو")
        self.assertContains(response, "کاوش")
        self.assertContains(response, "اصول")

    def test_german_home_renders_localized_principles_and_actions(self):
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plattformprinzipien")
        self.assertContains(response, "Kontext statt Bewertung")
        self.assertContains(response, "Belege statt Wahrheit")
        self.assertContains(response, "Portable Identität")
        self.assertContains(response, "Was Sie tun können")
        self.assertContains(response, "ORGANISIEREN")
        self.assertContains(response, "Marktplatz ansehen")


class PersianHomeTranslationTests(TestCase):
    def test_persian_home_renders_localized_principles_and_actions(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اصول پلتفرم")
        self.assertContains(response, "زمینه، نه امتیاز")
        self.assertContains(response, "شواهد، نه حقیقت")
        self.assertContains(response, "هویت قابل‌انتقال")
        self.assertContains(response, "چه کارهایی می‌توانید انجام دهید")
        self.assertContains(response, "سازمان‌دهی")
        self.assertContains(response, "مشاهده بازارچه")
