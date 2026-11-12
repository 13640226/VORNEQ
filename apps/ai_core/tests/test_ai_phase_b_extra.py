"""Extra fail-closed guard tests for production-disabled Phase B."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ai_core.engine.budget import BudgetExceeded, reserve_request
from apps.ai_core.engine.grounded import ask_grounded
from apps.ai_core.gateway import Citation
from apps.ai_core.providers.exceptions import ProviderTimeout
from apps.ai_core.sanitization import screen_and_redact, UnsafePrompt


class PhaseBAdditionalTests(SimpleTestCase):
    def test_persian_zero_width_non_joiner_is_allowed(self):
        text = "پاسخ\u200cهای مستند"
        self.assertEqual(screen_and_redact(text, limit=200), text)

    def test_hidden_zero_width_space_still_denied(self):
        with self.assertRaises(UnsafePrompt):
            screen_and_redact("a\u200bb", limit=200)

    def test_actual_budget_counter_exhaustion(self):
        counter = {}

        def add(key, value, timeout):
            counter.setdefault(key, value)
            return True

        def incr(key):
            counter[key] += 1
            return counter[key]

        with patch("apps.ai_core.engine.budget.cache") as cache:
            cache.add.side_effect = add
            cache.incr.side_effect = incr
            reserve_request(938277, per_minute=2, per_day=2)
            reserve_request(938277, per_minute=2, per_day=2)
            with self.assertRaises(BudgetExceeded):
                reserve_request(938277, per_minute=2, per_day=2)

    def test_cache_failure_rejects_request(self):
        with patch("apps.ai_core.engine.budget.cache") as cache:
            cache.add.side_effect = RuntimeError("cache unavailable")
            with self.assertRaises(BudgetExceeded):
                reserve_request(282848)

    def test_mocked_provider_timeout_is_not_swallowed(self):
        actor = SimpleNamespace(is_authenticated=True)
        class TimeoutProvider:
            def generate(self, **kwargs):
                raise ProviderTimeout("provider timed out")
        source = Citation("S1", "article:1", "Public",
                          "A meaningful public evidence excerpt.", "/en/a/")
        with self.assertRaises(ProviderTimeout):
            ask_grounded("hello", "en", actor=actor, provider=TimeoutProvider(),
                         retrieval=lambda q, lang: (source,), enabled=True)
