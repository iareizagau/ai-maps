"""Add NewsArticle (EV news aggregator) + HNSW index on embedding.

Why HNSW (not ivfflat): mandate from migration 0008 — ivfflat silently
missed TOP-1 on MobilityDocument; same risk applies to news embeddings
when the corpus grows.
"""

import pgvector.django
from django.db import migrations, models

CREATE_HNSW = """
    CREATE INDEX IF NOT EXISTS mubil_newsarticle_emb_hnsw
      ON mubil_newsarticle
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
"""

DROP_HNSW = "DROP INDEX IF EXISTS mubil_newsarticle_emb_hnsw;"


class Migration(migrations.Migration):
    dependencies = [
        ("mubil", "0012_seed_ice_generic"),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsArticle",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("newsapi", "NewsAPI"),
                            ("forocoches_ev", "Forococheselectricos"),
                            ("hibridos_electricos", "Híbridos y Eléctricos"),
                            ("movilidad_electrica", "Movilidad Eléctrica"),
                            ("motorpasion_ev", "Motorpasión Eléctrico"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("source_url", models.URLField(max_length=500, unique=True)),
                ("title_orig", models.CharField(max_length=300)),
                ("title_es", models.CharField(blank=True, max_length=300)),
                ("title_eu", models.CharField(blank=True, max_length=300)),
                ("summary_es", models.TextField(blank=True)),
                ("summary_eu", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("published_at", models.DateTimeField(db_index=True)),
                (
                    "relevance",
                    models.CharField(
                        choices=[
                            ("EUSKADI", "Euskadi"),
                            ("ESPANA", "España"),
                            ("GLOBAL", "Global"),
                        ],
                        db_index=True,
                        default="GLOBAL",
                        max_length=8,
                    ),
                ),
                ("tags", models.JSONField(blank=True, default=list)),
                (
                    "affects_user_plan",
                    models.BooleanField(db_index=True, default=False),
                ),
                (
                    "embedding",
                    pgvector.django.VectorField(blank=True, dimensions=768, null=True),
                ),
            ],
            options={
                "ordering": ["-published_at"],
                "indexes": [
                    models.Index(
                        fields=["-published_at", "relevance"],
                        name="mubil_newsa_publish_rel_idx",
                    ),
                ],
            },
        ),
        migrations.RunSQL(sql=CREATE_HNSW, reverse_sql=DROP_HNSW),
    ]
