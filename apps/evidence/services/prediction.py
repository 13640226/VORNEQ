from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.evidence.models import Prediction, PredictionResolution


class PredictionLedgerService:
    """Explicit write/read service for probabilistic forecasts and scoring."""

    @staticmethod
    @transaction.atomic
    def create(
        *,
        claim,
        event_statement,
        probability,
        resolution_date,
        rationale="",
        created_by=None,
    ):
        prediction = Prediction(
            claim=claim,
            event_statement=event_statement,
            probability=Decimal(str(probability)),
            resolution_date=resolution_date,
            rationale=rationale,
            created_by=created_by,
        )
        prediction.save()
        return prediction

    @staticmethod
    @transaction.atomic
    def resolve(
        *,
        prediction,
        outcome_occurred,
        evidence_ref=None,
        notes="",
        resolved_by=None,
        resolved_at=None,
    ):
        if hasattr(prediction, "resolution"):
            raise ValidationError("Prediction has already been resolved.")

        resolved_at = resolved_at or timezone.now()
        if resolved_at < prediction.resolution_date:
            raise ValidationError("Prediction cannot be resolved before its resolution date.")

        return PredictionResolution.objects.create(
            prediction=prediction,
            outcome_occurred=bool(outcome_occurred),
            evidence_ref=evidence_ref,
            notes=notes,
            resolved_by=resolved_by,
            resolved_at=resolved_at,
        )

    @staticmethod
    def score(prediction):
        try:
            resolution = prediction.resolution
        except PredictionResolution.DoesNotExist:
            return None

        probability = Decimal(prediction.probability)
        actual = Decimal("1") if resolution.outcome_occurred else Decimal("0")
        brier = (probability - actual) ** 2
        accuracy = Decimal("1") - brier
        return {
            "brier_score": float(brier),
            "accuracy_score": float(accuracy),
        }

    @classmethod
    def ledger(cls, claim):
        rows = []
        predictions = (
            Prediction.objects.filter(claim=claim)
            .select_related("created_by")
            .prefetch_related("resolution")
            .order_by("resolution_date", "created_at", "id")
        )

        for prediction in predictions:
            try:
                resolution = prediction.resolution
            except PredictionResolution.DoesNotExist:
                resolution = None

            rows.append(
                {
                    "id": str(prediction.id),
                    "event_statement": prediction.event_statement,
                    "probability": float(prediction.probability),
                    "resolution_date": prediction.resolution_date.isoformat(),
                    "rationale": prediction.rationale,
                    "created_at": prediction.created_at.isoformat(),
                    "created_by": prediction.created_by_id,
                    "resolution": (
                        {
                            "outcome_occurred": resolution.outcome_occurred,
                            "evidence_id": str(resolution.evidence_ref_id)
                            if resolution.evidence_ref_id
                            else None,
                            "notes": resolution.notes,
                            "resolved_at": resolution.resolved_at.isoformat(),
                            "resolved_by": resolution.resolved_by_id,
                            **cls.score(prediction),
                        }
                        if resolution
                        else None
                    ),
                }
            )
        return rows

    @classmethod
    def scoring_summary(cls, *, claim=None, user=None):
        queryset = Prediction.objects.select_related("resolution")
        if claim is not None:
            queryset = queryset.filter(claim=claim)
        if user is not None:
            queryset = queryset.filter(created_by=user)

        scores = [cls.score(item) for item in queryset]
        scores = [item for item in scores if item is not None]
        if not scores:
            return {
                "resolved_predictions": 0,
                "mean_brier_score": None,
                "mean_accuracy_score": None,
            }

        count = len(scores)
        return {
            "resolved_predictions": count,
            "mean_brier_score": sum(item["brier_score"] for item in scores) / count,
            "mean_accuracy_score": sum(item["accuracy_score"] for item in scores) / count,
        }
