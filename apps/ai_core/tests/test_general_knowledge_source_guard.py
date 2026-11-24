"""Offline tests for the uncited-answer guard (fa / de / en).

Persian text uses Unicode escapes so the file is encoding-safe. The guard must reject
links, DOI references and pseudo-source markers WITHOUT rejecting legitimate technical
answers, and a code fence must never become a way around the source rules.
"""
from django.test import SimpleTestCase

from apps.ai_core.general_knowledge_runtime import validate_knowledge
from apps.ai_core.providers.exceptions import ProviderInvalidResponse
from apps.ai_core.uncited_answer_guard import find_violation

FA_SOURCES = "\u0645\u0646\u0627\u0628\u0639:"  # "sources:"
FA_SOURCE_SENTENCE = "\u0645\u0646\u0628\u0639 \u0627\u06cc\u0646 \u062e\u0637\u0627 \u062d\u0644\u0642\u0647 \u0627\u0633\u062a."
FA_MARKER = "\u0627\u0628\u0646 \u0633\u06cc\u0646\u0627 [\u06f1]"
FA_URL_LINE = FA_SOURCES + " https://fa.wikipedia.org/wiki/X"
FA_CODE_INTRO = "\u0646\u0645\u0648\u0646\u0647 \u06a9\u062f:"
FA_PLAIN = "\u0627\u0628\u0646\u200c\u0633\u06cc\u0646\u0627 \u067e\u0632\u0634\u06a9 \u0628\u0648\u062f."
PY_URL = "```python\nimport requests\nrequests.get('https://api.example.com/v1/items')\n```"


def _run(answer, language="en"):
    return validate_knowledge({"answer": answer, "language": language},
                              language=language, max_answer_chars=100000)


class RejectsLinksAndSourceMarkers(SimpleTestCase):
    CASES = (
        # Markdown / links, mixed case and obfuscation
        ("en", "Read [Wikipedia](https://en.wikipedia.org/wiki/Avicenna)."),
        ("en", "[x](HTTP://X.ORG)"), ("en", "[x](www.x.org)"), ("en", "[x](//x.org/a)"),
        ("en", "<https://x.org>"), ("en", "[1]: https://x.org/a"), ("en", "[ref]: x.org/a"),
        ("en", "HtTp://x.org"), ("en", "WWW.X.ORG"), ("en", "ftp://x.org/a"),
        ("en", "https\u200b://x.org"), ("en", "https\uff1a//x.org"),
        ("de", "Siehe [Wikipedia](https://de.wikipedia.org/wiki/Avicenna) fuer Details."),
        ("fa", FA_URL_LINE),
        # DOI
        ("en", "doi:10.1000/xyz"), ("en", "DOI: 10.1000/xyz"), ("en", "DoI:10.1/x"),
        ("en", "https://doi.org/10.1000/xyz"), ("en", "doi.org/10.1000/xyz"),
        # pseudo-source markers and section labels
        ("en", "Avicenna wrote the Canon [1]."), ("fa", FA_MARKER),
        ("en", "[1] Ibn Sina, Canon of Medicine"), ("en", "Sources:"), ("en", "## References"),
        ("de", "**Quellen:**"), ("fa", FA_SOURCES), ("en", "Sources: [1] Canon"),
        ("de", "Quellen: [2]"), ("de", "Literatur:\n- Foo"),
    )

    def test_prose_cases(self):
        for language, answer in self.CASES:
            with self.subTest(answer=answer):
                with self.assertRaises(ProviderInvalidResponse):
                    _run(answer, language)

    def test_error_message_never_echoes_content(self):
        with self.assertRaises(ProviderInvalidResponse) as ctx:
            _run("see https://secret-host.example/path")
        self.assertNotIn("secret-host", str(ctx.exception))

    def test_reason_codes(self):
        self.assertEqual(find_violation("doi:10.1/x"), "doi")
        self.assertEqual(find_violation("see www.x.org"), "link")
        self.assertEqual(find_violation("as shown in [1]."), "source_marker")
        self.assertEqual(find_violation("```python\n# Source: https://x.org\n```"), "code_citation")
        self.assertIsNone(find_violation("plain answer"))


