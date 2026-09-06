from django.test import TestCase


class GermanHomeTranslationTests(TestCase):
    def test_german_home_renders_new_discovery_copy(self):
        response = self.client.get("/de/")

        self.assertEqual(response.status_code, 200)
        for translated_text in (
            "Wissen ohne Grenzen",
            "Bücher, Artikel, Dokumente, Audio und digitale Produkte",
            "Künstliche Intelligenz",
            "Digitale Produkte",
            "Nachvollziehbares Vertrauen",
            "Vielfältige Perspektiven",
            "Alles an einem Ort",
        ):
            self.assertContains(response, translated_text)
