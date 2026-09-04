from django.urls import path

from . import views


app_name = "graph"

urlpatterns = [
    path("claims/<uuid:claim_id>/", views.claim_graph, name="claim-graph"),
    path(
        "claims/<uuid:claim_id>/disagreements/",
        views.disagreement_map,
        name="disagreement-map",
    ),
    path(
        "claims/<uuid:claim_id>/evidence-gaps/",
        views.evidence_gaps,
        name="evidence-gaps",
    ),
    path(
        "claims/<uuid:claim_id>/decision-package/",
        views.decision_package,
        name="decision-package",
    ),
]
