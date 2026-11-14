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
        "single_turn": "Each question is independent. Chat is not saved or remembered.",
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
        "single_turn": "Jede Frage ist unabhängig. Der Chat wird nicht gespeichert oder gemerkt.",
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
        "single_turn": "هر سؤال مستقل است؛ گفت‌وگو ذخیره نمی‌شود و در حافظه نمی‌ماند.",
        "back": "بازگشت به جست‌وجو",
    },
}


def chat_labels(language):
    return LABELS.get((language or "en")[:2], LABELS["en"])
