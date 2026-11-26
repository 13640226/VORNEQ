from django import forms
from django.utils.translation import gettext_lazy as _

from .models import DocumentAccess


class DocumentForm(forms.Form):
    title = forms.CharField(max_length=200, label=_("Title"))
    content = forms.CharField(required=False, widget=forms.Textarea, label=_("Content"))
    tags = forms.CharField(required=False, label=_("Tags"), help_text=_("Comma-separated tags"))

    def clean_tags(self):
        raw_tags = self.cleaned_data.get("tags", "")
        return [tag.strip() for tag in raw_tags.split(",") if tag.strip()]


class DocumentShareForm(forms.Form):
    collaborator = forms.CharField(max_length=150, label=_("Username"))
    role = forms.ChoiceField(
        label=_("Role"), choices=(
            (DocumentAccess.Role.EDITOR, _("Editor")),
            (DocumentAccess.Role.VIEWER, _("Viewer")),
        )
    )


class DocumentCollaboratorForm(forms.Form):
    collaborator = forms.CharField(max_length=150, label=_("Username"))
