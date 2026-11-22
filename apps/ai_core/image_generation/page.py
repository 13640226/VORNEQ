"""Staging-only Image Studio. A UI gate never grants provider or Ledger access."""
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import get_language, override
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .policy import actor_allowed, paid_provider_enabled

LABELS = {
    "en": {
        "status_rejected": "Request rejected before queueing. No new image charge was initiated.",
        "status_rate_limited": "Request rejected. Try a new request in {seconds} seconds; no new image charge was initiated.",
        "status_daily_limit": "Daily request limit reached. No new image charge was initiated.",
        "status_misconfigured": "Image service unavailable. The request was not queued.",
        "status_poll_stopped": "Automatic checks paused. Check this same request manually.",
        "status_recovery_error": "Recovery unavailable. Check again before submitting a new request.",
        "ack": "I understand this request may have incurred a charge and must not be retried automatically.",
        "new_request": "Start a new request",
        "status_acknowledged": "Acknowledgment saved on this browser. You can still check this request.",
        "status_unknown_missing": "This request is not yet confirmed. Do not submit again until reconciled.",
        "title": "Image Studio", "intro": "Private, owner-authorized Staging image generation.",
        "mode_mock": "Mock preview — no paid generation",
        "mode_paid": "Paid OpenAI image generation — staging only",
        "prompt": "Describe the image", "placeholder": "Describe the image you want to create…",
        "size": "Image dimensions", "consent_paid": "I understand this submission may incur an OpenAI charge. The Ledger cap is not a guaranteed provider billing limit.",
        "consent_mock": "I understand this is a synthetic, non-billable mock image.",
        "send": "Create one image", "check": "Check job status",
        "disclosure_paid": "Exactly one submission from this page. A request may be billed even if the browser times out. Do not resend after an uncertain result.",
        "disclosure_mock": "This preview does not contact OpenAI. A separately authorized worker must process queued jobs.",
        "status_wait": "No request has been submitted.", "status_sending": "Submitting once…",
        "status_queued": "Queued. Check status later; do not submit again.",
        "status_running": "Processing. Checking status does not create another image.",
        "status_completed": "Completed. Your signed image link will expire.",
        "status_failed": "The job failed. Check usage before attempting a new request.",
        "status_uncertain": "Outcome uncertain. Do not resubmit; ask an operator to reconcile usage.",
        "status_error": "Request status could not be confirmed. Check the existing job; do not resubmit.",
        "status_invalid": "Invalid job response. Do not resubmit.",
        "image_alt": "Generated image", "open": "Open signed image",
        "result_note": "Private signed link: do not share it.", "back": "Back to chat",
        "heading": "Job result", "one_shot": "A page refresh never retries the request.",
        "gallery_title": "Image History",
        "gallery_empty": "No completed images yet.",
        "gallery_loading": "Loading history...",
        "gallery_error": "History could not be loaded. Try again; no new image is created.",
        "gallery_retry": "Try again",
        "load_more": "Load More",
        "download": "Download",
        "share": "Share",
        "copy_image": "Copy Image",
        "fullscreen": "Fullscreen",
        "zoom_in": "Zoom In",
        "zoom_out": "Zoom Out",
        "zoom_reset": "Reset Zoom",
        "close": "Close",
        "selected_image": "Selected image",
        "share_unsupported": "Sharing is not supported in this browser. Use Download instead.",
        "share_failed": "Sharing failed. Use Download instead.",
        "share_preparing": "Preparing file...",
        "share_retap": "File ready. Tap Share again.",
        "copy_done": "Image copied.",
        "copy_failed": "The image could not be copied. Use Download instead.",
        "image_card": "Image from {date}",
        "viewer_title": "Image viewer",
        "load_failed": "The image could not be loaded.",
        "mock_badge": "Mock",
    },
    "de": {
        "status_rejected": "Anfrage vor dem Einreihen abgelehnt. Keine neuen Bildkosten ausgelöst.",
        "status_rate_limited": "Anfrage abgelehnt. Neue Anfrage in {seconds} Sekunden möglich; keine neuen Bildkosten ausgelöst.",
        "status_daily_limit": "Tägliches Anfragelimit erreicht. Keine neuen Bildkosten ausgelöst.",
        "status_misconfigured": "Bilddienst nicht verfügbar. Die Anfrage wurde nicht eingereiht.",
        "status_poll_stopped": "Automatische Prüfung pausiert. Diesen Auftrag manuell prüfen.",
        "status_recovery_error": "Wiederherstellung nicht verfügbar. Vor einer neuen Anfrage erneut prüfen.",
        "ack": "Ich verstehe, dass Kosten entstanden sein können und die Anfrage nicht automatisch wiederholt werden darf.",
        "new_request": "Neue Anfrage beginnen",
        "status_acknowledged": "Bestätigung in diesem Browser gespeichert. Der Auftrag kann weiterhin geprüft werden.",
        "status_unknown_missing": "Dieser Auftrag ist noch nicht bestätigt. Bis zur Klärung nicht erneut senden.",
        "title": "Bildstudio", "intro": "Private, für Staging freigegebene Bildgenerierung.",
        "mode_mock": "Mock-Vorschau — kein kostenpflichtiger Aufruf",
        "mode_paid": "Kostenpflichtige OpenAI-Bildgenerierung — nur Staging",
        "prompt": "Bild beschreiben", "placeholder": "Beschreiben Sie das gewünschte Bild…",
        "size": "Bildgröße", "consent_paid": "Ich verstehe, dass diese Anfrage OpenAI-Kosten verursachen kann. Das Ledger-Limit garantiert keine Obergrenze der Anbieterrechnung.",
        "consent_mock": "Ich verstehe, dass dies ein synthetisches, kostenloses Mock-Bild ist.",
        "send": "Ein Bild erstellen", "check": "Auftragsstatus prüfen",
        "disclosure_paid": "Nur eine Übermittlung pro Seitenaufruf. Auch bei Browser-Timeout können Kosten entstehen. Bei unklarem Ergebnis nicht erneut senden.",
        "disclosure_mock": "Diese Vorschau ruft OpenAI nicht auf. Ein separat freigegebener Worker muss die Aufträge verarbeiten.",
        "status_wait": "Noch keine Anfrage gesendet.", "status_sending": "Einmalige Übermittlung…",
        "status_queued": "In Warteschlange. Status später prüfen; nicht erneut senden.",
        "status_running": "Wird verarbeitet. Statusabfragen erzeugen kein neues Bild.",
        "status_completed": "Fertig. Der signierte Bildlink läuft ab.",
        "status_failed": "Der Auftrag ist fehlgeschlagen. Vor einer neuen Anfrage den Verbrauch prüfen.",
        "status_uncertain": "Ergebnis unklar. Nicht erneut senden; Verbrauch manuell abgleichen.",
        "status_error": "Auftragsstatus nicht bestätigt. Vorhandenen Auftrag prüfen, nicht erneut senden.",
        "status_invalid": "Ungültige Auftragsantwort. Nicht erneut senden.",
        "image_alt": "Generiertes Bild", "open": "Signiertes Bild öffnen",
        "result_note": "Privater signierter Link: nicht weitergeben.", "back": "Zurück zum Chat",
        "heading": "Auftragsergebnis", "one_shot": "Ein Neuladen der Seite wiederholt keine Anfrage.",
        "gallery_title": "Bildverlauf",
        "gallery_empty": "Noch keine fertigen Bilder.",
        "gallery_loading": "Verlauf wird geladen ...",
        "gallery_error": "Verlauf konnte nicht geladen werden. Erneut versuchen; es wird kein neues Bild erzeugt.",
        "gallery_retry": "Erneut versuchen",
        "load_more": "Mehr laden",
        "download": "Herunterladen",
        "share": "Teilen",
        "copy_image": "Bild kopieren",
        "fullscreen": "Vollbild",
        "zoom_in": "Vergrößern",
        "zoom_out": "Verkleinern",
        "zoom_reset": "Originalgröße",
        "close": "Schließen",
        "selected_image": "Ausgewähltes Bild",
        "share_unsupported": "Teilen wird in diesem Browser nicht unterstützt. Bitte Herunterladen nutzen.",
        "share_failed": "Teilen fehlgeschlagen. Bitte Herunterladen nutzen.",
        "share_preparing": "Datei wird vorbereitet ...",
        "share_retap": "Datei bereit. Bitte erneut auf Teilen tippen.",
        "copy_done": "Bild kopiert.",
        "copy_failed": "Das Bild konnte nicht kopiert werden. Bitte Herunterladen nutzen.",
        "image_card": "Bild vom {date}",
        "viewer_title": "Bildansicht",
        "load_failed": "Das Bild konnte nicht geladen werden.",
        "mock_badge": "Mock",
    },
    "fa": {
        "status_rejected": "درخواست پیش از ورود به صف رد شد. هزینه‌ای برای تولید تصویر جدید آغاز نشد.",
        "status_rate_limited": "درخواست رد شد. پس از {seconds} ثانیه می‌توانید درخواست جدیدی بفرستید؛ هزینه جدیدی آغاز نشد.",
        "status_daily_limit": "سهمیه روزانه درخواست‌ها پر شده است. هزینه جدیدی آغاز نشد.",
        "status_misconfigured": "سرویس تولید تصویر در دسترس نیست. درخواست وارد صف نشد.",
        "status_poll_stopped": "بررسی خودکار متوقف شد. وضعیت همین درخواست را دستی بررسی کنید.",
        "status_recovery_error": "بازیابی در دسترس نیست. پیش از ارسال درخواست جدید، دوباره بررسی کنید.",
        "ack": "می‌دانم ممکن است برای این درخواست هزینه ثبت شده باشد و نباید خودکار تکرار شود.",
        "new_request": "شروع درخواست جدید",
        "status_acknowledged": "تأیید در همین مرورگر ثبت شد. همچنان می‌توانید وضعیت درخواست را بررسی کنید.",
        "status_unknown_missing": "نتیجه این درخواست هنوز تأیید نشده است. تا روشن شدن وضعیت دوباره ارسال نکنید.",
        "title": "استودیوی تصویر", "intro": "تولید تصویر خصوصی با مجوز محدود در محیط آزمایشی.",
        "mode_mock": "پیش‌نمایش ساختگی — بدون هزینه OpenAI",
        "mode_paid": "تولید تصویر پولی OpenAI — فقط Staging",
        "prompt": "تصویر مورد نظر را توصیف کنید", "placeholder": "توصیف تصویر را بنویسید…",
        "size": "ابعاد تصویر", "consent_paid": "می‌دانم که ارسال این درخواست ممکن است هزینه OpenAI داشته باشد و سقف Ledger تضمین سقف صورتحساب نیست.",
        "consent_mock": "می‌دانم این فقط تصویر آزمایشی ساختگی و بدون هزینه است.",
        "send": "ساخت یک تصویر", "check": "بررسی وضعیت درخواست",
        "disclosure_paid": "در این صفحه فقط یک بار ارسال انجام می‌شود. حتی در صورت پایان مهلت مرورگر ممکن است هزینه ثبت شده باشد. درخواست نامشخص را دوباره نفرستید.",
        "disclosure_mock": "این پیش‌نمایش OpenAI را فراخوانی نمی‌کند. پردازش صف به Worker مجاز جداگانه نیاز دارد.",
        "status_wait": "هنوز درخواستی ارسال نشده است.", "status_sending": "ارسال یک‌باره…",
        "status_queued": "در صف قرار گرفت. بعداً وضعیت را بررسی کنید؛ دوباره ارسال نکنید.",
        "status_running": "در حال پردازش. بررسی وضعیت تصویر جدید نمی‌سازد.",
        "status_completed": "کامل شد. لینک امضاشده تصویر موقت است.",
        "status_failed": "درخواست شکست خورد. پیش از درخواست جدید، میزان مصرف را بررسی کنید.",
        "status_uncertain": "نتیجه نامشخص است. دوباره ارسال نکنید؛ هزینه باید بررسی شود.",
        "status_error": "وضعیت درخواست تأیید نشد. همان درخواست را بررسی کنید؛ دوباره ارسال نکنید.",
        "status_invalid": "پاسخ درخواست نامعتبر است. دوباره ارسال نکنید.",
        "image_alt": "تصویر تولیدشده", "open": "باز کردن تصویر امضاشده",
        "result_note": "این لینک خصوصی است؛ آن را به اشتراک نگذارید.", "back": "بازگشت به چت",
        "heading": "نتیجه درخواست", "one_shot": "بارگذاری مجدد صفحه درخواست را تکرار نمی‌کند.",
        "gallery_title": "تاریخچه تصاویر",
        "gallery_empty": "هنوز تصویر تکمیل‌شده‌ای وجود ندارد.",
        "gallery_loading": "در حال بارگذاری تاریخچه...",
        "gallery_error": "تاریخچه بارگذاری نشد. دوباره تلاش کنید؛ هیچ تصویر جدیدی ساخته نمی‌شود.",
        "gallery_retry": "تلاش دوباره",
        "load_more": "نمایش بیشتر",
        "download": "دانلود",
        "share": "اشتراک‌گذاری",
        "copy_image": "کپی تصویر",
        "fullscreen": "تمام‌صفحه",
        "zoom_in": "بزرگ‌نمایی",
        "zoom_out": "کوچک‌نمایی",
        "zoom_reset": "اندازه اصلی",
        "close": "بستن",
        "selected_image": "تصویر انتخاب‌شده",
        "share_unsupported": "اشتراک‌گذاری در این مرورگر پشتیبانی نمی‌شود. از دانلود استفاده کنید.",
        "share_failed": "اشتراک‌گذاری انجام نشد. از دانلود استفاده کنید.",
        "share_preparing": "در حال آماده‌سازی فایل...",
        "share_retap": "فایل آماده است. دوباره اشتراک‌گذاری را بزنید.",
        "copy_done": "تصویر کپی شد.",
        "copy_failed": "کپی تصویر انجام نشد. از دانلود استفاده کنید.",
        "image_card": "تصویر {date}",
        "viewer_title": "نمایش تصویر",
        "load_failed": "تصویر بارگذاری نشد.",
        "mock_badge": "آزمایشی",
    },
}


