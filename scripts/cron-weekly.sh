#!/usr/bin/env bash
# Weekly data refresh — climbing scraping + geocoding.
# Slow; rate-limited by Nominatim (1 req/s).
set -uo pipefail

cd "$(dirname "$0")/.."

COMPOSE="docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml"

run_cmd() {
  local cmd="$1"
  echo "[$(date -Is)] >> $cmd"
  if $COMPOSE exec -T web python manage.py "$cmd"; then
    echo "[$(date -Is)] OK $cmd"
  else
    echo "[$(date -Is)] FAIL $cmd (exit $?)" >&2
  fi
}

run_cmd import_climbing
run_cmd geocode_crags
