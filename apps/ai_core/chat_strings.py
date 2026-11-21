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
        "unsupported": "This question cannot be processed. No model request was sent.",
        "rejectedEvidence": "The generated answer failed source checks and was not shown. The model request may have been billed; check usage before trying again.",
        "rejectedOutput": "The generated answer did not pass the response-format or safety checks. It was not shown; check usage before retrying.",
        "citationIdentity": "The answer cited an unknown or invalid source identifier. The answer was blocked; check usage before retrying.",
        "citationDigest": "The cited source fingerprint did not match the retrieved evidence. The answer was blocked; check usage before retrying.",
        "citationQuote": "The answer's quote could not be matched verbatim to its cited source. The answer was blocked; check usage before retrying.",
        "unsupportedNumber": "The answer contained a number absent from the cited evidence. The answer was blocked; check usage before retrying.",
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
        "unsupported": "Diese Frage kann nicht verarbeitet werden. Es wurde keine Modellanfrage gesendet.",
        "rejectedEvidence": "Die generierte Antwort hat die Quellenprüfung nicht bestanden und wird nicht angezeigt. Die Modellanfrage kann Kosten verursacht haben; vor einer Wiederholung den Verbrauch prüfen.",
        "rejectedOutput": "Die generierte Antwort hat die Format- oder Sicherheitsprüfung nicht bestanden. Sie wird nicht angezeigt; vor einer Wiederholung den Verbrauch prüfen.",
        "citationIdentity": "Die Antwort enthält eine unbekannte oder ungültige Quellenkennung. Sie wurde blockiert; vor einer Wiederholung den Verbrauch prüfen.",
        "citationDigest": "Der Prüffingerabdruck der Quelle stimmt nicht mit den abgerufenen Belegen überein. Die Antwort wurde blockiert; vor einer Wiederholung den Verbrauch prüfen.",
        "citationQuote": "Das Zitat konnte nicht wortgetreu mit der angegebenen Quelle abgeglichen werden. Die Antwort wurde blockiert; vor einer Wiederholung den Verbrauch prüfen.",
        "unsupportedNumber": "Die Antwort enthält eine Zahl, die durch die zitierten Quellen nicht belegt ist. Sie wurde blockiert; vor einer Wiederholung den Verbrauch prüfen.",
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
        "unsupported": "این پرسش قابل پردازش نیست. درخواستی به مدل ارسال نشد.",
        "rejectedEvidence": "پاسخ تولیدشده از بررسی شواهد عبور نکرد و نمایش داده نشد. ممکن است درخواست مدل هزینه داشته باشد؛ پیش از تکرار، مصرف را بررسی کنید.",
        "rejectedOutput": "ساختار یا وضعیت پاسخ تولیدشده معتبر نبود؛ پاسخ نمایش داده نشد. پیش از تکرار، مصرف درخواست را بررسی کنید.",
        "citationIdentity": "شناسهٔ منبع در پاسخ نامعتبر یا ناشناخته بود؛ پاسخ مسدود شد. پیش از تکرار، مصرف درخواست را بررسی کنید.",
        "citationDigest": "اثر انگشت استناد با منبع بازیابی‌شده مطابقت نداشت؛ پاسخ مسدود شد. پیش از تکرار، مصرف درخواست را بررسی کنید.",
        "citationQuote": "نقل‌قول پاسخ عیناً با متن منبع مطابقت نداشت؛ پاسخ مسدود شد. پیش از تکرار، مصرف درخواست را بررسی کنید.",
        "unsupportedNumber": "عدد ذکرشده در پاسخ، پشتوانه‌ای در شواهد استنادی نداشت؛ پاسخ مسدود شد. پیش از تکرار، مصرف درخواست را بررسی کنید.",
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



