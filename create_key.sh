#!/usr/bin/env bash
# Mint a Lattice API key. Usage:  ./create_key.sh [name]
# The key is shown ONCE — copy it into test_parse.py (API_KEY).

BASE="${LATTICE_BASE:-https://lattice-api-96cn.onrender.com}"
NAME="${1:-eng-team}"

curl -s -X POST "$BASE/keys" \
  -H 'Content-Type: application/json' \
  -d "{\"name\": \"$NAME\"}"
echo
