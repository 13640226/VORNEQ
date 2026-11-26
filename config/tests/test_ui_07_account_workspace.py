from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils.translation import override


class AccountWorkspaceV8Tests(TestCase):
    def test_public_account_shell_in_three_languages(self):
        for lang in ('de', 'fa', 'en'):
            with override(lang):
                for name in ('account_login', 'account_signup', 'account_reset_password'):
                    with self.subTest(lang=lang, route=name):
                        response = self.client.get(reverse(name))
                        self.assertContains(response, 'id="vq-main"', count=1)
                        for code in ('de', 'fa', 'en'):
                            self.assertContains(response, f'name="language" value="{code}"')
                        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_private_account_shell(self):
        user = get_user_model().objects.create_user(username='ui07-test', email='ui07@example.test', password='test-password-123')
        self.client.force_login(user)
        for name in ('profile', 'profile_edit', 'account_email', 'account_change_password', 'account_logout'):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, 'id="vq-main"', count=1)

    def test_login_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('account_login'), {'login':'ui07-test','password':'invalid'})
        self.assertEqual(response.status_code, 403)
