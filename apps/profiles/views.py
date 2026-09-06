import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from .forms import ProfileEditForm
from .models import UserProfile


@login_required
def profile_edit(request):
    form = ProfileEditForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Your profile was updated."))
        return redirect("profile")

    return render(
        request,
        "profile/edit.html",
        {"form": form, "profile_user": request.user, "user_profile": form.profile},
    )


@login_required
def profile_avatar(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    if not profile or not profile.avatar:
        raise Http404("Avatar not found.")

    try:
        handle = profile.avatar.storage.open(profile.avatar.name, "rb")
    except OSError as exc:
        raise Http404("Avatar not found.") from exc

    content_type = mimetypes.guess_type(profile.avatar.name)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type)
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response
