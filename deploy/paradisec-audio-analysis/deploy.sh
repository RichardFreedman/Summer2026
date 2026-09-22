#!/usr/bin/env bash
# Update the server checkout and rebuild the PARADISEC audio analysis app.
# Usage: deploy/paradisec-audio-analysis/deploy.sh
# The build downloads the audio excerpts from GitHub, so it takes a few minutes
# the first time; later builds reuse that layer unless the Dockerfile's pinned
# commit changes.
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

remote_update_checkout
ssh "$HOST" "cd $REMOTE_ROOT/deploy/paradisec-audio-analysis && \
  docker compose up -d --build && docker compose ps"
