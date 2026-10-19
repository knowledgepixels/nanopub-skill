#!/usr/bin/env bash
# Shared implementation behind download-queries.sh, download-assertion-templates.sh
# and download-resource-views.sh: fetch a listing of nanopublications from Nanopub
# Query and mirror them as individual TriG files in a local folder.
#
# Source this file and call:
#   download_collection <kind> <listing-np> <listing-query> <label-column> <output-dir>
#
# The listing must have an "np" column with the nanopub URI; <label-column> names the
# column the filename is derived from (filenames are "<trusty-id>_<slugified-label>.trig").

set -euo pipefail

# Generic Nanopub Query prefix: resolves to whichever instance is available, so the
# scripts do not break when one host goes stale (query.knowledgepixels.com silently
# returned empty result sets for weeks in 2026). It is a redirect, hence -L.
API_PREFIX="https://w3id.org/np/l/nanopub-query-1.1/api"
REPO_PREFIX="https://w3id.org/np/l/nanopub-query-1.1/repo"

# Of the trusty IDs on stdin (one per line), print those whose nanopub is superseded,
# invalidated or retracted by another nanopub, according to the full Nanopub Query
# repository. Anything else is still live and must stay in the mirror.
obsolete_nanopubs() {
  local IDS VALUES QUERY
  IDS=$(cat)
  [ -n "$IDS" ] || return 0
  VALUES=$(printf '%s\n' "$IDS" | sed 's|^|<https://w3id.org/np/|;s|$|>|' | tr '\n' ' ')
  QUERY="prefix npx: <http://purl.org/nanopub/x/>
select distinct ?old where {
  values ?old { $VALUES }
  graph ?g { ?new ?p ?old }
  filter(?p in (npx:supersedes, npx:invalidates, npx:retracts))
}"
  # tr -d '\r': the CSV comes back with CRLF line endings.
  curl -sfSL -G "$REPO_PREFIX/full" --data-urlencode "query=$QUERY" -H "Accept: text/csv" \
    | tail -n +2 | tr -d '\r' | sed 's|.*/||'
}

