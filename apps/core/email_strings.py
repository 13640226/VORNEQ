"""Localized copy (fa / de / en) for VORNEQ transactional e-mails, design V3.

Every key must define all three languages with identical {placeholders}.
Templates reference keys via the ``vq_mail`` tag (apps/core/templatetags/vq_email.py).
"""

SUPPORTED_LANGUAGES = ("fa", "de", "en")
FALLBACK_LANGUAGE = "en"

_ZW = "\u200c"  # ZWNJ for correct Persian orthography


def _e(fa, de, en):
    return {"fa": fa, "de": de, "en": en}


EMAIL_STRINGS = {
    "footer.security": _e(
        f"VORNEQ هرگز رمز عبور شما را از طریق ایمیل نم{_ZW}ی{_ZW}پرسد.",
        "VORNEQ fragt Sie niemals per E-Mail nach Ihrem Passwort.",
        "VORNEQ will never ask for your password by email.",
    ),
    "footer.automatic": _e(
        f"این پیام به{_ZW}صورت خودکار ارسال شده است؛ لطفاً به آن پاسخ ندهید.",
        "Diese Nachricht wurde automatisch versendet. Bitte antworten Sie nicht darauf.",
        "This message was sent automatically. Please do not reply.",
    ),
    "footer.fallback": _e(
        f"اگر دکمه کار نم{_ZW}ی{_ZW}کند، این نشانی را در مرورگر خود باز کنید:",
        "Falls die Schaltfläche nicht funktioniert, öffnen Sie diese Adresse in Ihrem Browser:",
        "If the button doesn't work, open this address in your browser:",
    ),
    "confirm.title": _e(
        "تأیید نشانی ایمیل",
        "E-Mail-Adresse bestätigen",
        "Confirm your email address",
    ),
    "confirm.intro": _e(
        "لطفاً نشانی ایمیل خود را برای حساب VORNEQ تأیید کنید.",
        "Bitte bestätigen Sie die E-Mail-Adresse für Ihr VORNEQ-Konto.",
        "Please confirm the email address for your VORNEQ account.",
    ),
    "confirm.button": _e(
        "تأیید نشانی ایمیل",
        "E-Mail-Adresse bestätigen",
        "Confirm email address",
    ),
    "confirm.ignore": _e(
        f"اگر شما این درخواست را نداده{_ZW}اید، م{_ZW}ی{_ZW}توانید این ایمیل را نادیده بگیرید.",
        "Wenn Sie dies nicht angefordert haben, können Sie diese E-Mail ignorieren.",
        "If you didn't request this, you can safely ignore this email.",
    ),
    "signup.title": _e(
        "به VORNEQ خوش آمدید",
        "Willkommen bei VORNEQ",
        "Welcome to VORNEQ",
    ),
    "signup.intro": _e(
        f"برای فعال{_ZW}سازی حساب خود، نشانی ایمیلتان را تأیید کنید.",
        "Bestätigen Sie Ihre E-Mail-Adresse, um Ihr Konto zu aktivieren.",
        "Confirm your email address to activate your account.",
    ),
    "reset.title": _e(
        "بازنشانی رمز عبور",
        "Passwort zurücksetzen",
        "Reset your password",
    ),
    "reset.intro": _e(
        "درخواستی برای بازنشانی رمز عبور حساب VORNEQ شما ثبت شده است. برای انتخاب رمز عبور جدید، دکمه زیر را بزنید.",
        "Für Ihr VORNEQ-Konto wurde das Zurücksetzen des Passworts angefordert. Wählen Sie über die Schaltfläche ein neues Passwort.",
        "A password reset was requested for your VORNEQ account. Use the button below to choose a new password.",
    ),
    "reset.button": _e(
        "انتخاب رمز عبور جدید",
        "Neues Passwort wählen",
        "Choose a new password",
    ),
    "reset.ignore": _e(
        f"اگر شما این درخواست را نداده{_ZW}اید، رمز عبور شما تغییر نم{_ZW}ی{_ZW}کند و نیازی به هیچ اقدامی نیست.",
        "Wenn Sie dies nicht angefordert haben, bleibt Ihr Passwort unverändert und Sie müssen nichts tun.",
        "If you didn't request this, your password stays unchanged and no action is needed.",
    ),
    "exists.title": _e(
        "برای این ایمیل از قبل حساب وجود دارد",
        "Für diese E-Mail-Adresse besteht bereits ein Konto",
        "An account with this email already exists",
    ),
    "exists.intro": _e(
        f"برای ثبت{_ZW}نام با نشانی {{email}} درخواستی ثبت شد، اما حسابی با این نشانی از قبل وجود دارد. اگر رمز عبور خود را فراموش کرده{_ZW}اید، م{_ZW}ی{_ZW}توانید آن را بازنشانی کنید.",
        "Für {email} wurde eine Registrierung versucht, aber es existiert bereits ein Konto mit dieser Adresse. Falls Sie Ihr Passwort vergessen haben, können Sie es zurücksetzen.",
        "Someone tried to sign up with {email}, but an account with this address already exists. If you forgot your password, you can reset it.",
    ),
    "exists.button": _e(
        "بازنشانی رمز عبور",
        "Passwort zurücksetzen",
        "Reset your password",
    ),
    "exists.ignore": _e(
        f"اگر خودتان این درخواست را نداده{_ZW}اید، م{_ZW}ی{_ZW}توانید این ایمیل را نادیده بگیرید و نیازی به اقدامی نیست.",
        "Wenn Sie dies nicht waren, können Sie diese E-Mail ignorieren. Es ist keine Aktion nötig.",
        "If this wasn't you, you can ignore this email. No action is needed.",
    ),
    "unknown.title": _e(
        "حسابی با این ایمیل پیدا نشد",
        "Kein Konto zu dieser E-Mail-Adresse gefunden",
        "No account found for this email address",
    ),
    "unknown.intro": _e(
        f"درخواستی برای دسترسی به حسابی با نشانی {{email}} ثبت شد، اما در VORNEQ حسابی با این نشانی وجود ندارد. اگر خودتان این کار را کرده{_ZW}اید، م{_ZW}ی{_ZW}توانید ثبت{_ZW}نام کنید.",
        "Für {email} wurde der Zugriff auf ein Konto angefragt, bei VORNEQ existiert jedoch kein Konto mit dieser Adresse. Wenn Sie das waren, können Sie sich registrieren.",
        "Access to an account with {email} was requested, but VORNEQ has no account with this address. If that was you, you can sign up.",
    ),
    "unknown.button": _e(
        f"ثبت{_ZW}نام در VORNEQ",
        "Bei VORNEQ registrieren",
        "Sign up for VORNEQ",
    ),
    "unknown.ignore": _e(
        f"اگر خودتان این درخواست را نداده{_ZW}اید، م{_ZW}ی{_ZW}توانید این ایمیل را نادیده بگیرید.",
        "Wenn Sie dies nicht angefordert haben, können Sie diese E-Mail ignorieren.",
        "If you didn't request this, you can safely ignore this email.",
    ),
}