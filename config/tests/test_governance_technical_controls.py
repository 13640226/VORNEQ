"""Regression tests: technical safety controls survive the STOP_340 retirement.

The prospective retirement of the blanket procedural STOP_340
(docs/governance/OWNER_GLOBAL_STOP_RETIREMENT_PROPOSAL_V1_2026-11-15.md)
must not loosen any executable control. These tests read the repository
files statically; they never run a workflow, open a database connection or
call a provider.
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import re
import sys
from pathlib import Path
from unittest import mock

import yaml
from django.test import SimpleTestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(f"governance_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


db_target_guard = _script("db_target_guard")
merge_authorization = _script("merge_authorization")
WORKFLOWS = ROOT / ".github" / "workflows"

# Workflows that may write to a database and are disabled by the C02 hard stop.
C02_DISABLED_WORKFLOWS = (
    "migrate-staging.yml",
    "migrate-production-db.yml",
    "seed-staging.yml",
    "dr-staging-rehearsal.yml",
)
OWNER_LOGIN = "13640226"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # PyYAML parses the bare key ``on`` as boolean True.
    return workflow.get("on", workflow.get(True)) or {}


class C02DatabaseWorkflowHardStopTests(SimpleTestCase):
    def test_database_writing_workflows_stay_disabled(self):
        for name in C02_DISABLED_WORKFLOWS:
            with self.subTest(workflow=name):
                jobs = _load(name)["jobs"]
                self.assertTrue(jobs)
                for job_name, job in jobs.items():
                    self.assertEqual(
                        str(job.get("if", "")).replace(" ", ""),
                        "${{false}}",
                        f"{name}:{job_name} must remain disabled (C02 hard stop)",
                    )

    def test_database_workflows_have_no_automatic_trigger(self):
        for name in (*C02_DISABLED_WORKFLOWS, "migrate-production.yml"):
            with self.subTest(workflow=name):
                self.assertEqual(set(_triggers(_load(name))), {"workflow_dispatch"})


class ProductionMigrationSafeHoldTests(SimpleTestCase):
    def setUp(self):
        self.steps = _load("migrate-production.yml")["jobs"]["migrate"]["steps"]

    def _index(self, predicate) -> int:
        for index, step in enumerate(self.steps):
            if predicate(step):
                return index
        self.fail("expected step not found")

    def test_fail_closed_guard_runs_before_any_django_command(self):
        guard = self._index(lambda s: "db_target_guard.py guard" in str(s.get("run", "")))
        first_django = self._index(lambda s: "manage.py" in str(s.get("run", "")))
        self.assertLess(guard, first_django)

    def test_guard_step_never_allows_production_target(self):
        guard = self.steps[self._index(lambda s: "db_target_guard.py guard" in str(s.get("run", "")))]
        self.assertEqual(str(guard["env"]["ALLOW_PRODUCTION_TARGET"]).lower(), "false")
        self.assertNotIn("continue-on-error", guard)
        self.assertNotIn("if", guard)


class DbTargetGuardFailClosedTests(SimpleTestCase):
    def test_decide_denies_every_input_combination(self):
        for target, allow, confirmed in itertools.product((None, False, True), (False, True), (False, True)):
            with self.subTest(target=target, allow=allow, confirmed=confirmed):
                allowed, reason = db_target_guard.decide(target, allow, confirmed)
                self.assertIs(allowed, False)
                self.assertTrue(reason.startswith("REFUSING"))


class MergeAuthorizationOwnerBindingTests(SimpleTestCase):
    SHA = "a" * 40

    def _comment(self, login: str, association: str) -> dict:
        return {
            "id": 1,
            "user": {"login": login, "type": "User"},
            "author_association": association,
            "body": f"OWNER-AUTH-MERGE TEST-01 PR #1 @ {self.SHA}",
            "created_at": "2026-11-15T00:00:00Z",
            "updated_at": "2026-11-15T00:00:00Z",
        }

    def test_owner_login_is_repository_owner(self):
        self.assertEqual(merge_authorization.DEFAULT_OWNER_LOGIN, OWNER_LOGIN)

    def test_former_reviewer_account_cannot_authorize(self):
        decision = merge_authorization.decide(
            pr_number=1,
            head_sha=self.SHA,
            comments=[self._comment("hamidrezaasadian7-boop", "COLLABORATOR")],
        )
        self.assertFalse(decision.allowed)

    def test_owner_authorization_is_sha_bound(self):
        comments = [self._comment(OWNER_LOGIN, "OWNER")]
        self.assertTrue(merge_authorization.decide(pr_number=1, head_sha=self.SHA, comments=comments).allowed)
        self.assertFalse(merge_authorization.decide(pr_number=1, head_sha="b" * 40, comments=comments).allowed)


class CodeOwnersTests(SimpleTestCase):
    def test_code_owner_is_repository_owner_only(self):
        lines = [
            line.split()
            for line in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertTrue(lines)
        owners = {owner for parts in lines for owner in parts[1:]}
        self.assertEqual(owners, {f"@{OWNER_LOGIN}"})


class AIEmergencyStopIndependenceTests(SimpleTestCase):
    """The architectural STOP_340 and the runtime AI emergency stop are distinct."""

    SHA = "c" * 40
    MODEL = "synthetic-model"

    def _production_enabled(self, emergency_stop: bool) -> bool:
        from apps.ai_core import production_policy

        env = {
            "RENDER_SERVICE_ID": production_policy.EXPECTED_PRODUCTION_SERVICE_ID,
            "RENDER_GIT_COMMIT": self.SHA,
            "VORNEQ_AI_PHASE_B_MODEL": self.MODEL,
            "OPENAI_API_KEY": "synthetic-not-a-key",
        }
        with override_settings(
            VORNEQ_ENV="production",
            DEBUG=False,
            VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=True,
            VORNEQ_AI_EMERGENCY_STOP=emergency_stop,
            VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA=self.SHA,
            VORNEQ_AI_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-PRODUCTION-SYNTHETIC-01",
            VORNEQ_AI_PRODUCTION_APPROVED_MODEL=self.MODEL,
        ), mock.patch.dict(os.environ, env), mock.patch.object(
            production_policy, "recovery_enabled", return_value=True
        ), mock.patch.object(production_policy, "ledger_enabled", return_value=True):
            return production_policy.production_enabled()

    def test_emergency_stop_alone_disables_otherwise_enabled_production_ai(self):
        self.assertTrue(self._production_enabled(emergency_stop=False))
        self.assertFalse(self._production_enabled(emergency_stop=True))

    def test_retirement_policy_keeps_emergency_stop(self):
        text = (ROOT / "docs" / "governance" / "OWNER_GLOBAL_STOP_RETIREMENT_PROPOSAL_V1_2026-11-15.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("VORNEQ_AI_EMERGENCY_STOP", text)
        self.assertRegex(text, re.compile(r"db_target_guard\.py`? fail-closed", re.I))