# Persistent conversations V1 (shown only when VORNEQ_AI_CONVERSATIONS_ENABLED).
CONVERSATION_LABELS = {
    "en": {
        "conv_not_saved": "This answer was shown but could NOT be saved to your history. It may have been billed; do not resend automatically.",
        "conv_title": "Conversations", "conv_new": "New conversation", "conv_search": "Search conversations",
        "conv_empty": "No conversations yet.", "conv_untitled": "New conversation",
        "conv_rename": "Rename", "conv_save": "Save", "conv_archive": "Archive", "conv_unarchive": "Unarchive",
        "conv_delete": "Delete", "conv_delete_confirm": "Move this conversation to the trash? It is deleted for good after 30 days.",
        "conv_export": "Export (JSON)", "conv_trash": "Trash", "conv_back": "Back to conversations",
        "conv_restore": "Restore", "conv_delete_forever": "Delete forever",
        "conv_delete_forever_confirm": "Delete this conversation permanently? This cannot be undone.",
        "conv_load_error": "The conversation could not be loaded.",
        "conv_stored_notice": "Conversations are stored on the VORNEQ server so you can continue them later. You can export or delete them at any time; deleted conversations are removed for good after 30 days (backups may keep them until they expire).",
        "conv_memory_value": "The last 6 exchanges of this conversation (context only, never a source)",
        "conv_turns": "Follow-up questions use the recent messages of this conversation as context. Facts and numbers are still taken only from the cited sources.",
        "conv_full": "This conversation is full. Please start a new conversation.",
    },
    "de": {
        "conv_not_saved": "Diese Antwort wurde angezeigt, konnte aber NICHT im Verlauf gespeichert werden. Sie wurde möglicherweise berechnet; nicht automatisch erneut senden.",
        "conv_title": "Gespräche", "conv_new": "Neues Gespräch", "conv_search": "Gespräche durchsuchen",
        "conv_empty": "Noch keine Gespräche.", "conv_untitled": "Neues Gespräch",
        "conv_rename": "Umbenennen", "conv_save": "Speichern", "conv_archive": "Archivieren", "conv_unarchive": "Aus dem Archiv holen",
        "conv_delete": "Löschen", "conv_delete_confirm": "Dieses Gespräch in den Papierkorb verschieben? Nach 30 Tagen wird es endgültig gelöscht.",
        "conv_export": "Exportieren (JSON)", "conv_trash": "Papierkorb", "conv_back": "Zurück zu den Gesprächen",
        "conv_restore": "Wiederherstellen", "conv_delete_forever": "Endgültig löschen",
        "conv_delete_forever_confirm": "Dieses Gespräch endgültig löschen? Das kann nicht rückgängig gemacht werden.",
        "conv_load_error": "Das Gespräch konnte nicht geladen werden.",
        "conv_stored_notice": "Gespräche werden auf dem VORNEQ-Server gespeichert, damit Sie sie später fortsetzen können. Sie können sie jederzeit exportieren oder löschen; gelöschte Gespräche werden nach 30 Tagen endgültig entfernt (Backups können sie bis zu deren Ablauf enthalten).",
        "conv_memory_value": "Die letzten 6 Wortwechsel dieses Gesprächs (nur Kontext, nie Quelle)",
        "conv_turns": "Folgefragen nutzen die letzten Nachrichten dieses Gesprächs als Kontext. Fakten und Zahlen stammen weiterhin nur aus den zitierten Quellen.",
        "conv_full": "Dieses Gespräch ist voll. Bitte beginnen Sie ein neues Gespräch.",
    },
    "fa": {
        "conv_not_saved": "این پاسخ نمایش داده شد اما در تاریخچه ذخیره نشد. ممکن است هزینه‌اش ثبت شده باشد؛ آن را خودکار دوباره نفرستید.",
        "conv_title": "گفت‌وگوها", "conv_new": "گفت‌وگوی تازه", "conv_search": "جست‌وجو در گفت‌وگوها",
        "conv_empty": "هنوز گفت‌وگویی ندارید.", "conv_untitled": "گفت‌وگوی تازه",
        "conv_rename": "تغییر نام", "conv_save": "ذخیره", "conv_archive": "بایگانی", "conv_unarchive": "خروج از بایگانی",
        "conv_delete": "حذف", "conv_delete_confirm": "این گفت‌وگو به سطل زباله برود؟ پس از ۳۰ روز برای همیشه حذف می‌شود.",
        "conv_export": "خروجی (JSON)", "conv_trash": "سطل زباله", "conv_back": "بازگشت به گفت‌وگوها",
        "conv_restore": "بازگرداندن", "conv_delete_forever": "حذف همیشگی",
        "conv_delete_forever_confirm": "این گفت‌وگو برای همیشه حذف شود؟ این کار برگشت‌پذیر نیست.",
        "conv_load_error": "گفت‌وگو بارگذاری نشد.",
        "conv_stored_notice": "گفت‌وگوها روی سرور VORNEQ ذخیره می‌شوند تا بعداً بتوانید ادامه‌شان دهید. هر زمان می‌توانید از آن‌ها خروجی بگیرید یا حذفشان کنید؛ گفت‌وگوی حذف‌شده پس از ۳۰ روز برای همیشه پاک می‌شود (نسخه‌های پشتیبان ممکن است تا پایان مدت نگهداری‌شان آن را داشته باشند).",
        "conv_memory_value": "۶ نوبت آخر همین گفت‌وگو (فقط برای فهم زمینه، هرگز منبع نیست)",
        "conv_turns": "پرسش‌های بعدی از پیام‌های اخیر همین گفت‌وگو برای فهم زمینه استفاده می‌کنند. واقعیت‌ها و عددها همچنان فقط از منابع ذکرشده گرفته می‌شوند.",
        "conv_full": "این گفت‌وگو پر شده است. لطفاً گفت‌وگوی تازه‌ای شروع کنید.",
    },
}

