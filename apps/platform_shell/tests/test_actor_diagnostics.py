"""CAP-ACTOR-02 — staging-only actor-binding diagnostic (N01–N18).

Synthetic, isolated data only. No external services.
"""

import json
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache.backends.locmem import LocMemCache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.core.models import Identity, UserIdentity
from apps.platform_shell import diagnostics
from apps.platform_shell.capabilities import CapabilityContext, executable_registry
from apps.platform_shell.diagnostics import (
    PROBE_CAPABILITY,
    ProbeInput,
    build_diagnostic_invoker,
    diagnostics_enabled,
    diagnostics_urlpatterns,
)
from apps.platform_shell.tests.actor_helpers import bound_actor_for


User = get_user_model()
URL = "/internal/diagnostics/actor-binding/"
PASS_BODY = {"status": "pass", "check": "trusted_actor_binding", "version": "CAP_ACTOR_02_V1"}
DENY_BODY = {"status": "deny"}


def bind(user, name, *, kind=Identity.Kind.HUMAN):
    identity = Identity.objects.create(kind=kind, display_name=name)
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


class DiagnosticsBase(TestCase):
    def setUp(self):
        self.diag_user = User.objects.create_user(
            username="diag-probe-account", email="diag-probe@example.invalid"
        )
        self.diag_identity = bind(self.diag_user, "Diag Probe Display Name")
        self.real_user = User.objects.create_user(username="real-user", email="real@example.invalid")
        self.real_identity = bind(self.real_user, "Real User")
        self.enabled = override_settings(
            ROOT_URLCONF="apps.platform_shell.tests.diagnostics_urls",
            VORNEQ_ENV="staging",
            VORNEQ_ACTOR_DIAGNOSTICS_ENABLED=True,
            REDIS_URL="redis://127.0.0.1:56380/14",
            CACHES={"default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": "redis://127.0.0.1:56380/14",
                "TIMEOUT": 300,
            }},
            VORNEQ_ACTOR_DIAGNOSTICS_IDENTITY_ID=str(self.diag_identity.pk),
        )
        self.enabled.enable()
        self.addCleanup(self.enabled.disable)

        # Model the Redis-backed counter using an isolated in-memory test double.
        # Production still requires the shared Redis gate; no Redis service is
        # needed or contacted during synthetic SQLite/PostgreSQL CI tests.
        counter = LocMemCache(f"actor-diag-test-{self.diag_identity.pk}", {})
        counter_patch = patch("apps.platform_shell.diagnostics.cache", counter)
        counter_patch.start()
        self.addCleanup(counter_patch.stop)

    def get_as(self, user=None, **extra):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client.get(URL, **extra)

    def assert_deny(self, response, status=403):
        self.assertEqual(response.status_code, status)
        self.assertEqual(json.loads(response.content), DENY_BODY)

    def assert_no_identifiers(self, response):
        body = response.content.decode()
        for secret in (
            self.diag_user.username,
            self.diag_user.email,
            "Diag Probe Display Name",
            str(self.diag_identity.pk),
            str(self.real_identity.pk),
            self.real_user.username,
        ):
            self.assertNotIn(secret, body)
        self.assertNotIn("Traceback", body)
        self.assertNotRegex(body, r"\b\d+\b")  # no numeric user ids in any response


