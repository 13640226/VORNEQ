"""PARITY-14 — Tests für audit_environment_parity (read-only, ohne Secrets)."""
import copy
import io
import json
import pathlib
import re
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import connections
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation

from apps.core import environment_parity as parity
from apps.core.models import Identity, UserIdentity
from apps.platform_shell.registry import registry

RELEASE = "a" * 40
OTHER = "b" * 40
ENV_READ = re.compile(
    r'(?:\benv_[a-z]+|\benv|os\.environ\.get|os\.getenv|os\.environ\[)\(?\s*["\']([A-Z][A-Z0-9_]{2,})["\']'
)


def _code_variables():
    root = pathlib.Path(settings.BASE_DIR)
    names = set()
    for folder in ("config", "apps", "library", "marketplace"):
        for path in (root / folder).rglob("*.py"):
            text = str(path)
            if "/tests/" in text or "/migrations/" in text:
                continue
            names.update(ENV_READ.findall(path.read_text(encoding="utf-8")))
    return names


class CatalogTests(SimpleTestCase):
    def test_every_variable_read_by_code_is_catalogued(self):
        missing = sorted(_code_variables() - set(parity.CATALOG_BY_NAME) - {"VORNEQ_RELEASE", "DJANGO_SETTINGS_MODULE"})
        self.assertEqual(missing, [], "Neue Umgebungsvariable ohne Katalogeintrag (Drift-Schutz)")

    def test_catalog_has_no_dead_entries(self):
        dead = sorted(set(parity.CATALOG_BY_NAME) - _code_variables())
        self.assertEqual(dead, [], "Katalogeintrag ohne Verwendung im Code")

    def test_catalog_entries_are_well_formed(self):
        kinds = {"secret", "reference", "pin", "allowlist", "flag", "config", "host", "runtime", "tooling"}
        for var in parity.CATALOG:
            with self.subTest(var=var.name):
                self.assertIn(var.kind, kinds)
                self.assertIn(var.scope, {"shared", "staging", "production", "local"})
                self.assertIn(var.parity, {"must_match", "allowed_difference", "staging_first", "informational"})
                if re.search(r"(PASSWORD|SECRET|API_KEY|_TOKEN$|DATABASE_URL|REDIS_URL)", var.name):
                    self.assertEqual(var.kind, "secret")


def _secret_environ():
    environ = {"RENDER_GIT_COMMIT": RELEASE, "RENDER_SERVICE_ID": parity.STAGING_SERVICE_ID, "RENDER": "true"}
    sentinels = {}
    for var in parity.CATALOG:
        if var.kind in ("secret", "reference", "tooling"):
            value = f"SENTINEL-{var.name}-9f8e7d"
            sentinels[var.name] = value
            environ[var.name] = value
        elif var.kind == "pin":
            environ[var.name] = OTHER
            sentinels[var.name] = OTHER
        elif var.kind == "allowlist":
            environ[var.name] = "424242,515151"
            sentinels[var.name] = "424242"
    return environ, sentinels


