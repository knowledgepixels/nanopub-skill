#!/usr/bin/env bash
# Download all resource view nanopublications from Nanopub Query
# and store them as individual TriG files in the resource-views/ subfolder.
#
# Usage: ./download-resource-views.sh [output-dir]
#   output-dir defaults to the resource-views/ directory next to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/download-collection.sh
source "$SCRIPT_DIR/lib/download-collection.sh"

download_collection \
  "resource views" \
  "RAlUUQZdB79bh2lHZdoC21crPDV1SdR9k6ilkGrlRKm94" \
  "get-all-resource-views" \
  "view_label" \
  "${1:-$SCRIPT_DIR/../resource-views}"
