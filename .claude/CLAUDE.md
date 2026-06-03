# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SaaS Maps — Django 6 monorepo for Euskal Herria GIS apps. Multiple Django apps share one DB and one project (`config/`); subdomains are wired through `django-hosts` but currently fall through to path-based routing (`/mubil/`, `/bidaiak/`, `/pintxos/`, …). All source lives under `src/`; nothing app-level belongs at the repo root.

**Active focus**: `apps.mubil` — MUBIL Mobility Awards 2026 submission, deadline **2026-06-19**. See [`src/apps/mubil/README.md`](../src/apps/mubil/README.md) for the four submodules (`advisor`, `ask`, `route`, `plan`).

## Common commands

Everything runs in Docker (compose project `ai-maps`). Container names are `maps_web`, `maps_worker`, `maps_beat`, `maps_db`, `maps_redis`.

```bash
# Day-to-day
docker compose up -d                                    # web on :9000, db on :5436, redis on :6379
docker compose restart web                              # REQUIRED after Python edits (see "Gotchas")
docker compose logs -f web

# Django manage.py (always via container, settings = config.settings.local in dev)
docker compose exec web python manage.py <cmd>
docker compose exec web python manage.py makemigrations <app>
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell_plus    # django-extensions

# Tests (pytest + pytest-django; no pytest.ini — uses defaults; tests live in src/apps/<app>/tests/)
docker compose exec web pytest
docker compose exec web pytest apps/mubil/tests/test_models.py
docker compose exec web pytest apps/mubil/tests/test_advisor_tco.py::TestTCO::test_x

# Frontend (Tailwind + vendored htmx/Alpine, built in the frontend stage of Dockerfile)
npm run build         # one-shot: copy vendor JS + build minified app.css
npm run watch         # tailwind --watch (run on host, mounted into container via override)

# Celery (worker + beat run as separate containers; Redis is the broker)
docker compose exec worker celery -A config call <task.name>
docker compose logs -f worker

# Deploy (on the VPS; uses .env.prod + docker-compose.prod.yml)
./scripts/deploy.sh         # build → migrate → init_apps → init_oauth → up -d
./scripts/bootstrap.sh      # one-time data seed (seed_inguru, kultur/sbk/inguru/gailur ingests)
```

## Architecture

### Layout
```
src/
├── config/              # Django project (settings/, urls.py, hosts.py, celery.py)
│   └── settings/        # base.py + local.py (DEBUG) + prod.py
├── apps/
│   ├── core/            # Shared kernel: custom User, app_config context proc, base templates
│   ├── mubil/           # MUBIL Awards app (active). Submodules: advisor/ ask/ route/ plan/
│   ├── pintxos/ bidaiak/ sbk/ kultur/ inguru/ gailur/ zbe/ adventure/ solar/ oceania/
├── templates/
│   ├── cotton/          # Atomic-Design components (atoms/ molecules/ organisms/) for django-cotton
│   └── <app>/           # Per-app templates
├── static/              # source.css → static/css/app.css (built); vendored htmx/alpine
└── locale/              # Translations (eu/es/en — LANGUAGE_CODE='eu')
```

### Key conventions

