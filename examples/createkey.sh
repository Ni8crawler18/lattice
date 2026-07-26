#!/usr/bin/env bash
# Mint a Lattice API key and print the export line.
#
#   ./examples/createkey.sh [name] [api-url]
#
# name     defaults to your username
# api-url  defaults to $LATTICE_API, then the deployed API
#
# The key is shown ONCE -- save the export line. Send it as `X-API-Key: <key>`
# (or `?key=<key>` where headers are awkward, e.g. a CSV download link).
set -euo pipefail

NAME="${1:-$(whoami)}"
API="${2:-${LATTICE_API:-https://lattice-api-96cn.onrender.com}}"

KEY=$(curl -sf -X POST "$API/keys" \
  -H 'Content-Type: application/json' \
  -d "{\"name\": \"$NAME\"}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['api_key'])")

echo "export LATTICE_KEY=$KEY"
echo "# shown once -- save it. e.g.:  curl -H \"X-API-Key: \$LATTICE_KEY\" $API/parse ..."
