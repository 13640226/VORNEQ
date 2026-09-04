from django.contrib import admin

from .models import Edge, Node


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("node_type", "label", "content_type", "object_id", "refreshed_at")
    list_filter = ("node_type", "content_type")
    search_fields = ("label", "object_id")
    readonly_fields = ("refreshed_at",)


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("kind", "source", "target", "canonical_ref", "refreshed_at")
    list_filter = ("kind",)
    search_fields = ("canonical_ref", "source__label", "target__label")
    readonly_fields = ("refreshed_at",)
