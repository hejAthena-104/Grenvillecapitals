# grenvillecapitals backend — Django 4.2 + gunicorn + WhiteNoise
#
# Built and run on the Contabo VPS alongside SwiftEagle (Caddy reverse-proxies
# dashboard.grenvillecapitals.com to the published port). DB is the existing
# Railway Postgres — no local DB on this host.
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# psycopg2-binary ships its own libpq, but we still need a C toolchain for any
# wheels that build from source (Pillow occasionally does). Strip back out
# afterwards to keep the image small.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
  && pip install -r requirements.txt

RUN apt-get purge -y --auto-remove build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY . /app/

# Run collectstatic at build time so WhiteNoise has its manifest. settings.py
# reads SECRET_KEY via python-decouple at import time, so we pass a throwaway
# value for the build step only — the real key is injected at runtime.
ENV DJANGO_SETTINGS_MODULE=config.settings \
    SECRET_KEY=build-time-throwaway-not-used-at-runtime \
    DEBUG=False
RUN python manage.py collectstatic --no-input --clear

# Drop root for the runtime user. Static files are already in place under
# /app/staticfiles owned by root; chown them so WhiteNoise can read after
# the user switch.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app \
  && chown -R app:app /app
USER app

# TCP healthcheck — Django may 404 on /, so just probe the listener.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import socket,os; s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1', int(os.environ.get('PORT','8000')))); s.close()" || exit 1

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
