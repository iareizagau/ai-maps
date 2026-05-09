#!/usr/bin/env bash
# Runs on the VPS during each deploy.
# Builds locally from the latest checkout and rolls services.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env.prod ]]; then
  echo "ERROR: .env.prod not found in $(pwd)" >&2
  exit 1
fi

# Force BuildKit so the cache mounts in the Dockerfile work everywhere.
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

COMPOSE="docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml"

echo ">> Building web image (worker/beat reuse the same image tag)..."
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

echo ">> Initializing app registry..."
$COMPOSE run --rm web python manage.py init_apps

echo ">> Starting services..."
$COMPOSE up -d --remove-orphans

echo ">> Pruning dangling images..."
docker image prune -f

echo ">> Deploy complete."
