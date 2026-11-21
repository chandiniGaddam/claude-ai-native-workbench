#!/usr/bin/env bash
# Repeatable reset: fresh isolated copy, a fresh database (volume removed), rebuild, start, and
# wait until all three services are healthy. Flyway re-seeds the database on backend startup.
#
# Usage: scripts/reset_aut.sh          (needs Docker access, i.e. the docker group)
#        scripts/reset_aut.sh --down   (stop the stack and delete its data volume)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--down" ]]; then
  docker compose down -v --remove-orphans
  exit 0
fi

if [[ ! -f .env ]]; then
  (umask 077; printf 'MYSQL_ROOT_PASSWORD=%s\n' "$(openssl rand -hex 24)" > .env)
  echo "reset: generated .env with a random MySQL root password (git-ignored, mode 600)"
fi

python3 -I scripts/snapshot_aut.py
docker compose down -v --remove-orphans
docker compose up -d --build --wait --wait-timeout 900
docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}\t{{.Ports}}'
