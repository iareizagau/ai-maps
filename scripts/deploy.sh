#!/usr/bin/env bash
# Production deploy. Runs on the VPS, called from .github/workflows/deploy.yml.
#
# Order of operations (each step is fail-fast):
#   1. Sanity-check the env file
#   2. Build the new web image
#   3. Bring db + redis up (no-op if already running) and wait healthy
#   4. pg_dump BEFORE migrate — non-negotiable safety net
#   5. Apply migrations
#   6. Idempotent app-data init (init_apps + init_oauth)
#   7. Roll web/worker/beat to the new image
#   8. Prune dangling images, prune old backups (keep last 14)
#
# If migrations fail, containers are NOT rolled, and the dump from step 4 is
# kept ready for restore via scripts/restore.sh.

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
BACKUP_RETENTION="${BACKUP_RETENTION:-14}"

# Force BuildKit so the cache mounts in the Dockerfile work everywhere.
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

COMPOSE="docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml"

# Resolve the running container ID for a compose service via labels. Avoids
# hardcoded container_name collisions on shared VPSs.
resolve_container() {
  docker ps -q \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter "label=com.docker.compose.service=$1" | head -n1
}

mkdir -p "$BACKUP_DIR"

echo ">> [1/8] Building web image (worker/beat reuse the same image tag)..."
$COMPOSE build web

echo ">> [2/8] Bringing db + redis up..."
$COMPOSE up -d db redis

echo ">> [3/8] Waiting for db to become healthy..."
DB_CONTAINER="${DB_CONTAINER:-$(resolve_container db)}"
if [[ -z "$DB_CONTAINER" ]]; then
  echo "ERROR: could not resolve db container after compose up" >&2
  exit 1
fi
HEALTHY=0
for _ in {1..60}; do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null || echo "starting")
  if [[ "$status" == "healthy" ]]; then
    HEALTHY=1
    break
  fi
  sleep 2
done
if [[ "$HEALTHY" -ne 1 ]]; then
  echo "ERROR: $DB_CONTAINER did not become healthy in 120s" >&2
  exit 1
fi

echo ">> [4/8] Backing up DB before migrate..."
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/pre-deploy-$TIMESTAMP.dump"
if docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$DB_CONTAINER" \
     pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -Z 6 > "$BACKUP_FILE"; then
  echo "   wrote $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
  echo "ERROR: pg_dump failed; refusing to migrate without a backup." >&2
  rm -f "$BACKUP_FILE"
  exit 1
fi

# Refuse to run if backup is suspiciously small (< 1KB ⇒ empty DB or auth issue).
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE")
if [[ "$BACKUP_SIZE" -lt 1024 ]]; then
  echo "WARN: backup is only ${BACKUP_SIZE} bytes — DB may be empty." >&2
  echo "      If this is the first ever deploy, set ALLOW_EMPTY_DB=1 to proceed." >&2
  if [[ "${ALLOW_EMPTY_DB:-0}" != "1" ]]; then
    exit 1
  fi
fi

echo ">> [5/8] Running migrations..."
$COMPOSE run --rm web python manage.py migrate --noinput

echo ">> [6/8] Initializing AppRegistry + OAuth (idempotent)..."
$COMPOSE run --rm web python manage.py init_apps
$COMPOSE run --rm web python manage.py init_oauth

echo ">> [7/8] Rolling services to new image..."
$COMPOSE up -d --remove-orphans

echo ">> [8/8] Pruning dangling images + old backups (keep last $BACKUP_RETENTION)..."
# Filter by our LABEL so we don't touch other projects' images on the host.
docker image prune -f --filter "label=com.maps.project=maps"
ls "$BACKUP_DIR"/pre-deploy-*.dump 2>/dev/null | sort -r | tail -n +$((BACKUP_RETENTION + 1)) | xargs -r rm -f

echo ">> Deploy complete. Backup: $BACKUP_FILE"
