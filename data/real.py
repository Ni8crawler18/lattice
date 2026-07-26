"""Real Indian addresses from Razorpay's open IFSC dataset.

Source: https://github.com/razorpay/ifsc  (releases -> IFSC.csv)

Two things this gives us that a hand-built seed set cannot:

1. Genuinely messy real-world addresses -- ALL-CAPS, no spaces after commas,
   inconsistent component order, landmark abbreviations, embedded phone numbers.

2. Ground truth for entity resolution that we did not author. MICR codes are
   assigned per physical branch, so two records sharing a MICR but carrying
   different IFSC codes are the SAME BUILDING described twice -- usually the
   residue of a bank merger (Dena/Vijaya -> BoB, Andhra/Corporation -> Union).
   Nobody wrote those pairs to be similar. They just are.
"""

import csv
import os
import random
import re

CSV_PATH = os.environ.get("IFSC_CSV", "/tmp/claude-1000/-home-ni8crawler-Data-research-work-lattice/2a7c11ed-211b-4871-900d-15f0725ce44c/scratchpad/IFSC.csv")

_PHONE = re.compile(r"\b(?:\+?91[-\s]?)?\d{6,12}\b")
_WS = re.compile(r"\s+")


def clean(addr: str) -> str:
    """Light touch only -- we want the mess, just not the phone numbers."""
    a = addr.strip().strip('"')
    a = _PHONE.sub("", a)
    a = a.replace(",", ", ")
    a = _WS.sub(" ", a).strip(" ,-")
    return a


def _usable(row) -> bool:
    a = row.get("ADDRESS") or ""
    if len(a) < 35 or len(a) > 240:
        return False
    # want addresses with real structure, not "MUMBAI"
    return a.count(",") >= 3


def load(limit=None):
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            if _usable(row):
                rows.append(row)
                if limit and len(rows) >= limit:
                    break
    return rows


def sample(n=25, seed=7):
    """Diverse real addresses -- one per district, spread across states."""
    rows = load()
    rnd = random.Random(seed)
    rnd.shuffle(rows)
    seen_district, out = set(), []
    for r in rows:
        key = (r.get("STATE"), r.get("DISTRICT"))
        if key in seen_district:
            continue
        seen_district.add(key)
        out.append({
            "id": r["IFSC"],
            "raw": clean(r["ADDRESS"]),
            "city": (r.get("CITY") or "").title(),
            "state": (r.get("STATE") or "").title(),
            "bank": r.get("BANK") or "",
        })
        if len(out) >= n:
            break
    return out


def micr_pairs(n=15, seed=7):
    """Same physical branch, two records -- ground truth we did not author.

    Same MICR + same district, different IFSC, and the address TEXT differs.
    """
    rows = load()
    by_micr: dict[str, list] = {}
    for r in rows:
        micr = (r.get("MICR") or "").strip()
        if micr and micr != "0" and len(micr) >= 6:
            by_micr.setdefault(micr, []).append(r)

    pairs = []
    for micr, group in by_micr.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a["IFSC"] == b["IFSC"]:
                    continue
                if a.get("DISTRICT") != b.get("DISTRICT"):
                    continue
                ta, tb = clean(a["ADDRESS"]), clean(b["ADDRESS"])
                if ta.lower() == tb.lower():
                    continue          # identical text is a trivial match
                pairs.append({
                    "micr": micr,
                    "a": {"id": a["IFSC"], "raw": ta, "bank": a.get("BANK", "")},
                    "b": {"id": b["IFSC"], "raw": tb, "bank": b.get("BANK", "")},
                })
                break
            if len(pairs) >= n * 4:
                break
        if len(pairs) >= n * 4:
            break

    rnd = random.Random(seed)
    rnd.shuffle(pairs)
    return pairs[:n]


def negative_pairs(n=15, seed=11):
    """Hard negatives: same district and pincode, different physical branch."""
    rows = load()
    rnd = random.Random(seed)
    by_dist: dict[tuple, list] = {}
    for r in rows:
        micr = (r.get("MICR") or "").strip()
        by_dist.setdefault((r.get("STATE"), r.get("DISTRICT")), []).append((micr, r))

    out = []
    keys = list(by_dist)
    rnd.shuffle(keys)
    for k in keys:
        group = by_dist[k]
        if len(group) < 2:
            continue
        rnd.shuffle(group)
        for i in range(len(group) - 1):
            (m1, r1), (m2, r2) = group[i], group[i + 1]
            if m1 and m2 and m1 == m2:
                continue                      # same branch -- not a negative
            out.append({
                "a": {"id": r1["IFSC"], "raw": clean(r1["ADDRESS"]), "bank": r1.get("BANK", "")},
                "b": {"id": r2["IFSC"], "raw": clean(r2["ADDRESS"]), "bank": r2.get("BANK", "")},
            })
            break
        if len(out) >= n:
            break
    return out[:n]
