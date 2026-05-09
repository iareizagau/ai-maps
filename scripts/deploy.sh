#!/usr/bin/env bash
# Runs on the VPS during each deploy.
# Builds locally from the latest checkout and rolls services.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.prod ]]; then
  echo "ERROR: .env.prod not found in $(pwd)" >&2
  exit 1
fi

COMPOSE="docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml"

echo ">> Building web image..."
$COMPOSE build web

echo ">> Bringing db up..."
$COMPOSE up -d db

echo ">> Waiting for db to be healthy..."
for _ in {1..30}; do
  status=$(docker inspect -f '{{.State.Health.Status}}' maps_db_prod 2>/dev/null || echo "starting")
  [[ "$status" == "healthy" ]] && break
  sleep 2
done

echo ">> Running migrations..."
$COMPOSE run --rm web python manage.py migrate --noinput

echo ">> Collecting static files..."
$COMPOSE run --rm web python manage.py collectstatic --noinput

echo ">> Initializing app registry..."
$COMPOSE run --rm web python manage.py init_apps

echo ">> Loading kultur events..."
$COMPOSE run --rm web python manage.py load_events || echo "WARN: load_events failed, continuing deploy"

echo ">> Loading sbk events..."
$COMPOSE run --rm web python manage.py load_sbk_events || echo "WARN: load_sbk_events failed, continuing deploy"

echo ">> Ingesting inguru data..."
$COMPOSE run --rm web python manage.py ingest_inguru || echo "WARN: ingest_inguru failed, continuing deploy"

echo ">> Importing gailur climbing data..."
$COMPOSE run --rm web python manage.py import_climbing || echo "WARN: import_climbing failed, continuing deploy"

echo ">> Geocoding gailur crags..."
$COMPOSE run --rm web python manage.py geocode_crags || echo "WARN: geocode_crags failed, continuing deploy"

echo ">> Starting services..."
$COMPOSE up -d --remove-orphans

echo ">> Pruning dangling images..."
docker image prune -f

echo ">> Deploy complete."
