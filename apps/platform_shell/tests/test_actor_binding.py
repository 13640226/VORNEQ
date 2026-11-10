"""CAP-ACTOR-01 — trusted actor binding for the capability boundary.

Synthetic, isolated data only. No external services.
"""

from dataclasses import FrozenInstanceError, dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase

from apps.core.capabilities.read_artifact import ReadArtifactCapability, ReadArtifactInput
from apps.core.models import ArtifactBinding, Identity, UserIdentity
from apps.documents.artifact_read_policy import DocumentArtifactReadPolicy
from apps.documents.models import Document
from apps.documents.services import DocumentService
from apps.platform_shell.capabilities import (
    ActorBindingError,
    BaseCapability,
    BoundActor,
    CapabilityContext,
    CapabilityInvoker,
    ExecutableCapabilityRegistry,
)
from apps.platform_shell.registry import AppManifest, PlatformRegistry
from apps.platform_shell.tests.actor_helpers import bound_actor_for


User = get_user_model()


def bind(user, name, *, kind=Identity.Kind.HUMAN):
    identity = Identity.objects.create(kind=kind, display_name=name)
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


@dataclass(frozen=True)
class ProbeInput:
    value: str


@dataclass(frozen=True)
class ProbeOutput:
    identity_id: str


class ProbeCapability(BaseCapability[ProbeInput, ProbeOutput]):
    """Records every call so tests can prove denied actors never reach it."""

    name = "probe_v1"
    input_schema = ProbeInput
    output_schema = ProbeOutput
    calls: list = []

    def authorize(self, context, input_data):
        self.calls.append("authorize")
        return True

    def execute(self, context, input_data):
        self.calls.append("execute")
        return ProbeOutput(identity_id=str(context.actor.identity_id))


def build_invoker(*capabilities):
    platform_registry = PlatformRegistry()
    platform_registry.register(
        AppManifest(
            slug="actor-test",
            label="Actor Test",
            url_name="home",
            capabilities=tuple(c.name for c in capabilities),
        )
    )
    registry = ExecutableCapabilityRegistry(platform_registry)
    for capability in capabilities:
        registry.register(capability)
    return CapabilityInvoker(registry)


class ActorBindingTestBase(TestCase):
    def setUp(self):
        ProbeCapability.calls = []
        self.factory = RequestFactory()
        self.alice = User.objects.create_user(username="actor-alice")
        self.bob = User.objects.create_user(username="actor-bob")
        self.alice_identity = bind(self.alice, "Actor Alice")
        self.bob_identity = bind(self.bob, "Actor Bob")
        self.invoker = build_invoker(ProbeCapability)

    def request_for(self, user, path="/", data=None, method="get"):
        request = getattr(self.factory, method)(path, data or {})
        request.user = user
        return request

    def probe(self, actor):
        return self.invoker.invoke(
            "probe_v1",
            context=CapabilityContext(actor=actor, request_id="actor-test"),
            input_data={"value": "x"},
        )

    def assert_denied_without_reaching_capability(self, result):
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")
        self.assertEqual(ProbeCapability.calls, [])


class BindingFromRequestTests(ActorBindingTestBase):
    # A01 / A02
    def test_a01_anonymous_or_missing_user_cannot_be_bound(self):
        for request in (None, object(), self.request_for(AnonymousUser())):
            with self.subTest(request=repr(request)), self.assertRaises(ActorBindingError):
                BoundActor.from_request(request)

    # A03–A06
    def test_a03_unbound_inactive_or_non_human_users_cannot_be_bound(self):
        unbound = User.objects.create_user(username="actor-unbound")
        inactive_identity_user = User.objects.create_user(username="actor-inactive-identity")
        identity = bind(inactive_identity_user, "Inactive Identity")
        identity.is_active = False
        identity.save(update_fields=["is_active"])
        inactive_user = User.objects.create_user(username="actor-inactive-user")
        bind(inactive_user, "Inactive User")
        inactive_user.is_active = False
        inactive_user.save(update_fields=["is_active"])
        org_user = User.objects.create_user(username="actor-org")
        bind(org_user, "Org", kind=Identity.Kind.ORGANIZATION)

        for user in (unbound, inactive_identity_user, inactive_user, org_user):
            with self.subTest(user=user.username), self.assertRaises(ActorBindingError):
                BoundActor.from_request(self.request_for(user))

    def test_bound_actor_carries_server_resolved_identity(self):
        actor = BoundActor.from_request(self.request_for(self.alice))
        self.assertIs(actor.user, self.alice)
        self.assertEqual(actor.identity_id, self.alice_identity.pk)

    # A07
    def test_a07_bound_actor_cannot_be_constructed_directly(self):
        with self.assertRaises(ActorBindingError):
            BoundActor(user=self.alice, identity_id=self.alice_identity.pk)

    # A16
    def test_a16_bound_actor_is_immutable(self):
        actor = bound_actor_for(self.alice)
        with self.assertRaises(FrozenInstanceError):
            actor.user = self.bob
        with self.assertRaises(FrozenInstanceError):
            actor.identity_id = self.bob_identity.pk

    # A12
    def test_a12_client_supplied_actor_fields_are_ignored(self):
        spoof = {"actor": "actor-bob", "user_id": str(self.bob.pk), "identity_id": str(self.bob_identity.pk)}
        for method in ("get", "post"):
            with self.subTest(method=method):
                request = self.request_for(self.alice, data=spoof, method=method)
                request.META["HTTP_X_ACTOR_ID"] = str(self.bob_identity.pk)
                context = CapabilityContext.for_request(request)
                self.assertEqual(context.actor.identity_id, self.alice_identity.pk)
                result = self.invoker.invoke("probe_v1", context=context, input_data={"value": "x"})
                self.assertTrue(result.success)
                self.assertEqual(result.data.identity_id, str(self.alice_identity.pk))

    # A13
    def test_a13_for_request_builds_complete_context(self):
        request = self.request_for(self.alice)
        context = CapabilityContext.for_request(request)
        self.assertIsInstance(context.actor, BoundActor)
        self.assertTrue(context.request_id)
        self.assertIs(context.request, request)
        self.assertEqual(
            CapabilityContext.for_request(request, request_id="fixed").request_id, "fixed"
        )
        with self.assertRaises(ActorBindingError):
            CapabilityContext.for_request(self.request_for(AnonymousUser()))

    # A14
    def test_a14_repr_does_not_expose_account_details(self):
        text = repr(bound_actor_for(self.alice))
        self.assertNotIn("actor-alice", text)
        self.assertNotIn(str(self.alice.pk) + ",", text)


