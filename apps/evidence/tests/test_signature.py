from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.test import TestCase

from apps.evidence.models import Evidence, SignatureEnvelope
from apps.evidence.services import EvidenceService
from apps.evidence.services.signature import get_public_key, sign_object, verify_signature


class SignatureEnvelopeTests(TestCase):
    def setUp(self):
        private_key = Ed25519PrivateKey.generate()
        self.private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        self.public_key_pem = get_public_key(self.private_key_pem)
        self.evidence = EvidenceService.create_with_provenance(
            content="A canonical observation",
            source_ref="test-suite",
        )

    def test_sign_and_verify_evidence(self):
        envelope = sign_object(
            target=self.evidence,
            private_key_pem=self.private_key_pem,
            key_id="test-key-1",
        )

        self.assertEqual(envelope.evidence_id, self.evidence.pk)
        self.assertEqual(envelope.algorithm, SignatureEnvelope.Algorithm.ED25519)
        self.assertTrue(verify_signature(envelope=envelope, public_key_pem=self.public_key_pem))

    def test_sign_and_verify_provenance_step(self):
        provenance = self.evidence.provenance_chain.get()
        envelope = sign_object(
            target=provenance,
            private_key_pem=self.private_key_pem,
            key_id="test-key-1",
        )

        self.assertEqual(envelope.provenance_step_id, provenance.pk)
        self.assertTrue(verify_signature(envelope=envelope, public_key_pem=self.public_key_pem))

    def test_database_tampering_is_detected(self):
        envelope = sign_object(
            target=self.evidence,
            private_key_pem=self.private_key_pem,
            key_id="test-key-1",
        )

        Evidence.objects.filter(pk=self.evidence.pk).update(content="tampered")
        envelope = SignatureEnvelope.objects.select_related("evidence").get(pk=envelope.pk)

        self.assertFalse(verify_signature(envelope=envelope, public_key_pem=self.public_key_pem))

    def test_wrong_public_key_fails_verification(self):
        envelope = sign_object(
            target=self.evidence,
            private_key_pem=self.private_key_pem,
            key_id="test-key-1",
        )
        other_private_key = Ed25519PrivateKey.generate()
        other_private_pem = other_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        self.assertFalse(
            verify_signature(
                envelope=envelope,
                public_key_pem=get_public_key(other_private_pem),
            )
        )

    def test_key_rotation_can_add_another_envelope(self):
        first = sign_object(
            target=self.evidence,
            private_key_pem=self.private_key_pem,
            key_id="test-key-1",
        )
        second_private = Ed25519PrivateKey.generate().private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        second = sign_object(
            target=self.evidence,
            private_key_pem=second_private,
            key_id="test-key-2",
        )

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(self.evidence.signature_envelopes.count(), 2)

    def test_envelope_is_append_only(self):
        envelope = sign_object(
            target=self.evidence,
            private_key_pem=self.private_key_pem,
            key_id="test-key-1",
        )
        envelope.key_id = "changed"

        with self.assertRaises(RuntimeError):
            envelope.save()
        with self.assertRaises(RuntimeError):
            envelope.delete()
