## 1. Setup and Models

- [ ] 1.1 Create Django app directory `src/apps/blog/` and setup basic files (`__init__.py`, `apps.py`, `models.py`, `views.py`, `urls.py`, `admin.py`).
- [ ] 1.2 Add `"apps.blog"` to `INSTALLED_APPS` in `src/config/settings/base.py`.
- [ ] 1.3 Define `Category`, `Tag`, and `Post` models in `src/apps/blog/models.py` with translation fields, property getters, and GIS fields.
- [ ] 1.4 Register models in `src/apps/blog/admin.py` with custom fieldsets for translated fields.
- [ ] 1.5 Create and execute database migrations.

## 2. Views and URL Routing

- [ ] 2.1 Route `/blog/` paths in `src/config/urls.py` by referencing `apps.blog.urls`.
- [ ] 2.2 Build views for listing posts, filtering by category/tag, and viewing post details in `src/apps/blog/views.py`.
- [ ] 2.3 Implement the `/blog/api/chat/` endpoint in `src/apps/blog/views.py` utilizing the Gemini SDK to query posts and answer user queries.

## 3. UI and Leaflet Map Integration

- [ ] 3.1 Create list view template (`src/apps/blog/templates/blog/list.html`) with category/tag sidebar and responsive card layout.
- [ ] 3.2 Create detail view template (`src/apps/blog/templates/blog/detail.html`) with rich typography (prose-like), reading time, difficulty badge, and dynamic Leaflet map initializer.
- [ ] 3.3 Implement the sidebar AI Chatbot component using HTMX and Alpine.js.

## 4. Platform Integration and Data Seed

- [ ] 4.1 Update `src/templates/cotton/organisms/navbar.html` (and the mobile menu/navbar_dock) to add links to the blog.
- [ ] 4.2 Display the 3 latest blog posts on the landing page by modifying `src/apps/core/views.py` and `src/templates/home.html`.
- [ ] 4.3 Create a management command to seed initial technical blog posts covering Django, WebGIS, PostGIS, pgvector, pgrouting, and AI collaboration.
