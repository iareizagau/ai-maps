#!/usr/bin/env bash
# Restore the production DB from a pg_dump custom-format file.
# Destructive — drops and recreates objects via pg_restore --clean.
#
# Usage: ./scripts/restore.sh <backup-file>
#
# Safety:
#   - Requires interactive confirmation (CONFIRM=I_UNDERSTAND env to skip).
#   - Takes a fresh snapshot first (pre-restore-*.dump) so a botched restore
#     doesn't mean lost data.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <backup-file>" >&2
  exit 1
fi

BACKUP_FILE="$1"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "ERROR: $BACKUP_FILE not found" >&2
  exit 1
fi

if [[ ! -f .env.prod ]]; then
  echo "ERROR: .env.prod not found in $(pwd)" >&2
  exit 1
fi

DB_CONTAINER="${DB_CONTAINER:-maps_db_prod}"
DB_NAME="${POSTGRES_DB:-maps_db}"
DB_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

echo ">> Will restore $BACKUP_FILE into $DB_NAME on $DB_CONTAINER."
echo ">> This is DESTRUCTIVE — current data will be replaced."

if [[ "${CONFIRM:-}" != "I_UNDERSTAND" ]]; then
  read -r -p "Type 'I_UNDERSTAND' to proceed: " confirm
  if [[ "$confirm" != "I_UNDERSTAND" ]]; then
    echo "Aborted."
    exit 1
  fi
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
SAFETY_FILE="$BACKUP_DIR/pre-restore-$TIMESTAMP.dump"

echo ">> Snapshotting current DB to $SAFETY_FILE before restoring..."
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$DB_CONTAINER" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -Z 6 > "$SAFETY_FILE"

echo ">> Restoring..."
docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$DB_CONTAINER" \
  pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner < "$BACKUP_FILE"

echo ">> Restore complete."
echo "   Pre-restore safety dump: $SAFETY_FILE"
