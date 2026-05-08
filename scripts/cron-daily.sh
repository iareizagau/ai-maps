#!/usr/bin/env bash
# Daily data refresh — events from external APIs.
# Designed for cron. Logs to stdout; redirect via crontab.
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

run_cmd load_events
run_cmd load_sbk_events
