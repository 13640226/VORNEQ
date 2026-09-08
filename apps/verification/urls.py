from django.urls import path

from . import api


app_name = "verification"

urlpatterns = [
    path(
        "product/<int:pk>/",
        api.product_verification_summary,
        name="product_summary",
    ),
    path(
        "library/<int:pk>/",
        api.library_verification_summary,
        name="library_summary",
    ),
    path(
        "evidence/",
        api.public_evidence_projection,
        name="public_evidence",
    ),
    path(
        "activity/",
        api.verification_activity,
        name="activity",
    ),
]
