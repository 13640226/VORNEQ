from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.services import ReputationService
from apps.evidence.models import PredictionResolution, ProvenanceStep


@receiver(post_save, sender=PredictionResolution)
def refresh_prediction_reputation(sender, instance, created, **kwargs):
    if not created:
        return
    forecaster = instance.prediction.created_by
    if forecaster is not None:
        ReputationService.update_prediction_accuracy(forecaster, instance)


@receiver(post_save, sender=ProvenanceStep)
def refresh_source_quality_reputation(sender, instance, created, **kwargs):
    if not created:
        return
    author = instance.evidence.created_by
    if author is not None:
        ReputationService.update_source_quality(
            author,
            instance.evidence,
            event_id=instance.pk,
        )
