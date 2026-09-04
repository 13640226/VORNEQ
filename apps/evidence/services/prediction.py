from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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
        # Re-read and lock the canonical Prediction row. This serializes competing
        # resolution attempts on databases that support SELECT ... FOR UPDATE and
        # avoids relying on possibly stale reverse-relation state on the caller's
        # model instance.
        locked = Prediction.objects.select_for_update().get(pk=prediction.pk)

        if PredictionResolution.objects.filter(prediction=locked).exists():
            raise ValidationError("Prediction has already been resolved.")

        resolved_at = resolved_at or timezone.now()
        if resolved_at < locked.resolution_date:
            raise ValidationError("Prediction cannot be resolved before its resolution date.")

        # The OneToOne constraint remains the database-level final defence. The
        # nested savepoint lets us translate a uniqueness race into the service's
        # stable ValidationError contract without leaving the outer transaction
        # in a broken state (useful on backends with weaker row-lock semantics).
        try:
            with transaction.atomic():
                return PredictionResolution.objects.create(
                    prediction=locked,
                    outcome_occurred=bool(outcome_occurred),
                    evidence_ref=evidence_ref,
                    notes=notes,
                    resolved_by=resolved_by,
                    resolved_at=resolved_at,
                )
        except IntegrityError as exc:
            if PredictionResolution.objects.filter(prediction=locked).exists():
                raise ValidationError("Prediction has already been resolved.") from exc
            raise

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
