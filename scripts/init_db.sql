-- Extensions for Maps.eus.
-- Installed both in the working DB and in template1 so any DB created later
-- (including Django's test DB, which is named test_<DB_NAME>) inherits them
-- automatically without needing CreateExtension migrations.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

\c template1
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

