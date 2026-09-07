#!/usr/bin/env bash
# Update the server checkout and (re)start the Liedertafel static site.
# Usage: deploy/liedertafel/deploy.sh
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

remote_update_checkout
ssh "$HOST" "cd $REMOTE_ROOT/deploy/liedertafel && docker compose up -d && docker compose ps"
