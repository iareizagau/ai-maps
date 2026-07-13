"""TimescaleDB hypertables + pgvector ivfflat index.

Manual migration that wraps the raw SQL we couldn't auto-generate from models.py.
Runs on empty tables in F0.

- `EnergyPricePVPC` → hypertable on `timestamp` (ESIOS PVPC horario).
- `MobilityTrip`    → hypertable on `date` (MITMA OD diario).
- `MobilityDocument` → ivfflat index on `embedding` (768d cosine).

TimescaleDB constraint: the partitioning column must be part of every unique
index, including the Django default `id` PK. Standard pattern:
  1. DROP existing PK (`id` alone).
  2. SELECT create_hypertable(...).
  3. ADD composite PK `(id, <partition_col>)` so Django ORM keeps working.

The ivfflat index is created empty with `lists=100`; reindex after the corpus
reaches ~1k rows for optimal performance.
"""

from django.db import migrations

HYPERTABLE_ENERGY_SQL = """
ALTER TABLE mubil_energypricepvpc DROP CONSTRAINT mubil_energypricepvpc_pkey;
SELECT create_hypertable(
    'mubil_energypricepvpc',
    'timestamp',
    if_not_exists => TRUE,
    migrate_data => TRUE
);
ALTER TABLE mubil_energypricepvpc ADD PRIMARY KEY (id, "timestamp");
"""

HYPERTABLE_ENERGY_REVERSE_SQL = """
-- Reversal not supported: hypertables cannot be downgraded without data loss.
SELECT 1;
"""

HYPERTABLE_TRIP_SQL = """
ALTER TABLE mubil_mobilitytrip DROP CONSTRAINT mubil_mobilitytrip_pkey;
SELECT create_hypertable(
    'mubil_mobilitytrip',
    'date',
    if_not_exists => TRUE,
    migrate_data => TRUE
);
ALTER TABLE mubil_mobilitytrip ADD PRIMARY KEY (id, "date");
"""

HYPERTABLE_TRIP_REVERSE_SQL = """
SELECT 1;
"""

CREATE_IVFFLAT_SQL = """
CREATE INDEX IF NOT EXISTS mubil_mobdoc_emb_ivf
    ON mubil_mobilitydocument
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""

DROP_IVFFLAT_SQL = """
DROP INDEX IF EXISTS mubil_mobdoc_emb_ivf;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("mubil", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=HYPERTABLE_ENERGY_SQL,
            reverse_sql=HYPERTABLE_ENERGY_REVERSE_SQL,
        ),
        migrations.RunSQL(
            sql=HYPERTABLE_TRIP_SQL,
            reverse_sql=HYPERTABLE_TRIP_REVERSE_SQL,
        ),
        migrations.RunSQL(
            sql=CREATE_IVFFLAT_SQL,
            reverse_sql=DROP_IVFFLAT_SQL,
        ),
    ]
