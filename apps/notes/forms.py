from django import forms


class NoteForm(forms.Form):
    title = forms.CharField(max_length=200)
    content = forms.CharField(required=False, widget=forms.Textarea)
