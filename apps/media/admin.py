from django.contrib import admin

from apps.media.models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("media_type", "title", "mime_type", "byte_size", "is_active", "created_at")
    list_filter = ("media_type", "is_active")
    search_fields = ("title", "alt_text", "mime_type")
    readonly_fields = ("created_at", "updated_at")
