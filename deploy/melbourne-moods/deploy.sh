#!/usr/bin/env bash
# Sync this repo to the workshops server and (re)start the stack.
# Usage: deploy/melbourne-moods/deploy.sh [ssh-host]   (default: workshops)
set -euo pipefail

HOST="${1:-workshops}"
REMOTE_DIR="~/melbourne-moods"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

rsync -az --delete \
  --exclude '.git' --exclude '.summer' --exclude '.env' --exclude '.shared-password' \
  --exclude '__pycache__' --exclude '.ipynb_checkpoints' \
  --exclude 'recommender.ipynb' --exclude '*_network.html' \
  "$REPO_ROOT/moodrec" "$REPO_ROOT/deploy" "$HOST:$REMOTE_DIR/"

ssh "$HOST" "cd $REMOTE_DIR/deploy/melbourne-moods && \
  test -f .env || { echo 'Missing .env on server; copy .env.example and fill it in.'; exit 1; } && \
  docker compose up -d --build && \
  docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile && docker compose ps"
