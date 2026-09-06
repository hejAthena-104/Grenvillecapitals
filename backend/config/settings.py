"""
Django settings for config project.

Generated for Django 4.2.7

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
import os
from decouple import config
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production-123456789')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# --- Brand ------------------------------------------------------------------
# Single source of truth for every user-visible name/URL. Templates read these
# via accounts.context_processors.brand; email_utils reads them from settings.
SITE_NAME = config('SITE_NAME', default='Grenville Capitals')
SITE_URL = config('SITE_URL', default='http://localhost:8000')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='support@grenvillecapitals.com')
EMAIL_FROM = config('EMAIL_FROM', default='onboarding@resend.dev')
EMAIL_FROM_NAME = config('EMAIL_FROM_NAME', default=SITE_NAME)
RESEND_API_KEY = config('RESEND_API_KEY', default='')



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Third party apps
    'django_extensions',

    # Local apps
    'accounts',
    'dashboard',
    'transactions',
    'support',
    'services',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.brand',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# Use PostgreSQL in production (Render/Railway), SQLite in development
DATABASE_URL = config('DATABASE_URL', default=None)

if DATABASE_URL:
    # Production: Use PostgreSQL
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Development: Use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise configuration for serving static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication Backends (allows login with email or username)
AUTHENTICATION_BACKENDS = [
    'accounts.views.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Login/Logout URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# Frontend URL (for CORS and redirects)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:8080')

# CSRF Trusted Origins (required for Django 4.0+ with HTTPS).
# Defensive: always seed the prod hosts so a missing env var doesn't lock
# out logins, and merge in anything supplied via the env on top of that.
_DEFAULT_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
_env_trusted = config('CSRF_TRUSTED_ORIGINS', default='', cast=str)
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    _DEFAULT_TRUSTED_ORIGINS
    + [s.strip() for s in _env_trusted.split(',') if s.strip()]
))

# Trust Caddy's X-Forwarded-Proto so Django.request.is_secure() returns True
# behind the reverse proxy. Without this, CSRF Origin checks see scheme=http
# even though the browser used https — and the 'Origin checking failed' error
# trips even when the request host is in CSRF_TRUSTED_ORIGINS, because Django
# also checks the scheme match.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Cookie security: only flip Secure/HttpOnly defaults when we're actually
# behind HTTPS (production). DEBUG=True for local dev keeps the cookies
# usable over plain http://localhost.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    # CSRF cookie must stay JS-readable so the Django template tag/JS clients
    # can echo it back in the X-CSRFToken header — leave CSRF_COOKIE_HTTPONLY
    # at its default (False).

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