@override_settings(VORNEQ_ENV="staging", DEBUG=False)
class SnapshotTests(TestCase):
    databases = {"default", "ai_ledger"}

    def test_snapshot_never_contains_secret_values(self):
        environ, sentinels = _secret_environ()
        output = parity.dumps(parity.build_snapshot(environ))
        for name, value in sentinels.items():
            with self.subTest(var=name):
                self.assertNotIn(value, output)
        self.assertIn('"state": "PRESENT"', output)

    def test_pin_and_allowlist_are_reduced_to_status(self):
        environ = {"RENDER_GIT_COMMIT": RELEASE, "VORNEQ_AI_STAGING_AUTHORIZED_SHA": RELEASE,
                   "VORNEQ_AI_IMAGE_AUTHORIZED_SHA": OTHER, "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": "4,7"}
        variables = parity.build_snapshot(environ, include_database=False)["variables"]
        self.assertEqual(variables["VORNEQ_AI_STAGING_AUTHORIZED_SHA"]["value"], "MATCHES_RELEASE")
        self.assertEqual(variables["VORNEQ_AI_IMAGE_AUTHORIZED_SHA"]["value"], "MISMATCH")
        self.assertEqual(variables["VORNEQ_AI_STAGING_ALLOWED_USER_IDS"]["value"], 2)
        self.assertEqual(variables["OPENAI_API_KEY"]["state"], "MISSING")

    def test_snapshot_is_read_only(self):
        environ, _ = _secret_environ()
        with CaptureQueriesContext(connections["default"]) as queries:
            report = parity.build_snapshot(environ)
        self.assertEqual(report["status"], "COMPLETE", report["errors"])
        writes = [q["sql"] for q in queries.captured_queries
                  if not q["sql"].lstrip().upper().startswith(("SELECT", "PRAGMA", "SAVEPOINT", "RELEASE SAVEPOINT"))]
        self.assertEqual(writes, [])

    def test_missing_release_is_invalid_on_hosted_environments(self):
        report = parity.build_snapshot({}, include_database=False)
        self.assertEqual(report["status"], "INVALID")
        self.assertIn("release_unknown", report["errors"])

    def test_broken_section_fails_closed(self):
        from unittest import mock

        with mock.patch.object(parity, "_urls_section", side_effect=RuntimeError("secret detail")):
            report = parity.build_snapshot({"RENDER_GIT_COMMIT": RELEASE}, include_database=False)
        self.assertEqual(report["status"], "INVALID")
        self.assertEqual(report["urls"], {"error": "RuntimeError"})
        self.assertNotIn("secret detail", parity.dumps(report))

    def test_unreachable_database_alias_is_reported_per_alias(self):
        from unittest import mock

        from django.db.migrations import loader

        real = loader.MigrationLoader

        def fake(connection, *args, **kwargs):
            if connection.alias == "ai_ledger":
                raise RuntimeError("password=geheim")
            return real(connection, *args, **kwargs)

        with mock.patch.object(loader, "MigrationLoader", side_effect=fake):
            report = parity.build_snapshot({"RENDER_GIT_COMMIT": RELEASE})
        self.assertEqual(report["status"], "INVALID")
        self.assertIn("migrations.ai_ledger", report["errors"])
        self.assertEqual(report["migrations"]["ai_ledger"], {"error": "RuntimeError"})
        self.assertIn("applied_count", report["migrations"]["default"])
        self.assertNotIn("geheim", parity.dumps(report))

    def test_uncatalogued_variables_are_reported_by_name_only(self):
        report = parity.build_snapshot({"RENDER_GIT_COMMIT": RELEASE, "VORNEQ_OLD_FLAG": "geheim"}, include_database=False)
        self.assertEqual(report["uncatalogued_vorneq_variables"], ["VORNEQ_OLD_FLAG"])
        self.assertNotIn("geheim", parity.dumps(report))


