"""V4-01 TEST-17 — Architekturgrenze für kostenpflichtige Provider (AST).

Statische Prüfung aller Laufzeitmodule (ohne Tests/Migrationen):

* ``OpenAIResponsesProvider(...)`` wird nirgends direkt konstruiert; einzige
  Konstruktionsstelle ist ``paid_provider.paid_text_provider`` (über
  ``provider_class``, gehostet immer in ``BudgetedProvider``).
* ``provider_class=`` darf nur an ``paid_text_provider`` übergeben werden.
* Der OpenAI-SDK-Client (``OpenAI(...)``/``AsyncOpenAI(...)``) darf nur in den
  Provider-Adaptern selbst entstehen.
* ``OpenAIImageProvider(...)`` nur im Image-Worker, und dort erst nach einer
  Ledger-Reservierung im selben Funktionskörper.
* Direkte SDK-Ressourcen (``.responses.*``, ``.images.*``, ``.audio.*``,
  ``.embeddings.*``, ``.chat.completions.*``) nur in den Adaptern.

Neue zulässige Stellen müssen hier bewusst eingetragen werden (Review-Pflicht).
Der Laufzeitnachweis steht in ``test_v4_ledger_enforcement.py``.
"""
import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
SCAN = ("apps", "config", "library", "marketplace", "scripts")

ALLOWED_CONSTRUCTION = {
    # Nirgends direkt: paid_provider.paid_text_provider konstruiert über ``provider_class``.
    "OpenAIResponsesProvider": set(),
    "OpenAI": {
        ("apps/ai_core/providers/openai_responses.py", "OpenAIResponsesProvider.generate"),
        ("apps/ai_core/providers/openai_responses.py", "OpenAIResponsesProvider.generate_knowledge"),
        # V7-03: gestreamte Wissensantwort – derselbe Adapter, dieselbe Freigabeprüfung.
        ("apps/ai_core/providers/openai_responses.py", "OpenAIResponsesProvider.stream_knowledge"),
        ("apps/ai_core/image_generation/providers.py", "OpenAIImageProvider.generate"),
    },
    "AsyncOpenAI": set(),
    "OpenAIImageProvider": {("apps/ai_core/image_generation/service.py", "process_next_image_job")},
}
SDK_RESOURCES = {"responses", "images", "audio", "embeddings", "completions", "realtime"}
ALLOWED_SDK_FILES = {"apps/ai_core/providers/openai_responses.py", "apps/ai_core/image_generation/providers.py"}
# Nur Ledger-Aufrufer dürfen die Aufruf-Freigabe setzen (V4-01 Aufrufgrenze).
ALLOWED_AUTHORIZATION = {
    ("apps/ai_core/budgeted_provider.py", "BudgetedProvider.generate"),
    ("apps/ai_core/budgeted_provider.py", "BudgetedProvider.generate_knowledge"),
    ("apps/ai_core/budgeted_provider.py", "BudgetedProvider.stream_knowledge"),  # V7-03
    ("apps/ai_core/image_generation/service.py", "process_next_image_job"),
}
# Bezahlte Adapter: Prüfung der Freigabe vor jedem SDK-Client.
GUARDED_ADAPTERS = {
    ("apps/ai_core/providers/openai_responses.py", "OpenAIResponsesProvider.generate"): "_require_ledger_reservation",
    ("apps/ai_core/providers/openai_responses.py", "OpenAIResponsesProvider.generate_knowledge"): "_require_ledger_reservation",
    ("apps/ai_core/providers/openai_responses.py", "OpenAIResponsesProvider.stream_knowledge"): "_require_ledger_reservation",
    ("apps/ai_core/image_generation/providers.py", "OpenAIImageProvider.generate"): "require_authorized_paid_call",
}
# Die Ledger-Reservierung muss im selben Funktionskörper VOR dem Bild-Provider stehen.
IMAGE_LEDGER_CALLS = {"reserve_with_config", "reserve_prepaid_image"}


def _is_runtime(path: Path) -> bool:
    parts = path.parts
    return not ("tests" in parts or "migrations" in parts or path.name.startswith("test_"))


