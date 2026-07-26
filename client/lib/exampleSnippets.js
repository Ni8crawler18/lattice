// GENERATED from examples/* — static copies so the docs render the code even
// when the API is cold or unreachable (the Vercel build ships these; not
// fetched live — the deployed API can lag the repo).
// Regenerate after editing examples/: see "exampleSnippets" note in tasklist.md.

export const EXAMPLE_SNIPPETS = {
  "createkey.sh": `#!/usr/bin/env bash
# Mint a Lattice API key and print the export line.
#   ./examples/createkey.sh [name] [api-url]
set -euo pipefail

NAME="\${1:-$(whoami)}"
API="\${2:-\${LATTICE_API:-https://lattice-api-96cn.onrender.com}}"

KEY=$(curl -sf -X POST "$API/keys" \\
  -H 'Content-Type: application/json' \\
  -d "{\\"name\\": \\"$NAME\\"}" \\
  | python3 -c "import sys, json; print(json.load(sys.stdin)['api_key'])")

echo "export LATTICE_KEY=$KEY"
# shown once -- save it. Send as:  X-API-Key: $LATTICE_KEY`,
  "usage.py": `#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-96cn.onrender.com/parse \\\\
      -H 'Content-Type: application/json' \\\\
      -H "X-API-Key: $LATTICE_KEY" \\\\
      -d '{"address": "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"}'

Edit the three values below, then run:  python3 examples/usage.py
"""

import json
import urllib.request

URL = "https://lattice-api-96cn.onrender.com"
KEY = ""  # paste your ltk_... key here -- leave empty to mint a fresh one
ADDRESS = "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"


def post(path, body):
    req = urllib.request.Request(
        URL.rstrip("/") + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": KEY})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


if not KEY:  # shown once -- save it
    KEY = post("/keys", {"name": "usage-example"})["api_key"]
    print(f"minted key (save it): {KEY}\\n")

print(json.dumps(post("/parse", {"address": ADDRESS}), ensure_ascii=False, indent=2))`,
};
