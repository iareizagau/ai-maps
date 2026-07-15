import json
from unittest import mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from apps.blog.models import Category, Tag, Post
from apps.blog import services
from apps.blog.tasks import generate_daily_post

User = get_user_model()


def _gemini_payload(**overrides) -> str:
    data = {
        "title_es": "Nueva IA Geoespacial",
        "title_eu": "IA Geoespazial berria",
        "title_en": "New Geospatial AI",
        "slug_es": "nueva-ia-geoespacial",
        "slug_eu": "ia-geoespazial-berria",
        "slug_en": "new-geospatial-ai",
        "summary_es": "Un análisis sobre la nueva IA geoespacial.",
        "summary_eu": "IA geoespazial berriari buruzko azterketa.",
        "summary_en": "An analysis of the new geospatial AI.",
        "content_es": "<p>Contenido en español</p>",
        "content_eu": "<p>Euskarazko edukia</p>",
        "content_en": "<p>English content</p>",
        "category_slug": "webgis-postgis",
        "tag_slugs": ["postgis", "gemini", "ia"],
        "difficulty": "intermediate",
        "read_time": 6,
        "map_geojson": '{"type": "FeatureCollection", "features": []}',
        "map_center_lat": 43.2630,
        "map_center_lng": -2.9350,
        "map_zoom": 12,
    }
    data.update(overrides)
    return json.dumps(data)


class DailyPostServicesTests(TestCase):

    def setUp(self):
        # Create default categories and users
        self.category = Category.objects.create(
            name_es="WebGIS y PostGIS",
            name_eu="WebGIS eta PostGIS",
            name_en="WebGIS and PostGIS",
            slug="webgis-postgis",
        )
        self.user = User.objects.create_superuser(
            email="admin@maps.eus",
            username="admin",
            password="password",
        )

    @override_settings(NEWS_API_KEY="fake-key")
    @mock.patch("apps.blog.services.requests.get")
    def test_fetch_news_success(self, mock_get):
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {
                    "title": "PostGIS optimizations",
                    "description": "How to optimize spatial indexes.",
                    "url": "https://example.com/postgis",
                }
            ],
        }
        mock_get.return_value = mock_response

        news = services.fetch_latest_tech_news()
        self.assertIsNotNone(news)
        self.assertEqual(news["title"], "PostGIS optimizations")
        self.assertEqual(news["url"], "https://example.com/postgis")

    @override_settings(NEWS_API_KEY="")
    @mock.patch("apps.blog.services.feedparser.parse")
    def test_fetch_news_fallback_rss(self, mock_parse):
        # Mock feedparser.parse
        mock_feed = mock.Mock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {
                "title": "RSS Tech News",
                "summary": "This is a summary from RSS feed.",
                "link": "https://example.com/rss-news",
            }
        ]
        mock_parse.return_value = mock_feed

        news = services.fetch_latest_tech_news()
        self.assertIsNotNone(news)
        self.assertEqual(news["title"], "RSS Tech News")
        self.assertEqual(news["url"], "https://example.com/rss-news")

    def test_get_recent_posts_history_empty(self):
        history = services.get_recent_posts_history()
        self.assertEqual(history, "(No hay posts previos en el blog)")

    def test_get_recent_posts_history_populated(self):
        Post.objects.create(
            category=self.category,
            author=self.user,
            title_es="Post Existente",
            slug_es="post-existente",
            summary_es="Resumen previo",
        )
        history = services.get_recent_posts_history()
        self.assertIn("Post Existente", history)
        self.assertIn("Resumen previo", history)

    def test_validate_and_clean_geojson_valid(self):
        geojson_str = '{"type": "FeatureCollection", "features": []}'
        clean, ok = services.validate_and_clean_geojson(geojson_str)
        self.assertTrue(ok)
        self.assertIsNotNone(clean)

    def test_validate_and_clean_geojson_invalid(self):
        geojson_str = "invalid json string"
        clean, ok = services.validate_and_clean_geojson(geojson_str)
        self.assertFalse(ok)
        self.assertIsNone(clean)

    @override_settings(NEWS_API_KEY="fake-key")
    @mock.patch("apps.blog.services.fetch_latest_tech_news")
    @mock.patch("apps.blog.services._call_gemini_generate")
    def test_create_daily_post_success(self, mock_gemini, mock_fetch):
        mock_fetch.return_value = {
            "title": "PostGIS optimizations",
            "snippet": "Index speedups.",
            "url": "https://example.com/postgis",
        }
        mock_gemini.return_value = _gemini_payload()

        post = services.create_daily_post()
        self.assertIsNotNone(post)
        self.assertEqual(post.title_es, "Nueva IA Geoespacial")
        self.assertEqual(post.is_published, False)  # Draft by default
        self.assertEqual(post.category, self.category)
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.read_time, 6)
        self.assertEqual(post.difficulty, "intermediate")
        self.assertIsNotNone(post.map_geojson)
        self.assertEqual(post.map_center_lat, 43.2630)

        # Tags should be populated
        self.assertEqual(post.tags.count(), 3)
        self.assertTrue(Tag.objects.filter(slug="postgis").exists())

    @override_settings(NEWS_API_KEY="fake-key")
    @mock.patch("apps.blog.services.fetch_latest_tech_news")
    @mock.patch("apps.blog.services._call_gemini_generate")
    def test_create_daily_post_fenced_json(self, mock_gemini, mock_fetch):
        mock_fetch.return_value = {
            "title": "PostGIS optimizations",
            "snippet": "Index speedups.",
            "url": "https://example.com/postgis",
        }
        # Gemini returning markdown fences
        mock_gemini.return_value = "```json\n" + _gemini_payload(title_es="Fenced Title") + "\n```"

        post = services.create_daily_post()
        self.assertIsNotNone(post)
        self.assertEqual(post.title_es, "Fenced Title")

    @override_settings(NEWS_API_KEY="fake-key")
    @mock.patch("apps.blog.services.fetch_latest_tech_news")
    @mock.patch("apps.blog.services._call_gemini_generate")
    def test_create_daily_post_invalid_geojson_recovery(self, mock_gemini, mock_fetch):
        mock_fetch.return_value = {
            "title": "PostGIS optimizations",
            "snippet": "Index speedups.",
            "url": "https://example.com/postgis",
        }
        # Gemini returning invalid GeoJSON format
        mock_gemini.return_value = _gemini_payload(map_geojson="{bad geojson}")

        post = services.create_daily_post()
        self.assertIsNotNone(post)
        self.assertIsNone(post.map_geojson)
        self.assertIsNone(post.map_center_lat)


class DailyPostTasksTests(TestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name_es="WebGIS",
            name_eu="WebGIS",
            name_en="WebGIS",
            slug="webgis-postgis",
        )
        self.user = User.objects.create_superuser(
            email="admin@maps.eus",
            username="admin",
            password="password",
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    @mock.patch("apps.blog.tasks.create_daily_post")
    def test_task_runs_successfully(self, mock_create):
        # Setup mock post
        post = Post.objects.create(
            category=self.category,
            author=self.user,
            title_es="Task Created Post",
            slug_es="task-created-post",
        )
        mock_create.return_value = post

        res = generate_daily_post.delay()
        self.assertTrue(res.successful())
        self.assertIn("Post ID", res.result)
        mock_create.assert_called_once()
