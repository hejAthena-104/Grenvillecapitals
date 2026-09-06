"""Expose the brand to every template, so no template hardcodes the name."""
from django.conf import settings


def brand(request):
    return {
        'site_name': settings.SITE_NAME,
        'site_url': settings.SITE_URL,
        'support_email': settings.SUPPORT_EMAIL,
        'frontend_url': settings.FRONTEND_URL,
    }
