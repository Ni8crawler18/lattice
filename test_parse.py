#!/usr/bin/env python3
"""Test the Lattice /parse API. Stdlib only — no pip installs needed.

Usage:
    python3 test_parse.py "any unstructured address, any language"
    python3 test_parse.py            # uses the sample MESSAGE below

Change API_KEY to your own (mint one with ./create_key.sh).
"""

import json
import sys
import urllib.request

# ---- edit these two lines ------------------------------------------------
API_KEY = "ltk_f802c48e4749537e4a3eb752c576fe10"
BASE = "https://lattice-api-96cn.onrender.com"      # or http://127.0.0.1:8077
# --------------------------------------------------------------------------

MESSAGE = "गणेश मंदिराच्या मागे, निळा गेट, कोथरूड, पुणे ४११०३८"


def parse(message: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/parse",
        data=json.dumps({"address": message}).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_status": e.code, **json.loads(e.read() or b"{}")}


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) or MESSAGE
    result = parse(message)
    print(json.dumps(result, indent=2, ensure_ascii=False))
