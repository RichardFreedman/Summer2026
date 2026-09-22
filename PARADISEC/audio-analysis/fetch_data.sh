#!/usr/bin/env sh
# Download the PARADISEC excerpts and metadata from github.com/dan321/soundscape
# into ./soundscape (audio/ and csv/ only). Used by the Dockerfile and for local runs.
#   ./fetch_data.sh            latest master
#   ./fetch_data.sh <commit>   a pinned commit
set -eu

REF="${1:-master}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HERE/soundscape"
TMP="$(mktemp -d)"

echo "Fetching dan321/soundscape@$REF ..."
curl -fsSL "https://codeload.github.com/dan321/soundscape/tar.gz/$REF" | tar -xz -C "$TMP" --strip-components=1

mkdir -p "$DEST"
rm -rf "$DEST/audio" "$DEST/csv"
mv "$TMP/audio" "$TMP/csv" "$DEST/"
cp "$TMP/LICENSE" "$DEST/LICENSE" 2>/dev/null || true
rm -rf "$TMP"

echo "$(ls "$DEST/audio" | grep -c '\.mp3$') excerpts in $DEST/audio"