def chat_labels(language, environment=None):
    """Select appropriate warnings and V2 UI labels without weakening the Production policy."""
    code = (language or "en")[:2]
    if code not in LABELS:
        code = "en"
    if environment is None:
        environment = getattr(settings, "VORNEQ_ENV", "development")
    labels = {**UI_LABELS[code], **LABELS[code], **CONVERSATION_LABELS[code]}
    if environment == "staging":
        labels.update(ENVIRONMENT_LABELS[code]["staging"])
    elif environment == "production":
        labels.update(ENVIRONMENT_LABELS[code]["production"])
        # PR #639 copy is authoritative for Production's safety and recovery language.
        labels.update(PRODUCTION_LABELS[code])
    messages = {
        "en": (
            "The model reached its output budget. No incomplete response was displayed. Check usage before submitting a new request.",
            "The configured context budget is too small for this request. No provider call was made.",
        ),
        "de": (
            "Das Ausgabelimit wurde erreicht. Keine unvollst\u00e4ndige Antwort angezeigt. Vor einer neuen Anfrage den Verbrauch pr\u00fcfen.",
            "Das konfigurierte Kontextbudget reicht nicht aus. Es wurde kein Provider aufgerufen.",
        ),
        "fa": (
            "\u0645\u062f\u0644 \u0628\u0647 \u0633\u0642\u0641 \u067e\u0627\u0633\u062e \u0631\u0633\u06cc\u062f. \u067e\u0627\u0633\u062e \u0646\u0627\u0642\u0635 \u0646\u0645\u0627\u06cc\u0634 \u062f\u0627\u062f\u0647 \u0646\u0634\u062f. \u067e\u06cc\u0634 \u0627\u0632 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062c\u062f\u06cc\u062f \u0647\u0632\u06cc\u0646\u0647 \u0631\u0627 \u0628\u0631\u0631\u0633\u06cc \u06a9\u0646\u06cc\u062f.",
            "\u0628\u0648\u062f\u062c\u0647 \u0645\u062a\u0646 \u0628\u0631\u0627\u06cc \u0627\u06cc\u0646 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u06a9\u0627\u0641\u06cc \u0646\u06cc\u0633\u062a. \u0647\u06cc\u0686 \u062f\u0631\u062e\u0648\u0627\u0633\u062a\u06cc \u0628\u0647 \u0627\u0631\u0627\u0626\u0647\u200c\u062f\u0647\u0646\u062f\u0647 \u0627\u0631\u0633\u0627\u0644 \u0646\u0634\u062f.",
        ),
    }
    labels["outputLimited"], labels["contextLimited"] = messages[code]
    return labels
