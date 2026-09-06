from django.contrib import admin

from .models import (
    Artifact,
    ArtifactBinding,
    ArtifactIdentityRole,
    Identity,
    UserIdentity,
)


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "is_active", "created_at")
    list_filter = ("kind", "is_active")
    search_fields = ("id",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ArtifactBinding)
class ArtifactBindingAdmin(admin.ModelAdmin):
    list_display = ("artifact", "content_type", "object_id", "created_by", "created_at")
    list_filter = ("content_type", "created_at")
    search_fields = ("artifact__id", "object_id")
    raw_id_fields = ("artifact", "content_type", "created_by")
    readonly_fields = ("created_at",)


@admin.register(Identity)
class IdentityAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "kind", "is_active", "created_at")
    list_filter = ("kind", "is_active")
    search_fields = ("id", "display_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(UserIdentity)
class UserIdentityAdmin(admin.ModelAdmin):
    list_display = ("user", "identity", "created_at")
    raw_id_fields = ("user", "identity")
    readonly_fields = ("created_at",)


@admin.register(ArtifactIdentityRole)
class ArtifactIdentityRoleAdmin(admin.ModelAdmin):
    list_display = ("artifact", "identity", "role", "is_primary", "valid_from", "valid_until")
    list_filter = ("role", "is_primary")
    raw_id_fields = ("artifact", "identity")
    readonly_fields = ("created_at",)
