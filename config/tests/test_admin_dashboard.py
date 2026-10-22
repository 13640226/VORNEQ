"""Regression tests for the permission-aware admin dashboard."""
from urllib.parse import parse_qs, urlsplit

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.templatetags.vorneq_admin_dashboard import vorneq_dashboard


class AdminDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superuser = User.objects.create_superuser(
            username="dashboard_super", email="super@example.com", password="test-password"
        )
        cls.staff = User.objects.create_user(
            username="dashboard_staff", email="staff@example.com",
            password="test-password", is_staff=True,
        )

    def test_superuser_home_renders_with_rtl_and_stylesheet(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "vorneq_admin_dashboard.")
        self.assertContains(response, "vorneq_admin.")
        self.assertContains(response, "درخواست‌های در انتظار بررسی")

    @override_settings(LANGUAGE_CODE="en", LANGUAGES=[("en", "English")])
    def test_english_admin_direction(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="vorneq-dashboard" dir="ltr"')

    def test_staff_without_permissions_cannot_see_stats_or_actions(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="vorneq-dashboard__stat ')
        self.assertNotContains(response, 'class="vorneq-dashboard__action"')
        self.assertNotContains(response, "درخواست‌های در انتظار بررسی")

    def test_view_permission_does_not_grant_add(self):
        article = apps.get_model("content", "Article")
        view_permission = Permission.objects.get(
            content_type__app_label="content", codename="view_article"
        )
        self.staff.user_permissions.add(view_permission)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vorneq-dashboard__stat--article')
        self.assertNotContains(response, 'class="vorneq-dashboard__action"')
        self.assertEqual(article._default_manager.count(), 0)

    def test_add_permission_does_not_expose_stat(self):
        permission = Permission.objects.get(
            content_type__app_label="content", codename="add_article"
        )
        self.staff.user_permissions.add(permission)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'vorneq-dashboard__stat--article')
        self.assertContains(response, 'class="vorneq-dashboard__action"')
        self.assertContains(response, "افزودن مقاله")
        self.assertNotContains(response, "افزودن مقالات")

    def test_pending_card_filter_and_admin_allowlist(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        cards = response.context["request"]
        dashboard = vorneq_dashboard({"request": cards})
        pending = next(card for card in dashboard["cards"] if card["tone"] == "verification")
        self.assertEqual(
            parse_qs(urlsplit(pending["url"]).query),
            {"status__in": ["requested,in_progress"]},
        )
        model = apps.get_model("verification", "VerificationRequest")
        self.assertIn("status", admin.site._registry[model].list_filter)
        changelist = self.client.get(pending["url"])
        self.assertEqual(changelist.status_code, 200)

    def test_stylesheet_is_discoverable(self):
        self.assertIsNotNone(finders.find("admin/css/vorneq_admin_dashboard.css"))

    def test_stylesheet_overrides_django_fixed_dashboard_width(self):
        # Django base.css sets `.dashboard #content { width: 600px; }`, which
        # squeezed the redesigned index into a narrow column on desktop.
        stylesheet = finders.find("admin/css/vorneq_admin_dashboard.css")
        with open(stylesheet, encoding="utf-8") as handle:
            css = handle.read()
        self.assertIn("body.vorneq-dashboard-page #content{width:auto", css)
