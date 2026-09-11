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

    def test_german_home_renders_localized_value_cards(self):
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VORNEQ-Werte")
        self.assertContains(response, "Einfaches Entdecken")
        self.assertContains(response, "Intelligente Organisation")
        self.assertContains(response, "Sicherer Zugriff")
        self.assertContains(response, ">Werte</")

    def test_german_home_renders_user_centric_feature_cards(self):
        with override("de"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Relevante Ressourcen finden")
        self.assertContains(
            response,
            "Einheitliche Suche in Büchern, Artikeln, Dokumenten und Audioinhalten",
        )
        self.assertContains(response, "Suche starten")
        self.assertContains(response, "Eigene Funde speichern und organisieren")
        self.assertContains(
            response,
            "Notizen erstellen, Schlagwörter hinzufügen und schnell auf Informationen zugreifen",
        )
        self.assertContains(response, "Zu den Notizen")
        self.assertContains(response, "Ergänzende Werkzeuge und Dienste entdecken")
        self.assertContains(
            response,
            "Erweiterungen, Analysewerkzeuge und spezialisierte Dienste",
        )
        self.assertContains(response, "Marktplatz ansehen")


class PersianHomeTranslationTests(TestCase):
    def test_persian_home_renders_localized_value_cards(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ارزش‌های VORNEQ")
        self.assertContains(response, "کشف آسان")
        self.assertContains(response, "سازماندهی هوشمند")
        self.assertContains(response, "دسترسی امن")
        self.assertContains(response, ">ارزش‌ها</")

    def test_persian_home_renders_exact_issue_163_feature_copy(self):
        with override("fa"):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "منابع مرتبط را پیدا کنید")
        self.assertContains(
            response,
            "جستجوی یکپارچه در کتاب‌ها، مقاله‌ها، اسناد و محتوای صوتی",
        )
        self.assertContains(response, "شروع جستجو")
        self.assertContains(response, "یافته‌های خود را ذخیره و سازمان‌دهی کنید")
        self.assertContains(
            response,
            "یادداشت‌برداری، برچسب‌گذاری و دسترسی سریع به اطلاعات",
        )
        self.assertContains(response, "رفتن به یادداشت‌ها")
        self.assertContains(response, "ابزارها و قابلیت‌های تکمیلی را کشف کنید")
        self.assertContains(
            response,
            "افزونه‌ها، ابزارهای تحلیلی و خدمات تخصصی",
        )
        self.assertContains(response, "مشاهده بازارچه")
