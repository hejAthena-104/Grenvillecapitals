"""Expose the brand to every template, so no template hardcodes the name."""
from django.conf import settings


def brand(request):
    # Feature flags ride along with the brand context so every template — nav,
    # bottom bar, dashboard tiles — hides a disabled feature consistently.
    try:
        from transactions.models import FeatureFlags
        flags = FeatureFlags.get()
    except Exception:
        flags = None

    return {
        'flags': flags,
        'site_name': settings.SITE_NAME,
        'site_url': settings.SITE_URL,
        'support_email': settings.SUPPORT_EMAIL,
        'frontend_url': settings.FRONTEND_URL,
    }
