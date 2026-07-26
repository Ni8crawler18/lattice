#!/usr/bin/env python3
"""Lattice API, full surface -- stdlib only, nothing to install.

    python3 examples/usage.py            # edit MESSAGE below, then run

    export LATTICE_API=<url>             # optional: point at another instance
    export LATTICE_KEY=ltk_...           # optional: mints one if absent

Your address goes in; every layer reports back:
  parse       POST /parse                components + risk + pincode check + DIGIPIN
  directory   GET  /pincode/{pin}        offline postal-directory lookup
  resolve     POST /compare              are two strings the same door?
  dedupe      POST /batch                cluster a list + golden records
  match       POST /match, GET /corpus   incoming address vs reference corpus
  digipin     POST /digipin/*            text->code, encode/decode, neighbors, group
  jobs        POST /jobs/csv             async CSV in -> poll -> results
Spoken input: examples/stt.py posts YOUR audio recording to /stt/parse.
"""

import json
import os
import time
import urllib.request

API = os.environ.get("LATTICE_API", "https://lattice-api-96cn.onrender.com").rstrip("/")
KEY = os.environ.get("LATTICE_KEY", "")

# ---- put YOUR address in this string, then run -----------------------------
MESSAGE = "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"


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

# ----------------------------------------------------------------- 1. parse
# One message -> structured components, deliverability risk, pincode check,
# and (when the geocoder resolves it) location + DIGIPIN.
p = call("/parse", {"address": MESSAGE})
print("PARSE      ", MESSAGE)
print("  components ", {k: p[k] for k in
      ("house_number", "building", "street", "locality", "city", "state", "pincode")
      if p.get(k)})
print("  landmarks  ", [(l["name"], l["relation"]) for l in p.get("landmarks") or []])
print("  descriptor ", p.get("visual_descriptor"), "· script:", p.get("script_code"))
d = p["deliverability"]
print("  risk       ", d["risk"], f"({d['band']})",
      "· ask for:", (d.get("ask_for") or {}).get("label"))
pc = p.get("pincode_check") or {}
print("  pin check  ", "exists:", pc.get("exists"),
      "· conflicts:", pc.get("conflicts") or "none",
      "· directory:", (pc.get("directory") or {}).get("district"))
if p.get("digipin"):
    print("  digipin    ", p["digipin"], f"(geocoded, {p.get('digipin_at_precision')})")
else:
    print("  digipin    ", "-- geocoder had no fix; text->DIGIPIN needs one")

# ------------------------------------------------------- 2. pincode directory
pin = p.get("pincode") or "411038"
e = call(f"/pincode/{pin}")
print("PINCODE    ", pin, "->", e.get("district"), e.get("state"),
      "· serves:", ", ".join(e.get("areas", [])[:3]), "...")

# ----------------------------------------------------------------- 3. compare
# Fixed demo pair: the same door written in two different alphabets.
r = call("/compare", {
    "a": "Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038",
    "b": "Blue gate house, behind Ganesh Temple, nr SBI ATM, Kothrood, Pune - 411 038",
})["result"]
print("COMPARE     verdict:", r["verdict"], "· score:", r["score"],
      "· matched landmarks:", r["matched_landmarks"])

# ------------------------------------------------------------------ 4. batch
# Demo list: the same door three ways + one unrelated record
# -> cluster ids + one merged "golden record" per cluster.
b = call("/batch", {"addresses": [
    "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८",
    "Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038",
    "Blue gate house, behind Ganesh Temple, Kothrood, Pune - 411 038",
    "ICICI BANK LTD., 19B BROAD STREET, KOLKATA, WEST BENGAL.",
]})
print("BATCH       clusters:", b["clusters"], "->", b["unique_locations"], "unique",
      f"({b['duplicates_collapsed']} duplicates collapsed)")
for g in b["golden_records"]:
    if len(g["members"]) > 1:
        print("  golden     ", g["canonical_text"])
        print("             members:", g["members"],
              "· contested:", g["contested_fields"] or "none")

# ------------------------------------------------------------------ 5. match
# Does this message match anything in the reference corpus (Razorpay IFSC)?
m = call("/match", {"address": "MADHAVLEELA COMPLEX, MASKASATH SQUARE, ITWARI NAGPUR",
                    "top_k": 1})
top = (m.get("matches") or [{}])[0]
print("MATCH       corpus of", m.get("corpus"), "records · top:",
      top.get("verdict"), top.get("score"), "·", (top.get("raw") or "")[:60])

# ---------------------------------------------------------------- 6. digipin
# Text -> DIGIPIN via the geocoder bridge (honest about precision):
fa = call("/digipin/from-address", {"address": "India Gate, New Delhi 110001"})
geo = fa.get("geocoder") or {}
print("DIGIPIN     from-address:", fa.get("digipin"),
      f"({geo.get('precision')}, {geo.get('source', '')})")
# Pure grid arithmetic -- no geocoder involved:
code = call("/digipin/encode", {"latitude": 28.6139, "longitude": 77.209})["digipin"]
back = call("/digipin/decode", {"digipin": code})
print("  encode     (28.6139, 77.209) ->", code,
      "-> decode:", (back["latitude"], back["longitude"]))
n = call("/digipin/neighbors", {"digipin": code[:7]})  # 6 symbols ~ 1 km cell
print("  neighbors  of", n["cell"], f"({n['cell_size_approx']}):",
      {x["direction"]: x["digipin"] for x in n["neighbors"][:4]}, "...")
grp = call("/digipin/group", {"level": 6, "points": [
    {"id": "ord-1", "digipin": "4FP-4CK-6L24"},
    {"id": "ord-2", "digipin": "4FP-4CK-645F"},
    {"id": "ord-3", "latitude": 12.9166, "longitude": 77.6101},
]})
print("  group      level 6 (~1 km):",
      [(g["cell"], [mm["id"] for mm in g["members"]]) for g in grp["groups"]])

# ------------------------------------------------------------------- 7. jobs
# A whole file, async: CSV in (any column named like an address), poll, results.
csv_text = "order_id,address\n" + "\n".join(
    f'{i},"{a}"' for i, a in enumerate([
        "MADHAVLEELA COMPLEX, 1ST FLOOR, MASKASATH SQUARE, ITWARI",
        "1ST FLOOR, MADHAVLEELA COMPLEX, MASKASATH SQUARE, ITWARI NAGPUR",
        "ICICI BANK LTD., 19B BROAD STREET, KOLKATA, WEST BENGAL.",
    ]))
job = call("/jobs/csv?label=usage-example", raw=csv_text)
while call(f"/jobs/{job['id']}")["status"] not in ("done", "failed"):
    time.sleep(1)
s = call(f"/jobs/{job['id']}/results")["summary"]
print(f"JOB         {s['addresses']} addresses -> {s['unique_locations']} unique "
      f"({s['duplicates_collapsed']} duplicates collapsed) "
      f"· bands: {s['bands']}")
print(f"  csv        {API}/jobs/{job['id']}/results?format=csv&key=<your-key>")
