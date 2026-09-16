#!/usr/bin/env bash
# Download all resource view nanopublications from Nanopub Query
# and store them as individual TriG files in the resource-views/ subfolder.
#
# Usage: ./download-resource-views.sh [output-dir]
#   output-dir defaults to the resource-views/ directory next to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${1:-$SCRIPT_DIR/../resource-views}"

mkdir -p "$OUTPUT_DIR"

echo "Fetching resource view list from Nanopub Query..."
QUERY_LIST=$(curl -s "https://query.knowledgepixels.com/api/RAlUUQZdB79bh2lHZdoC21crPDV1SdR9k6ilkGrlRKm94/get-all-resource-views")

# Parse the CSV properly: labels contain commas and quotes, so a naive IFS=,
# split shifts the columns and the nanopub URI ends up holding label text
# (curl then fails with "URL malformed" and set -e aborts the whole run).
# Emit one TAB-separated "trustyId<TAB>label" record per view instead.
RECORDS=$(printf '%s' "$QUERY_LIST" | python3 -c '
import csv, sys
r = csv.reader(sys.stdin)
header = next(r, None)
cols = {name: i for i, name in enumerate(header or [])}
for row in r:
    if not row:
        continue
    np_uri = row[cols["np"]] if "np" in cols else row[9]
    label = row[cols["view_label"]] if "view_label" in cols else row[1]
    print(np_uri.rsplit("/", 1)[-1] + "\t" + label.replace("\t", " "))
')

# Count actual CSV records, not lines (quoted fields may span lines)
TOTAL=$(printf '%s\n' "$RECORDS" | grep -c .)
echo "Found $TOTAL resource views."

# Collect current trusty IDs for cleanup later
CURRENT_IDS=$(printf '%s\n' "$RECORDS" | cut -f1)

COUNT=0
printf '%s\n' "$RECORDS" | while IFS=$'\t' read -r TRUSTY_ID view_label; do
  np="https://w3id.org/np/${TRUSTY_ID}"
  # Use view_label if available, otherwise fall back to trusty ID
  if [ -n "$view_label" ]; then
    # Sanitize label for filename: lowercase, replace spaces/special chars with hyphens
    FILENAME=$(echo "$view_label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
    OUTFILE="${OUTPUT_DIR}/${TRUSTY_ID}_${FILENAME}.trig"
  else
    OUTFILE="${OUTPUT_DIR}/${TRUSTY_ID}.trig"
  fi

  if [ -f "$OUTFILE" ]; then
    COUNT=$((COUNT + 1))
    echo "[$COUNT/$TOTAL] Skipping (exists): ${view_label:-$TRUSTY_ID}"
    continue
  fi

  COUNT=$((COUNT + 1))
  echo "[$COUNT/$TOTAL] Downloading: ${view_label:-$TRUSTY_ID}"
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

echo "Done. Resource views stored in: $OUTPUT_DIR"
