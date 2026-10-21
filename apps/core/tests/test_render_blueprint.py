"""
Contract tests for the version-controlled Render blueprint (render.yaml).

The staging service must be bootable from render.yaml plus dashboard-managed
secrets alone. These tests read the blueprint as text so they need no YAML
dependency; they pin the env contract that config.settings enforces at boot.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase


REPO_ROOT = Path(__file__).resolve().parents[3]
BLUEPRINT = REPO_ROOT / "render.yaml"


def _env_vars(text):
    """Return {key: value-or-None} for each '- key:' entry under envVars."""
    entries = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        key_match = re.match(r"^- key:\s*(\S+)\s*$", line)
        if key_match:
            current = key_match.group(1)
            entries[current] = None
            continue
        value_match = re.match(r"^value:\s*(.+?)\s*$", line)
        if current and value_match:
            entries[current] = value_match.group(1).strip("\"'")
            continue
        if current and line.startswith("generateValue:"):
            entries[current] = "<generated>"
    return entries


class RenderBlueprintContractTests(SimpleTestCase):
    def setUp(self):
        self.text = BLUEPRINT.read_text(encoding="utf-8")
        self.env = _env_vars(self.text)

    def test_declares_valid_vorneq_env(self):
        self.assertIn("VORNEQ_ENV", self.env)
        self.assertEqual(self.env["VORNEQ_ENV"], "staging")

    def test_debug_is_disabled(self):
        self.assertEqual(self.env.get("DJANGO_DEBUG"), "False")

    def test_secret_key_is_generated_not_literal(self):
        self.assertEqual(self.env.get("DJANGO_SECRET_KEY"), "<generated>")

    def test_uses_render_settings_module(self):
        self.assertEqual(
            self.env.get("DJANGO_SETTINGS_MODULE"), "config.settings_render"
        )

    def test_deploy_never_runs_migrations(self):
        # Migrations are applied only through the guarded GitHub workflow.
        self.assertNotRegex(self.text, r"manage\.py\s+migrate\b")
