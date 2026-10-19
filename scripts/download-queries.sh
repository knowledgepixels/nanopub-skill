#!/usr/bin/env bash
# Download all query template nanopublications from Nanopub Query
# and store them as individual TriG files in the queries/ subfolder.
#
# Usage: ./download-queries.sh [output-dir]
#   output-dir defaults to the queries/ directory next to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/download-collection.sh
source "$SCRIPT_DIR/lib/download-collection.sh"

download_collection \
  "query templates" \
  "RAQqjXQYlxYQeI4Y3UQy9OrD5Jx1E3PJ8KwKKQlWbiYSw" \
  "get-queries" \
  "label" \
  "${1:-$SCRIPT_DIR/../queries}"
