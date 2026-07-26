#!/usr/bin/env python3
"""Lattice API in ~50 lines -- stdlib only, nothing to install.

    python3 examples/usage.py            # runs against the deployed API

    export LATTICE_API=<url>             # optional: point at another instance
    export LATTICE_KEY=ltk_...           # optional: mints one if absent

Covers the three questions Lattice answers:
  1. what does this address say?          POST /parse
  2. are these two the same door?         POST /compare
  3. dedupe a whole file, async           POST /jobs/csv -> poll -> results
"""

import json
import os
import time
import urllib.request

API = os.environ.get("LATTICE_API", "https://lattice-api-96cn.onrender.com").rstrip("/")
KEY = os.environ.get("LATTICE_KEY", "")


def call(path, body=None, raw=None):
    """POST json/raw text (or GET when neither), with the API key header."""
    data = raw.encode() if raw is not None else (
        json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data)
    req.add_header("X-API-Key", KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


if not KEY:  # self-service: mint a key on first run (shown once -- save it)
    KEY = call("/keys", {"name": "usage-example"})["api_key"]
    print(f"minted key (save it):  export LATTICE_KEY={KEY}\n")

# 1. one messy, multi-script address -> structured components + risk
p = call("/parse", {"address": "गणेश मंदिराच्या मागे, निळा गेट, कोथरूड, पुणे ४११०३८"})
print("parse:   locality:", p["locality"], "· pincode:", p["pincode"],
      "· risk:", p["deliverability"]["band"])
if p["deliverability"]["ask_for"]:
    print("         ask the customer for:", p["deliverability"]["ask_for"]["label"])

# 2. two strings, written nothing alike -- same door?
r = call("/compare", {
    "a": "Ganesh mandir ke peeche, blue gate wala ghar, Kothrud, Pune 411038",
    "b": "Blue gate house, behind Ganesh Temple, Kothrood, Pune - 411 038",
})["result"]
print("compare: verdict:", r["verdict"], "· score:", r["score"])

# 3. a whole file: CSV in (any column named like an address), CSV/JSON out
csv_text = "order_id,address\n" + "\n".join(
    f'{i},"{a}"' for i, a in enumerate([
        "MADHAVLEELA COMPLEX, 1ST FLOOR, MASKASATH SQUARE, ITWARI",
        "1ST FLOOR, MADHAVLEELA COMPLEX, MASKASATH SQUARE, ITWARI NAGPUR",
        "ICICI BANK LTD., 19B BROAD STREET, KOLKATA, WEST BENGAL.",
    ]))
job = call("/jobs/csv?label=usage-example", raw=csv_text)
while call(f"/jobs/{job['id']}")["status"] not in ("done", "failed"):
    time.sleep(1)
res = call(f"/jobs/{job['id']}/results")
s = res["summary"]
print(f"job:     {s['addresses']} addresses -> {s['unique_locations']} unique "
      f"locations ({s['duplicates_collapsed']} duplicates collapsed)")
print(f"         csv download: {API}/jobs/{job['id']}/results?format=csv&key=<your-key>")
