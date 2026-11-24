from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import NoteForm
from .services import IdentityBindingRequired, IdentityInactive, NoteService


def _forbidden(request, exc):
    reason = "missing" if isinstance(exc, IdentityBindingRequired) else "inactive" if isinstance(exc, IdentityInactive) else "denied"
    return render(request, "notes/forbidden.html", {"reason": reason}, status=403)


@login_required
def note_list(request):
    try:
        notes = NoteService.list_notes(request.user)
    except PermissionDenied as exc:
        return _forbidden(request, exc)
    return render(request, "notes/list.html", {"notes": notes})


@login_required
def note_create(request):
    try:
        NoteService.identity_for_user(request.user)
    except PermissionDenied as exc:
        return _forbidden(request, exc)
    form = NoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            note = NoteService.create_note(user=request.user, **form.cleaned_data)
        except PermissionDenied as exc:
            return _forbidden(request, exc)
        return redirect("notes:detail", note_id=note.pk)
    return render(request, "notes/form.html", {"form": form, "mode": "create"})


@login_required
def note_detail(request, note_id):
    try:
        note = NoteService.get_note(request.user, note_id)
    except PermissionDenied as exc:
        return _forbidden(request, exc)
    return render(request, "notes/detail.html", {"note": note})


@login_required
def note_update(request, note_id):
    try:
        note = NoteService.get_note(request.user, note_id)
    except PermissionDenied as exc:
        return _forbidden(request, exc)

    form = NoteForm(
        request.POST or None,
        initial={"title": note.title, "content": note.content},
    )
    if request.method == "POST" and form.is_valid():
        try:
            note = NoteService.update_note(
                user=request.user,
                note_id=note_id,
                **form.cleaned_data,
            )
        except PermissionDenied as exc:
            return _forbidden(request, exc)
        return redirect("notes:detail", note_id=note.pk)
    return render(
        request,
        "notes/form.html",
        {"form": form, "mode": "update", "note": note},
    )


@login_required
@require_POST
def note_delete(request, note_id):
    try:
        NoteService.delete_note(user=request.user, note_id=note_id)
    except PermissionDenied as exc:
        return _forbidden(request, exc)
    return redirect("notes:list")
