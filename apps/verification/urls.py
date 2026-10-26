from django.urls import path

from . import api, views


app_name = "verification"

urlpatterns = [
    path("manage/", views.VerificationListView.as_view(), name="list"),
    path("manage/new/", views.VerificationCreateView.as_view(), name="create"),
    path("manage/<int:pk>/", views.VerificationDetailView.as_view(), name="detail"),
    path("manage/<int:pk>/start/", views.VerificationStartView.as_view(), name="start"),
    path("manage/<int:pk>/submit/", views.VerificationSubmitView.as_view(), name="submit"),
    path("manage/<int:pk>/cancel/", views.VerificationCancelView.as_view(), name="cancel"),
    path("manage/<int:pk>/fail/", views.VerificationFailView.as_view(), name="fail"),
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
