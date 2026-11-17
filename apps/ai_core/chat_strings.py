"""Multilingual Chat AI labels with separate Production safety copy and V2 UI labels."""

from django.conf import settings

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



ENVIRONMENT_LABELS = {
    "en": {
        "staging": {
            "entry": "Open AI chat (staging trial)",
            "warning": "Authorized staging trial: do not enter personal or confidential data.",
        },
        "production": {
            "entry": "Open AI chat",
            "warning": "Do not enter personal or confidential data. Answers are generated drafts.",
        },
    },
    "de": {
        "staging": {
            "entry": "KI-Chat öffnen (Staging-Test)",
            "warning": "Autorisierter Staging-Test: Bitte keine persönlichen oder vertraulichen Daten eingeben.",
        },
        "production": {
            "entry": "KI-Chat öffnen",
            "warning": "Bitte keine persönlichen oder vertraulichen Daten eingeben. Antworten sind generierte Entwürfe.",
        },
    },
    "fa": {
        "staging": {
            "entry": "باز کردن گفت‌وگوی AI (آزمایش Staging)",
            "warning": "آزمایش مجاز Staging: اطلاعات شخصی یا محرمانه وارد نکنید.",
        },
        "production": {
            "entry": "باز کردن گفت‌وگوی AI",
            "warning": "اطلاعات شخصی یا محرمانه وارد نکنید. پاسخ‌ها پیش‌نویس تولیدشده‌اند.",
        },
    },
}

# Chat UI V2 labels: shared by every environment.
UI_LABELS = {
    "en": {
        "single_turn": "Each question is answered on its own; earlier messages are not sent to the model.",
        "recovery_note": "If the page reloads, the answer is fetched again without a new model call, using only a request ID kept in this tab (up to 15 minutes). Clearing the chat does not cancel a request that was already sent.",
        "you": "You",
        "assistant": "VORNEQ AI",
        "copy": "Copy answer",
        "copied": "Copied",
        "examples_title": "Try a question",
        "examples": ("What is photosynthesis?", "Who was Avicenna?", "How does a solar cell work?"),
        "examples_note": "Examples only fill in the box; nothing is sent until you press Ask.",
        "hint": "Ctrl + Enter to send",
        "panel_title": "About this chat",
        "sources_label": "Sources",
        "sources_global": "Public encyclopedia articles (Wikipedia)",
        "sources_local": "Public VORNEQ sources",
        "answers_label": "Answers",
        "answers_value": "Generated drafts; claims not verified",
        "quotes_label": "Quotes",
        "quotes_value": "Checked word for word against the cited source",
        "memory_label": "Memory",
        "memory_value": "None: each question stands alone",
        "privacy_title": "Privacy",
    },
    "de": {
        "single_turn": "Jede Frage wird einzeln beantwortet; frühere Nachrichten werden nicht an das Modell gesendet.",
        "recovery_note": "Nach einem Neuladen wird die Antwort ohne neuen Modellaufruf erneut abgerufen; dafür bleibt nur eine Anfrage-ID in diesem Tab (bis zu 15 Minuten). Chat löschen bricht eine bereits gesendete Anfrage nicht ab.",
        "you": "Sie",
        "assistant": "VORNEQ KI",
        "copy": "Antwort kopieren",
        "copied": "Kopiert",
        "examples_title": "Probieren Sie eine Frage",
        "examples": ("Was ist Photosynthese?", "Wer war Avicenna?", "Wie funktioniert eine Solarzelle?"),
        "examples_note": "Beispiele füllen nur das Eingabefeld; gesendet wird erst mit „Fragen“.",
        "hint": "Strg + Enter zum Senden",
        "panel_title": "Über diesen Chat",
        "sources_label": "Quellen",
        "sources_global": "Öffentliche Lexikonartikel (Wikipedia)",
        "sources_local": "Öffentliche VORNEQ-Quellen",
        "answers_label": "Antworten",
        "answers_value": "Generierte Entwürfe; Aussagen nicht verifiziert",
        "quotes_label": "Zitate",
        "quotes_value": "Wörtlich mit der zitierten Quelle abgeglichen",
        "memory_label": "Gedächtnis",
        "memory_value": "Keines: jede Frage steht für sich",
        "privacy_title": "Datenschutz",
    },
    "fa": {
        "single_turn": "به هر پرسش جداگانه پاسخ داده می‌شود؛ پیام‌های قبلی برای مدل فرستاده نمی‌شوند.",
        "recovery_note": "اگر صفحه دوباره بارگذاری شود، پاسخ بدون فراخوانی دوبارهٔ مدل بازیابی می‌شود؛ برای این کار فقط یک شناسهٔ درخواست در همین زبانه نگه داشته می‌شود (حداکثر ۱۵ دقیقه). پاک‌کردن گفت‌وگو درخواستی را که فرستاده شده لغو نمی‌کند.",
        "you": "شما",
        "assistant": "هوش مصنوعی VORNEQ",
        "copy": "کپی پاسخ",
        "copied": "کپی شد",
        "examples_title": "یک پرسش را امتحان کنید",
        "examples": ("فتوسنتز چیست؟", "ابن‌سینا که بود؟", "سلول خورشیدی چگونه کار می‌کند؟"),
        "examples_note": "نمونه‌ها فقط کادر را پر می‌کنند؛ تا «ارسال» را نزنید چیزی فرستاده نمی‌شود.",
        "hint": "Ctrl + Enter برای ارسال",
        "panel_title": "دربارهٔ این گفت‌وگو",
        "sources_label": "منابع",
        "sources_global": "مقاله‌های عمومی دانشنامه (ویکی‌پدیا)",
        "sources_local": "منابع عمومی VORNEQ",
        "answers_label": "پاسخ‌ها",
        "answers_value": "پیش‌نویس تولیدشده؛ درستی ادعاها تأیید نشده",
        "quotes_label": "نقل‌قول‌ها",
        "quotes_value": "کلمه‌به‌کلمه با منبع ذکرشده مطابقت داده می‌شود",
        "memory_label": "حافظه",
        "memory_value": "ندارد: هر پرسش مستقل است",
        "privacy_title": "حریم خصوصی",
    },
}


def chat_labels(language, environment=None):
    """Select appropriate warnings and V2 UI labels without weakening the Production policy."""
    code = (language or "en")[:2]
    if code not in LABELS:
        code = "en"
    if environment is None:
        environment = getattr(settings, "VORNEQ_ENV", "development")
    labels = {**UI_LABELS[code], **LABELS[code]}
    if environment == "staging":
        labels.update(ENVIRONMENT_LABELS[code]["staging"])
    elif environment == "production":
        labels.update(ENVIRONMENT_LABELS[code]["production"])
        # PR #639 copy is authoritative for Production's safety and recovery language.
        labels.update(PRODUCTION_LABELS[code])
    return labels
