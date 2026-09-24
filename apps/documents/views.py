from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import DocumentCollaboratorForm, DocumentForm, DocumentShareForm
from .identity_resolver import IdentityResolver
from .services import DocumentService


User = get_user_model()


def _forbidden(exc):
    return HttpResponseForbidden(str(exc))


def _resolve_collaborator(form):
    username = form.cleaned_data["collaborator"]
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        form.add_error("collaborator", "User not found.")
        return None


@login_required
def document_list(request):
    try:
        documents = DocumentService.list_documents(user=request.user)
    except PermissionDenied as exc:
        return _forbidden(exc)
    return render(request, "documents/list.html", {"documents": documents})


@login_required
def document_create(request):
    form = DocumentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            document = DocumentService.create_document(
                user=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:detail", document_id=document.pk)
    return render(request, "documents/form.html", {"form": form, "mode": "create"})


@login_required
def document_detail(request, document_id):
    try:
        document = DocumentService.get_document(
            user=request.user,
            document_id=document_id,
        )
        identity = IdentityResolver.resolve(request.user)
    except PermissionDenied as exc:
        return _forbidden(exc)

    is_owner = identity.pk == document.owner_identity_id
    access_entries = (
        document.access_entries.select_related("identity").all() if is_owner else ()
    )
    return render(
        request,
        "documents/detail.html",
        {
            "document": document,
            "is_owner": is_owner,
            "access_entries": access_entries,
            "share_form": DocumentShareForm(),
            "revoke_form": DocumentCollaboratorForm(),
        },
    )


@login_required
def document_update(request, document_id):
    try:
        document = DocumentService.get_document(
            user=request.user,
            document_id=document_id,
        )
    except PermissionDenied as exc:
        return _forbidden(exc)

    form = DocumentForm(
        request.POST or None,
        initial={
            "title": document.title,
            "content": document.content,
            "tags": ", ".join(document.tags),
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            document = DocumentService.update_document(
                user=request.user,
                document_id=document_id,
                **form.cleaned_data,
            )
        except PermissionDenied as exc:
            return _forbidden(exc)
        except ValidationError as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("documents:detail", document_id=document.pk)
    return render(
        request,
        "documents/form.html",
        {"form": form, "mode": "update", "document": document},
    )


@login_required
@require_POST
def document_share(request, document_id):
    form = DocumentShareForm(request.POST)
    if not form.is_valid():
        return _render_access_error(request, document_id, form, DocumentCollaboratorForm())

    collaborator = _resolve_collaborator(form)
    if collaborator is None:
        return _render_access_error(request, document_id, form, DocumentCollaboratorForm())

    try:
        DocumentService.share_document(
            user=request.user,
            document_id=document_id,
            collaborator=collaborator,
            role=form.cleaned_data["role"],
        )
    except PermissionDenied as exc:
        return _forbidden(exc)
    except ValidationError as exc:
        form.add_error(None, str(exc))
        return _render_access_error(request, document_id, form, DocumentCollaboratorForm())
    return redirect("documents:detail", document_id=document_id)


@login_required
@require_POST
def document_revoke(request, document_id):
    form = DocumentCollaboratorForm(request.POST)
    if not form.is_valid():
        return _render_access_error(request, document_id, DocumentShareForm(), form)

    collaborator = _resolve_collaborator(form)
    if collaborator is None:
        return _render_access_error(request, document_id, DocumentShareForm(), form)

    try:
        DocumentService.revoke_access(
            user=request.user,
            document_id=document_id,
            collaborator=collaborator,
        )
    except PermissionDenied as exc:
        return _forbidden(exc)
    except ValidationError as exc:
        form.add_error(None, str(exc))
        return _render_access_error(request, document_id, DocumentShareForm(), form)
    return redirect("documents:detail", document_id=document_id)


def _render_access_error(request, document_id, share_form, revoke_form):
    try:
        document = DocumentService.get_document(
            user=request.user,
            document_id=document_id,
        )
        identity = IdentityResolver.resolve(request.user)
    except PermissionDenied as exc:
        return _forbidden(exc)

    is_owner = identity.pk == document.owner_identity_id
    access_entries = (
        document.access_entries.select_related("identity").all() if is_owner else ()
    )
    return render(
        request,
        "documents/detail.html",
        {
            "document": document,
            "is_owner": is_owner,
            "access_entries": access_entries,
            "share_form": share_form,
            "revoke_form": revoke_form,
        },
        status=400,
    )
