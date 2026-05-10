#!/usr/bin/env bash
# Sanity-check that the running DB container's data_directory lives on the
# named volume mounted by docker-compose.yml. If it sits on an anonymous
# volume, persistence WILL break the next time the container is recreated.
#
# This is a guard against the bug we hit in May 2026: timescale/timescaledb-ha
# stores data in /home/postgres/pgdata/data, NOT /var/lib/postgresql/data.
# A mount on the wrong path silently sends data to an anonymous volume.

set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-maps}"

# Resolve the db container by compose label so container_name is not pinned.
DB_CONTAINER="${DB_CONTAINER:-$(docker ps -q \
  --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
  --filter "label=com.docker.compose.service=db" | head -n1)}"

if [[ -z "$DB_CONTAINER" ]] || ! docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: db container not found for project '$COMPOSE_PROJECT'" >&2
  exit 1
fi

DATA_DIR=$(docker exec "$DB_CONTAINER" psql -U postgres -tAc "SHOW data_directory;" 2>/dev/null | tr -d '[:space:]')
if [[ -z "$DATA_DIR" ]]; then
  echo "ERROR: could not read data_directory from $DB_CONTAINER" >&2
  exit 1
fi

echo "data_directory inside container: $DATA_DIR"

# Inspect the mount that contains data_directory.
# Format: "<src>:<dst>" lines, one per Mounts[*].
MOUNTS=$(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.Name}}{{"\n"}}{{end}}' "$DB_CONTAINER")

MATCH=""
while IFS='|' read -r mtype msrc mdst mname; do
  [[ -z "$mtype" ]] && continue
  if [[ "$DATA_DIR" == "$mdst"* ]]; then
    MATCH="$mtype|$msrc|$mdst|$mname"
    break
  fi
done <<< "$MOUNTS"

if [[ -z "$MATCH" ]]; then
  echo "FAIL: data_directory is NOT inside any docker mount."
  echo "      It lives in the container's writable layer — data WILL be lost on recreate."
  exit 2
fi

IFS='|' read -r mtype msrc mdst mname <<< "$MATCH"

echo "Mount covering data_directory:"
echo "  type:        $mtype"
echo "  source:      $msrc"
echo "  destination: $mdst"
echo "  name:        ${mname:-<anonymous>}"

if [[ "$mtype" != "volume" ]]; then
  echo "WARN: mount is $mtype, not a named volume. Verify this is intentional."
  exit 0
fi

if [[ -z "$mname" ]] || [[ "$mname" =~ ^[a-f0-9]{32,}$ ]]; then
  echo "FAIL: data_directory is on an ANONYMOUS volume (\$mname)."
  echo "      Fix docker-compose.yml so the named volume is mounted at $DATA_DIR."
  exit 3
fi

echo "OK: persistence is set up correctly."
