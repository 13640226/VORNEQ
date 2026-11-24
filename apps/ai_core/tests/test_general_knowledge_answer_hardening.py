"""Offline tests: uncited knowledge answers must not carry links or DOI references.

Bracketed markers such as ``[1]`` are deliberately NOT rejected: they are legitimate
in code (``items[1]``) and cannot be told apart from prose by a simple rule.
"""
from django.test import SimpleTestCase

from apps.ai_core.general_knowledge_runtime import validate_knowledge
from apps.ai_core.providers.exceptions import ProviderInvalidResponse


def _validate(answer):
    return validate_knowledge({"answer": answer, "language": "en"},
                              language="en", max_answer_chars=1000)


class UncitedAnswerHardeningTests(SimpleTestCase):
    def test_links_and_doi_references_are_rejected(self):
        for answer in (
            "http://example.org", "https://example.org", "HTTPS://X.ORG",
            "ftp://x.org/a", "See www.example.org for details", "visit WWW.Example.org",
            "doi:10.1000/xyz", "DOI: 10.1000/xyz", "https://doi.org/10.1000/xyz",
            "doi.org/10.1000/xyz", "custom+scheme://host/path",
        ):
            with self.subTest(answer=answer):
                with self.assertRaises(ProviderInvalidResponse):
                    _validate(answer)

    def test_ordinary_answers_and_code_are_accepted_unchanged(self):
        for answer in (
            "Avicenna wrote the Canon of Medicine.",
            "Python 3.12 e.g. i.e. version 1.2.3",
            "values = [1, 2, 3]\nprint(values[1])",
            "```python\nprint(sum(range(1, 11)))  # 55\n```",
            "The word windows or meowww. is not a host",
        ):
            with self.subTest(answer=answer):
                self.assertEqual(_validate(answer)["answer"], answer)