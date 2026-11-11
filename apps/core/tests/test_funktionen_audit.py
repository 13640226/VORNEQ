import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.core.services.funktionen_audit import (
    TOOL_LIMITATIONS,
    TOOL_VERSION,
    VERIFICATION_METHODS,
    build_report,
    duplicate_headings,
    scan_index,
    scan_post_forms,
    validate_report,
)

SAMPLE_INDEX = """<main>
<section id="capabilities">
  <ul>
    <li><a href="{% url 'discover' %}"><h3>{% trans "Discover" %}</h3></a></li>
  </ul>
</section>
<section id="how-it-works">
  <ol>
    <li class="world-flow__step">
      <h3>{% trans "Collect" %}</h3>
      <a class="world-flow__action" href="{% url 'search_page' %}">x</a>
    </li>
    <li class="world-flow__step">
      <h3>{% trans "Connect" %}</h3>
      <p>no action</p>
    </li>
    <li class="world-flow__step">
      <h3>{% trans "Discover" %}</h3>
      <a class="world-flow__action" href="{% url 'discover' %}">x</a>
    </li>
  </ol>
</section>
</main>
"""


def _report_for(files):
    """Build a report from {relative path: text} in an isolated temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        templates = Path(tmp) / "templates"
        templates.mkdir()
        for name, text in files.items():
            target = templates / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        before = sorted(str(p) for p in Path(tmp).rglob("*"))
        report = build_report(templates, release="unknown")
        after = sorted(str(p) for p in Path(tmp).rglob("*"))
    assert before == after, "build_report must not create files"
    return report


def _results(report):
    return {f["result"] for f in report["findings"]}


class ScanIndexTests(SimpleTestCase):
    def test_only_flow_section_cards_are_collected(self):
        cards = scan_index(SAMPLE_INDEX).cards
        self.assertEqual([c.title for c in cards], ["Collect", "Connect", "Discover"])

    def test_duplicate_heading_resolves_to_flow_card(self):
        scanner = scan_index(SAMPLE_INDEX)
        discover = scanner.cards[2]
        self.assertEqual(discover.heading_line, 18)
        self.assertEqual(discover.route_names, ["discover"])
        dup = duplicate_headings(scanner.headings)["discover"]
        self.assertEqual([h.section_id for h in dup], ["capabilities", "how-it-works"])

    def test_card_without_link(self):
        cards = scan_index(SAMPLE_INDEX).cards
        self.assertFalse(cards[1].has_action_link)
        self.assertEqual(cards[1].route_names, [])

    def test_multi_line_heading(self):
        text = (
            '<section id="how-it-works"><ol><li class="world-flow__step">\n'
            "<h3>\n  {% trans \"Collect\" %}\n</h3>\n</li></ol></section>"
        )
        card = scan_index(text).cards[0]
        self.assertEqual((card.title, card.heading_line), ("Collect", 2))

    def test_link_does_not_imply_http_method(self):
        card = scan_index(SAMPLE_INDEX).cards[0]
        self.assertEqual(card.link_evidence, "LINK_PRESENCE_ONLY")
        self.assertFalse(hasattr(card, "http_methods"))


class ScanPostFormTests(SimpleTestCase):
    def test_csrf_and_action_route(self):
        text = (
            '<form method="get" action="/s"></form>\n'
            "<form method='POST' action=\"{% url 'inspect_entry' %}\">\n"
            "  {% csrf_token %}\n"
            "</form>\n"
            "<form method=post>\n</form>\n"
        )
        forms = scan_post_forms(text, "t.html")
        self.assertEqual(len(forms), 2)
        self.assertEqual((forms[0].line_start, forms[0].line_end), (2, 4))
        self.assertTrue(forms[0].has_csrf)
        self.assertEqual(forms[0].action_route, "inspect_entry")
        self.assertFalse(forms[1].has_csrf)
        self.assertIsNone(forms[1].action_route)

    def test_unclosed_form_does_not_borrow_next_forms_csrf(self):
        text = '<form method="post">\n<form method="post">{% csrf_token %}</form>'
        forms = scan_post_forms(text, "t.html")
        self.assertFalse(forms[0].closed)
        self.assertFalse(forms[0].has_csrf)
        self.assertTrue(forms[1].has_csrf)


class NegativeCaseTests(SimpleTestCase):
    def test_missing_index_file(self):
        report = _report_for({})
        self.assertEqual(report["status"], "INCOMPLETE")
        precond = [f for f in report["findings"] if f["id"] == "F-PRECOND-01"]
        self.assertEqual(len(precond), 1)
        self.assertEqual(precond[0]["result"], "INPUT_FILE_MISSING")
        self.assertEqual(precond[0]["verification_method"], "PRECONDITION_CHECK")

    def test_missing_templates_directory(self):
        report = build_report(Path(tempfile.gettempdir()) / "vorneq-no-such-dir", release="unknown")
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("INPUT_FILE_MISSING", _results(report))

    def test_malformed_markup_is_flagged_not_trusted(self):
        broken = '<section id="how-it-works"><ol><li class="world-flow__step"><h3>{% trans "Collect" %}'
        report = _report_for({"index.html": broken})
        self.assertIn("CARD_NOT_CLOSED", _results(report))
        self.assertTrue(report["cards"][0]["heuristic"])
        self.assertEqual(report["cards"][0]["verification_method"], "HEURISTIC_TEMPLATE_SCAN")

    def test_missing_flow_section(self):
        report = _report_for({"index.html": "<main><h3>Collect</h3></main>"})
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("FLOW_SECTION_NOT_FOUND", _results(report))

    def test_missing_cards(self):
        report = _report_for({"index.html": '<section id="how-it-works"><ol></ol></section>'})
        self.assertIn("NO_CARDS_FOUND", _results(report))

    def test_post_form_without_csrf(self):
        report = _report_for({"index.html": SAMPLE_INDEX, "sub/form.html": '<form method="post"></form>'})
        ids = [f["id"] for f in report["findings"]]
        self.assertIn("F-POST-NO-CSRF-templates/sub/form.html:1", ids)
        self.assertEqual(report["status"], "COMPLETE")

    def test_include_is_reported_not_treated_as_absent(self):
        text = '<section id="how-it-works">\n{% include "partials/flow.html" %}\n</section>'
        report = _report_for({"index.html": text})
        self.assertIn("INCLUDE_NOT_TRAVERSED", _results(report))
        self.assertNotIn("NO_CARDS_FOUND", _results(report))

    def test_unresolved_route_is_explicit(self):
        text = (
            '<section id="how-it-works"><ol><li class="world-flow__step"><h3>X</h3>'
            "<a href=\"{% url 'no_such_route_name' %}\">x</a></li></ol></section>"
        )
        report = _report_for({"index.html": text})
        self.assertEqual(report["routes"][0]["result"], "ROUTE_NOT_RESOLVED_BY_TOOL")
        self.assertIn("ROUTE_NOT_RESOLVED_BY_TOOL", _results(report))


class SelfReportingTests(SimpleTestCase):
    def test_metadata_limitations_and_meta_finding(self):
        report = _report_for({"index.html": SAMPLE_INDEX})
        meta = report["tool_metadata"]
        self.assertEqual(meta["version"], TOOL_VERSION)
        self.assertEqual(meta["scope"], "STRICT_READ_ONLY")
        self.assertEqual(meta["known_limitations"], [lim.id for lim in TOOL_LIMITATIONS])
        self.assertEqual(set(meta["verification_methods_supported"]), VERIFICATION_METHODS)
        self.assertEqual(len(report["tool_limitations"]), len(TOOL_LIMITATIONS))
        tool = [f for f in report["findings"] if f["id"] == "F-TOOL-00"]
        self.assertEqual(len(tool), 1)
        self.assertEqual(tool[0]["result"], "TOOL_SELF_AUDIT")

    def test_validate_rejects_unknown_method(self):
        report = _report_for({"index.html": SAMPLE_INDEX})
        self.assertEqual(validate_report(report), [])
        report["findings"][0]["verification_method"] = "GUESSED"
        self.assertTrue(validate_report(report))


class AuditCommandTests(SimpleTestCase):
    def test_command_fails_closed_after_homepage_v2_removed_flow_section(self):
        # Homepage V2 removed the "How VORNEQ works" section by owner request.
        # The audit must not report COMPLETE for cards that no longer exist.
        with self.assertRaises(CommandError):
            call_command("audit_funktionen", stdout=StringIO())

    def test_command_fails_on_incomplete_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CommandError):
                call_command("audit_funktionen", templates_dir=tmp, stdout=StringIO())
