"""Account email feedback without changing allauth ownership or rate limits."""
import logging

from allauth.account.views import EmailView
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext as _

from config.email_backends import EmailDeliveryError

logger = logging.getLogger(__name__)


class AccountEmailView(EmailView):
    def _action_send(self, request, *args, **kwargs):
        try:
            response = super()._action_send(request, *args, **kwargs)
        except (EmailDeliveryError, OSError, ImproperlyConfigured):
            # Do not expose provider details or email addresses.
            logger.warning("Account verification email could not be sent")
            messages.error(request, _("Unable to send the verification email. Please try again later."))
            return None
        if not self._did_send_verification_email:
            messages.warning(request, _("No new verification email was sent. Check the selected address or try again later."))
        return response

    def post(self, request, *args, **kwargs):
        if "action_send" in request.POST and not request.POST.get("email") and "action_add" not in request.POST:
            messages.warning(request, _("Choose an email address before sending verification."))
        return super().post(request, *args, **kwargs)
