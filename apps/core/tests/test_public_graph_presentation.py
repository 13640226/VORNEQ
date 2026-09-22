from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils.translation import override

from apps.core.services.public_graph import PublicGraphUnavailable


class PublicGraphPresentationV1Tests(SimpleTestCase):
    def _artifact_id(self):
        return "11111111-1111-1111-1111-111111111111"

    def _url(self):
        return reverse(
            "public_graph_presentation",
            kwargs={"artifact_id": self._artifact_id()},
        )

    @patch("config.public_graph_views.get_public_graph")
    def test_presentation_reuses_public_graph_authority_and_renders_contract(self, graph):
        graph.return_value = {
            "root": {"type": "artifact", "ref": self._artifact_id(), "truncated": True},
            "nodes": [
                {"type": "evidence", "ref": "e1", "truncated": True},
                {
                    "type": "provenance",
                    "ref": "p1",
                    "source_type": "document",
                    "timestamp": None,
                },
            ],
            "edges": [
                {
                    "source": {"type": "artifact", "ref": self._artifact_id()},
                    "target": {"type": "evidence", "ref": "e1"},
                    "relation": "INCLUDES_EVIDENCE",
                },
                {
                    "source": {"type": "evidence", "ref": "e1"},
                    "target": {"type": "provenance", "ref": "p1"},
                    "relation": "HAS_PROVENANCE",
                },
            ],
            "private_note": "SECRET GRAPH DTO",
        }

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        graph.assert_called_once()
        self.assertEqual(str(graph.call_args.args[0]), self._artifact_id())
        self.assertContains(response, self._artifact_id())
        self.assertContains(response, "e1")
        self.assertContains(response, "p1")
        self.assertContains(response, "INCLUDES_EVIDENCE")
        self.assertContains(response, "HAS_PROVENANCE")
        self.assertContains(response, "Additional public evidence is not shown in this bounded view.")
        self.assertContains(response, "Additional provenance is not shown in this bounded view.")
        self.assertNotContains(response, "SECRET GRAPH DTO")
        self.assertContains(response, reverse("context_view", kwargs={"artifact_id": self._artifact_id()}))
        self.assertContains(response, reverse("discover"))

    @patch("config.public_graph_views.get_public_graph")
    def test_presentation_fails_closed_with_404(self, graph):
        graph.side_effect = PublicGraphUnavailable

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 404)

    @patch("config.public_graph_views.get_public_graph")
    def test_presentation_post_does_not_enter_graph_authority(self, graph):
        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 404)
        graph.assert_not_called()

    @patch("config.public_graph_views.get_public_graph")
    def test_presentation_preserves_fa_rtl_shell(self, graph):
        graph.return_value = {
            "root": {"type": "artifact", "ref": self._artifact_id(), "truncated": False},
            "nodes": [],
            "edges": [],
        }

        with override("fa"):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')