@override_settings(VORNEQ_ENV="staging", DEBUG=False)
class CapabilityGateTests(SimpleTestCase):
    def _chat(self, environ):
        return parity._capabilities_section(environ, RELEASE)["ai_chat"]

    def test_staging_chat_disabled_lists_failing_predicates(self):
        chat = self._chat({"RENDER_SERVICE_ID": parity.STAGING_SERVICE_ID})
        self.assertEqual(chat["state"], "DISABLED")
        self.assertFalse(chat["predicates"]["trial_flag"])

    @override_settings(VORNEQ_AI_STAGING_TRIAL_ENABLED=True, VORNEQ_AI_CORE_ENABLED=True, VORNEQ_AI_PHASE_B_ENABLED=True)
    def test_staging_chat_enabled_when_all_static_gates_hold(self):
        environ = {
            "RENDER_SERVICE_ID": parity.STAGING_SERVICE_ID, "VORNEQ_AI_STAGING_AUTHORIZED_SHA": RELEASE,
            "VORNEQ_AI_STAGING_OWNER_AUTH": "x", "VORNEQ_AI_STAGING_APPROVED_MODEL": "m",
            "VORNEQ_AI_PHASE_B_MODEL": "m", "OPENAI_API_KEY": "k", "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": "1",
        }
        self.assertEqual(self._chat(environ)["state"], "ENABLED")

    @override_settings(VORNEQ_AI_STAGING_TRIAL_ENABLED=True, VORNEQ_AI_CORE_ENABLED=True,
                       VORNEQ_AI_PHASE_B_ENABLED=True, VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=True)
    def test_follow_mode_is_not_verified_offline(self):
        environ = {
            "RENDER_SERVICE_ID": parity.STAGING_SERVICE_ID, "VORNEQ_AI_STAGING_OWNER_AUTH": "x",
            "VORNEQ_AI_STAGING_APPROVED_MODEL": "m", "VORNEQ_AI_PHASE_B_MODEL": "m", "OPENAI_API_KEY": "k",
            "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": "1",
        }
        self.assertEqual(self._chat(environ)["state"], "NOT_VERIFIED")

    @override_settings(VORNEQ_AI_EMERGENCY_STOP=True)
    def test_emergency_stop_is_reported(self):
        caps = parity._capabilities_section({}, RELEASE)
        self.assertEqual(caps["ai_emergency_stop"]["state"], "ACTIVE")
        self.assertEqual(caps["ai_chat"]["state"], "DISABLED")


def _snapshot(env):
    return {
        "snapshot_version": parity.SNAPSHOT_VERSION, "status": "COMPLETE", "environment": env,
        "release": RELEASE, "errors": [],
        "settings": {"installed_apps": ["a"], "middleware": ["m"], "debug": False, "vorneq_env": env,
                     "allowed_hosts": [f"{env}.example"]},
        "platform_registry": {"apps": [{"slug": "notes", "reversible": True}], "problems": []},
        "urls": {"patterns_sha256": "x", "named_routes": ["home"]},
        "capabilities": {"ai_chat": {"state": "DISABLED"}, "ai_emergency_stop": {"state": "CLEAR"}},
        "variables": {"OPENAI_API_KEY": {"state": "PRESENT"}, "VORNEQ_AI_RESPONSE_V3_ENABLED": {"state": "PRESENT", "value": False}},
        "uncatalogued_vorneq_variables": [],
        "migrations": {"default": {"unapplied": [], "conflicts": {}, "applied_not_on_disk": []}},
        "system_data": {"groups": [], "permission_count": 1, "content_type_count": 1, "sites": []},
        "accounts": {"privileged_accounts": []},
    }


