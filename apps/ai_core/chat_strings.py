"""Phase C development-preview labels; no extra production catalog changes."""

LABELS = {
    "en": {
        "entry": "Try AI chat (development preview)",
        "title": "VORNEQ AI chat",
        "intro": "Ask about public VORNEQ sources. Answers are drafts, not verified facts.",
        "warning": "Development preview: do not enter personal or confidential data.",
        "question": "Ask about a public source",
        "send": "Ask",
        "clear": "Clear chat",
        "loading": "Checking public sources and preparing a draft…",
        "empty": "No sufficiently relevant public source was found.",
        "error": "The response could not be displayed. Check request usage before trying again to avoid duplicate charges.",
        "timeout": "The request timed out in this browser. It may have completed on the server; check usage before resending.",
        "sources": "Sources",
        "status": "Generated draft — source quotes checked; factual claims not verified",
        "recoveryChecking": "Checking the previous request without calling the model again…",
        "recoveryUncertain": "Previous request status is uncertain. Do not resend automatically; check usage first. Clear chat only if you intend a new billable request.",
        "recoveryExpired": "The previous answer is no longer available after the short recovery window. No new request was sent.",
        "single_turn": "Questions are independent. For Staging recovery, only a request ID is kept in this tab; the response is temporarily cached on the server for up to 15 minutes. Refresh does not resend. Clearing chat never cancels an already-billed request.",
        "back": "Back to search",
    },
    "de": {
        "entry": "KI-Chat testen (Entwicklungsvorschau)",
        "title": "VORNEQ KI-Chat",
        "intro": "Fragen Sie zu öffentlichen VORNEQ-Quellen. Antworten sind Entwürfe, keine verifizierten Fakten.",
        "warning": "Entwicklungsvorschau: Bitte keine persönlichen oder vertraulichen Daten eingeben.",
        "question": "Frage zu einer öffentlichen Quelle",
        "send": "Fragen",
        "clear": "Chat löschen",
        "loading": "Öffentliche Quellen werden geprüft und ein Entwurf vorbereitet…",
        "empty": "Keine ausreichend relevante öffentliche Quelle gefunden.",
        "error": "Die Antwort konnte nicht angezeigt werden. Prüfen Sie vor einem erneuten Versuch die Nutzung, um doppelte Kosten zu vermeiden.",
        "timeout": "Zeitüberschreitung im Browser. Der Server könnte fertig sein; prüfen Sie die Nutzung vor erneutem Senden.",
        "sources": "Quellen",
        "status": "Generierter Entwurf – Quellenzitate geprüft; Sachbehauptungen nicht verifiziert",
        "recoveryChecking": "Vorherige Anfrage wird geprüft – ohne erneuten Modellaufruf…",
        "recoveryUncertain": "Status der vorherigen Anfrage unklar. Nicht automatisch erneut senden; zuerst Verbrauch prüfen. Chat nur löschen, wenn eine neue kostenpflichtige Anfrage beabsichtigt ist.",
        "recoveryExpired": "Die vorherige Antwort ist nach dem kurzen Wiederherstellungsfenster nicht mehr verfügbar. Keine neue Anfrage wurde gesendet.",
        "single_turn": "Fragen sind unabhängig. Für die Staging-Wiederherstellung bleibt nur eine Anfrage-ID im Tab; die Antwort wird bis zu 15 Minuten serverseitig zwischengespeichert. Neuladen sendet nicht erneut. Chat löschen bricht laufende Anfragen nicht ab.",
        "back": "Zurück zur Suche",
    },
    "fa": {
        "entry": "آزمایش گفت‌وگوی AI (پیش‌نمایش توسعه)",
        "title": "گفت‌وگوی هوش مصنوعی VORNEQ",
        "intro": "دربارهٔ منابع عمومی VORNEQ سؤال کنید. پاسخ‌ها پیش‌نویس‌اند و صحت مستقل ندارند.",
        "warning": "پیش‌نمایش توسعه: اطلاعات شخصی یا محرمانه وارد نکنید.",
        "question": "دربارهٔ یک منبع عمومی بپرسید",
        "send": "ارسال",
        "clear": "پاک‌کردن گفت‌وگو",
        "loading": "در حال بررسی منابع عمومی و تهیهٔ پیش‌نویس…",
        "empty": "منبع عمومی کافی و مرتبط پیدا نشد.",
        "error": "پاسخ نمایش داده نشد. پیش از ارسال دوباره، مصرف درخواست را بررسی کنید تا هزینهٔ تکراری ایجاد نشود.",
        "timeout": "مهلت انتظار مرورگر تمام شد. ممکن است درخواست در سرور کامل شده باشد؛ پیش از ارسال دوباره مصرف را بررسی کنید.",
        "sources": "منابع",
        "status": "پیش‌نویس تولیدشده؛ نقل‌قول منابع بررسی شده، درستی ادعاها تأیید نشده است",
        "recoveryChecking": "در حال بررسی درخواست قبلی، بدون فراخوانی دوباره مدل…",
        "recoveryUncertain": "وضعیت درخواست قبلی نامشخص است. ارسال خودکار مجدد ممنوع؛ ابتدا مصرف را بررسی کنید. پاک‌کردن چت فقط زمانی انجام شود که واقعاً قصد درخواست هزینه‌دار تازه دارید.",
        "recoveryExpired": "پاسخ قبلی پس از پایان مهلت کوتاه بازیابی دیگر در دسترس نیست؛ درخواست جدیدی ارسال نشد.",
        "single_turn": "پرسش‌ها مستقل‌اند. برای بازیابی در Staging فقط شناسه درخواست در همین زبانه می‌ماند و پاسخ حداکثر ۱۵ دقیقه در کش سرور ذخیره می‌شود. Refresh درخواست را تکرار نمی‌کند. پاک‌کردن چت درخواست در حال اجرا را لغو نمی‌کند.",
        "back": "بازگشت به جست‌وجو",
    },
}