class GateTests(DiagnosticsBase):
    # N12
    def test_staging_without_redis_is_not_registered(self):
        with override_settings(REDIS_URL=None):
            self.assertFalse(diagnostics_enabled())
            self.assertEqual(diagnostics_urlpatterns(), [])

    def test_staging_with_locmem_backend_is_not_registered(self):
        with override_settings(CACHES={"default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "audit-only",
        }}):
            self.assertFalse(diagnostics_enabled())
            self.assertEqual(diagnostics_urlpatterns(), [])

    def test_n12_production_is_not_registered_and_view_404s(self):
        with override_settings(VORNEQ_ENV="production"):
            self.assertFalse(diagnostics_enabled())
            self.assertEqual(diagnostics_urlpatterns(), [])
            self.assertEqual(self.get_as(self.diag_user).status_code, 404)

    def test_development_is_not_registered(self):
        with override_settings(VORNEQ_ENV="development"):
            self.assertEqual(diagnostics_urlpatterns(), [])
            self.assertEqual(self.get_as(self.diag_user).status_code, 404)

    # N13
    def test_n13_flag_disabled_404s(self):
        with override_settings(VORNEQ_ACTOR_DIAGNOSTICS_ENABLED=False):
            self.assertEqual(diagnostics_urlpatterns(), [])
            self.assertEqual(self.get_as(self.diag_user).status_code, 404)

    def test_truthy_non_bool_flag_does_not_enable(self):
        with override_settings(VORNEQ_ACTOR_DIAGNOSTICS_ENABLED="True"):
            self.assertFalse(diagnostics_enabled())

    def test_missing_or_invalid_identity_config_404s(self):
        for value in ("", "not-a-uuid", None):
            with self.subTest(value=value), override_settings(VORNEQ_ACTOR_DIAGNOSTICS_IDENTITY_ID=value):
                self.assertEqual(diagnostics_urlpatterns(), [])
                self.assertEqual(self.get_as(self.diag_user).status_code, 404)

    def test_real_root_urlconf_does_not_expose_endpoint_in_test_environment(self):
        with override_settings(ROOT_URLCONF="config.urls"):
            self.assertEqual(Client().get(URL).status_code, 404)

    def test_gate_open_registers_exactly_one_route(self):
        patterns = diagnostics_urlpatterns()
        self.assertEqual(len(patterns), 1)
        self.assertEqual(str(patterns[0].pattern), URL.lstrip("/"))

    def test_only_get_is_allowed(self):
        client = Client(enforce_csrf_checks=False)
        client.force_login(self.diag_user)
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(client, method)(URL).status_code, 405)


