"""
Admin configuration for the Library application.

Project:
    Saman Kherad

This admin configuration is intentionally schema-safe:
it does not assume optional model fields exist.
"""

from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered

from .models import LibraryItem, AudioItem


# =============================================================================
# GLOBAL ADMIN SITE
# =============================================================================

admin.site.site_header = "مدیریت سامان خرد"
admin.site.site_title = "سامان خرد"
admin.site.index_title = "پنل مدیریت"


# =============================================================================
# BASE ADMIN
# =============================================================================

class SamanKheradAdmin(admin.ModelAdmin):
    """
    Shared configuration for Saman Kherad admin models.

    No model-specific field names are referenced here so this base class
    remains safe when model schemas change.
    """

    save_on_top = True

    actions_on_top = True
    actions_on_bottom = False

    empty_value_display = "—"

    list_per_page = 25

    list_max_show_all = 200

    preserve_filters = True

    save_as = False

    save_as_continue = True

    view_on_site = True


# =============================================================================
# LIBRARY ITEM ADMIN
# =============================================================================

class LibraryItemAdmin(SamanKheradAdmin):
    """
    Administration interface for LibraryItem.

    Model-specific list_display, list_filter, search_fields and
    prepopulated_fields should only be added after confirming the exact
    LibraryItem model schema.
    """

    pass


# =============================================================================
# AUDIO ITEM ADMIN
# =============================================================================

class AudioItemAdmin(SamanKheradAdmin):
    """
    Administration interface for AudioItem.

    This configuration deliberately avoids references to fields that may
    not exist in the current AudioItem model.
    """

    pass


# =============================================================================
# REGISTRATION
# =============================================================================

try:
    admin.site.register(LibraryItem, LibraryItemAdmin)
except AlreadyRegistered:
    pass


try:
    admin.site.register(AudioItem, AudioItemAdmin)
except AlreadyRegistered:
    pass