def scan_source(source: str, rel: str):
    """Gibt Verstöße als Liste von Strings zurück (auch für Test-Fixtures nutzbar)."""
    tree = ast.parse(source)
    violations = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.stack = []
            self.function_calls = []

        def _scoped(self, node):
            self.stack.append(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                outer, self.function_calls = self.function_calls, []
                self.generic_visit(node)
                self.function_calls = outer
            else:
                self.generic_visit(node)
            self.stack.pop()

        visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped

        def visit_Call(self, node):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            scope = ".".join(self.stack) or "<module>"
            if name in ALLOWED_CONSTRUCTION and (rel, scope) not in ALLOWED_CONSTRUCTION[name]:
                violations.append(f"{rel}:{node.lineno} {scope}: {name}(...) außerhalb der Provider-Grenze")
            if name == "OpenAIImageProvider" and not (IMAGE_LEDGER_CALLS & set(self.function_calls)):
                violations.append(f"{rel}:{node.lineno} {scope}: OpenAIImageProvider ohne vorherige Ledger-Reservierung")
            if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
                    and func.value.attr in SDK_RESOURCES and rel not in ALLOWED_SDK_FILES
                    and func.attr in {"create", "parse", "generate", "edit", "stream", "transcribe"}):
                violations.append(f"{rel}:{node.lineno} {scope}: direkte SDK-Ressource .{func.value.attr}.{func.attr}")
            if (any(k.arg == "provider_class" for k in node.keywords)
                    and name != "paid_text_provider"):
                violations.append(f"{rel}:{node.lineno} {scope}: provider_class an {name}() statt paid_text_provider")
            if name == "authorized_paid_call" and (rel, scope) not in ALLOWED_AUTHORIZATION:
                violations.append(f"{rel}:{node.lineno} {scope}: authorized_paid_call außerhalb der Ledger-Aufrufer")
            if name in ("OpenAI", "AsyncOpenAI") and (rel, scope) in GUARDED_ADAPTERS \
                    and GUARDED_ADAPTERS[(rel, scope)] not in self.function_calls:
                violations.append(f"{rel}:{node.lineno} {scope}: SDK-Client vor der Ledger-Freigabeprüfung")
            if name:
                self.function_calls.append(name)
            self.generic_visit(node)

    Visitor().visit(tree)
    return violations


class PaidProviderBoundaryTests(SimpleTestCase):
    def test_runtime_code_respects_the_paid_provider_boundary(self):
        violations, scanned = [], 0
        for folder in SCAN:
            for path in (ROOT / folder).rglob("*.py"):
                if not _is_runtime(path.relative_to(ROOT)):
                    continue
                scanned += 1
                rel = path.relative_to(ROOT).as_posix()
                violations += scan_source(path.read_text(encoding="utf-8-sig"), rel)
        self.assertGreater(scanned, 300, "Scan hat zu wenige Dateien gefunden")
        self.assertEqual(violations, [])

    def test_every_allowed_site_still_exists(self):
        """Veraltete Ausnahmen werden sichtbar statt still erhalten zu bleiben."""
        for name, sites in ALLOWED_CONSTRUCTION.items():
            for rel, scope in sites:
                with self.subTest(name=name, site=f"{rel}:{scope}"):
                    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8-sig"))
                    found = []

                    class Finder(ast.NodeVisitor):
                        def __init__(self):
                            self.stack = []

                        def _s(self, node):
                            self.stack.append(node.name)
                            self.generic_visit(node)
                            self.stack.pop()

                        visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _s

                        def visit_Call(self, node):
                            f = node.func
                            n = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
                            if n == name and ".".join(self.stack) == scope:
                                found.append(node.lineno)
                            self.generic_visit(node)

                    Finder().visit(tree)
                    self.assertTrue(found)

    def test_single_factory_constructs_and_wraps(self):
        tree = ast.parse((ROOT / "apps/ai_core/paid_provider.py").read_text(encoding="utf-8"))
        factory = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "paid_text_provider")
        calls = {n.func.id for n in ast.walk(factory) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertTrue({"provider_class", "BudgetedProvider", "require_paid_text_ledger"} <= calls)

    def test_guard_detects_a_new_direct_provider_path(self):
        fixture = (
            "from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider\n"
            "def sneaky_view(request):\n"
            "    return OpenAIResponsesProvider(model='x').generate(question='q', language='en', sources=[])\n"
        )
        violations = scan_source(fixture, "apps/ai_core/sneaky.py")
        self.assertEqual(len(violations), 1)
        self.assertIn("OpenAIResponsesProvider", violations[0])

    def test_guard_detects_direct_sdk_use_and_unreserved_image_provider(self):
        fixture = (
            "def raw(client):\n"
            "    return client.chat.completions.create(model='x')\n"
            "def process_next_image_job():\n"
            "    return OpenAIImageProvider()\n"
        )
        violations = scan_source(fixture, "apps/ai_core/image_generation/service.py")
        self.assertTrue(any("completions.create" in v for v in violations))
        self.assertTrue(any("ohne vorherige Ledger-Reservierung" in v for v in violations))

    def test_guard_detects_unguarded_adapter_and_foreign_authorization(self):
        fixture = (
            "class OpenAIResponsesProvider:\n"
            "    def generate(self):\n"
            "        return OpenAI(api_key='x')\n"
            "def sneaky():\n"
            "    with authorized_paid_call(object(), kind='text'):\n"
            "        pass\n"
        )
        violations = scan_source(fixture, "apps/ai_core/providers/openai_responses.py")
        self.assertTrue(any("vor der Ledger-Freigabeprüfung" in v for v in violations))
        self.assertTrue(any("außerhalb der Ledger-Aufrufer" in v for v in violations))

    def test_guard_ignores_references_and_mock_providers(self):
        fixture = (
            "from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider\n"
            "def view():\n"
            "    return paid_text_provider(actor_id=1, provider_class=OpenAIResponsesProvider)\n"
            "def mock():\n"
            "    return MockImageProvider()\n"
        )
        self.assertEqual(scan_source(fixture, "apps/ai_core/views_global.py"), [])