class AccessTests(DiagnosticsBase):
    # N03
    def test_n03_authorized_diagnostic_account_passes(self):
        response = self.get_as(self.diag_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), PASS_BODY)
        self.assertIn("no-store", response["Cache-Control"])
        self.assert_no_identifiers(response)

    # N01
    def test_n01_anonymous_denied(self):
        response = self.get_as(None)
        self.assert_deny(response)
        self.assert_no_identifiers(response)

    # N02 / N18
    def test_n02_n18_other_real_user_denied(self):
        response = self.get_as(self.real_user)
        self.assert_deny(response)
        self.assert_no_identifiers(response)

    # N04
    def test_n04_inactive_diagnostic_user_denied(self):
        User.objects.filter(pk=self.diag_user.pk).update(is_active=False)
        self.assert_deny(self.get_as(self.diag_user))

    # N05
    def test_n05_inactive_diagnostic_identity_denied(self):
        Identity.objects.filter(pk=self.diag_identity.pk).update(is_active=False)
        self.assert_deny(self.get_as(self.diag_user))

    # N06
    def test_n06_missing_binding_denied(self):
        UserIdentity.objects.filter(user=self.diag_user).delete()
        self.assert_deny(self.get_as(self.diag_user))

    def test_non_human_diagnostic_identity_denied(self):
        Identity.objects.filter(pk=self.diag_identity.pk).update(kind=Identity.Kind.SYSTEM)
        self.assert_deny(self.get_as(self.diag_user))

    # N07 / N08 / N09
    def test_n07_n08_n09_forged_ids_have_no_impact(self):
        forged_query = (
            f"?user_id={self.diag_user.pk}&identity_id={self.diag_identity.pk}"
            f"&actor_id={self.diag_identity.pk}&actor=diag-probe-account"
        )
        forged_headers = {
            "HTTP_X_ACTOR_ID": str(self.diag_identity.pk),
            "HTTP_X_USER_ID": str(self.diag_user.pk),
        }
        client = Client()
        client.force_login(self.real_user)
        response = client.get(URL + forged_query, **forged_headers)
        self.assert_deny(response)
        self.assert_no_identifiers(response)

        anonymous = Client().get(URL + forged_query, **forged_headers)
        self.assert_deny(anonymous)

        legit = Client()
        legit.force_login(self.diag_user)
        spoof_away = f"?user_id={self.real_user.pk}&identity_id={self.real_identity.pk}"
        response = legit.get(URL + spoof_away, HTTP_X_ACTOR_ID=str(self.real_identity.pk))
        self.assertEqual(json.loads(response.content), PASS_BODY)

    # N10 / N11
    def test_n10_stale_and_n11_rebound_actor_denied_by_invoker(self):
        invoker = build_diagnostic_invoker()

        def probe(actor):
            return invoker.invoke(
                PROBE_CAPABILITY,
                context=CapabilityContext(actor=actor, request_id="n10"),
                input_data=ProbeInput(),
            )

        stale = bound_actor_for(self.diag_user)
        self.assertTrue(probe(stale).success)
        Identity.objects.filter(pk=self.diag_identity.pk).update(is_active=False)
        self.assertEqual(probe(stale).error.code, "not_authorized")

        Identity.objects.filter(pk=self.diag_identity.pk).update(is_active=True)
        rebound = bound_actor_for(self.diag_user)
        replacement = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name="Replacement")
        UserIdentity.objects.filter(user=self.diag_user).update(identity=replacement)
        self.assertEqual(probe(rebound).error.code, "not_authorized")

    def test_probe_capability_rejects_non_diagnostic_bound_actor(self):
        result = build_diagnostic_invoker().invoke(
            PROBE_CAPABILITY,
            context=CapabilityContext(actor=bound_actor_for(self.real_user), request_id="x"),
            input_data=ProbeInput(),
        )
        self.assertEqual(result.error.code, "not_authorized")

    # N17
    def test_n17_no_capability_enumeration_or_business_capabilities(self):
        invoker = build_diagnostic_invoker()
        self.assertEqual(invoker.registry.all(), (PROBE_CAPABILITY,))
        diag_actor = bound_actor_for(self.diag_user)
        business = invoker.invoke(
            "read_artifact_v1",
            context=CapabilityContext(actor=diag_actor, request_id="n17"),
            input_data={"artifact_id": str(self.diag_identity.pk)},
        )
        self.assertEqual(business.error.code, "unknown_capability")
        untrusted = invoker.invoke(
            "read_artifact_v1",
            context=CapabilityContext(actor=object(), request_id="n17"),
            input_data={},
        )
        self.assertEqual(untrusted.error.code, "not_authorized")
        self.assertNotIn(PROBE_CAPABILITY, executable_registry.all())

    def test_rate_limit_returns_generic_429(self):
        client = Client()
        client.force_login(self.diag_user)
        statuses = [client.get(URL).status_code for _ in range(diagnostics.RATE_LIMIT_REQUESTS + 1)]
        self.assertEqual(statuses[:-1], [200] * diagnostics.RATE_LIMIT_REQUESTS)
        self.assertEqual(statuses[-1], 429)


class SideEffectTests(DiagnosticsBase):
    BUSINESS_TABLES = re.compile(
        r'"(documents_\w+|core_artifact\w*|library_\w+|marketplace_\w+|media_\w+|notes_\w+)"'
    )
    WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b", re.IGNORECASE)

    def captured(self, user):
        client = Client()
        client.force_login(user)
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(URL)
        return response, [q["sql"] for q in ctx.captured_queries]

    # N14 / N15 / N16
    def test_n14_n15_n16_pass_and_deny_paths_read_no_business_data_and_write_nothing(self):
        for user, status in ((self.diag_user, 200), (self.real_user, 403)):
            with self.subTest(status=status):
                response, queries = self.captured(user)
                self.assertEqual(response.status_code, status)
                self.assert_no_identifiers(response)
                self.assertFalse([q for q in queries if self.WRITE.match(q)], queries)
                self.assertFalse([q for q in queries if self.BUSINESS_TABLES.search(q)], queries)

    def test_logs_contain_no_identifiers(self):
        with self.assertLogs("apps.platform_shell.diagnostics", level="INFO") as logs:
            self.get_as(self.diag_user)
            self.get_as(self.real_user)
        text = "\n".join(logs.output)
        for secret in (self.diag_user.username, str(self.diag_identity.pk), self.real_user.username):
            self.assertNotIn(secret, text)


