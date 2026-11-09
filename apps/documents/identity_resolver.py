from django.core.exceptions import PermissionDenied

from apps.core.models import Identity, UserIdentity


# Generic, caller-safe messages: views echo PermissionDenied text in 403 bodies,
# so no account or Identity identifiers may appear here.
AUTHENTICATION_REQUIRED_MESSAGE = "Authentication is required."
IDENTITY_NOT_BOUND_MESSAGE = "No canonical Identity is bound to this account."
IDENTITY_UNAVAILABLE_MESSAGE = "Identity is unavailable."


class IdentityNotFoundError(PermissionDenied):
    """Raised when an authenticated account has no canonical Identity binding."""


class InactiveIdentityError(PermissionDenied):
    """Raised when the account or its bound Identity may not act."""


class IdentityResolver:
    """Resolve a Django user to its canonical VORNEQ Identity.

    Resolution is read-only and fail-closed. This service never creates an
    Identity or UserIdentity binding implicitly.

    ``resolve`` is the actor path: it returns an Identity only for an
    authenticated, active Django user bound to an active human Identity.
    ``resolve_subject`` only names a target account (for example a
    collaborator whose access is being revoked); it never grants authority.
    """

    @staticmethod
    def _bound_identity(user):
        try:
            return UserIdentity.objects.select_related("identity").get(user=user).identity
        except UserIdentity.DoesNotExist as exc:
            raise IdentityNotFoundError(IDENTITY_NOT_BOUND_MESSAGE) from exc

    @classmethod
    def resolve(cls, user):
        if user is None or not getattr(user, "is_authenticated", False):
            raise PermissionDenied(AUTHENTICATION_REQUIRED_MESSAGE)
        if getattr(user, "is_active", False) is not True:
            raise InactiveIdentityError(IDENTITY_UNAVAILABLE_MESSAGE)

        identity = cls._bound_identity(user)
        if identity.is_active is not True or identity.kind != Identity.Kind.HUMAN:
            raise InactiveIdentityError(IDENTITY_UNAVAILABLE_MESSAGE)
        return identity

    @classmethod
    def resolve_subject(cls, user):
        if user is None or getattr(user, "pk", None) is None:
            raise PermissionDenied(IDENTITY_NOT_BOUND_MESSAGE)
        return cls._bound_identity(user)
