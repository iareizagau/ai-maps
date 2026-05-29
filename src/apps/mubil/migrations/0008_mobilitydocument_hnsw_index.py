"""Replace the ivfflat ANN index on MobilityDocument.embedding with HNSW.

Why: the ivfflat index created in migration 0002 was missing a critical
TOP-1 doc in live RAG queries (verified 2026-05-29 — the "MOVES III IDAE
oficial" chunk had cosine sim 0.9099 to a MOVES question, yet ORDER BY
embedding <=> q LIMIT 8 returned only docs scoring ≤ 0.80). Cause: ivfflat
is an approximate index with ``lists=100`` and a default probe count of 1
— if a document's centroid falls outside the single probed list, the query
silently skips it. Raising ``ivfflat.probes`` is a band-aid; the standard
fix is HNSW (better recall at comparable speed for this corpus size).

This migration:
  1. Drops the old ``mubil_mobdoc_emb_ivf``.
  2. Creates ``mubil_mobdoc_emb_hnsw`` with conservative defaults
     (``m=16``, ``ef_construction=64``) — builds in <1 s for our ~2 K rows
     and scales to tens of thousands.

Runtime tuning ``hnsw.ef_search`` (default 40) can be raised per-query
when extra recall is worth the latency cost.
"""

from django.db import migrations


CREATE_HNSW = """
    CREATE INDEX IF NOT EXISTS mubil_mobdoc_emb_hnsw
      ON mubil_mobilitydocument
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
"""

DROP_HNSW = "DROP INDEX IF EXISTS mubil_mobdoc_emb_hnsw;"

RECREATE_IVFFLAT = """
    CREATE INDEX IF NOT EXISTS mubil_mobdoc_emb_ivf
      ON mubil_mobilitydocument
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
"""

DROP_IVFFLAT = "DROP INDEX IF EXISTS mubil_mobdoc_emb_ivf;"


class Migration(migrations.Migration):

    dependencies = [
        ('mubil', '0007_vehicle_widen_model_variant'),
    ]

    operations = [
        migrations.RunSQL(sql=DROP_IVFFLAT, reverse_sql=RECREATE_IVFFLAT),
        migrations.RunSQL(sql=CREATE_HNSW, reverse_sql=DROP_HNSW),
    ]