download_collection() {
  local KIND="$1" LISTING_NP="$2" LISTING_QUERY="$3" LABEL_COLUMN="$4" OUTPUT_DIR="$5"

  mkdir -p "$OUTPUT_DIR"

  echo "Fetching $KIND list from Nanopub Query..."
  local LISTING
  # -f so an HTTP error aborts the run instead of being parsed as an empty listing.
  LISTING=$(curl -sfSL -H "Accept: text/csv" "$API_PREFIX/$LISTING_NP/$LISTING_QUERY")

  # Parse the CSV properly: labels contain commas and quotes, so a naive IFS=, split
  # shifts the columns and the nanopub URI ends up holding label text (which both
  # breaks the download and truncates the filename at the comma, leaving two
  # differently named copies of the same nanopub behind). One listing can also carry
  # several rows per nanopub (e.g. a nanopub defining more than one view, or a row
  # with an empty label), so collapse them to one record per trusty ID, preferring a
  # non-empty label and picking deterministically when several are non-empty.
  local RECORDS
  RECORDS=$(printf '%s' "$LISTING" | LABEL_COLUMN="$LABEL_COLUMN" python3 -c '
import csv, os, sys
label_column = os.environ["LABEL_COLUMN"]
reader = csv.DictReader(sys.stdin)
labels = {}
for row in reader:
    np_uri = (row.get("np") or "").strip()
    if not np_uri:
        continue
    trusty_id = np_uri.rsplit("/", 1)[-1]
    label = (row.get(label_column) or "").replace("\t", " ").strip()
    labels.setdefault(trusty_id, set()).add(label)
for trusty_id in sorted(labels):
    candidates = sorted(l for l in labels[trusty_id] if l)
    print(trusty_id + "\t" + (candidates[0] if candidates else ""))
')

  local TOTAL LOCAL_COUNT
  TOTAL=$(printf '%s\n' "$RECORDS" | grep -c . || true)
  LOCAL_COUNT=$(find "$OUTPUT_DIR" -maxdepth 1 -name '*.trig' | wc -l)
  echo "Found $TOTAL $KIND ($LOCAL_COUNT file(s) currently mirrored)."

  # Refuse to work from an implausible listing: an empty or badly truncated response
  # means the service is broken, not that the collection shrank.
  if [ "$TOTAL" -eq 0 ] || { [ "$LOCAL_COUNT" -gt 0 ] && [ "$((TOTAL * 2))" -lt "$LOCAL_COUNT" ]; }; then
    echo "Aborting: the listing ($TOTAL rows) is implausibly small next to the $LOCAL_COUNT mirrored file(s)." >&2
    echo "Check the Nanopub Query service before running this again; nothing was changed." >&2
    return 1
  fi

  local CURRENT_IDS
  CURRENT_IDS=$(printf '%s\n' "$RECORDS" | cut -f1)

  local COUNT=0 DOWNLOADED=0 FAILED=0 REMOVED=0
  local TRUSTY_ID LABEL FILENAME OUTFILE TMPFILE NP
  while IFS=$'\t' read -r TRUSTY_ID LABEL; do
    [ -n "$TRUSTY_ID" ] || continue
    COUNT=$((COUNT + 1))
    NP="https://w3id.org/np/${TRUSTY_ID}"
    # Sanitize label for filename: lowercase, replace spaces/special chars with hyphens
    FILENAME=$(printf '%s' "$LABEL" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
    if [ -n "$FILENAME" ]; then
      OUTFILE="${OUTPUT_DIR}/${TRUSTY_ID}_${FILENAME}.trig"
    else
      OUTFILE="${OUTPUT_DIR}/${TRUSTY_ID}.trig"
    fi

    # Other files holding the same nanopub under a stale name (an earlier truncated
    # label, a hand-shortened name, a row that had no label yet). They are dropped
    # once the canonically named file is in place, never before: a failed download
    # must leave the nanopub mirrored under its old name rather than nowhere.
    local DUPLICATES=""
    local other
    for other in "${OUTPUT_DIR}/${TRUSTY_ID}"*.trig; do
      [ -f "$other" ] || continue
      [ "$other" != "$OUTFILE" ] || continue
      DUPLICATES="${DUPLICATES}${other}"$'\n'
    done

    if [ -f "$OUTFILE" ]; then
      echo "[$COUNT/$TOTAL] Skipping (exists): ${LABEL:-$TRUSTY_ID}"
    else
      echo "[$COUNT/$TOTAL] Downloading: ${LABEL:-$TRUSTY_ID}"
      # Download to a temp file and only keep it once it looks like a signed nanopub,
      # so a transient error page never ends up mirrored as a .trig file.
      TMPFILE="${OUTFILE}.part"
      if curl -sfSL -H "Accept: application/trig" "$NP" -o "$TMPFILE" \
         && grep -q "npx:hasSignature" "$TMPFILE"; then
        mv "$TMPFILE" "$OUTFILE"
        DOWNLOADED=$((DOWNLOADED + 1))
      else
        rm -f "$TMPFILE"
        echo "  WARNING: could not download a signed nanopub for $NP" >&2
        FAILED=$((FAILED + 1))
        DUPLICATES=""
      fi
    fi

    while IFS= read -r other; do
      [ -n "$other" ] || continue
      echo "Removing duplicate: $(basename "$other") (same nanopub as $(basename "$OUTFILE"))"
      rm "$other"
      REMOVED=$((REMOVED + 1))
    done <<< "$DUPLICATES"
  done <<< "$RECORDS"

  # Candidates for removal: local files whose trusty ID is not in the listing.
  local f BASENAME FILE_ID CANDIDATES="" STALE=0 KEPT=0
  for f in "$OUTPUT_DIR"/*.trig; do
    [ -f "$f" ] || continue
    # Extract trusty ID (first 45 chars: "RA" + 43 base64url chars)
    BASENAME=$(basename "$f" .trig)
    FILE_ID="${BASENAME:0:45}"
    if ! printf '%s\n' "$CURRENT_IDS" | grep -qxF "$FILE_ID"; then
      CANDIDATES="${CANDIDATES}${FILE_ID}"$'\t'"${f}"$'\n'
    fi
  done

  # Never delete a local file just because it is missing from the listing: these
  # listings have repeatedly been incomplete (a per-type repo that has not loaded
  # every nanopub, a listing version keyed on something too narrow) and have asked
  # for live, latest-version nanopubs to be deleted. Only remove a file once the
  # nanopub itself is confirmed superseded, invalidated or retracted; anything else
  # is reported and kept.
  if [ -n "$CANDIDATES" ]; then
    local SUPERSEDED
    SUPERSEDED=$(printf '%s' "$CANDIDATES" | cut -f1 | obsolete_nanopubs)
    while IFS=$'\t' read -r FILE_ID f; do
      [ -n "$FILE_ID" ] || continue
      if printf '%s\n' "$SUPERSEDED" | grep -qxF "$FILE_ID"; then
        echo "Removing superseded: $(basename "$f")"
        rm "$f"
        STALE=$((STALE + 1))
      else
        echo "  WARNING: $(basename "$f") is absent from the listing but is not superseded, invalidated or retracted - keeping it." >&2
        KEPT=$((KEPT + 1))
      fi
    done <<< "$CANDIDATES"
  fi

  echo "Done. $DOWNLOADED downloaded, $STALE superseded file(s) removed, $REMOVED duplicate(s) removed, $KEPT unlisted file(s) kept, $FAILED failed."
  echo "$KIND stored in: $OUTPUT_DIR"
  [ "$FAILED" -eq 0 ]
}
