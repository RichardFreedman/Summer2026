#!/usr/bin/env bash
# Update the server checkout and reload the shared Caddy.
# Usage: deploy/caddy/deploy.sh          (env: DEPLOY_HOST, DEPLOY_BRANCH)
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

remote_update_checkout
ssh "$HOST" "cd $REMOTE_ROOT/deploy/caddy && \
  test -f .env || { echo 'Missing .env on server; copy .env.example and fill it in.'; exit 1; } && \
  docker network inspect web >/dev/null 2>&1 || docker network create web && \
  docker compose up -d && \
  docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile && docker compose ps"
