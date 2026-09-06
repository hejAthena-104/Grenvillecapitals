"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from decouple import config
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

def _admin_path():
    """Resolve the admin mount point.

    decouple returns '' for a var that is set but empty, so a bare `ADMIN_URL=`
    in an env file would otherwise mount the whole admin at the site root — far
    worse than the /admin/ this is meant to avoid. Empty, '/' and whitespace all
    fall back to the local default, and the value is normalised to `something/`.
    """
    raw = (config('ADMIN_URL', default='') or '').strip().strip('/')
    if not raw:
        raw = 'admin-local-only'
    return raw + '/'


ADMIN_PATH = _admin_path()

urlpatterns = [
    # The admin holds every customer's KYC documents and balances, and this host
    # is public, so it is not served at /admin/. The real path comes from
    # ADMIN_URL in .env.prod and is deliberately NOT in this repo — the default
    # below is only for local development.
    path(ADMIN_PATH, admin.site.urls),

    # Authentication URLs
    path('auth/', include('accounts.urls')),

    # Dashboard URLs
    path('dashboard/', include('dashboard.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
