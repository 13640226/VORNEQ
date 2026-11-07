"""Regression tests for the post-deploy favicon and HEAD response fixes."""
from django.test import TestCase
from django.urls import reverse


class PostDeployHttpTests(TestCase):
    def test_health_head_has_no_body(self):
        response = self.client.head(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_health_get_keeps_json_payload(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_favicon_legacy_path_redirects_to_static_asset(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/static/favicon.svg")

    def test_english_homepage_has_favicon_and_language(self):
        response = self.client.get("/en/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="en"')
        self.assertContains(response, 'rel="icon"')
        self.assertContains(response, "/static/favicon.svg")
