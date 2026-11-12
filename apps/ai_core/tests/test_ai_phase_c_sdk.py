"""Actual OpenAI SDK parsing against httpx2.MockTransport, never the network.

Optional on normal CI (SDK intentionally absent from production/CI locks).
Run in an isolated development venv with requirements-ai-phase-c-dev.txt.
"""
import importlib.util
import json
import os
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ai_core.engine.citation import authorized_context
from apps.ai_core.gateway import Citation
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider


_HAS_SDK = (importlib.util.find_spec("openai") is not None
            and importlib.util.find_spec("httpx2") is not None
            and importlib.util.find_spec("pydantic") is not None)


@skipUnless(_HAS_SDK, "OpenAI/Pydantic SDK only installed in isolated dev environment")
class OfflineRealSDKIntegrationTests(SimpleTestCase):
    def test_real_responses_parse_against_only_mock_transport(self):
        import httpx2
        from openai import OpenAI

        source = authorized_context((Citation(
            "S1", "article:1", "Public article",
            "Public excerpt for grounded answer testing.", "/en/article/1/"
        ),))[0]
        draft = {
            "answer": "Public excerpt for grounded answer testing.",
            "language": "en",
            "citations": [{
                "source_id": "S1", "evidence_digest": source["evidence_digest"],
                "evidence_quote": "Public excerpt for grounded answer testing.",
            }],
            "model_status": "generated",
            "grounded_status": "proposed",
            "verified": False,
            "error_code": "",
        }
        observed = []

        def offline_handler(request):
            body = json.loads(request.content)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.host, "phase-c-offline.invalid")
            self.assertEqual(body["tools"], [])
            self.assertIs(body["store"], False)
            self.assertEqual(body["model"], "synthetic-model")
            self.assertEqual(body["max_output_tokens"], 256)
            self.assertEqual(body["text"]["format"]["type"], "json_schema")
            self.assertEqual(body["input"][0]["role"], "user")
            self.assertNotIn(source["excerpt"], body["instructions"])
            self.assertIn(source["excerpt"], body["input"][0]["content"])
            observed.append(body)
            return httpx2.Response(200, json={
                "id": "resp_synthetic_only", "object": "response",
                "created_at": 1762920000, "status": "completed",
                "model": "synthetic-model", "error": None,
                "incomplete_details": None,
                "output": [{
                    "id": "msg_synthetic_only", "type": "message",
                    "role": "assistant", "status": "completed",
                    "content": [{
                        "type": "output_text",
                        "text": json.dumps(draft),
                        "annotations": [],
                    }],
                }],
                "usage": {"input_tokens": 30, "output_tokens": 40,
                          "total_tokens": 70},
            })

        client = OpenAI(
            api_key="sk-synthetic-offline-do-not-use",
            base_url="https://phase-c-offline.invalid/v1",
            timeout=10,
            max_retries=0,
            http_client=httpx2.Client(transport=httpx2.MockTransport(offline_handler)),
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-synthetic-offline-do-not-use"}):
            with patch("openai.OpenAI", return_value=client):
                result = OpenAIResponsesProvider(
                    model="synthetic-model", timeout_s=10,
                    max_output_tokens=256,
                ).generate(question="public question", language="en", sources=[source])
        self.assertEqual(result, draft)
        self.assertEqual(len(observed), 1)
