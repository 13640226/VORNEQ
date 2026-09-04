from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.evidence.models import EvidenceRelation, EvidenceState


@receiver(post_save, sender=EvidenceRelation)
def refresh_evidence_state_on_relation_save(sender, instance, **kwargs):
    if instance.claim_id:
        EvidenceState.update_for_claim(instance.claim)


@receiver(post_delete, sender=EvidenceRelation)
def refresh_evidence_state_on_relation_delete(sender, instance, **kwargs):
    if instance.claim_id:
        EvidenceState.update_for_claim(instance.claim)
