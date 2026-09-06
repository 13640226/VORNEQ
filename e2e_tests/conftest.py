import pytest
from django.contrib.auth import get_user_model


@pytest.fixture(scope="session")
def e2e_user(django_db_setup, django_db_blocker):
    User = get_user_model()
    with django_db_blocker.unblock():
        user, _ = User.objects.get_or_create(
            username="e2e-user",
            defaults={"email": "e2e@example.com"},
        )
        user.set_password("e2e-pass-123")
        user.save(update_fields=["password"])
    return {"username": "e2e-user", "password": "e2e-pass-123"}
