# syntax=docker/dockerfile:1.6

# ----------------------------------------------------------------------------
# Stage 1: build frontend assets (Tailwind CSS + vendored JS).
# ----------------------------------------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Tailwind needs to scan templates and python files for class names.
COPY tailwind.config.js postcss.config.js ./
COPY scripts ./scripts
COPY src ./src

RUN npm run build

# ----------------------------------------------------------------------------
# Stage 2: Django app.
# ----------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        binutils \
        libproj-dev \
        gdal-bin \
        libgdal-dev \
        python3-gdal \
        gettext \
        libjpeg-dev \
        zlib1g-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        tcl8.6-dev \
        tk8.6-dev \
        python3-tk \
        libharfbuzz-dev \
        libfribidi-dev \
        libxcb1-dev

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY src/ .

# Pull built CSS + vendored JS from the frontend stage.
COPY --from=frontend /build/src/static/css/app.css      ./static/css/app.css
COPY --from=frontend /build/src/static/js/htmx.min.js   ./static/js/htmx.min.js
COPY --from=frontend /build/src/static/js/alpine.min.js ./static/js/alpine.min.js

# Compile .po -> .mo so translations bundled in the image are runtime-ready.
# Failures are fatal: missing .mo means missing translations in production.
RUN python manage.py compilemessages

# Bake collected static files into the image. Placeholder env vars only exist
# for this RUN; collectstatic does not touch the DB.
RUN mkdir -p static && \
    SECRET_KEY=build-placeholder \
    DATABASE_URL=postgres://x:x@localhost/x \
    ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
