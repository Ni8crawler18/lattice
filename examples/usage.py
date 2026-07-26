#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-96cn.onrender.com/parse \\
      -H 'Content-Type: application/json' \\
      -H "X-API-Key: $LATTICE_KEY" \\
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
    print(f"minted key (save it): {KEY}\n")

print(json.dumps(post("/parse", {"address": ADDRESS}), ensure_ascii=False, indent=2))
