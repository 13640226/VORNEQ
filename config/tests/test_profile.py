from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile-user",
            email="profile@example.com",
            password="test-password-123",
        )

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_profile_renders_real_empty_state(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "profile-user")
        self.assertContains(response, 'id="overview"')
        self.assertContains(response, 'id="library"')
        self.assertContains(response, 'id="products"')
        self.assertContains(response, 'id="reputation"')
        self.assertContains(response, 'id="settings"')
        self.assertContains(response, 'href="#library"')
        self.assertContains(response, 'href="#products"')
        self.assertNotContains(response, "Verification & Evidence")
        self.assertNotContains(response, "Identities")
        self.assertNotContains(response, "VORNEQ Plus")
        self.assertNotContains(response, "Friends' activity")

    def test_profile_preserves_contextual_reputation_semantics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))

        self.assertContains(
            response,
            "These scores are context-specific projections. They are not a global trust score and do not represent truth.",
        )
        self.assertContains(response, "Context-specific reputation records, never a global trust score.")
        self.assertNotContains(response, "Verified true")
        self.assertNotContains(response, "Trust rank")

    def test_profile_navigation_and_existing_account_actions_remain_available(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))

        self.assertContains(response, 'href="#overview"')
        self.assertContains(response, 'href="#library"')
        self.assertContains(response, 'href="#products"')
        self.assertContains(response, 'href="#reputation"')
        self.assertContains(response, 'href="#settings"')
        self.assertContains(response, reverse("profile_edit"))
        self.assertContains(response, reverse("account_email"))
        self.assertContains(response, reverse("account_change_password"))
        self.assertContains(response, reverse("account_logout"))
        self.assertContains(response, reverse("marketplace:index"))
        self.assertContains(response, reverse("marketplace:seller_dashboard"))

    def test_profile_uses_existing_backend_counts(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.context["entitlement_count"], 0)
        self.assertEqual(response.context["seller_product_count"], 0)
        self.assertEqual(response.context["reputation_context_count"], 0)
