#!/usr/bin/env bash
# Update the server checkout and rebuild "Ask the transcripts".
# Usage: deploy/paradisec-transcripts/deploy.sh
#
# Needs, on the server, in this directory: .env (OPENAI_API_KEY) and data/ with at
# least one *_metadata.csv manifest. Neither is in git; see README.md here.
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

remote_update_checkout
ssh "$HOST" "cd $REMOTE_ROOT/deploy/paradisec-transcripts && \
  test -f .env || { echo 'Missing .env on server; copy .env.example and fill it in.'; exit 1; } && \
  ls data/*_metadata.csv >/dev/null 2>&1 || { echo 'No manifests in data/ on server; copy the corpus there first.'; exit 1; } && \
  docker compose up -d --build && docker compose ps"
