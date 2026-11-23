from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.test import RequestFactory, TestCase, override_settings

from apps.media import api


class FakeService:
    calls = 0

    def search_by_text(self, text, limit=10):
        FakeService.calls += 1
        return []

    def search_by_image(self, data, mime_type, limit=10):
        FakeService.calls += 1
        return []


def _post(user, **kw):
    # Calling the view directly models a request that already passed CSRF.
    req = RequestFactory().post("/x", data={"text": "cat"}, **kw)
    req.user = user
    return req


@override_settings(DEBUG=True)
class MediaApiAuthzTests(TestCase):
    def setUp(self):
        FakeService.calls = 0
        U = get_user_model()
        self.plain = U.objects.create_user("plain", password="x")
        self.viewer = U.objects.create_user("viewer", password="x")
        self.viewer.user_permissions.add(Permission.objects.get(codename="view_mediaasset"))
        self.inactive = U.objects.create_user("off", password="x", is_active=False)
        self.inactive.user_permissions.add(Permission.objects.get(codename="view_mediaasset"))
        p = mock.patch.object(api, "MediaSimilarityService", lambda **k: FakeService())
        p.start(); self.addCleanup(p.stop)

    def _open(self):
        p = mock.patch.object(api, "MEDIA_SIMILARITY_API_HOLD", False)
        p.start(); self.addCleanup(p.stop)

    def test_hold_returns_503_for_everyone_and_never_reaches_service(self):
        for u in (AnonymousUser(), self.plain, self.viewer):
            self.assertEqual(api.search_by_text(_post(u)).status_code, 503)
        self.assertEqual(FakeService.calls, 0)

    @override_settings(DEBUG=False)
    def test_production_without_provider_fails_closed_503(self):
        self._open()
        for u in (AnonymousUser(), self.viewer):
            self.assertEqual(api.search_by_text(_post(u)).status_code, 503)
        self.assertEqual(FakeService.calls, 0)

    def test_anonymous_denied_even_with_csrf_passed(self):
        self._open()
        self.assertEqual(api.search_by_text(_post(AnonymousUser())).status_code, 401)
        self.assertEqual(api.search_by_image(_post(AnonymousUser())).status_code, 401)
        self.assertEqual(FakeService.calls, 0)

    def test_missing_user_attribute_fails_closed(self):
        self._open()
        req = RequestFactory().post("/x", data={"text": "cat"})
        self.assertEqual(api.search_by_text(req).status_code, 401)

    def test_authenticated_without_permission_denied(self):
        self._open()
        self.assertEqual(api.search_by_text(_post(self.plain)).status_code, 403)
        self.assertEqual(FakeService.calls, 0)

    def test_inactive_user_denied(self):
        self._open()
        self.assertIn(api.search_by_text(_post(self.inactive)).status_code, (401, 403))
        self.assertEqual(FakeService.calls, 0)

    def test_permitted_user_reaches_service(self):
        self._open()
        self.assertEqual(api.search_by_text(_post(self.viewer)).status_code, 200)
        self.assertEqual(FakeService.calls, 1)

    def test_non_dict_json_is_400_not_500(self):
        self._open()
        req = RequestFactory().post("/x", data="[1]", content_type="application/json")
        req.user = self.viewer
        self.assertEqual(api.search_by_text(req).status_code, 400)
