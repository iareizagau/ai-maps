# Design: Daily Blog Post Creator (Gemini & NewsAPI)

## Context

We are implementing an automated content generation pipeline for the `blog` app. The system will run as a daily scheduled Celery task, querying technology trends from NewsAPI, comparing them against the database of existing posts to avoid duplication, and generating high-quality, trilingual technical articles featuring Leaflet interactive maps when relevant.

## Goals and Non-Goals

### Goals

* Fetch daily articles/trends via NewsAPI and Spanish/Basque RSS feeds.
* Programmatically analyze existing posts (deduplication) to ensure content variety and fresh perspectives.
* Generate complete trilingual content (ES, EU, EN) aligned with the `Post` schema.
* Dynamically autogenerate valid spatial data (GeoJSON and coordinates centered in Euskal Herria) for interactive map rendering.
* Queue tasks safely using Celery + Celery Beat, storing drafts by default.

### Non-Goals

* Autogenerate the featured image (fallback to default category cover, or let the human editor upload one).
* Auto-publish without a safety override (by default, posts remain as drafts with `is_published=False`).

## Technical Architecture & Decisions

```text
+------------------+     +-----------------------+
|  NewsAPI / RSS   | --> |  Existing Post titles |
+------------------+     +-----------------------+
         |                           |
         +-------------+-------------+
                       ▼
         +---------------------------+
         |  apps.blog.services       |
         |  (Deduplication & Prompt) |
         +---------------------------+
                       │ (Send news + history + maps.eus dossier)
                       ▼
             +───────────────────+
             |    Gemini API     |
             +───────────────────+
                       │ (Returns Trilingual Structured JSON)
                       ▼
         +---------------------------+
         |   Post (is_published=F)   |
         +---------------------------+
```

### 1. Database Schema Alignment & Default Author

* The generated post requires a valid `author`. The service will look for the first active superuser or staff user.
* The post is created with `is_published=False` (draft) and `published_at=None`. The `published_at` date will be set automatically when the editor publishes it from the Django Admin.
* To prevent database corruption, all fields are validated before creation.

### 2. Services Layer (`src/apps/blog/services.py`)

#### A. Fetching News

We will construct a search query targeting key technical themes:
`NEWSAPI_QUERY = '("software development" OR "inteligencia artificial" OR "WebGIS" OR "PostGIS" OR "pgvector")'`
The `fetch_latest_tech_news()` function will query NewsAPI `everything` (or fallback to developer-focused feeds if API limits are reached) and return raw candidates.

#### B. Content Deduplication

We fetch the last 10 blog posts:

```python
existing_posts = Post.objects.all().order_by("-created_at")[:10]
history = "\n".join([f"- {p.title_es} (Resumen: {p.summary_es})" for p in existing_posts])
```

We inject this history into the Gemini prompt. Gemini is instructed:
*"If the selected news topic overlaps with any of these titles, do not repeat the basic concepts. Instead, write a sequels article (Part 2), change focus to advanced optimizations, or detail specific success stories."*

#### C. Gemini Prompt & JSON Output

We will call Gemini using the `google.genai` SDK and enforce a structured JSON response matching the database fields:

```json
{
  "title_es": "string",
  "title_eu": "string",
  "title_en": "string",
  "summary_es": "string",
  "summary_eu": "string",
  "summary_en": "string",
  "content_es": "html_string",
  "content_eu": "html_string",
  "content_en": "html_string",
  "tags": ["list", "of", "slugs"],
  "difficulty": "beginner|intermediate|advanced",
  "read_time": 5,
  "map_geojson": "string_or_null",
  "map_center_lat": 42.8485,
  "map_center_lng": -2.6705,
  "map_zoom": 13
}
```

The prompt instructions guarantee:

* Clean HTML content (prose-styled paragraphs, headers `<h3>`, and `<code>` blocks) without markdown outer blocks.
* Map coordinates placed in Euskal Herria (Bilbao, Vitoria-Gasteiz, Donostia, Pamplona, etc.) with valid GeoJSON geometries (Point, LineString, or Polygon) illustrating a topic-related concept (e.g. showing a route or spatial boundary).

### 3. Celery Task & Scheduling (`src/apps/blog/tasks.py`)

A Celery task `apps.blog.tasks.generate_daily_post` will wrap the service calls.

* **Celery configuration via migration (django-celery-beat):**
We register a crontab schedule at 03:00 Europe/Madrid and associate it with a `PeriodicTask` model record, aligning with the project's DatabaseScheduler standard.

* **Retry logic:** The task is decorated with auto-retry on exceptions (e.g. NewsAPI/Gemini temporary server errors) with exponential backoff.

### 4. Admin Enhancements

In `src/apps/blog/admin.py`, we will add a filter to easily find automated drafts:

* Filter: `list_filter = ("is_published", "category", "difficulty", "tags", "created_at")`
* Action: A custom admin action to bulk-publish selected drafts, automatically setting their `published_at` to the current time.

## Risks & Trade-offs

* **API Key Quota Limits:** NewsAPI free tier limits could prevent daily executions in active dev environments.
  * *Mitigation*: Gracefully catch `429` / request limits and fall back to RSS feeds or mock trend seeds so the pipeline never breaks.
* **GeoJSON Integrity:** If Gemini outputs invalid GeoJSON, Django saving or Leaflet loading might fail.
  * *Mitigation*: Parse the GeoJSON string using Python's `json.loads` inside the service before persisting. If parsing fails, nullify the map fields and log a warning.
