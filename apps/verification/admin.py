from django.contrib import admin

from .models import (
    VerificationEvidence,
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)


@admin.register(VerificationMethod)
class VerificationMethodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "mode", "version", "is_active")
    list_filter = ("mode", "is_active")
    search_fields = ("code", "name", "description")


class VerificationResultInline(admin.TabularInline):
    model = VerificationResult
    extra = 0
    fields = ("verifier", "outcome", "reported_confidence", "summary")
    raw_id_fields = ("verifier",)


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "artifact_display",
        "claim",
        "method",
        "requested_by",
        "status",
        "created_at",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = (
        "claim__claim_text",
        "method__code",
        "method__name",
        "requested_by__username",
        "requested_by__email",
        "artifact_object_id",
    )
    raw_id_fields = ("requested_by", "claim", "artifact_content_type")
    inlines = (VerificationResultInline,)

    @admin.display(description="Artifact")
    def artifact_display(self, obj):
        return str(obj.artifact) if obj.artifact is not None else "—"


class VerificationEvidenceInline(admin.TabularInline):
    model = VerificationEvidence
    extra = 0
    fields = ("evidence_relation", "visibility", "notes")
    raw_id_fields = ("evidence_relation",)


@admin.register(VerificationResult)
class VerificationResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "verifier",
        "outcome",
        "reported_confidence",
        "created_at",
    )
    list_filter = ("outcome", "created_at")
    search_fields = (
        "request__claim__claim_text",
        "verifier__username",
        "verifier__email",
        "summary",
    )
    raw_id_fields = ("request", "verifier")
    inlines = (VerificationEvidenceInline,)


@admin.register(VerificationEvidence)
class VerificationEvidenceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "result",
        "evidence_relation",
        "visibility",
        "created_at",
    )
    list_filter = ("visibility", "created_at")
    search_fields = (
        "result__request__claim__claim_text",
        "evidence_relation__evidence__integrity_digest",
        "notes",
    )
    raw_id_fields = ("result", "evidence_relation")
