"""Regression tests for the permission-aware admin dashboard."""
from urllib.parse import parse_qs, urlsplit

from django.apps import apps
from django.contrib import admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.templatetags.vorneq_admin_dashboard import vorneq_dashboard


def _static_text(path):
    found = finders.find(path)
    with open(found, encoding="utf-8") as handle:
        return handle.read()


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

    def get_index(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_superuser_home_renders_rtl_with_assets(self):
        response = self.get_index(self.superuser)
        self.assertContains(response, 'class="vorneq-dashboard" dir="rtl"')
        self.assertContains(response, "vorneq_admin_dashboard.")
        self.assertContains(response, "vorneq_admin.")
        self.assertContains(response, "admin/js/vorneq_admin_dashboard.")
        self.assertContains(response, "چرخهٔ راستی‌آزمایی")
        self.assertContains(response, 'id="vq-filter"')

    @override_settings(LANGUAGE_CODE="en", LANGUAGES=[("en", "English")])
    def test_english_admin_direction(self):
        response = self.get_index(self.superuser)
        self.assertContains(response, 'class="vorneq-dashboard" dir="ltr"')

    def test_environment_badge_names_env_and_database(self):
        response = self.get_index(self.superuser)
        self.assertContains(response, 'class="vq-env vq-env--')

    def test_staff_without_permissions_sees_no_stats_actions_or_verification(self):
        response = self.get_index(self.staff)
        self.assertNotContains(response, 'class="vq-stat ')
        self.assertNotContains(response, 'class="vq-action"')
        self.assertNotContains(response, "چرخهٔ راستی‌آزمایی")

    def test_view_permission_does_not_grant_add(self):
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="content", codename="view_article")
        )
        response = self.get_index(self.staff)
        self.assertContains(response, "vq-stat--article")
        self.assertNotContains(response, 'class="vq-action"')
        self.assertEqual(apps.get_model("content", "Article")._default_manager.count(), 0)

    def test_add_permission_does_not_expose_stat(self):
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="content", codename="add_article")
        )
        response = self.get_index(self.staff)
        self.assertNotContains(response, "vq-stat--article")
        self.assertContains(response, 'class="vq-action"')
        self.assertContains(response, "افزودن مقاله")
        self.assertNotContains(response, "افزودن مقالات")

    def test_verification_summary_links_are_accepted_by_admin(self):
        response = self.get_index(self.superuser)
        summary = vorneq_dashboard({"request": response.context["request"]})["verification"]
        self.assertIsNotNone(summary)
        self.assertEqual(summary["total"], 0)
        self.assertEqual(
            [s["value"] for s in summary["statuses"]],
            ["requested", "in_progress", "completed", "failed", "cancelled"],
        )
        self.assertEqual(
            parse_qs(urlsplit(summary["pending_url"]).query),
            {"status__in": ["requested,in_progress"]},
        )
        model = apps.get_model("verification", "VerificationRequest")
        self.assertIn("status", admin.site._registry[model].list_filter)
        # Django redirects with ?e=1 when a lookup is not allowed.
        for url in [summary["pending_url"]] + [s["url"] for s in summary["statuses"]]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_recent_activity_lists_own_log_entries(self):
        LogEntry.objects.create(
            user=self.superuser,
            content_type=ContentType.objects.get_for_model(get_user_model()),
            object_id=str(self.superuser.pk),
            object_repr="dashboard log probe",
            action_flag=ADDITION,
            change_message="[]",
        )
        response = self.get_index(self.superuser)
        self.assertContains(response, "dashboard log probe")
        self.assertContains(response, "vq-chip--add")

    def test_recent_activity_empty_state(self):
        response = self.get_index(self.superuser)
        self.assertContains(response, "هنوز فعالیتی ثبت نکرده‌اید.")

    def test_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("admin/css/vorneq_admin_dashboard.css"))
        self.assertIsNotNone(finders.find("admin/js/vorneq_admin_dashboard.js"))

    def test_stylesheet_overrides_django_dashboard_layout(self):
        # Django base.css sets `.dashboard #content { width: 600px; }` and floats
        # #content-main; both squeezed or off-centred the redesigned index.
        css = _static_text("admin/css/vorneq_admin_dashboard.css")
        self.assertIn("body.vorneq-dashboard-page #content{width:auto", css)
        self.assertIn("body.vorneq-dashboard-page #content-main{float:none}", css)
