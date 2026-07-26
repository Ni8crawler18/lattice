#!/usr/bin/env bash
# Mint a Lattice API key and print the export line.
#   ./examples/createkey.sh [name] [api-url]
set -euo pipefail

NAME="${1:-$(whoami)}"
API="${2:-${LATTICE_API:-https://lattice-api-96cn.onrender.com}}"

KEY=$(curl -sf -X POST "$API/keys" \
  -H 'Content-Type: application/json' \
  -d "{\"name\": \"$NAME\"}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['api_key'])")

echo "export LATTICE_KEY=$KEY"
# shown once -- save it. Send as:  X-API-Key: $LATTICE_KEY
