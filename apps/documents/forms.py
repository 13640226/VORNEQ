from django import forms

from .models import DocumentAccess


class DocumentForm(forms.Form):
    title = forms.CharField(max_length=200)
    content = forms.CharField(required=False, widget=forms.Textarea)
    tags = forms.CharField(required=False, help_text="Comma-separated tags")

    def clean_tags(self):
        raw_tags = self.cleaned_data.get("tags", "")
        return [tag.strip() for tag in raw_tags.split(",") if tag.strip()]


class DocumentShareForm(forms.Form):
    collaborator = forms.CharField(max_length=150, label="Username")
    role = forms.ChoiceField(
        choices=(
            (DocumentAccess.Role.EDITOR, "Editor"),
            (DocumentAccess.Role.VIEWER, "Viewer"),
        )
    )


class DocumentCollaboratorForm(forms.Form):
    collaborator = forms.CharField(max_length=150, label="Username")
