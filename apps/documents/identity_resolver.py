from django.core.exceptions import PermissionDenied

from apps.core.models import UserIdentity


class IdentityNotFoundError(PermissionDenied):
    """Raised when an authenticated account has no canonical Identity binding."""


class IdentityResolver:
    """Resolve an authenticated Django user to its canonical VORNEQ Identity.

    Resolution is read-only and fail-closed. This service never creates an
    Identity or UserIdentity binding implicitly.
    """

    @staticmethod
    def resolve(user):
        if user is None or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Authentication is required.")

        try:
            return UserIdentity.objects.select_related("identity").get(user=user).identity
        except UserIdentity.DoesNotExist as exc:
            raise IdentityNotFoundError(
                f"No canonical Identity is bound to authenticated user {user.pk}."
            ) from exc
