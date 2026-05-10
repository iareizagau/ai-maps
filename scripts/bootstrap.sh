#!/usr/bin/env bash
# One-shot data bootstrap. Run AFTER the first successful deploy, then never again.
# Idempotent: safe to re-run, but slow (calls every external API once).
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.prod ]]; then
  echo "ERROR: .env.prod not found in $(pwd)" >&2
  exit 1
fi

COMPOSE="docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml"

echo ">> Seeding inguru stations (one-time)..."
$COMPOSE exec -T web python manage.py seed_inguru || echo "WARN: seed_inguru failed"

echo ">> Triggering kultur.load_events via celery..."
$COMPOSE exec -T worker celery -A config call kultur.load_events || echo "WARN: kultur.load_events dispatch failed"

echo ">> Triggering sbk.load_events via celery..."
$COMPOSE exec -T worker celery -A config call sbk.load_events || echo "WARN: sbk.load_events dispatch failed"

echo ">> Triggering inguru.ingest via celery..."
$COMPOSE exec -T worker celery -A config call inguru.ingest || echo "WARN: inguru.ingest dispatch failed"

echo ">> Triggering gailur.import_and_geocode via celery..."
$COMPOSE exec -T worker celery -A config call gailur.import_and_geocode || echo "WARN: gailur.import_and_geocode dispatch failed"

echo ">> Bootstrap dispatched. Tasks running async; check worker logs for progress."
echo ">> $COMPOSE logs -f worker"
