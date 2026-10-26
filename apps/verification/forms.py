from django import forms
from django.contrib.contenttypes.models import ContentType
from apps.evidence.models import Claim
from .models import ALLOWED_ARTIFACT_MODELS, VerificationMethod, VerificationResult


class VerificationRequestForm(forms.Form):
    artifact_content_type = forms.ModelChoiceField(queryset=ContentType.objects.none())
    artifact_object_id = forms.CharField(max_length=255)
    claim = forms.ModelChoiceField(queryset=Claim.objects.all())
    method = forms.ModelChoiceField(queryset=VerificationMethod.objects.filter(is_active=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["artifact_content_type"].queryset = ContentType.objects.filter(
            app_label__in={a for a, _ in ALLOWED_ARTIFACT_MODELS},
            model__in={m for _, m in ALLOWED_ARTIFACT_MODELS},
        )

    def clean_artifact_content_type(self):
        ct = self.cleaned_data["artifact_content_type"]
        if (ct.app_label, ct.model) not in ALLOWED_ARTIFACT_MODELS:
            raise forms.ValidationError("Unsupported artifact type.")
        return ct


class VerificationResultForm(forms.Form):
    outcome = forms.ChoiceField(choices=VerificationResult.Outcome.choices)
    reported_confidence = forms.IntegerField(min_value=0, max_value=100)
    summary = forms.CharField(widget=forms.Textarea, required=False)
