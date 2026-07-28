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
API="\${2:-\${LATTICE_API:-https://lattice-api-fs5f.onrender.com}}"

KEY=$(curl -sf -X POST "$API/keys" \\
  -H 'Content-Type: application/json' \\
  -d "{\\"name\\": \\"$NAME\\"}" \\
  | python3 -c "import sys, json; print(json.load(sys.stdin)['api_key'])")

echo "export LATTICE_KEY=$KEY"
# shown once -- save it. Send as:  X-API-Key: $LATTICE_KEY`,
  "usage.py": `#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-fs5f.onrender.com/parse \\\\
      -H 'Content-Type: application/json' \\\\
      -H "X-API-Key: $LATTICE_KEY" \\\\
      -d '{"address": "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"}'

Get a key first:  ./examples/createkey.sh
"""

import json
import urllib.request

URL: str = "https://lattice-api-fs5f.onrender.com"
KEY = ""
ADDRESS = "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"

req = urllib.request.Request(
    URL.rstrip("/") + "/parse",
    data=json.dumps({"address": ADDRESS}).encode(),
    headers={"Content-Type": "application/json", "X-API-Key": KEY})
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r), ensure_ascii=False, indent=2))`,
  "stt.py": `#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-fs5f.onrender.com/stt/parse \\\\
      -H 'Content-Type: audio/wav' \\\\
      -H "X-API-Key: $LATTICE_KEY" \\\\
      --data-binary @spoken_address.wav

Speak an address; get the same JSON as /parse, plus \`transcript\` and
\`spoken_language\`.  Get a key first:  ./examples/createkey.sh
"""

import json
import urllib.request

URL = "https://lattice-api-fs5f.onrender.com"
KEY = ""
AUDIO = input("Audio file path (wav/mp3/ogg/webm): ").strip()

req = urllib.request.Request(
    URL.rstrip("/") + "/stt/parse",
    data=open(AUDIO, "rb").read(),
    headers={"Content-Type": "audio/" + AUDIO.rsplit(".", 1)[-1].lower(),
             "X-API-Key": KEY})
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r), ensure_ascii=False, indent=2))`,
};