class InvokerActorEnforcementTests(ActorBindingTestBase):
    # A08
    def test_a08_untrusted_actor_values_are_rejected_before_any_capability_code(self):
        for actor in (self.alice, AnonymousUser(), None, object(), "actor-alice", self.alice_identity):
            with self.subTest(actor=repr(actor)):
                ProbeCapability.calls = []
                self.assert_denied_without_reaching_capability(self.probe(actor))

    def test_non_context_object_is_rejected(self):
        class FakeContext:
            actor = None
            request_id = "fake"

        result = self.invoker.invoke("probe_v1", context=FakeContext(), input_data={"value": "x"})
        self.assert_denied_without_reaching_capability(result)

    # A09
    def test_a09_untrusted_actor_cannot_probe_capability_registry(self):
        unknown = self.invoker.invoke(
            "does_not_exist_v1",
            context=CapabilityContext(actor=object(), request_id="enum"),
            input_data={},
        )
        known = self.probe(object())
        self.assertEqual(unknown.error, known.error)
        self.assertEqual(unknown.error.code, "not_authorized")

    def test_trusted_actor_still_gets_unknown_capability(self):
        result = self.invoker.invoke(
            "does_not_exist_v1",
            context=CapabilityContext(actor=bound_actor_for(self.alice), request_id="known"),
            input_data={},
        )
        self.assertEqual(result.error.code, "unknown_capability")

    def test_valid_bound_actor_reaches_capability(self):
        result = self.probe(bound_actor_for(self.alice))
        self.assertTrue(result.success)
        self.assertEqual(ProbeCapability.calls, ["authorize", "execute"])

    # A10
    def test_a10_actor_invalidated_after_binding_is_rejected(self):
        actor = bound_actor_for(self.alice)
        self.alice_identity.is_active = False
        self.alice_identity.save(update_fields=["is_active"])
        self.assert_denied_without_reaching_capability(self.probe(actor))

    def test_a10_deactivated_user_after_binding_is_rejected(self):
        actor = bound_actor_for(self.alice)
        # Committed elsewhere: the in-memory user object stays stale (is_active=True).
        User.objects.filter(pk=self.alice.pk).update(is_active=False)
        self.assertTrue(actor.user.is_active)
        self.assert_denied_without_reaching_capability(self.probe(actor))

    def test_a10_deleted_user_after_binding_is_rejected(self):
        actor = bound_actor_for(self.bob)
        UserIdentity.objects.filter(user=self.bob).delete()
        User.objects.filter(pk=self.bob.pk).delete()
        self.assert_denied_without_reaching_capability(self.probe(actor))

    # A11
    def test_a11_rebound_identity_invalidates_existing_actor(self):
        actor = bound_actor_for(self.alice)
        replacement = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name="Replacement")
        UserIdentity.objects.filter(user=self.alice).update(identity=replacement)
        self.assert_denied_without_reaching_capability(self.probe(actor))

    def test_a11_removed_binding_invalidates_existing_actor(self):
        actor = bound_actor_for(self.alice)
        UserIdentity.objects.filter(user=self.alice).delete()
        self.assert_denied_without_reaching_capability(self.probe(actor))


class ReadArtifactEndToEndTests(ActorBindingTestBase):
    # A15
    def setUp(self):
        super().setUp()
        self.invoker = build_invoker(ReadArtifactCapability)
        self.document = DocumentService.create_document(
            user=self.alice, title="Actor e2e", content="ACTOR-E2E-BODY", tags=["e2e"]
        )
        content_type = ContentType.objects.get_for_model(Document, for_concrete_model=False)
        self.artifact = ArtifactBinding.objects.get(
            content_type=content_type, object_id=str(self.document.pk)
        ).artifact

    def read_as(self, request):
        return self.invoker.invoke(
            "read_artifact_v1",
            context=CapabilityContext.for_request(request),
            input_data=ReadArtifactInput(artifact_id=self.artifact.id),
        )

    def test_a15_owner_reads_through_request_binding(self):
        result = self.read_as(self.request_for(self.alice))
        self.assertTrue(result.success)
        self.assertEqual(result.data.metadata, {"title": "Actor e2e", "tags": ["e2e"]})
        self.assertNotIn("ACTOR-E2E-BODY", repr(result))

    def test_a15_other_user_is_denied_even_when_spoofing_owner_ids(self):
        request = self.request_for(
            self.bob, data={"identity_id": str(self.alice_identity.pk), "user_id": str(self.alice.pk)}
        )
        result = self.read_as(request)
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "not_authorized")

    def test_a15_policy_rejects_raw_user_as_defense_in_depth(self):
        policy = DocumentArtifactReadPolicy()
        self.assertFalse(policy.authorize(actor=self.alice, artifact=self.artifact))
        self.assertTrue(policy.authorize(actor=bound_actor_for(self.alice), artifact=self.artifact))
