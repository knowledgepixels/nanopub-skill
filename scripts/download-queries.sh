#!/usr/bin/env bash
# Download all query template nanopublications from Nanopub Query
# and store them as individual TriG files in the queries/ subfolder.
#
# Usage: ./download-queries.sh [output-dir]
#   output-dir defaults to the queries/ directory next to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${1:-$SCRIPT_DIR/../queries}"

mkdir -p "$OUTPUT_DIR"

echo "Fetching query list from Nanopub Query..."
QUERY_LIST=$(curl -s "https://query.knowledgepixels.com/api/RAQqjXQYlxYQeI4Y3UQy9OrD5Jx1E3PJ8KwKKQlWbiYSw/get-queries")

# Skip the CSV header line
TOTAL=$(echo "$QUERY_LIST" | tail -n +2 | wc -l)
echo "Found $TOTAL query templates."

# Collect current trusty IDs for cleanup later
CURRENT_IDS=$(echo "$QUERY_LIST" | tail -n +2 | while IFS=, read -r np _rest; do
  echo "$np" | sed 's|.*/||'
done)

COUNT=0
echo "$QUERY_LIST" | tail -n +2 | while IFS=, read -r np label _rest; do
  # Extract the trusty ID from the nanopub URI
  TRUSTY_ID=$(echo "$np" | sed 's|.*/||')
  # Sanitize label for filename: lowercase, replace spaces/special chars with hyphens
  FILENAME=$(echo "$label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
  OUTFILE="${OUTPUT_DIR}/${TRUSTY_ID}_${FILENAME}.trig"

  if [ -f "$OUTFILE" ]; then
    COUNT=$((COUNT + 1))
    echo "[$COUNT/$TOTAL] Skipping (exists): $label"
    continue
  fi

  COUNT=$((COUNT + 1))
  echo "[$COUNT/$TOTAL] Downloading: $label"
  curl -s -L -H "Accept: application/trig" "$np" -o "$OUTFILE"
done

# Remove local files whose trusty ID is no longer in the API response
REMOVED=0
for f in "$OUTPUT_DIR"/*.trig; do
  [ -f "$f" ] || continue
  # Extract trusty ID (first 45 chars: "RA" + 43 base64url chars)
  BASENAME=$(basename "$f" .trig)
  FILE_ID="${BASENAME:0:45}"
  if ! echo "$CURRENT_IDS" | grep -qxF "$FILE_ID"; then
    echo "Removing stale: $(basename "$f")"
    rm "$f"
    REMOVED=$((REMOVED + 1))
  fi
done
[ "$REMOVED" -gt 0 ] && echo "Removed $REMOVED stale file(s)."

echo "Done. Query templates stored in: $OUTPUT_DIR"
