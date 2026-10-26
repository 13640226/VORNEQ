from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import FormView, ListView, DetailView
from django.contrib.contenttypes.models import ContentType

from .forms import VerificationRequestForm, VerificationResultForm
from .models import VerificationRequest
from .services.verification import (
    request_verification, start_verification, submit_verification_result,
    cancel_verification, fail_verification,
)


class VerificationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "verification.view_verificationrequest"
    model = VerificationRequest
    template_name = "verification/index.html"
    context_object_name = "requests"

    def get_queryset(self):
        qs = super().get_queryset().select_related("claim", "method")
        if not self.request.user.is_staff:
            qs = qs.filter(requested_by=self.request.user)
        return qs


class VerificationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "verification.view_verificationrequest"
    model = VerificationRequest
    template_name = "verification/detail.html"
    context_object_name = "verification"

    def get_queryset(self):
        qs = super().get_queryset().select_related("claim", "method")
        if not self.request.user.is_staff:
            qs = qs.filter(requested_by=self.request.user)
        return qs


class VerificationCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "verification.add_verificationrequest"
    template_name = "verification/create.html"
    form_class = VerificationRequestForm

    def form_valid(self, form):
        data = form.cleaned_data
        content_type = ContentType.objects.get_for_id(data["artifact_content_type"].pk)
        artifact = get_object_or_404(content_type.model_class(), pk=data["artifact_object_id"])
        try:
            created = request_verification(
                artifact=artifact, claim=data["claim"], method=data["method"],
                requested_by=self.request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return redirect("verification:detail", pk=created.pk)


class _ActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    http_method_names = ["post"]
    permission_required = "verification.change_verificationrequest"
    operation = None

    def post(self, request, pk):
        obj = get_object_or_404(VerificationRequest, pk=pk)
        if not request.user.is_staff and obj.requested_by_id != request.user.pk:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        try:
            self.operation(verification_request=obj, actor=request.user)
        except (ValidationError, ValueError) as exc:
            return HttpResponseBadRequest(str(exc))
        return redirect("verification:detail", pk=pk)


class VerificationStartView(_ActionView):
    operation = staticmethod(start_verification)


class VerificationCancelView(_ActionView):
    operation = staticmethod(cancel_verification)


class VerificationFailView(_ActionView):
    operation = staticmethod(fail_verification)


class VerificationSubmitView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "verification.add_verificationresult"
    template_name = "verification/start.html"
    form_class = VerificationResultForm

    def dispatch(self, request, *args, **kwargs):
        self.verification = get_object_or_404(VerificationRequest, pk=kwargs["pk"])
        if not request.user.is_staff and self.verification.requested_by_id != request.user.pk:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            submit_verification_result(
                verification_request=self.verification,
                verifier=self.request.user,
                **form.cleaned_data,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return redirect("verification:detail", pk=self.verification.pk)
