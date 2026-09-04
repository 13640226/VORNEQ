import difflib

from django.db import transaction

from apps.evidence.models import Claim, ContentVersion


class ContentVersionService:
    """Explicit, transaction-safe Claim versioning and knowledge-diff service."""

    VERSIONED_FIELDS = ("claim_text", "scope")

    @classmethod
    @transaction.atomic
    def record_snapshot(cls, *, claim: Claim, change_note: str = "", created_by=None):
        if claim._state.adding:
            raise ValueError("Claim must be persisted before recording a version")

        locked = Claim.objects.select_for_update().get(pk=claim.pk)
        latest = (
            ContentVersion.objects.filter(claim=locked)
            .order_by("-version_number")
            .first()
        )
        version_number = 1 if latest is None else latest.version_number + 1
        snapshot = ContentVersion.snapshot_for_claim(locked)

        if latest is not None and latest.snapshot == snapshot:
            return latest

        return ContentVersion.objects.create(
            claim=locked,
            version_number=version_number,
            snapshot=snapshot,
            change_note=change_note,
            created_by=created_by,
        )

    @classmethod
    @transaction.atomic
    def update_claim(
        cls,
        *,
        claim: Claim,
        claim_text: str | None = None,
        scope: str | None = None,
        change_note: str = "",
        created_by=None,
    ):
        """Update mutable Claim fields while preserving pre/post snapshots."""
        if claim._state.adding:
            raise ValueError("Claim must be persisted before it can be versioned")

        locked = Claim.objects.select_for_update().get(pk=claim.pk)
        cls.record_snapshot(
            claim=locked,
            change_note="Baseline snapshot" if not locked.content_versions.exists() else "",
            created_by=created_by,
        )

        changed_fields = []
        if claim_text is not None and claim_text != locked.claim_text:
            locked.claim_text = claim_text
            changed_fields.append("claim_text")
        if scope is not None and scope != locked.scope:
            locked.scope = scope
            changed_fields.append("scope")

        if changed_fields:
            locked.save(update_fields=[*changed_fields, "updated_at"])
            cls.record_snapshot(
                claim=locked,
                change_note=change_note,
                created_by=created_by,
            )

        return locked

    @staticmethod
    def _field_diff(field, before, after):
        before_text = "" if before is None else str(before)
        after_text = "" if after is None else str(after)
        return {
            "field": field,
            "before": before,
            "after": after,
            "changed": before != after,
            "unified_diff": list(
                difflib.unified_diff(
                    before_text.splitlines(),
                    after_text.splitlines(),
                    fromfile="before",
                    tofile="after",
                    lineterm="",
                )
            ),
        }

    @classmethod
    def compare(cls, *, before: ContentVersion, after: ContentVersion):
        if before.claim_id != after.claim_id:
            raise ValueError("ContentVersion objects must belong to the same Claim")
        if before.version_number > after.version_number:
            before, after = after, before

        fields = [
            cls._field_diff(field, before.snapshot.get(field), after.snapshot.get(field))
            for field in cls.VERSIONED_FIELDS
        ]
        return {
            "claim_id": str(before.claim_id),
            "from_version": before.version_number,
            "to_version": after.version_number,
            "from_created_at": before.created_at.isoformat(),
            "to_created_at": after.created_at.isoformat(),
            "changed_fields": [item["field"] for item in fields if item["changed"]],
            "fields": fields,
        }

    @classmethod
    def history(cls, claim: Claim):
        versions = ContentVersion.objects.filter(claim=claim).order_by("version_number")
        return [
            {
                "id": str(version.id),
                "version_number": version.version_number,
                "snapshot": version.snapshot,
                "change_note": version.change_note,
                "created_at": version.created_at.isoformat(),
            }
            for version in versions
        ]
