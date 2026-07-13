## Why

The `maps.eus` platform is a complex WebGIS and AI-assisted ecosystem for Euskal Herria, combining advanced technologies like PostGIS, pgrouting, pgvector, Django, and Gemini AI. 
To showcase technical depth, share development updates, and provide high-value tutorials to the community, we need a dedicated **Developer Blog**.

Rather than a static, generic blog, this app must be a showcase of the platform's capabilities:
1. **Multilingual (i18n)**: Fully supporting Euskara, Español, and English to align with the platform's native languages.
2. **Interactive WebGIS Integration**: Allowing authors to embed Leaflet map layers (GeoJSON, routing paths, or markers) directly inside posts to visually demonstrate PostGIS, pgrouting, and GIS concepts.
3. **AI-Powered Exploration**: Embedding a sidebar AI Assistant (powered by the platform's Gemini integration) that indexes blog posts and answers user questions semantically.

## What Changes

- **New App `apps.blog`**: A self-contained Django app with its own models, views, URLs, and templates.
- **Bilingual/Trilingual Models**: Fields for Title, Slug, Summary, and Content in Euskara (`_eu`), Español (`_es`), and English (`_en`), with property getters that fallback gracefully based on the active language context.
- **Interactive GIS Model Fields**: Custom fields (`map_geojson`, `map_center_lat`, `map_center_lng`, `map_zoom`) in the `Post` model that, when set, render an interactive Leaflet map widget directly inside the blog post.
- **AI Blog Q&A Endpoint**: A view or Ninja API endpoint that utilizes the Gemini API to search and answer questions based on published blog posts.
- **Home & Navbar Integration**:
  - Link to `/blog/` in the main navbar and mobile navbar dock.
  - A beautiful "Novedades Técnicas" / "Blog" section on the home page highlighting the last 3 technical articles.

## Capabilities

### New Capabilities

- `blog-multilingual`: Read, write, and display blog posts dynamically in Basque (`eu`), Spanish (`es`), or English (`en`) depending on user's active session language.
- `blog-interactive-gis`: Render responsive, interactive geographic maps inside blog posts to explain spatial data, routing, or GIS features.
- `blog-ai-search`: Chatbot assistant on the blog sidebar that uses Gemini to answer questions regarding the topics written in the posts.

### Modified Capabilities

- `core-navigation`: Add navigation paths to the blog on desktop navbar and mobile menus.
- `home-dashboard`: Add a section displaying featured technical posts to enrich the landing experience.

## Impact

- `src/apps/blog/` (entirely new app directory)
- `src/config/settings/base.py` (add `"apps.blog"` to `INSTALLED_APPS`)
- `src/config/urls.py` (include `"apps.blog.urls"`)
- `src/templates/cotton/organisms/navbar.html` (add blog link)
- `src/apps/core/views.py` (add latest blog posts to context)
- `src/templates/home.html` (add a section for latest blog posts)