class CompareTests(SimpleTestCase):
    def setUp(self):
        self.staging, self.production = _snapshot("staging"), _snapshot("production")

    def groups(self, result, area=None):
        return {(f["group"], f["item"]) for f in result["findings"] if area is None or f["area"] == area}

    def test_identical_snapshots_are_parity(self):
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertEqual(result["status"], "PARITY", result["findings"])

    def test_feature_only_in_production_is_group_a(self):
        self.production["capabilities"]["ai_chat"]["state"] = "ENABLED"
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertEqual(result["status"], "DRIFT")
        self.assertIn(("A", "ai_chat"), self.groups(result))

    def test_feature_only_in_staging_is_group_c(self):
        self.staging["capabilities"]["ai_chat"]["state"] = "ENABLED"
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertEqual(result["status"], "PARITY")
        self.assertIn(("C", "ai_chat"), self.groups(result))

    def test_hosts_and_secrets_are_allowed_differences(self):
        self.production["variables"]["OPENAI_API_KEY"] = {"state": "MISSING"}
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertIn(("B", "allowed_hosts"), self.groups(result))
        self.assertIn(("B", "OPENAI_API_KEY"), self.groups(result))
        self.assertEqual(result["status"], "PARITY")

    def test_shared_flag_on_in_production_only_is_group_a(self):
        self.production["variables"]["VORNEQ_AI_RESPONSE_V3_ENABLED"] = {"state": "PRESENT", "value": True}
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertIn(("A", "VORNEQ_AI_RESPONSE_V3_ENABLED"), self.groups(result))

    def test_missing_registry_app_and_unapplied_migration_are_group_a(self):
        self.staging["platform_registry"]["apps"] = []
        self.staging["migrations"]["default"]["unapplied"] = ["notes.0002_x"]
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertIn(("A", "notes"), self.groups(result))
        self.assertIn(("A", "default.unapplied"), self.groups(result))

    def test_uncatalogued_variable_is_architecture_finding(self):
        self.production["uncatalogued_vorneq_variables"] = ["VORNEQ_OLD"]
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertIn(("D", "VORNEQ_OLD"), self.groups(result))
        self.assertEqual(result["status"], "DRIFT")

    def test_admin_profile_missing_in_staging_is_group_a(self):
        self.production["accounts"]["privileged_accounts"] = [{
            "pk": 3, "is_active": True, "is_superuser": True, "identity_active_human": True,
            "verified_primary_email": True, "allowlisted": ["ai_production"],
        }]
        self.staging["accounts"]["privileged_accounts"] = [{
            "pk": 9, "is_active": True, "is_superuser": True, "identity_active_human": False,
            "verified_primary_email": True, "allowlisted": [],
        }]
        result = parity.compare_snapshots(self.staging, self.production)
        self.assertTrue(any(g == "A" and item.startswith("superuser:ready") for g, item in self.groups(result, "accounts")))

    def test_invalid_or_mislabelled_snapshots_are_rejected(self):
        broken = copy.deepcopy(self.staging)
        broken["status"] = "INVALID"
        self.assertEqual(parity.compare_snapshots(broken, self.production)["status"], "INVALID")
        self.assertEqual(parity.compare_snapshots(self.production, self.staging)["status"], "INVALID")


class CommandTests(TestCase):
    databases = {"default", "ai_ledger"}

    def test_snapshot_command_prints_complete_json_locally(self):
        out = io.StringIO()
        call_command("audit_environment_parity", stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["environment"], settings.VORNEQ_ENV)

    def test_compare_command_exit_codes(self):
        staging, production = _snapshot("staging"), _snapshot("production")
        production["capabilities"]["ai_chat"]["state"] = "ENABLED"
        with tempfile.TemporaryDirectory() as folder:
            a, b = pathlib.Path(folder, "s.json"), pathlib.Path(folder, "p.json")
            a.write_text(json.dumps(staging)), b.write_text(json.dumps(production))
            with self.assertRaises(CommandError):
                call_command("audit_environment_parity", "--compare", str(a), str(b), stdout=io.StringIO())
            out = io.StringIO()
            call_command("audit_environment_parity", "--compare", str(a), str(b), "--allow-drift", stdout=out)
            self.assertEqual(json.loads(out.getvalue())["status"], "DRIFT")
            a.write_text("{broken")
            with self.assertRaises(CommandError):
                call_command("audit_environment_parity", "--compare", str(a), str(b), stdout=io.StringIO())

    def test_accounts_section_reports_roles_without_personal_data(self):
        user = get_user_model().objects.create_user(
            username="parity-admin", email="parity-admin@example.invalid", password="x-unused-123",
            is_staff=True, is_superuser=True,
        )
        identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name="Parity Admin")
        UserIdentity.objects.create(user=user, identity=identity)
        section = parity._accounts_section({"VORNEQ_AI_STAGING_ALLOWED_USER_IDS": str(user.pk)})
        account = section["privileged_accounts"][0]
        self.assertTrue(account["identity_bound"])
        self.assertTrue(account["identity_active_human"])
        self.assertEqual(account["allowlisted"], ["ai_staging"])
        dumped = parity.dumps(section)
        for personal in ("parity-admin", "example.invalid", "Parity Admin"):
            self.assertNotIn(personal, dumped)


class NavigationVisibilityTests(SimpleTestCase):
    def test_every_registered_app_resolves_in_all_languages(self):
        for lang in ("fa", "de", "en"):
            for manifest in registry.all():
                with self.subTest(lang=lang, app=manifest.slug), translation.override(lang):
                    self.assertTrue(reverse(manifest.url_name).startswith(f"/{lang}/"))
