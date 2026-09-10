"""
Tests for VORNEQ_ENV environment classification (ADR-018 D1).

All scenarios exercise the real config.settings import path in a fresh
interpreter. No validation rules are mirrored in the test suite.
"""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class VorneqEnvBootTests(SimpleTestCase):
    REPO_ROOT = Path(__file__).resolve().parents[3]
    BOOT_COMMAND = [
        sys.executable,
        "-c",
        "import logging; logging.basicConfig(level=logging.WARNING); import config.settings",
    ]

    def _boot(self, *, env_value=None, debug_value=None):
        env = os.environ.copy()
        env.pop("VORNEQ_ENV", None)
        env.pop("DJANGO_DEBUG", None)

        if env_value is not None:
            env["VORNEQ_ENV"] = env_value
        if debug_value is not None:
            env["DJANGO_DEBUG"] = debug_value

        return subprocess.run(
            self.BOOT_COMMAND,
            cwd=self.REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def _assert_improperly_configured(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)

    def test_development_with_debug_true_succeeds(self):
        result = self._boot(env_value="development", debug_value="True")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_staging_with_debug_false_succeeds(self):
        result = self._boot(env_value="staging", debug_value="False")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_staging_with_debug_true_succeeds_with_warning(self):
        result = self._boot(env_value="staging", debug_value="True")
        self.assertEqual(result.returncode, 0, result.stderr)
        stderr_lower = result.stderr.lower()
        self.assertIn("warning", stderr_lower)
        self.assertIn("staging", stderr_lower)

    def test_production_with_debug_false_succeeds(self):
        result = self._boot(env_value="production", debug_value="False")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_with_debug_true_fails(self):
        result = self._boot(env_value="production", debug_value="True")
        self._assert_improperly_configured(result)
        self.assertIn("production", result.stderr)
        self.assertIn("DEBUG", result.stderr)

    def test_unset_env_fails(self):
        result = self._boot(env_value=None, debug_value="True")
        self._assert_improperly_configured(result)
        self.assertIn("unset", result.stderr)

    def test_empty_env_fails(self):
        result = self._boot(env_value="", debug_value="True")
        self._assert_improperly_configured(result)
        self.assertIn("unset", result.stderr)

    def test_invalid_env_fails(self):
        result = self._boot(env_value="invalid", debug_value="True")
        self._assert_improperly_configured(result)
        self.assertIn("invalid", result.stderr)

    def test_capitalized_env_fails(self):
        result = self._boot(env_value="Production", debug_value="False")
        self._assert_improperly_configured(result)
        self.assertIn("invalid", result.stderr)