def image_studio_allowed(user):
    """Independent UI switch in addition to the existing server-side image gates."""
    if (getattr(settings, "VORNEQ_ENV", "") != "staging"
            or getattr(settings, "DEBUG", True)
            or not getattr(settings, "VORNEQ_AI_IMAGE_UI_ENABLED", False)
            or not actor_allowed(user)):
        return False
    provider = getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "")
    return provider == "mock" or (provider == "openai" and paid_provider_enabled())


@never_cache
@require_GET
def image_studio_page(request):
    if (getattr(settings, "VORNEQ_ENV", "") != "staging"
            or getattr(settings, "DEBUG", True)
            or not getattr(settings, "VORNEQ_AI_IMAGE_UI_ENABLED", False)):
        raise Http404("Image Studio disabled")
    if not request.user.is_authenticated:
        result = HttpResponse("Authentication required", status=401)
        result["Cache-Control"] = "no-store, private"
        result["X-Robots-Tag"] = "noindex, nofollow"
        return result
    if not image_studio_allowed(request.user):
        raise Http404("Image Studio unavailable")
    requested = request.GET.get("lang", "")
    language = requested if requested in LABELS else (get_language() or "en")[:2]
    if language not in LABELS:
        language = "en"
    provider = getattr(settings, "VORNEQ_AI_IMAGE_PROVIDER", "mock")
    request.LANGUAGE_CODE = language
    with override(language):
        result = render(request, "ai_core/image_studio.html", {
            "labels": LABELS[language],
            "image_paid": provider == "openai",
            "image_create_url": reverse("ai_core:image-jobs"),
            "image_history_url": reverse("ai_core:image-history"),
            "chat_url": reverse("ai_core:chat"),
        })
    result["Cache-Control"] = "no-store, private"
    result["X-Robots-Tag"] = "noindex, nofollow"
    return result
