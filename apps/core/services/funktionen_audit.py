"""Read-only static audit of the "How VORNEQ works" (Funktionen) cards.

The audit reads templates and resolves URL names through Django's URL
resolver. It never writes files, never touches the database, and never sends
network requests. The report is a plain dictionary meant for stdout only.

Every observation carries a ``verification_method`` from a closed set and a
``heuristic`` flag. A heuristic observation is a hint, not proof that a
capability exists or works. The tool reports its own known limitations in
``tool_limitations`` and in the meta finding ``F-TOOL-00``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path

TOOL_VERSION = "1.1.0"
REPORT_SCHEMA_VERSION = 1

FLOW_SECTION_ID = "how-it-works"
FLOW_STEP_CLASS = "world-flow__step"

STATIC_TEMPLATE_SCAN = "STATIC_TEMPLATE_SCAN"
HEURISTIC_TEMPLATE_SCAN = "HEURISTIC_TEMPLATE_SCAN"
REGEX_MATCH = "REGEX_MATCH"
LINK_PRESENCE_ONLY = "LINK_PRESENCE_ONLY"
PRECONDITION_CHECK = "PRECONDITION_CHECK"
DJANGO_URL_RESOLVER = "DJANGO_URL_RESOLVER"
SCHEMA_CHECK = "SCHEMA_CHECK"

VERIFICATION_METHODS = frozenset(
    {
        STATIC_TEMPLATE_SCAN,
        HEURISTIC_TEMPLATE_SCAN,
        REGEX_MATCH,
        LINK_PRESENCE_ONLY,
        PRECONDITION_CHECK,
        DJANGO_URL_RESOLVER,
        SCHEMA_CHECK,
    }
)
SEVERITIES = frozenset({"INFO", "REVIEW_REQUIRED", "ERROR"})

TRANS_RE = re.compile(r"""{%\s*(?:trans|translate)\s+(['"])(.*?)\1""", re.DOTALL)
URL_TAG_RE = re.compile(r"""{%\s*url\s+(['"])([\w:\-]+)\1""")
INCLUDE_RE = re.compile(r"""{%\s*include\s+(['"])(.*?)\1""")
FORM_OPEN_RE = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
FORM_CLOSE_RE = re.compile(r"</form\s*>", re.IGNORECASE)
METHOD_POST_RE = re.compile(r"""\bmethod\s*=\s*(['"]?)post\1""", re.IGNORECASE)
CSRF_RE = re.compile(r"{%\s*csrf_token\s*%}")
ACTION_RE = re.compile(r"""\baction\s*=\s*(['"])(.*?)\1""", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class ToolLimitation:
    id: str
    description: str
    impact: str
    support_status: str


TOOL_LIMITATIONS = (
    ToolLimitation(
        id="LIM-01-INCLUDE-NOT-TRAVERSED",
        description="{% include %} partials inside the flow section are not opened when collecting cards.",
        impact="Cards rendered from a partial are not listed; each include is reported as a "
        "REVIEW_REQUIRED finding instead, so absence is never claimed.",
        support_status="NOT_IMPLEMENTED",
    ),
    ToolLimitation(
        id="LIM-02-FORMS-REGEX",
        description="POST form boundaries are found with regular expressions, not a full HTML parser.",
        impact="Invalid or unusual form markup (nested forms, '>' inside attributes, forms "
        "built across template blocks) may be misparsed; unclosed forms are reported.",
        support_status="PARTIAL",
    ),
    ToolLimitation(
        id="LIM-03-CARD-STRUCTURE",
        description=f"Cards are recognised only as <li class=\"{FLOW_STEP_CLASS}\"> inside "
        f"<section id=\"{FLOW_SECTION_ID}\">.",
        impact="A markup change that renames these hooks makes the tool find no cards; this "
        "is reported as an ERROR finding, not as success.",
        support_status="BY_DESIGN",
    ),
    ToolLimitation(
        id="LIM-04-POST-HANDLING-TEXT-MATCH",
        description="Whether a view handles POST is inferred from the literal string \"POST\" in its source.",
        impact="Heuristic only; decorators, class-based dispatch or indirection are not analysed.",
        support_status="HEURISTIC",
    ),
    ToolLimitation(
        id="LIM-05-NO-JSON-SCHEMA",
        description="The report is checked by a built-in structural check, not by a formal JSON Schema.",
        impact="Field names, types and closed value sets are enforced; nothing beyond that.",
        support_status="PARTIAL",
    ),
    ToolLimitation(
        id="LIM-06-LINK-IS-NOT-METHOD",
        description="A link on a card shows navigation presence only.",
        impact="No HTTP method, permission or working endpoint is inferred from a link.",
        support_status="BY_DESIGN",
    ),
)


@dataclass
class FlowCard:
    position: int
    title: str
    line_start: int
    line_end: int
    heading_line: int
    route_names: list[str] = field(default_factory=list)
    has_action_link: bool = False
    link_evidence: str = LINK_PRESENCE_ONLY
    verification_method: str = STATIC_TEMPLATE_SCAN
    heuristic: bool = False
    closed: bool = True


@dataclass
class Heading:
    title: str
    line: int
    section_id: str | None


@dataclass
class PostForm:
    template: str
    line_start: int
    line_end: int
    has_csrf: bool
    action_route: str | None
    closed: bool = True
    verification_method: str = REGEX_MATCH
    heuristic: bool = True


def _heading_text(raw: str) -> str:
    match = TRANS_RE.search(raw)
    if match:
        return " ".join(match.group(2).split())
    return " ".join(raw.split())


class _TemplateScanner(HTMLParser):
    """Collect <h3> headings with their enclosing section, flow cards and includes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.headings: list[Heading] = []
        self.cards: list[FlowCard] = []
        self.flow_section_found = False
        self.flow_includes: list[tuple[int, str]] = []
        self._section_stack: list[str | None] = []
        self._in_h3 = False
        self._h3_line = 0
        self._h3_text: list[str] = []
        self._card: FlowCard | None = None
        self._li_depth = 0

    @property
    def _section(self) -> str | None:
        for section_id in reversed(self._section_stack):
            if section_id:
                return section_id
        return None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        line = self.getpos()[0]
        if tag == "section":
            self._section_stack.append(attrs.get("id"))
            if attrs.get("id") == FLOW_SECTION_ID:
                self.flow_section_found = True
        elif tag == "li":
            if self._card is not None:
                self._li_depth += 1
            elif self._section == FLOW_SECTION_ID and FLOW_STEP_CLASS in (attrs.get("class") or "").split():
                self._card = FlowCard(
                    position=len(self.cards) + 1, title="", line_start=line, line_end=line, heading_line=0
                )
                self._li_depth = 0
        elif tag == "h3":
            self._in_h3 = True
            self._h3_line = line
            self._h3_text = []
        elif tag == "a" and self._card is not None:
            href = attrs.get("href") or ""
            match = URL_TAG_RE.search(href)
            if match:
                self._card.route_names.append(match.group(2))
            if href:
                self._card.has_action_link = True

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag == "section" and self._section_stack:
            self._section_stack.pop()
        elif tag == "h3" and self._in_h3:
            self._finish_heading()
        elif tag == "li" and self._card is not None:
            if self._li_depth:
                self._li_depth -= 1
            else:
                self._card.line_end = line
                self.cards.append(self._card)
                self._card = None

    def handle_data(self, data):
        if self._in_h3:
            self._h3_text.append(data)
        if self._section == FLOW_SECTION_ID:
            line = self.getpos()[0]
            for match in INCLUDE_RE.finditer(data):
                self.flow_includes.append((line + data.count("\n", 0, match.start()), match.group(2)))

    def _finish_heading(self):
        self._in_h3 = False
        title = _heading_text("".join(self._h3_text))
        self.headings.append(Heading(title=title, line=self._h3_line, section_id=self._section))
        if self._card is not None and not self._card.title:
            self._card.title = title
            self._card.heading_line = self._h3_line

    def close(self):
        super().close()
        if self._in_h3:
            self._finish_heading()
        if self._card is not None:
            # The card's </li> never arrived: keep what was seen, flag it.
            self._card.closed = False
            self._card.heuristic = True
            self._card.verification_method = HEURISTIC_TEMPLATE_SCAN
            self._card.line_end = self.getpos()[0]
            self.cards.append(self._card)
            self._card = None


def scan_index(text: str) -> _TemplateScanner:
    scanner = _TemplateScanner()
    scanner.feed(text)
    scanner.close()
    return scanner


def duplicate_headings(headings: list[Heading]) -> dict[str, list[Heading]]:
    by_title: dict[str, list[Heading]] = {}
    for heading in headings:
        by_title.setdefault(heading.title.casefold(), []).append(heading)
    return {key: items for key, items in by_title.items() if len(items) > 1}


def scan_post_forms(text: str, template: str) -> list[PostForm]:
    forms: list[PostForm] = []
    openings = list(FORM_OPEN_RE.finditer(text))
    for index, opening in enumerate(openings):
        if not METHOD_POST_RE.search(opening.group(0)):
            continue
        next_open = openings[index + 1].start() if index + 1 < len(openings) else len(text)
        closing = FORM_CLOSE_RE.search(text, opening.end(), next_open)
        end = closing.end() if closing else next_open
        body = text[opening.end():end]
        action = ACTION_RE.search(opening.group(0))
        route = None
        if action:
            url = URL_TAG_RE.search(action.group(2))
            route = url.group(2) if url else None
        forms.append(
            PostForm(
                template=template,
                line_start=text.count("\n", 0, opening.start()) + 1,
                line_end=text.count("\n", 0, end) + 1,
                has_csrf=bool(CSRF_RE.search(body)),
                action_route=route,
                closed=closing is not None,
            )
        )
    return forms


def resolve_route(name: str) -> dict:
    """Resolve a URL name through Django's URL resolver (no request is made).

    Includes, namespaces and i18n prefixes are followed by Django itself. An
    unresolved name is reported explicitly; that is not proof the route is absent.
    """
    import inspect

    from django.urls import NoReverseMatch, resolve, reverse

    try:
        path = reverse(name)
    except NoReverseMatch:
        return {
            "route": name,
            "resolved": False,
            "result": "ROUTE_NOT_RESOLVED_BY_TOOL",
            "verification_method": DJANGO_URL_RESOLVER,
            "heuristic": False,
        }
    func = resolve(path).func
    target = getattr(func, "view_class", func)
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        source = ""
    return {
        "route": name,
        "resolved": True,
        "result": "ROUTE_RESOLVED",
        "path": path,
        "view": f"{target.__module__}.{target.__qualname__}",
        "verification_method": DJANGO_URL_RESOLVER,
        "heuristic": False,
        "view_source_mentions_post": {
            "value": '"POST"' in source or "'POST'" in source,
            "verification_method": REGEX_MATCH,
            "heuristic": True,
        },
    }


def _finding(finding_id, severity, method, result, summary, locations, heuristic=False):
    return {
        "id": finding_id,
        "severity": severity,
        "verification_method": method,
        "heuristic": heuristic,
        "result": result,
        "summary": summary,
        "locations": locations,
    }


def _tool_metadata() -> dict:
    return {
        "version": TOOL_VERSION,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "scope": "STRICT_READ_ONLY",
        "writes": "none (stdout only)",
        "database_access": "none",
        "network_access": "none",
        "known_limitations": [limitation.id for limitation in TOOL_LIMITATIONS],
        "verification_methods_supported": sorted(VERIFICATION_METHODS),
    }


def build_report(templates_dir: Path, release: str) -> dict:
    templates_dir = Path(templates_dir)
    index_path = templates_dir / "index.html"
    findings: list[dict] = []
    cards: list[FlowCard] = []
    routes: list[dict] = []
    post_forms: list[PostForm] = []

    if not templates_dir.is_dir():
        findings.append(
            _finding(
                "F-PRECOND-01", "ERROR", PRECONDITION_CHECK, "INPUT_FILE_MISSING",
                "Templates directory is missing.", [{"path": str(templates_dir)}],
            )
        )
    elif not index_path.is_file():
        findings.append(
            _finding(
                "F-PRECOND-01", "ERROR", PRECONDITION_CHECK, "INPUT_FILE_MISSING",
                "templates/index.html is missing.", [{"path": str(index_path)}],
            )
        )

    if index_path.is_file():
        scanner = scan_index(index_path.read_text(encoding="utf-8"))
        cards = scanner.cards
        if not scanner.flow_section_found:
            findings.append(
                _finding(
                    "F-FLOW-SECTION-MISSING", "ERROR", STATIC_TEMPLATE_SCAN, "FLOW_SECTION_NOT_FOUND",
                    f"No <section id=\"{FLOW_SECTION_ID}\"> in templates/index.html.", [],
                )
            )
        elif not cards and not scanner.flow_includes:
            findings.append(
                _finding(
                    "F-FLOW-CARDS-MISSING", "ERROR", STATIC_TEMPLATE_SCAN, "NO_CARDS_FOUND",
                    f"Flow section has no <li class=\"{FLOW_STEP_CLASS}\"> cards.", [],
                )
            )
        for line, partial in scanner.flow_includes:
            findings.append(
                _finding(
                    f"F-INCLUDE-{line}", "REVIEW_REQUIRED", STATIC_TEMPLATE_SCAN, "INCLUDE_NOT_TRAVERSED",
                    f"Flow section includes {partial!r}; cards inside it are not inspected "
                    "and must not be treated as absent.",
                    [{"line": line, "section": FLOW_SECTION_ID}],
                )
            )
        for title, items in sorted(duplicate_headings(scanner.headings).items()):
            findings.append(
                _finding(
                    f"F-DUP-HEADING-{title.upper().replace(' ', '-')}", "INFO", STATIC_TEMPLATE_SCAN,
                    "DUPLICATE_HEADING",
                    "Heading text appears more than once in templates/index.html; "
                    "text-only matching would pick the wrong card.",
                    [{"line": h.line, "section": h.section_id} for h in items],
                )
            )
        for card in cards:
            location = [{"line": card.line_start, "section": FLOW_SECTION_ID}]
            if not card.closed:
                findings.append(
                    _finding(
                        f"F-CARD-UNCLOSED-{card.position:02d}", "REVIEW_REQUIRED", HEURISTIC_TEMPLATE_SCAN,
                        "CARD_NOT_CLOSED", "Card <li> is never closed; its line range is a guess.",
                        location, heuristic=True,
                    )
                )
            if not card.title:
                findings.append(
                    _finding(
                        f"F-CARD-NO-HEADING-{card.position:02d}", "REVIEW_REQUIRED", STATIC_TEMPLATE_SCAN,
                        "CARD_WITHOUT_HEADING", "Card has no <h3> heading.", location,
                    )
                )
            if not card.has_action_link:
                findings.append(
                    _finding(
                        f"F-CARD-NO-ACTION-{card.position:02d}", "INFO", LINK_PRESENCE_ONLY,
                        "NO_ACTION_LINK", f"Flow card {card.title!r} has no action link.", location,
                    )
                )
        route_names = sorted({name for card in cards for name in card.route_names})
        routes = [resolve_route(name) for name in route_names]
        for route in routes:
            if not route["resolved"]:
                findings.append(
                    _finding(
                        f"F-ROUTE-UNRESOLVED-{route['route']}", "REVIEW_REQUIRED", DJANGO_URL_RESOLVER,
                        "ROUTE_NOT_RESOLVED_BY_TOOL",
                        "URL name used on a card could not be reversed.", [{"route": route["route"]}],
                    )
                )

    if templates_dir.is_dir():
        for path in sorted(templates_dir.rglob("*.html")):
            relative = path.relative_to(templates_dir.parent).as_posix()
            post_forms.extend(scan_post_forms(path.read_text(encoding="utf-8"), relative))
    for form in post_forms:
        location = [{"template": form.template, "line": form.line_start}]
        if not form.has_csrf:
            findings.append(
                _finding(
                    f"F-POST-NO-CSRF-{form.template}:{form.line_start}", "REVIEW_REQUIRED", REGEX_MATCH,
                    "POST_WITHOUT_CSRF", "POST form without {% csrf_token %} inside the form body.",
                    location, heuristic=True,
                )
            )
        if not form.closed:
            findings.append(
                _finding(
                    f"F-POST-UNCLOSED-{form.template}:{form.line_start}", "REVIEW_REQUIRED", REGEX_MATCH,
                    "FORM_NOT_CLOSED", "POST form has no closing </form> before the next form.",
                    location, heuristic=True,
                )
            )

    findings.append(
        _finding(
            "F-TOOL-00", "INFO", PRECONDITION_CHECK, "TOOL_SELF_AUDIT",
            f"Tool version {TOOL_VERSION}, {len(TOOL_LIMITATIONS)} known limitations. "
            "This records the tool's own state; it is not a security approval.",
            [],
        )
    )

    report = {
        "tool_metadata": _tool_metadata(),
        "tool_limitations": [asdict(limitation) for limitation in TOOL_LIMITATIONS],
        "release": release,
        "flow_section": FLOW_SECTION_ID,
        "cards": [asdict(card) for card in cards],
        "routes": routes,
        "post_forms": [asdict(form) for form in post_forms],
        "findings": findings,
    }
    errors = validate_report(report)
    if errors:
        report["findings"].append(
            _finding(
                "F-SCHEMA-01", "ERROR", SCHEMA_CHECK, "REPORT_INVALID",
                "Report failed the structural check.", [{"error": e} for e in errors],
            )
        )
    report["status"] = (
        "INCOMPLETE" if any(f["severity"] == "ERROR" for f in report["findings"]) else "COMPLETE"
    )
    return report


_REQUIRED_KEYS = {
    "report": {"tool_metadata", "tool_limitations", "release", "flow_section", "cards", "routes",
               "post_forms", "findings"},
    "finding": {"id", "severity", "verification_method", "heuristic", "result", "summary", "locations"},
    "card": {"position", "title", "line_start", "line_end", "heading_line", "route_names",
             "has_action_link", "verification_method", "heuristic", "closed"},
    "route": {"route", "resolved", "result", "verification_method", "heuristic"},
    "post_form": {"template", "line_start", "line_end", "has_csrf", "action_route", "closed",
                  "verification_method", "heuristic"},
}


def validate_report(report: dict) -> list[str]:
    """Structural check of the report: required keys, closed value sets, types."""
    errors: list[str] = []
    missing = _REQUIRED_KEYS["report"] - report.keys()
    if missing:
        return [f"report: missing {sorted(missing)}"]
    for kind, items in (("finding", report["findings"]), ("card", report["cards"]),
                        ("route", report["routes"]), ("post_form", report["post_forms"])):
        for index, item in enumerate(items):
            missing = _REQUIRED_KEYS[kind] - item.keys()
            if missing:
                errors.append(f"{kind}[{index}]: missing {sorted(missing)}")
                continue
            if item["verification_method"] not in VERIFICATION_METHODS:
                errors.append(f"{kind}[{index}]: unknown verification_method {item['verification_method']!r}")
            if not isinstance(item["heuristic"], bool):
                errors.append(f"{kind}[{index}]: heuristic is not a bool")
            if kind == "finding" and item["severity"] not in SEVERITIES:
                errors.append(f"finding[{index}]: unknown severity {item['severity']!r}")
    return errors
