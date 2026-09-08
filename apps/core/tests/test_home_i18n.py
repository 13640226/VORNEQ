from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class GermanHomeTranslationTests(TestCase):
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

        # "Discover across" and "VORNEQ" are rendered in separate HTML nodes:
        #
        #   Entdecken auf <span>VORNEQ</span>
        #
        # Therefore checking "Entdecken auf VORNEQ" as one continuous
        # response substring is incorrect.
        self.assertContains(response, "Entdecken auf")
        self.assertContains(response, ">VORNEQ</span>")

        self.assertContains(
            response,
            (
                "Wissen, Produkte, Medien, Dokumente und Audio "
                "über eine vernetzte Entdeckungsoberfläche durchsuchen."
            ),
        )