- **Per-app structure**: `models.py`, `schemas.py` (Ninja/Pydantic), `services.py` (business logic), `api.py` (Ninja router), `views.py` (HTMX-returning Django views), `tasks.py` (Celery). `mubil` further splits submodules with their own `api.py`/`services.py`/`schemas.py`.
- **API**: Django Ninja. Core API mounts at `/api/` (`apps.core.api:api`). Mubil mounts its own NinjaAPI at `/mubil/api/` (deliberately un-nested to keep its namespace separate — see comment in `apps/mubil/urls.py`).
- **Auth**: `AUTH_USER_MODEL = 'core.User'`, `django-allauth` (email login, Google/Instagram/Facebook social). `init_oauth` management command seeds `Site` + `SocialApp` during deploy.
- **Subdomains**: `django-hosts` middleware is enabled (`config/hosts.py`) but currently routes everything through `config.urls`. Don't add subdomain-specific URL configs until that comment in `hosts.py` is resolved.
- **GIS**: `django.contrib.gis` everywhere. Storage in EPSG:4326, web display in 3857. Use `ST_DWithin` (not `ST_Distance` in WHERE) and **GIST** indexes on geometry fields.
- **Vector search**: `pgvector` with **HNSW** indexes only. `ivfflat` silently missed top-1 in mubil RAG — see migration `mubil/migrations/0008*`. Embedding dim is 768 (Gemini `gemini-embedding-001` with `output_dimensionality=768`).
- **Frontend**: HTMX + Alpine + django-cotton (Atomic Design). No SPA framework. Mobile-first Tailwind only — base classes target 375 px, `sm/md/lg/xl` scale up.
- **TimescaleDB**: image is `timescale/timescaledb-ha:pg15`; PostGIS + pgvector are installed by `scripts/init_db.sql`. **Data dir is `/home/postgres/pgdata/data`** (not the stock `/var/lib/postgresql/data`) — the volume mount in `docker-compose.yml` depends on this.
- **i18n**: `LANGUAGE_CODE='eu'` formats `88.0` as `88,0` in templates. When passing floats into URLs (`{% url ... param=value %}`), apply `|unlocalize` first or `float()` parsing downstream breaks.

### Mubil-specific notes (active app)

- **Gemini fallback ladder**: `GEMINI_GENERATION_FALLBACK_MODELS` in `config/settings/base.py` is ordered by expected wall-clock to a usable answer, not RPD. Don't reorder without re-testing on demo prompts — `gemini-3.1-flash-lite` leads, Gemma variants are last-resort overflow due to safety filters on Spanish gov-policy prompts.
- **User vehicle identification**: uses **photo of permiso de circulación + Gemini Vision + cascade fallback** — NOT DGT NAP. See `apps/mubil/services.py`.
- **External APIs**: ESIOS (PVPC prices, `x-api-key` header), OpenChargeMap (`X-API-Key`), MINCOTUR fuel stations (**requires a custom HTTPAdapter for TLS** to ingest from inside the container). Ingest commands live under `apps/mubil/management/commands/ingest_*.py`.
- **Don't probe Gemini live to diagnose quota** — check the AI Studio dashboard. The fallback ladder distinguishes 503 (transient, advance) vs 429 (depleted, advance).

## Gotchas (must read)

- **Docker autoreload is unreliable**: dev `web` runs with `--noreload`. After any Python edit, `docker compose restart web`. Template/CSS edits don't need a restart.
- **Tailwind**: when you add new variants or arbitrary values (`hover:bg-[#xyz]`, `lg:grid-cols-5`, etc.), the JIT misses them until you `npm run build:css`. Layout will look broken with no error.
- **Django template comments**: `{# #}` is **single-line only**. Multi-line `{# ... \n ... #}` renders literally. Use `{% comment %}{% endcomment %}` or delete.
- **Never overwrite the DB image**: keep `timescale/timescaledb-ha:pg15` (drives PostGIS + pgvector + Timescale on one container). Memory entry: `database_preferences.md`.
- **Settings module**: dev = `config.settings.local`, prod = `config.settings.prod` (set in Dockerfile). Both inherit `base.py`. `.env` is read by `environ` from the repo root in local, from `/app/.env` in container.

## Where to look next

| File | Why |
|---|---|
| [`TECHNICAL_RUNBOOK.md`](TECHNICAL_RUNBOOK.md) | Hybrid spatial+semantic search, Atomic Design patterns, perf targets |
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | Current status of each subdomain (most are placeholders; mubil is active) |
| [`DECISIONS.md`](DECISIONS.md) | Why PostGIS+pgvector+Timescale, why HTMX, why django-hosts |
| [`src/apps/mubil/README.md`](../src/apps/mubil/README.md) | Mubil submodule map, models, data sources |
| `memory/MEMORY.md` (user-level) | Cross-session preferences and incident learnings |

## Working with the user

Solopreneur project — bias to small, reversible changes. The user wants pushback on weak proposals and prefers measurement over guessing on performance questions. When in doubt about scope (one bundled PR vs many small ones, etc.), ask before committing to either direction.