class CodeFenceIsNotAnEscapeHatch(SimpleTestCase):
    CASES = (
        "```\nhttps://x.org\n```",                         # untagged
        "~~~\nhttps://x.org\n~~~",                         # untagged tilde fence
        "```text\nhttps://x.org\n```",                     # text-like tag
        "```markdown\n[a](https://x.org)\n```",
        "```md\nSources:\n```",
        "```foo\nhttps://x.org\n```",                      # unknown tag
        "```python\nprint(1)\nSee https://x.org",          # unclosed fence
        "````python\nrequests.get('https://api.example.com')\n```",  # closer too short
        "```python https://x.org\nprint(1)\n```",          # URL in the info string
        "```python\nprint(1)\n```\nSee https://x.org",     # prose after the fence
        "See https://x.org\n```python\nprint(1)\n```",     # prose before the fence
        "```python\n# Source: https://en.wikipedia.org/wiki/X\n```",
        "```python\nSource: https://x.org\n```",
        "```python\nhttps://en.wikipedia.org/wiki/Avicenna\n```",   # bare URL line
        "```python\n# https://en.wikipedia.org/wiki/Avicenna\n```",  # bare URL comment
        "```yaml\n# Quelle: https://x.org\n```",
        "```json\n// Reference: https://x.org\n```",
        "```html\n<!-- Source: https://x.org -->\n```",
        "```python\n# doi:10.1000/xyz\n```",               # DOI is rejected even in code
    )

    def test_cases(self):
        for answer in self.CASES:
            with self.subTest(answer=answer):
                with self.assertRaises(ProviderInvalidResponse):
                    _run(answer)


class AcceptsLegitimateTechnicalAnswers(SimpleTestCase):
    CASES = (
        ("en", "Use requests:\n" + PY_URL),
        ("en", "```bash\ncurl -s https://example.org/health\n```"),
        ("en", "```js\nfetch('https://example.org/api')\n```"),
        ("en", '```json\n{"homepage": "https://example.org"}\n```'),
        ("en", '```json\n[\n  "https://a.example",\n  "https://b.example"\n]\n```'),
        ("en", "```yaml\nurl: https://example.org\nsource: https://example.org/src\n```"),
        ("en", '```html\n<a href="https://example.org">link</a>\n```'),
        ("en", "```http\nGET https://api.example.com/x HTTP/1.1\n```"),
        ("en", "```python\n# See the docs for details\nvalue = 1\n```"),
        ("en", "```python\n# Source of randomness: os.urandom\nimport os\n```"),
        ("en", "```python\n# See https://docs.python.org/3/library/functions.html for details\n```"),
        ("en", "~~~python\nrequests.get('https://api.example.com')\n~~~"),
        ("en", "```PYTHON\nrequests.get('https://api.example.com')\n```"),
        ("fa", FA_CODE_INTRO + "\n" + PY_URL),
        ("de", "Beispiel:\n" + PY_URL),
        ("en", "values = [1, 2, 3]\nprint(values[1])"),
        ("en", "Use `items[1]` for the second element."),
        ("en", "The list [1, 2, 3] has three items."),
        ("en", "x[0] and y[1] are elements."),
        ("en", "```python\nprint(sum(range(1, 11)))  # 55\n```"),
        ("en", "Reference: the function returns a reference to the list."),
        ("de", "Quelle: Die Funktion liest die Quelle der Daten."),
        ("en", "The source of the bug is the loop."),
        ("en", "Sources of error include rounding."),
        ("fa", FA_SOURCE_SENTENCE),
        ("fa", FA_PLAIN),
        ("en", "Python 3.12 e.g. i.e. version 1.2.3"),
        ("en", "The word windows or meowww. is not a host"),
        ("en", "Doi is a name and 10.5 results are fine."),
    )

    def test_cases_are_accepted_unchanged(self):
        for language, answer in self.CASES:
            with self.subTest(answer=answer):
                result = _run(answer, language)
                self.assertEqual(result["answer"], answer)
                self.assertEqual(result["citations"], [])
                self.assertFalse(result["verified"])

    def test_pathological_inputs_finish(self):
        for answer in ("[1" * 5000, "`" * 5000, "https:/" * 2000, "[" * 20000, "\n" * 5000 + "x"):
            with self.subTest(length=len(answer)):
                find_violation(answer)