#!/usr/bin/env bash
# Update the server checkout and rebuild the Melbourne Moods app.
# Usage: deploy/melbourne-moods/deploy.sh   (env: DEPLOY_HOST, DEPLOY_BRANCH)
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

remote_update_checkout
ssh "$HOST" "cd $REMOTE_ROOT/deploy/melbourne-moods && \
  test -f .env || { echo 'Missing .env on server; copy .env.example and fill it in.'; exit 1; } && \
  docker compose up -d --build && docker compose ps"