# Production has its own factual status and recovery wording. Staging and
# development retain their existing language packs and safety notices.
PRODUCTION_LABELS = {
    "en": {
        "entry": "Open AI chat",
        "warning": (
            "Production AI pilot: do not enter personal or confidential data. "
            "Answers are drafts, not independently verified facts."
        ),
        "single_turn": (
            "Questions are independent. For Production request recovery, only a request ID "
            "is kept in this tab; the response is temporarily cached on the server for up to "
            "15 minutes. Refresh does not resend. Clearing chat cannot cancel an already "
            "submitted request or undo its cost."
        ),
    },
    "de": {
        "entry": "KI-Chat öffnen",
        "warning": (
            "KI-Pilot in Production: Bitte keine persönlichen oder vertraulichen Daten "
            "eingeben. Antworten sind Entwürfe, keine unabhängig verifizierten Fakten."
        ),
        "single_turn": (
            "Fragen sind unabhängig. Zur Wiederherstellung von Production-Anfragen bleibt "
            "nur eine Anfrage-ID in diesem Tab; die Antwort wird serverseitig bis zu "
            "15 Minuten zwischengespeichert. Neuladen sendet nicht erneut. Das Löschen "
            "des Chats bricht eine bereits gesendete Anfrage nicht ab und macht "
            "keine Kosten rückgängig."
        ),
    },
    "fa": {
        "entry": "بازکردن گفت‌وگوی هوش مصنوعی",
        "warning": (
            "نسخه آزمایشی هوش مصنوعی Production: اطلاعات شخصی یا محرمانه وارد نکنید. "
            "پاسخ‌ها پیش‌نویس‌اند و صحت آن‌ها مستقلاً تأیید نشده است."
        ),
        "single_turn": (
            "پرسش‌ها مستقل‌اند. برای بازیابی درخواست در Production فقط شناسهٔ درخواست "
            "در همین زبانه نگه‌داری می‌شود و پاسخ حداکثر ۱۵ دقیقه به‌طور موقت "
            "در سرور ذخیره می‌شود. بارگذاری دوبارهٔ صفحه درخواست را تکرار نمی‌کند. "
            "پاک‌کردن چت، درخواست ارسال‌شده یا هزینهٔ آن را لغو نمی‌کند."
        ),
    },
}


def chat_labels(language, *, environment="development"):
    language = (language or "en")[:2]
    if language not in LABELS:
        language = "en"
    labels = LABELS[language]
    if environment == "production":
        return {**labels, **PRODUCTION_LABELS[language]}
    return labels