class BrokenCache:
    """Simulates an unreachable Redis: every operation raises."""

    def __init__(self, fail_on=("add", "incr", "set")):
        self.fail_on = set(fail_on)
        self.calls = []

    def _op(self, name, *args, **kwargs):
        self.calls.append(name)
        if name in self.fail_on:
            raise ConnectionError("Error 111 connecting to 10.0.0.5:6379. Connection refused.")
        return 1

    def add(self, *a, **k):
        return self._op("add", *a, **k)

    def incr(self, *a, **k):
        return self._op("incr", *a, **k)

    def set(self, *a, **k):
        return self._op("set", *a, **k)


class CacheOutageTests(DiagnosticsBase):
    UNAVAILABLE = {"status": "unavailable"}

    def get_with_cache(self, fake, user):
        with patch("apps.platform_shell.diagnostics.cache", fake):
            return self.get_as(user)

    def assert_unavailable(self, response):
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.content), self.UNAVAILABLE)
        body = response.content.decode()
        for leak in ("6379", "10.0.0.5", "Connection refused", "Error", "redis", "Traceback"):
            self.assertNotIn(leak, body)
        self.assert_no_identifiers(response)

    # R01: outage on the very first operation (the observed failure)
    def test_r01_outage_on_add_fails_closed_with_503(self):
        fake = BrokenCache(fail_on=("add",))
        self.assert_unavailable(self.get_with_cache(fake, self.diag_user))
        self.assertEqual(fake.calls, ["add"])

    # R02: outage on incr and on the fallback set
    def test_r02_outage_on_incr_or_set_fails_closed(self):
        for fail_on in (("incr",), ("incr", "set"), ("add", "incr", "set")):
            with self.subTest(fail_on=fail_on):
                self.assert_unavailable(self.get_with_cache(BrokenCache(fail_on=fail_on), self.diag_user))

    # R03: outage never produces a pass, for any caller
    def test_r03_outage_never_passes_and_never_binds_actor(self):
        with patch("apps.platform_shell.diagnostics.BoundActor.from_request") as bind:
            for user in (self.diag_user, self.real_user, None):
                with self.subTest(user=getattr(user, "username", None)):
                    response = self.get_with_cache(BrokenCache(), user)
                    self.assert_unavailable(response)
            bind.assert_not_called()

    # R04: recovery — with the store back, the normal limit applies again
    def test_r04_recovery_restores_normal_behaviour_and_limit(self):
        self.assert_unavailable(self.get_with_cache(BrokenCache(), self.diag_user))
        client = Client()
        client.force_login(self.diag_user)
        statuses = [client.get(URL).status_code for _ in range(diagnostics.RATE_LIMIT_REQUESTS + 1)]
        self.assertEqual(statuses[:-1], [200] * diagnostics.RATE_LIMIT_REQUESTS)
        self.assertEqual(statuses[-1], 429)

    def test_outage_is_logged_without_details(self):
        with self.assertLogs("apps.platform_shell.diagnostics", level="ERROR") as logs:
            self.get_with_cache(BrokenCache(), self.diag_user)
        text = "\n".join(logs.output)
        self.assertIn("unavailable", text)
        for leak in ("6379", "10.0.0.5", self.diag_user.username):
            self.assertNotIn(leak, text)

    def test_expired_key_between_add_and_incr_fails_closed_without_reset(self):
        class ExpiringCache(BrokenCache):
            def incr(self, *a, **k):
                self.calls.append("incr")
                raise ValueError("Key not found")

        fake = ExpiringCache(fail_on=())
        response = self.get_with_cache(fake, self.diag_user)
        self.assert_unavailable(response)
        self.assertEqual(fake.calls, ["add", "incr"])
