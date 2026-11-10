"""Trusted actor binding for executable capabilities (CAP-ACTOR-01).

The actor of a capability invocation is always derived on the server from the
authenticated Django session. It is never chosen by the client: no actor,
user id or identity id from a request body, query string or header is ever
consulted.

Chain::

    authenticated request.user
        -> IdentityResolver.resolve (active user, bound, active human Identity)
        -> BoundActor
        -> CapabilityContext
        -> CapabilityInvoker (re-validates the binding on every invocation)
        -> domain authorization policy
"""

from dataclasses import dataclass, field

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied


# Construction guard: a BoundActor is only created by ``BoundActor.from_request``.
# This prevents accidental construction; the security control is that the
# invoker re-resolves the binding from the database on every invocation.
_MINT = object()

ACTOR_UNAVAILABLE_MESSAGE = "A trusted actor is required."


class ActorBindingError(PermissionDenied):
    """Raised when no trusted actor can be bound or a binding is no longer valid."""


def _resolver():
    # Imported lazily: this module is imported while apps are being loaded.
    from apps.documents.identity_resolver import IdentityResolver

    return IdentityResolver


@dataclass(frozen=True, eq=False)
class BoundActor:
    """A server-verified pairing of an authenticated user and their Identity."""

    user: object
    identity_id: object
    _mint: object = field(default=None, repr=False)

    def __post_init__(self):
        if self._mint is not _MINT:
            raise ActorBindingError(ACTOR_UNAVAILABLE_MESSAGE)

    def __repr__(self):
        return f"BoundActor(identity_id={self.identity_id!s})"

    @classmethod
    def from_request(cls, request):
        """Bind the actor of an authenticated HTTP request; fail closed."""
        user = getattr(request, "user", None) if request is not None else None
        try:
            identity = _resolver().resolve(user)
        except PermissionDenied as exc:
            raise ActorBindingError(ACTOR_UNAVAILABLE_MESSAGE) from exc
        return cls(user=user, identity_id=identity.pk, _mint=_MINT)

    def revalidate(self):
        """Re-resolve the binding from the database now; raise if it changed.

        The user row is re-read so that a deactivation committed after binding
        is honoured even if this in-memory user object is stale.
        """
        try:
            fresh_user = type(self.user)._default_manager.get(pk=self.user.pk)
            identity = _resolver().resolve(fresh_user)
        except (PermissionDenied, ObjectDoesNotExist, AttributeError) as exc:
            raise ActorBindingError(ACTOR_UNAVAILABLE_MESSAGE) from exc
        if identity.pk != self.identity_id:
            raise ActorBindingError(ACTOR_UNAVAILABLE_MESSAGE)
        return identity
