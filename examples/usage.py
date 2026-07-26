#!/usr/bin/env python3
"""This curl, in Python (stdlib only -- nothing to install):

    curl -s -X POST https://lattice-api-96cn.onrender.com/parse \\
      -H 'Content-Type: application/json' \\
      -H "X-API-Key: $LATTICE_KEY" \\
      -d '{"address": "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"}'

Get a key first:  ./examples/createkey.sh
"""

import json
import urllib.request

URL: str = "https://lattice-api-96cn.onrender.com"
KEY = ""
ADDRESS = "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"

req = urllib.request.Request(
    URL.rstrip("/") + "/parse",
    data=json.dumps({"address": ADDRESS}).encode(),
    headers={"Content-Type": "application/json", "X-API-Key": KEY})
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.load(r), ensure_ascii=False, indent=2))
