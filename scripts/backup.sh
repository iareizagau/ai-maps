#!/usr/bin/env bash
# On-demand pg_dump of the production DB. Standalone — does not roll services.
# Useful before risky manual operations (data migrations, schema surgery).
#
# Usage: ./scripts/backup.sh [label]
#   label  optional tag baked into the filename (default: "manual")
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.prod ]]; then
  echo "ERROR: .env.prod not found in $(pwd)" >&2
  exit 1
fi

COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-maps}"
DB_NAME="${POSTGRES_DB:-maps_db}"
DB_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
LABEL="${1:-manual}"

mkdir -p "$BACKUP_DIR"

# Resolve the db container by compose label so container_name is not pinned.
DB_CONTAINER="${DB_CONTAINER:-$(docker ps -q \
  --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
  --filter "label=com.docker.compose.service=db" | head -n1)}"

if [[ -z "$DB_CONTAINER" ]] || ! docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: db container not found for project '$COMPOSE_PROJECT'." >&2
  echo "       Is the stack up? docker compose ps" >&2
  exit 1
fi

TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${LABEL}-${TIMESTAMP}.dump"

echo ">> Dumping $DB_NAME from $DB_CONTAINER..."
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$DB_CONTAINER" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -Z 6 > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo ">> Wrote $BACKUP_FILE ($SIZE)"
