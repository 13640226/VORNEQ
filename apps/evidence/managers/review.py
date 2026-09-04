from django.contrib.contenttypes.models import ContentType
from django.db import models


class ReviewRecordQuerySet(models.QuerySet):
    """
    QuerySet مخصوص ReviewRecord.

    ReviewRecord append-only است.
    """

    def for_object(self, obj):
        content_type = ContentType.objects.get_for_model(
            obj,
            for_concrete_model=False,
        )

        return self.filter(
            content_type=content_type,
            object_id=str(obj.pk),
        )

    def update(self, **kwargs):
        raise RuntimeError(
            "ReviewRecord is append-only; bulk update is forbidden"
        )

    def delete(self):
        raise RuntimeError(
            "ReviewRecord is append-only; bulk delete is forbidden"
        )


class ReviewRecordManager(models.Manager):
    def get_queryset(self):
        return ReviewRecordQuerySet(
            self.model,
            using=self._db,
        )

    def for_object(self, obj):
        return self.get_queryset().for_object(obj)