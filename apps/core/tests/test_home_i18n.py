from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomeTranslationTests(TestCase):
    def test_german_home_renders_new_discovery_copy(self):
        """
        Homepage German translation must render the redesign copy.

        The locale is explicitly activated so this test does not depend
        on the project's default LANGUAGE_CODE.
        """
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Wissen ohne Grenzen")
        self.assertContains(response, "Globale Wissensplattform")
        self.assertContains(
            response,
            (
                "Finden und organisieren Sie Bücher, Artikel, Dokumente, "
                "Audioinhalte und digitale Ressourcen an einem Ort."
            ),
        )
        self.assertContains(response, "Suche starten")
        self.assertContains(response, "Mehr über VORNEQ erfahren")

        self.assertContains(
            response,
            (
                "Wissen, Produkte, Medien, Dokumente und Audio "
                "über eine vernetzte Entdeckungsoberfläche durchsuchen."
            ),
        )

    def test_persian_home_renders_new_discovery_copy(self):
        """Homepage Persian translation must render the approved #161 copy."""
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پلتفرم دانش جهانی")
        self.assertContains(
            response,
            (
                "کتاب‌ها، مقاله‌ها، اسناد، محتوای صوتی و منابع دیجیتال "
                "را از یک نقطه پیدا و سازمان‌دهی کنید."
            ),
        )
        self.assertContains(response, "شروع جستجو")
        self.assertContains(response, "درباره VORNEQ بیشتر بدانید")
