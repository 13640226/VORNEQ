from django.db import transaction
from django.db.models import Exists, OuterRef

from apps.core.models import Reputation, ReputationHistory
from apps.evidence.models import Evidence, Prediction
from apps.evidence.services import PredictionLedgerService


class ReputationService:
    """Maintain a rebuildable reputation cache from explicit canonical events.

    Only dimensions with defensible signals are updated automatically. Dimensions that
    require human judgement (fair critique, domain expertise, social behaviour, general
    accuracy/corrigibility) are intentionally not inferred from activity volume.
    """

    @staticmethod
    def _get_or_create_reputation(user):
        reputation, _ = Reputation.objects.get_or_create(user=user)
        return reputation

    @classmethod
    @transaction.atomic
    def _apply_dimension(
        cls,
        *,
        user,
        dimension,
        field_name,
        new_value,
        event_type,
        event_id,
    ):
        event_id = str(event_id)
        if ReputationHistory.objects.filter(
            user=user,
            dimension=dimension,
            event_type=event_type,
            event_id=event_id,
        ).exists():
            return cls._get_or_create_reputation(user)

        reputation, _ = Reputation.objects.select_for_update().get_or_create(user=user)
        old_value = float(getattr(reputation, field_name))
        new_value = max(0.0, min(1.0, float(new_value)))
        setattr(reputation, field_name, new_value)
        reputation.update_overall()
        reputation.save()

        if old_value != new_value:
            ReputationHistory.objects.create(
                user=user,
                dimension=dimension,
                old_value=old_value,
                new_value=new_value,
                event_type=event_type,
                event_id=event_id,
            )
        return reputation

    @classmethod
    def update_prediction_accuracy(cls, user, resolution):
        if user is None:
            return None
        summary = PredictionLedgerService.scoring_summary(user=user)
        score = summary["mean_accuracy_score"]
        if score is None:
            score = 0.0
        return cls._apply_dimension(
            user=user,
            dimension=ReputationHistory.Dimension.PREDICTION_ACCURACY,
            field_name="prediction_accuracy_score",
            new_value=score,
            event_type="PredictionResolution",
            event_id=resolution.pk,
        )

    @classmethod
    def update_source_quality(cls, user, evidence, event_id=None):
        if user is None:
            return None
        from apps.evidence.models import ProvenanceStep

        provenance = ProvenanceStep.objects.filter(
            evidence_id=OuterRef("pk"),
            source_ref__gt="",
            source_type__gt="",
        )
        authored = Evidence.objects.filter(created_by=user).annotate(
            has_complete_provenance=Exists(provenance)
        )
        total = authored.count()
        complete = authored.filter(has_complete_provenance=True).count()
        score = (complete / total) if total else 0.0
        return cls._apply_dimension(
            user=user,
            dimension=ReputationHistory.Dimension.SOURCE_QUALITY,
            field_name="source_quality_score",
            new_value=score,
            event_type="ProvenanceStep",
            event_id=event_id or evidence.pk,
        )

    @classmethod
    def update_corrigibility(cls, user, review_record, *, confirmed_self_correction=False):
        """Update only when the caller explicitly confirms a self-correction event."""
        if user is None or not confirmed_self_correction:
            return cls._get_or_create_reputation(user) if user is not None else None
        existing = ReputationHistory.objects.filter(
            user=user,
            dimension=ReputationHistory.Dimension.CORRIGIBILITY,
        ).count()
        score = min(1.0, (existing + 1) / 10.0)
        return cls._apply_dimension(
            user=user,
            dimension=ReputationHistory.Dimension.CORRIGIBILITY,
            field_name="corrigibility_score",
            new_value=score,
            event_type="ReviewRecord",
            event_id=review_record.pk,
        )

    @classmethod
    def update_fair_critique(cls, user, critique):
        """No automatic score: fairness needs an explicit assessment signal."""
        return cls._get_or_create_reputation(user) if user is not None else None

    @classmethod
    def update_domain_expertise(cls, user, claim):
        """No automatic score: contribution count is not treated as expertise."""
        return cls._get_or_create_reputation(user) if user is not None else None

    @classmethod
    def update_accuracy(cls, user, claim_or_evidence):
        """No automatic score until a canonical accuracy assessment exists."""
        return cls._get_or_create_reputation(user) if user is not None else None

    @classmethod
    @transaction.atomic
    def recalculate_all(cls, user):
        """Rebuild defensible dimensions from canonical history without fabricating scores."""
        reputation, _ = Reputation.objects.select_for_update().get_or_create(user=user)

        prediction_summary = PredictionLedgerService.scoring_summary(user=user)
        reputation.prediction_accuracy_score = (
            prediction_summary["mean_accuracy_score"]
            if prediction_summary["mean_accuracy_score"] is not None
            else 0.0
        )

        from apps.evidence.models import ProvenanceStep

        provenance = ProvenanceStep.objects.filter(
            evidence_id=OuterRef("pk"), source_ref__gt="", source_type__gt=""
        )
        authored = Evidence.objects.filter(created_by=user).annotate(
            has_complete_provenance=Exists(provenance)
        )
        total = authored.count()
        complete = authored.filter(has_complete_provenance=True).count()
        reputation.source_quality_score = (complete / total) if total else 0.0

        reputation.update_overall()
        reputation.save()
        return reputation

    @staticmethod
    def snapshot(user, history_limit=25):
        reputation, _ = Reputation.objects.get_or_create(user=user)
        history = ReputationHistory.objects.filter(user=user)[:history_limit]
        return {
            "user_id": user.pk,
            "scores": {
                "accuracy": reputation.accuracy_score,
                "corrigibility": reputation.corrigibility_score,
                "source_quality": reputation.source_quality_score,
                "fair_critique": reputation.fair_critique_score,
                "domain_expertise": reputation.domain_expertise_score,
                "prediction_accuracy": reputation.prediction_accuracy_score,
                "social_behavior": reputation.social_behavior_score,
                "overall": reputation.overall_score,
            },
            "last_updated": reputation.last_updated.isoformat(),
            "history": [
                {
                    "dimension": item.dimension,
                    "old_value": item.old_value,
                    "new_value": item.new_value,
                    "event_type": item.event_type,
                    "event_id": item.event_id,
                    "created_at": item.created_at.isoformat(),
                }
                for item in history
            ],
            "methodology": {
                "prediction_accuracy": "Mean 1 - Brier score across resolved forecasts authored by the user.",
                "source_quality": "Share of authored Evidence items with at least one provenance step containing source type and source reference.",
                "unscored_dimensions": [
                    "accuracy",
                    "corrigibility",
                    "fair_critique",
                    "domain_expertise",
                    "social_behavior",
                ],
            },
        }
