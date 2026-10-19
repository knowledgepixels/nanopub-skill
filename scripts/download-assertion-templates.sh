#!/usr/bin/env bash
# Download all assertion template nanopublications from Nanopub Query
# and store them as individual TriG files in the assertion-templates/ subfolder.
#
# Usage: ./download-assertion-templates.sh [output-dir]
#   output-dir defaults to the assertion-templates/ directory next to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/download-collection.sh
source "$SCRIPT_DIR/lib/download-collection.sh"

download_collection \
  "assertion templates" \
  "RAi6EPio6sbvJ06mqfYm_QBmisWQnJ8cvzm-DKRHKPGUg" \
  "get-assertion-templates" \
  "label" \
  "${1:-$SCRIPT_DIR/../assertion-templates}"
