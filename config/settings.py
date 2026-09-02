"""
Django settings for Saman Kherad.

سامان خرد — بنیاد عریان پرسش
Development configuration
"""

from pathlib import Path


# ============================================================
# BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# SECURITY
# ============================================================

# مهم:
# SECRET_KEY واقعی فعلی پروژه را اینجا نگه دارید.
# این مقدار را در GitHub عمومی منتشر نکنید.

SECRET_KEY = "SECRET_KEY-فعلی-پروژه-را-اینجا-قرار-دهید"

DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]


# ============================================================
# INSTALLED APPS
# ============================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # django-allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # Local applications
    "library",
    "marketplace",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    # Internationalization
    "django.middleware.locale.LocaleMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # django-allauth
    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URL CONFIGURATION
# ============================================================

ROOT_URLCONF = "config.urls"


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django.DjangoTemplates"
        ),

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]


# ============================================================
# WSGI
# ============================================================

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# DATABASE
# ============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

# زبان پیش‌فرض سایت
LANGUAGE_CODE = "fa"

# زبان‌های پشتیبانی‌شده
LANGUAGES = [
    ("fa", "فارسی"),
    ("en", "English"),
    ("de", "Deutsch"),
]

# فایل‌های ترجمه
LOCALE_PATHS = [
    BASE_DIR / "locale",
]

TIME_ZONE = "Asia/Tehran"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "assets",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# ============================================================
# MEDIA FILES
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# DJANGO SITES
# ============================================================

SITE_ID = 1


# ============================================================
# AUTHENTICATION BACKENDS
# ============================================================

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]


# ============================================================
# LOGIN / LOGOUT
# ============================================================

LOGIN_URL = "/accounts/login/"

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/"

ACCOUNT_LOGOUT_REDIRECT_URL = "/"


# ============================================================
# DJANGO ALLAUTH
# ============================================================

# ورود با ایمیل
ACCOUNT_LOGIN_METHODS = {
    "email",
}

# فیلدهای ثبت‌نام
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]

# هر ایمیل فقط متعلق به یک حساب باشد
ACCOUNT_UNIQUE_EMAIL = True

# فعلاً در محیط توسعه تأیید ایمیل اجباری نیست
ACCOUNT_EMAIL_VERIFICATION = "none"

# نشست ورود حفظ شود
ACCOUNT_SESSION_REMEMBER = True

# خروج با GET را فعال نمی‌کنیم.
# خروج بهتر است از طریق فرم POST انجام شود.
ACCOUNT_LOGOUT_ON_GET = False


# ============================================================
# SOCIAL ACCOUNT
# ============================================================

# زیرساخت Social Account فعال است،
# اما Google/GitHub تا زمان تنظیم OAuth
# به INSTALLED_APPS اضافه نمی‌شوند.

SOCIALACCOUNT_AUTO_SIGNUP = True

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True


# ============================================================
# EMAIL — DEVELOPMENT
# ============================================================

# ایمیل‌ها فعلاً در PowerShell نمایش داده می‌شوند.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = "noreply@localhost"


# ============================================================
# CACHE — DEVELOPMENT
# ============================================================

CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
        ),
        "LOCATION": "saman-kherad-development",
    }
}


# ============================================================
# SECURITY — DEVELOPMENT
# ============================================================

# این تنظیمات برای localhost هستند.
# هنگام Deploy تنظیمات Production جداگانه اضافه می‌کنیم.

SESSION_COOKIE_SECURE = False

CSRF_COOKIE_SECURE = False

SECURE_SSL_REDIRECT = False


# ============================================================
# DEFAULT PRIMARY KEY
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"