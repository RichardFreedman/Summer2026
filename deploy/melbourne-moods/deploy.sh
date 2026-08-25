#!/usr/bin/env bash
# Sync the app to the server and (re)build it. Run deploy/caddy/deploy.sh
# first if the shared proxy is not up yet.
# Usage: deploy/melbourne-moods/deploy.sh [ssh-host]   (default: workshops)
set -euo pipefail

HOST="${1:-workshops}"
REMOTE_ROOT="/volume/summer2026"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

rsync -az --delete \
  --exclude '.git' --exclude '.summer' --exclude '.env' --exclude '.shared-password' \
  --exclude '__pycache__' --exclude '.ipynb_checkpoints' \
  --exclude 'recommender.ipynb' --exclude '*_network.html' \
  "$REPO_ROOT/moodrec" "$HOST:$REMOTE_ROOT/"
rsync -az --delete --exclude '.env' --exclude '.shared-password' \
  "$REPO_ROOT/deploy/melbourne-moods/" "$HOST:$REMOTE_ROOT/deploy/melbourne-moods/"

ssh "$HOST" "cd $REMOTE_ROOT/deploy/melbourne-moods && \
  test -f .env || { echo 'Missing .env on server; copy .env.example and fill it in.'; exit 1; } && \
  docker compose up -d --build && docker compose ps"
