from types import SimpleNamespace
from django.test import SimpleTestCase
from apps.ai_core.conversations import service
from apps.ai_core.models import AIMessage


class KnowledgePersistenceTests(SimpleTestCase):
    def test_classify_and_replay_without_fabricating_sources(self):
        response = {
            "mode": "model_knowledge", "answer": "The result is 55.",
            "language": "en", "citations": [], "verified": False,
            "model_status": "generated", "grounded_status": "model_knowledge_unverified",
            "error_code": "", "route": "general_public",
        }
        status, content, marker, citations = service.classify(response, 200)
        self.assertEqual(status, AIMessage.STATUS_COMPLETED)
        self.assertEqual(marker, "model_knowledge")
        self.assertEqual(citations, [])
        message = SimpleNamespace(status=status, content=content, error_code=marker,
                                  citations=citations)
        conversation = SimpleNamespace(id="mock-id", language="en")
        replay, http_status = service.stored_response(message, conversation)
        self.assertEqual(http_status, 200)
        self.assertEqual(replay["mode"], "model_knowledge")
        self.assertEqual(replay["citations"], [])
        self.assertFalse(replay["verified"])
        self.assertEqual(replay["answer"], response["answer"])
