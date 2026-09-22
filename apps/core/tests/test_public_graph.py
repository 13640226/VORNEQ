from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Artifact, ArtifactBinding
from apps.core.services.registry import register_artifact
from apps.evidence.models import Claim, Evidence, EvidenceRelation, ProvenanceStep
from apps.graph.models import Edge, Node
from apps.verification.models import (
    VerificationEvidence,
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from marketplace.models import Product


User = get_user_model()


class PublicGraphV1Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="public-graph-owner",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Public Graph Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.artifact, _ = register_artifact(self.product, created_by=self.user)
        self.method = VerificationMethod.objects.create(
            code="public-graph",
            name="Public graph",
        )
        self._digest_counter = 0

    def _url(self, artifact=None):
        return reverse(
            "public_graph",
            kwargs={"artifact_id": (artifact or self.artifact).pk},
        )

    def _result(self, *, status=VerificationRequest.Status.COMPLETED):
        claim = Claim.objects.create(
            claim_text="SECRET CLAIM TEXT",
            created_by=self.user,
        )
        request = VerificationRequest.objects.create(
            artifact_content_type=ContentType.objects.get_for_model(
                self.product, for_concrete_model=False
            ),
            artifact_object_id=str(self.product.pk),
            canonical_artifact=self.artifact,
            claim=claim,
            method=self.method,
            requested_by=self.user,
            status=status,
        )
        result = VerificationResult.objects.create(
            request=request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=99,
            summary="SECRET VERIFIER SUMMARY",
        )
        return claim, result

    def _evidence(
        self,
        claim,
        result,
        *,
        visibility=VerificationEvidence.Visibility.PUBLIC,
        content="SECRET EVIDENCE CONTENT",
    ):
        self._digest_counter += 1
        evidence = Evidence.objects.create(
            content=content,
            integrity_digest=f"{self._digest_counter:064x}"[-64:],
            metadata={"secret": "SECRET METADATA"},
            created_by=self.user,
        )
        relation = EvidenceRelation.objects.create(
            claim=claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            relation_basis="SECRET RELATION BASIS",
            created_by=self.user,
        )
        VerificationEvidence.objects.create(
            result=result,
            evidence_relation=relation,
            visibility=visibility,
        )
        return evidence

    def _provenance(self, evidence, *, index=0, timestamp=None):
        return ProvenanceStep.objects.create(
            evidence=evidence,
            source_type=ProvenanceStep.SourceType.DOCUMENT,
            source_ref=f"SECRET SOURCE {index}",
            transformation=f"SECRET TRANSFORMATION {index}",
            timestamp=timestamp or (timezone.now() + timedelta(seconds=index)),
            note=f"SECRET NOTE {index}",
        )

    def test_eligible_empty_graph_has_exact_minimum_shape(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "root": {
                    "type": "artifact",
                    "ref": str(self.artifact.pk),
                    "truncated": False,
                },
                "nodes": [],
                "edges": [],
            },
        )

    def test_uniform_absence_for_nonexistent_and_ineligible_roots(self):
        missing = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        missing_id = missing.pk
        missing.delete()
        hidden_product = Product.objects.create(
            seller=self.user,
            title="Hidden Product",
            status=Product.STATUS_APPROVED,
            is_published=False,
        )
        hidden_artifact, _ = register_artifact(hidden_product, created_by=self.user)

        for url in (
            reverse("public_graph", kwargs={"artifact_id": missing_id}),
            self._url(hidden_artifact),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"detail": "Not found."})

        # A previously public root becomes the same uniform absence.
        self.product.is_published = False
        self.product.save()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_malformed_uuid_never_enters_public_graph_service(self):
        with patch("config.public_graph_views.get_public_graph") as graph:
            response = self.client.get("/artifacts/not-a-uuid/graph/")
        self.assertEqual(response.status_code, 404)
        graph.assert_not_called()

    def test_only_completed_explicitly_public_evidence_is_emitted(self):
        claim, result = self._result()
        public = self._evidence(claim, result)
        self._evidence(
            claim,
            result,
            visibility=VerificationEvidence.Visibility.PRIVATE,
            content="PRIVATE EVIDENCE",
        )
        self._evidence(
            claim,
            result,
            visibility=VerificationEvidence.Visibility.PARTICIPANTS,
            content="PARTICIPANTS EVIDENCE",
        )
        incomplete_claim, incomplete_result = self._result(
            status=VerificationRequest.Status.IN_PROGRESS
        )
        self._evidence(incomplete_claim, incomplete_result, content="INCOMPLETE EVIDENCE")

        response = self.client.get(self._url())
        payload = response.json()
        evidence_nodes = [n for n in payload["nodes"] if n["type"] == "evidence"]
        self.assertEqual(evidence_nodes, [
            {"type": "evidence", "ref": str(public.pk), "truncated": False}
        ])
        body = response.content.decode()
        self.assertNotIn("PRIVATE EVIDENCE", body)
        self.assertNotIn("PARTICIPANTS EVIDENCE", body)
        self.assertNotIn("INCOMPLETE EVIDENCE", body)

    def test_evidence_claim_user_and_relation_fields_do_not_leak(self):
        claim, result = self._result()
        evidence = self._evidence(claim, result)
        response = self.client.get(self._url())
        body = response.content.decode()

        self.assertIn(str(evidence.pk), body)
        for secret in (
            "SECRET CLAIM TEXT",
            "SECRET EVIDENCE CONTENT",
            "SECRET METADATA",
            "SECRET RELATION BASIS",
            "SECRET VERIFIER SUMMARY",
            self.user.username,
            evidence.integrity_digest,
        ):
            self.assertNotIn(secret, body)
        self.assertNotIn("supports", body)
        self.assertNotIn("confidence", body.lower())

    def test_provenance_is_terminal_narrow_and_response_local(self):
        claim, result = self._result()
        evidence = self._evidence(claim, result)
        step = self._provenance(evidence)

        response = self.client.get(self._url())
        payload = response.json()
        provenance = [n for n in payload["nodes"] if n["type"] == "provenance"]
        self.assertEqual(len(provenance), 1)
        self.assertEqual(provenance[0]["ref"], "p1")
        self.assertEqual(provenance[0]["source_type"], "document")
        self.assertIn("timestamp", provenance[0])
        self.assertNotIn("truncated", provenance[0])

        body = response.content.decode()
        self.assertNotIn(str(step.pk), body)
        self.assertNotIn("SECRET SOURCE", body)
        self.assertNotIn("SECRET TRANSFORMATION", body)
        self.assertNotIn("SECRET NOTE", body)

    def test_edges_are_only_authorized_relations_with_emitted_endpoints(self):
        claim, result = self._result()
        evidence = self._evidence(claim, result)
        self._provenance(evidence)

        payload = self.client.get(self._url()).json()
        relations = {edge["relation"] for edge in payload["edges"]}
        self.assertEqual(relations, {"INCLUDES_EVIDENCE", "HAS_PROVENANCE"})

        emitted = {
            (payload["root"]["type"], payload["root"]["ref"]),
            *((node["type"], node["ref"]) for node in payload["nodes"]),
        }
        for edge in payload["edges"]:
            self.assertIn((edge["source"]["type"], edge["source"]["ref"]), emitted)
            self.assertIn((edge["target"]["type"], edge["target"]["ref"]), emitted)
            self.assertEqual(set(edge), {"source", "target", "relation"})

    def test_f1_bounds_only_public_evidence_and_sets_root_truncation(self):
        claim, result = self._result()
        for index in range(26):
            self._evidence(claim, result, content=f"public-{index}")
        for index in range(3):
            self._evidence(
                claim,
                result,
                visibility=VerificationEvidence.Visibility.PRIVATE,
                content=f"private-{index}",
            )

        payload = self.client.get(self._url()).json()
        evidence_nodes = [n for n in payload["nodes"] if n["type"] == "evidence"]
        self.assertEqual(len(evidence_nodes), 25)
        self.assertTrue(payload["root"]["truncated"])
        self.assertNotIn("count", str(payload).lower())

    def test_private_evidence_does_not_consume_f1_or_trigger_truncation(self):
        claim, result = self._result()
        public = [
            self._evidence(claim, result, content=f"public-{index}")
            for index in range(25)
        ]
        for index in range(5):
            self._evidence(
                claim,
                result,
                visibility=VerificationEvidence.Visibility.PRIVATE,
                content=f"private-{index}",
            )

        payload = self.client.get(self._url()).json()
        refs = [n["ref"] for n in payload["nodes"] if n["type"] == "evidence"]
        self.assertEqual(refs, sorted(str(item.pk) for item in public))
        self.assertFalse(payload["root"]["truncated"])

    def test_f2_bounds_provenance_and_p_refs_are_contiguous(self):
        claim, result = self._result()
        first = self._evidence(claim, result)
        second = self._evidence(claim, result, content="SECOND PUBLIC")
        base = timezone.now()
        for index in range(11):
            self._provenance(first, index=index, timestamp=base + timedelta(seconds=index))
        self._provenance(second, index=20, timestamp=base)

        payload = self.client.get(self._url()).json()
        evidence_nodes = {
            n["ref"]: n for n in payload["nodes"] if n["type"] == "evidence"
        }
        self.assertTrue(evidence_nodes[str(first.pk)]["truncated"])
        self.assertFalse(evidence_nodes[str(second.pk)]["truncated"])

        provenance = [n for n in payload["nodes"] if n["type"] == "provenance"]
        self.assertEqual([n["ref"] for n in provenance], [f"p{i}" for i in range(1, 12)])
        self.assertEqual(len(provenance), 11)

    def test_equal_provenance_timestamps_are_deterministic(self):
        claim, result = self._result()
        evidence = self._evidence(claim, result)
        timestamp = timezone.now()
        for index in range(3):
            self._provenance(evidence, index=index, timestamp=timestamp)

        first = self.client.get(self._url()).json()
        second = self.client.get(self._url()).json()
        self.assertEqual(first, second)

    def test_get_is_read_only_and_persisted_graph_cannot_expand_disclosure(self):
        private_claim, private_result = self._result()
        private_evidence = self._evidence(
            private_claim,
            private_result,
            visibility=VerificationEvidence.Visibility.PRIVATE,
        )
        content_type = ContentType.objects.get_for_model(private_evidence)
        Node.objects.create(
            node_type=Node.NodeType.EVIDENCE,
            content_type=content_type,
            object_id=str(private_evidence.pk),
            label="SECRET GRAPH LABEL",
            metadata={"secret": "SECRET GRAPH METADATA"},
        )

        before = {
            "artifact": Artifact.objects.count(),
            "binding": ArtifactBinding.objects.count(),
            "node": Node.objects.count(),
            "edge": Edge.objects.count(),
            "evidence": Evidence.objects.count(),
            "provenance": ProvenanceStep.objects.count(),
        }
        response = self.client.get(self._url())
        after = {
            "artifact": Artifact.objects.count(),
            "binding": ArtifactBinding.objects.count(),
            "node": Node.objects.count(),
            "edge": Edge.objects.count(),
            "evidence": Evidence.objects.count(),
            "provenance": ProvenanceStep.objects.count(),
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before, after)
        self.assertEqual(response.json()["nodes"], [])
        self.assertNotIn("SECRET GRAPH", response.content.decode())
