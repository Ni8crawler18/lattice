"""Build the offline pincode directory: data/pincode_dir.json.gz

Source: GeoNames postal-code dump for India (CC-BY 4.0)
        https://download.geonames.org/export/zip/IN.zip  ->  IN.txt

One entry per pincode: state, district, the post-office/area names it serves,
and a lat/lon. CAVEAT: GeoNames India coordinates are district-level centroids
(every office in a pincode carries the same point), so the lat/lon locates a
DISTRICT, not the pincode. Kept in the file for possible future use; the
validation layer deliberately does not expose it.

Regenerate:
    curl -L -o /tmp/IN.zip https://download.geonames.org/export/zip/IN.zip
    unzip -o /tmp/IN.zip -d /tmp
    env/bin/python3 data/pincodes.py /tmp/IN.txt
"""

import gzip
import json
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pincode_dir.json.gz")

MAX_AREAS = 40  # a handful of pincodes serve 100+ villages; cap for size


def build(in_txt: str) -> dict:
    pins: dict[str, dict] = {}
    with open(in_txt, encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 11:
                continue
            pincode, place, state, district = f[1].strip(), f[2].strip(), f[3].strip(), f[5].strip()
            if len(pincode) != 6 or not pincode.isdigit():
                continue
            try:
                lat, lon = float(f[9]), float(f[10])
            except ValueError:
                lat = lon = None
            e = pins.setdefault(pincode, {"state": state, "district": district,
                                          "areas": [], "_lats": [], "_lons": []})
            if place and place not in e["areas"] and len(e["areas"]) < MAX_AREAS:
                e["areas"].append(place)
            if lat is not None:
                e["_lats"].append(lat)
                e["_lons"].append(lon)

    for e in pins.values():
        if e["_lats"]:
            e["lat"] = round(sum(e["_lats"]) / len(e["_lats"]), 4)
            e["lon"] = round(sum(e["_lons"]) / len(e["_lons"]), 4)
        del e["_lats"], e["_lons"]
    return pins


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 data/pincodes.py <path-to-IN.txt>")
    pins = build(sys.argv[1])
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(pins, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(pins)} pincodes -> {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
