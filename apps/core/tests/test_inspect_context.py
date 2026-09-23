from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override
from unittest.mock import patch

from apps.core.models import ArtifactBinding
from apps.core.services.context import get_context_view, resolve_artifact_from_input
from apps.core.services.public_graph import PublicGraphUnavailable
from apps.core.services.registry import register_artifact
from apps.evidence.models import Claim, Evidence, EvidenceRelation, ProvenanceStep
from apps.verification.models import (
    VerificationEvidence,
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from marketplace.models import Product


class InspectContextV1Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inspect-owner",
            email="inspect@example.com",
            password="test-password",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Inspectable Research Artifact",
            slug="inspectable-research-artifact",
            short_description="A public artifact used by Inspect Context V1 tests.",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact, _created = register_artifact(
            self.product,
            created_by=self.user,
        )

    def test_resolves_existing_public_artifact_without_creating_records(self):
        artifact_count = type(self.artifact).objects.count()

        resolved = resolve_artifact_from_input(self.product.title)

        self.assertEqual(resolved, self.artifact)
        self.assertEqual(type(self.artifact).objects.count(), artifact_count)

    def test_resolves_artifact_slug(self):
        resolved = resolve_artifact_from_input(self.product.slug)
        self.assertEqual(resolved, self.artifact)

    def test_resolves_artifact_url(self):
        resolved = resolve_artifact_from_input(
            f"https://staging.example.test/products/{self.product.slug}/"
        )
        self.assertEqual(resolved, self.artifact)

    def test_resolves_artifact_uuid(self):
        resolved = resolve_artifact_from_input(str(self.artifact.id))
        self.assertEqual(resolved, self.artifact)

    def test_does_not_resolve_unpublished_product(self):
        hidden = Product.objects.create(
            seller=self.user,
            title="Hidden Inspect Artifact",
            slug="hidden-inspect-artifact",
            status=Product.STATUS_APPROVED,
            is_published=False,
        )
        register_artifact(hidden, created_by=self.user)

        self.assertIsNone(resolve_artifact_from_input(hidden.title))

    def test_context_projection_contains_no_global_trust_score(self):
        context = get_context_view(self.artifact.id, language="en")

        self.assertEqual(context["artifact"], self.artifact)
        self.assertEqual(context["source"]["title"], self.product.title)
        self.assertEqual(context["verification"]["total_verifications"], 0)
        self.assertNotIn("score", context)
        self.assertNotIn("trust_score", context)

    def test_context_page_is_linkable_by_artifact_uuid(self):
        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertContains(response, str(self.artifact.id))

    def test_inspect_post_redirects_to_canonical_context_page(self):
        response = self.client.post(
            reverse("inspect_entry"),
            {"input": self.product.title},
        )

        self.assertRedirects(
            response,
            reverse("context_view", kwargs={"artifact_id": self.artifact.id}),
        )


    @patch("config.inspect_views.get_public_graph")
    def test_context_cross_links_public_provenance_to_evidence_identifier(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        claim = Claim.objects.create(claim_text="Cross-linked public claim")
        evidence = Evidence.objects.create(
            content="Cross-linked public evidence",
            integrity_digest="0" * 64,
        )
        relation = EvidenceRelation.objects.create(
            claim=claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.CONTEXTUALIZES,
        )
        ProvenanceStep.objects.create(
            evidence=evidence,
            source_type=ProvenanceStep.SourceType.DOCUMENT,
            source_ref="cross-link-test-source",
        )
        method = VerificationMethod.objects.create(
            code="context-cross-link",
            name="Context cross-link",
        )
        request = VerificationRequest.objects.create(
            artifact_content_type=ContentType.objects.get_for_model(
                self.product,
                for_concrete_model=False,
            ),
            artifact_object_id=str(self.product.pk),
            canonical_artifact=self.artifact,
            claim=claim,
            method=method,
            status=VerificationRequest.Status.COMPLETED,
        )
        result = VerificationResult.objects.create(
            request=request,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=100,
        )
        VerificationEvidence.objects.create(
            result=result,
            evidence_relation=relation,
            visibility=VerificationEvidence.Visibility.PUBLIC,
        )

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )
        html = response.content.decode()
        evidence_id = str(evidence.id)
        target = f'id="evidence-{evidence_id}"'
        link = f'href="#evidence-{evidence_id}"'

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, target)
        self.assertContains(response, link)
        self.assertEqual(html.count(target), 1)
        self.assertEqual(html.count(link), 1)
        self.assertLess(html.index(target), html.index(link))


    def _create_public_provenance_fixture(self, *, source_ref, public_source_ref=None):
        claim = Claim.objects.create(claim_text="Public source reference claim")
        evidence = Evidence.objects.create(
            content="Public source reference evidence",
            integrity_digest="1" * 64,
        )
        relation = EvidenceRelation.objects.create(
            claim=claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.CONTEXTUALIZES,
        )
        ProvenanceStep.objects.create(
            evidence=evidence,
            source_type=ProvenanceStep.SourceType.DOCUMENT,
            source_ref=source_ref,
            public_source_ref=public_source_ref,
        )
        method = VerificationMethod.objects.create(
            code=f"public-source-ref-{evidence.id}",
            name="Public source reference",
        )
        request = VerificationRequest.objects.create(
            artifact_content_type=ContentType.objects.get_for_model(
                self.product,
                for_concrete_model=False,
            ),
            artifact_object_id=str(self.product.pk),
            canonical_artifact=self.artifact,
            claim=claim,
            method=method,
            status=VerificationRequest.Status.COMPLETED,
        )
        result = VerificationResult.objects.create(
            request=request,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=100,
        )
        VerificationEvidence.objects.create(
            result=result,
            evidence_relation=relation,
            visibility=VerificationEvidence.Visibility.PUBLIC,
        )

    @patch("config.inspect_views.get_public_graph")
    def test_context_renders_explicit_public_source_ref(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        self._create_public_provenance_fixture(
            source_ref="raw-source-ref-must-stay-hidden",
            public_source_ref="test-public-ref",
        )

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test-public-ref")
        self.assertContains(response, 'class="context-provenance__source-ref"')
        self.assertNotContains(response, "raw-source-ref-must-stay-hidden")

    def test_context_renders_public_source_reference_label_in_en(self):
        self._create_public_provenance_fixture(
            source_ref="private://raw-source",
            public_source_ref="Public source",
        )
        with override("en"):
            response = self.client.get(reverse("context_view", kwargs={"artifact_id": self.artifact.id}))
        self.assertContains(response, "Public source reference")

    def test_context_de_renders_translated_public_source_reference_label(self):
        self._create_public_provenance_fixture(
            source_ref="private://raw-source",
            public_source_ref="Public source",
        )
        with override("de"):
            response = self.client.get(reverse("context_view", kwargs={"artifact_id": self.artifact.id}))
        self.assertContains(response, "Öffentliche Quellenangabe")

    def test_context_fa_renders_translated_public_source_reference_label(self):
        self._create_public_provenance_fixture(
            source_ref="private://raw-source",
            public_source_ref="Public source",
        )
        with override("fa"):
            response = self.client.get(reverse("context_view", kwargs={"artifact_id": self.artifact.id}))
        self.assertContains(response, "ارجاع عمومی منبع")

    @patch("config.inspect_views.get_public_graph")
    def test_context_does_not_fallback_to_raw_source_ref(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        self._create_public_provenance_fixture(
            source_ref="raw-canonical-ref-should-not-render",
        )

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "raw-canonical-ref-should-not-render")
        self.assertNotContains(response, 'class="context-provenance__source-ref"')


    @patch("config.inspect_views.get_public_graph")
    def test_context_exposes_existing_public_graph_handoff_when_available(self, graph):
        graph.return_value = {
            "root": {"private_note": "SECRET GRAPH DTO"},
            "nodes": [],
            "edges": [],
        }

        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_discover_url = reverse("discover")
        expected_url = reverse("public_graph", kwargs={"artifact_id": self.artifact.id})

        self.assertEqual(response.status_code, 200)
        graph.assert_called_once_with(self.artifact.id)
        self.assertContains(response, "Inspect Evidence Graph")
        self.assertContains(response, expected_url)
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, expected_discover_url)
        self.assertNotContains(response, "SECRET GRAPH DTO")
        self.assertNotContains(response, "trust score")

    @patch("config.inspect_views.get_public_graph")
    def test_context_hides_graph_handoff_when_public_graph_is_unavailable(self, graph):
        graph.side_effect = PublicGraphUnavailable

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Inspect Evidence Graph")
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, reverse("discover"))
        self.assertNotContains(response, "unverified")
        self.assertNotContains(response, "low trust")

    @patch("config.inspect_views.get_public_graph")
    def test_context_graph_handoff_get_does_not_mutate_artifact_registry(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        before_artifacts = type(self.artifact).objects.count()
        before_bindings = ArtifactBinding.objects.count()

        response = self.client.get(
            reverse("context_view", kwargs={"artifact_id": self.artifact.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(self.artifact).objects.count(), before_artifacts)
        self.assertEqual(ArtifactBinding.objects.count(), before_bindings)


    @patch("config.inspect_views.get_public_graph")
    def test_context_page_has_single_canonical_main_and_accessible_affordances(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_discover_url = reverse("discover")
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<main"), 1)
        self.assertContains(response, '<main id="main-content"')
        self.assertNotContains(response, '<main class="container"')
        self.assertContains(response, '<div class="container" aria-labelledby="context-title">')
        self.assertContains(response, 'id="context-title"')
        self.assertContains(response, "Open source artifact")
        self.assertContains(response, "Inspect Evidence Graph")
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, expected_discover_url)
        self.assertContains(response, 'aria-hidden="true"')
        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, 'type="button"')
        self.assertContains(response, 'class="global-back__button"')
        self.assertContains(response, 'aria-label="Go back to the previous page"')
        self.assertContains(response, 'class="global-back__icon" aria-hidden="true"')

    @patch("config.inspect_views.get_public_graph")
    def test_context_graph_unavailable_has_no_interactive_graph_affordance(self, graph):
        graph.side_effect = PublicGraphUnavailable
        with override("en"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
            expected_discover_url = reverse("discover")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Inspect Evidence Graph")
        self.assertContains(response, '<nav class="context-actions" aria-labelledby="context-title">')
        self.assertContains(response, expected_discover_url)



class InspectContextI18nRtlStructuralTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inspect-i18n-owner",
            email="inspect-i18n@example.com",
            password="test-password",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Inspectable I18n Artifact",
            slug="inspectable-i18n-artifact",
            short_description="A public artifact used by Context i18n/RTL tests.",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact, _created = register_artifact(
            self.product,
            created_by=self.user,
        )

    @patch("config.inspect_views.get_public_graph")
    def test_context_de_renders_translated_affordances(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("de"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
        self.assertContains(response, 'lang="de"')
        self.assertContains(response, "Kontext prüfen")
        self.assertContains(response, "Evidenzgraph prüfen")
        self.assertNotContains(response, "Inspect Evidence Graph")

    @patch("config.inspect_views.get_public_graph")
    def test_context_fa_renders_rtl_translated_affordances(self, graph):
        graph.return_value = {"root": {}, "nodes": [], "edges": []}
        with override("fa"):
            response = self.client.get(
                reverse("context_view", kwargs={"artifact_id": self.artifact.id})
            )
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "بررسی زمینه")
        self.assertContains(response, "بررسی گراف شواهد")
        self.assertNotContains(response, "Inspect Evidence Graph")
