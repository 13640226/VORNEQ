"""
Django settings for Saman Kherad.

Development / Production aware configuration.
"""

import os
from pathlib import Path


# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# =============================================================================
# HELPERS
# =============================================================================

def env_bool(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name, default=""):
    value = os.environ.get(name, default)

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


# =============================================================================
# APPLICATIONS
# =============================================================================

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

    # Security
    "axes",

    # Local applications
    "library",
    "marketplace",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Static files
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # Sessions
    "django.contrib.sessions.middleware.SessionMiddleware",

    # Languages
    "django.middleware.locale.LocaleMiddleware",

    # Django
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # django-allauth
    "allauth.account.middleware.AccountMiddleware",

    # Messages
    "django.contrib.messages.middleware.MessageMiddleware",

    # Clickjacking protection
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Login protection
    "axes.middleware.AxesMiddleware",
]


# =============================================================================
# URL / WSGI
# =============================================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.debug",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]


# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
        "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {
        "NAME":
        "django.contrib.auth.password_validation."
        "MinimumLengthValidator",
    },
    {
        "NAME":
        "django.contrib.auth.password_validation."
        "CommonPasswordValidator",
    },
    {
        "NAME":
        "django.contrib.auth.password_validation."
        "NumericPasswordValidator",
    },
]


# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "fa"

LANGUAGES = [
    ("fa", "فارسی"),
    ("en", "English"),
    ("de", "Deutsch"),
]

TIME_ZONE = "Asia/Tehran"

USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]


# =============================================================================
# STATIC FILES
# =============================================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "assets",
]


# Django 4.2+ storage configuration

STORAGES = {
    "default": {
        "BACKEND":
        "django.core.files.storage.FileSystemStorage",
    },

    "staticfiles": {
        "BACKEND":
        "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# =============================================================================
# MEDIA
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# DJANGO SITES
# =============================================================================

SITE_ID = 1


# =============================================================================
# AUTHENTICATION BACKENDS
# =============================================================================

AUTHENTICATION_BACKENDS = [
    # IMPORTANT:
    # Axes must be first so locked accounts cannot bypass the lockout.
    "axes.backends.AxesStandaloneBackend",

    # Django authentication
    "django.contrib.auth.backends.ModelBackend",

    # django-allauth
    "allauth.account.auth_backends.AuthenticationBackend",
]


# =============================================================================
# LOGIN / LOGOUT
# =============================================================================

LOGIN_URL = "/accounts/login/"

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/"

ACCOUNT_LOGOUT_REDIRECT_URL = "/"

ACCOUNT_LOGOUT_ON_GET = False


# =============================================================================
# DJANGO-ALLAUTH — MODERN CONFIGURATION
# =============================================================================

# Users can login using either username or email.

ACCOUNT_LOGIN_METHODS = {
    "username",
    "email",
}


# Fields shown during registration.
#
# * means required.

ACCOUNT_SIGNUP_FIELDS = [
    "username*",
    "email*",
    "password1*",
    "password2*",
]


ACCOUNT_UNIQUE_EMAIL = True


# Development:
# email verification is disabled for easier local testing.
#
# Production:
# change this to "mandatory".

# Prevent account enumeration where possible.

ACCOUNT_PREVENT_ENUMERATION = True


# Remember sessions.

ACCOUNT_SESSION_REMEMBER = True


# Do not automatically login merely by visiting a confirmation URL.

ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False


# =============================================================================
# SOCIAL ACCOUNT
# =============================================================================

SOCIALACCOUNT_AUTO_SIGNUP = True

SOCIALACCOUNT_LOGIN_ON_GET = False


DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "Saman Kherad <noreply@localhost>",
)


# =============================================================================
# CACHE
# =============================================================================

REDIS_URL = os.environ.get(
    "REDIS_URL",
)


if REDIS_URL:

    CACHES = {
        "default": {
            "BACKEND":
            "django.core.cache.backends.redis.RedisCache",

            "LOCATION":
            REDIS_URL,

            "TIMEOUT":
            300,
        }
    }

else:

    CACHES = {
        "default": {
            "BACKEND":
            "django.core.cache.backends.locmem.LocMemCache",

            "LOCATION":
            "saman-kherad-local-cache",

            "TIMEOUT":
            300,
        }
    }


# =============================================================================
# DJANGO AXES
# =============================================================================

AXES_ENABLED = True

AXES_FAILURE_LIMIT = 5

AXES_COOLOFF_TIME = 1


# Lock the combination of username + IP.
#
# This is the modern replacement for older
# AXES_LOCK_OUT_BY_* settings.

AXES_LOCKOUT_PARAMETERS = [
    [
        "username",
        "ip_address",
    ],
]


AXES_RESET_ON_SUCCESS = True

AXES_ENABLE_ADMIN = True

# Optional custom template.
#
# Enable this only after creating:
#
# templates/account/lockout.html

# AXES_LOCKOUT_TEMPLATE = "account/lockout.html"


# =============================================================================
# SESSION SECURITY
# =============================================================================

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"


# =============================================================================
# CLICKJACKING
# =============================================================================

X_FRAME_OPTIONS = "DENY"


# =============================================================================
# MIME / CONTENT SECURITY
# =============================================================================

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format":
            "[{levelname}] {asctime} {name}: {message}",

            "style":
            "{",
        },
    },

    "handlers": {
        "console": {
            "class":
            "logging.StreamHandler",

            "formatter":
            "verbose",
        },
    },

    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],

            "level":
            "INFO",

            "propagate":
            False,
        },

        "axes": {
            "handlers": [
                "console",
            ],

            "level":
            "WARNING",

            "propagate":
            False,
        },
    },
}
