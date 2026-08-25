#!/usr/bin/env bash
# Sync the shared Caddy config to the server and reload it.
# Usage: deploy/caddy/deploy.sh [ssh-host]   (default: workshops)
set -euo pipefail

HOST="${1:-workshops}"
REMOTE_DIR="/volume/summer2026/deploy/caddy"
HERE="$(cd "$(dirname "$0")" && pwd)"

rsync -az --delete --exclude '.env' "$HERE/" "$HOST:$REMOTE_DIR/"

ssh "$HOST" "cd $REMOTE_DIR && \
  test -f .env || { echo 'Missing .env on server; copy .env.example and fill it in.'; exit 1; } && \
  docker network inspect web >/dev/null 2>&1 || docker network create web && \
  docker compose up -d && \
  docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile && docker compose ps"
