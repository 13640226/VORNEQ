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


class BlueprintLayoutError(AssertionError):
    """render.yaml no longer has the layout this text reader understands."""


def _env_vars(text):
    """Return {key: value} for the block-style ``envVars:`` list.

    Deliberately strict: anything outside the expected block layout (a second
    envVars section, flow-style ``{...}``/``[...]``, an unknown field, a value
    before its key) raises BlueprintLayoutError instead of being skipped, so a
    restructured blueprint fails loudly rather than being misread.
    """
    lines = text.splitlines()
    starts = [i for i, raw in enumerate(lines) if raw.strip() == "envVars:"]
    if len(starts) != 1:
        raise BlueprintLayoutError(
            f"Expected exactly one block-style 'envVars:' section, found {len(starts)}."
        )

    start = starts[0]
    section_indent = len(lines[start]) - len(lines[start].lstrip())
    entries = {}
    current = None

    for number, raw in enumerate(lines[start + 1:], start=start + 2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= section_indent:
            break  # left the envVars section
        if line[0] in "{[" or line.endswith(("{", "[")):
            raise BlueprintLayoutError(f"Flow-style YAML is not supported (line {number}).")

        key_match = re.fullmatch(r"- key:\s*([A-Za-z_][A-Za-z0-9_]*)", line)
        if key_match:
            current = key_match.group(1)
            if current in entries:
                raise BlueprintLayoutError(f"Duplicate env var {current} (line {number}).")
            entries[current] = None
            continue
        if current is None:
            raise BlueprintLayoutError(f"Field before any '- key:' entry (line {number}).")

        field_match = re.fullmatch(r"(value|generateValue|sync):\s*(.+)", line)
        if not field_match:
            raise BlueprintLayoutError(f"Unrecognised envVars field (line {number}): {line}")
        field, raw_value = field_match.groups()
        if field == "value":
            entries[current] = raw_value.strip().strip("\"'")
        elif field == "generateValue":
            entries[current] = "<generated>"
        else:
            entries[current] = "<dashboard>"

    if not entries:
        raise BlueprintLayoutError("'envVars:' section contains no entries.")
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


class EnvVarsReaderTests(SimpleTestCase):
    """The reader must refuse layouts it cannot read, never guess."""

    def _yaml(self, body):
        return "services:\n  - type: web\n    envVars:\n" + body + "    plan: free\n"

    def test_reads_value_generated_and_dashboard_fields(self):
        env = _env_vars(self._yaml(
            "      - key: A\n        value: \"x\"\n"
            "      - key: B\n        generateValue: true\n"
            "      - key: C\n        sync: false\n"
        ))
        self.assertEqual(env, {"A": "x", "B": "<generated>", "C": "<dashboard>"})

    def test_stops_at_end_of_section(self):
        env = _env_vars(self._yaml("      - key: A\n        value: x\n"))
        self.assertEqual(env, {"A": "x"})

    def test_rejects_missing_section(self):
        with self.assertRaises(BlueprintLayoutError):
            _env_vars("services:\n  - type: web\n")

    def test_rejects_two_sections(self):
        text = self._yaml("      - key: A\n        value: x\n") * 2
        with self.assertRaises(BlueprintLayoutError):
            _env_vars(text)

    def test_rejects_flow_style(self):
        with self.assertRaises(BlueprintLayoutError):
            _env_vars(self._yaml("      - {key: A, value: x}\n"))

    def test_rejects_unknown_field(self):
        with self.assertRaises(BlueprintLayoutError):
            _env_vars(self._yaml("      - key: A\n        fromGroup: shared\n"))

    def test_rejects_duplicate_key(self):
        with self.assertRaises(BlueprintLayoutError):
            _env_vars(self._yaml(
                "      - key: A\n        value: x\n      - key: A\n        value: y\n"
            ))
