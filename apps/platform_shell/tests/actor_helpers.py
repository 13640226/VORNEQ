"""Test helpers for CAP-ACTOR-01: obtain actors only through the real binding path."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from apps.core.models import Identity, UserIdentity
from apps.platform_shell.capabilities import BoundActor


def bound_actor_for(user):
    """Bind ``user`` exactly as an HTTP view would; raises if it cannot be bound."""
    request = RequestFactory().get("/")
    request.user = user
    return BoundActor.from_request(request)


def actor_or_untrusted(candidate):
    """Return a BoundActor when ``candidate`` can be bound, else ``candidate`` itself.

    Lets negative tests pass a raw/untrusted object to the invoker, which must
    reject it with the same ``not_authorized`` failure as a policy denial.
    """
    try:
        return bound_actor_for(candidate)
    except PermissionDenied:
        return candidate


def make_bound_actor(username="cap-actor"):
    user = get_user_model().objects.create_user(username=username)
    identity = Identity.objects.create(kind=Identity.Kind.HUMAN, display_name=username)
    UserIdentity.objects.create(user=user, identity=identity)
    return bound_actor_for(user)
