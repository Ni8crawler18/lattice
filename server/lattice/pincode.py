"""Pincode directory validation.

Answers three questions about a parsed address, from open data, offline:
  1. Does the pincode exist?
  2. Is it consistent with the stated city/state/locality?
  3. If city/state are absent, what does the directory say they are?

The inference in (3) is a LOOKUP, not a guess -- so it does not violate the
parser's "never invent a city" rule. It is labelled as inferred and kept out
of the parsed fields themselves.

Directory: data/pincode_dir.json.gz, built by data/pincodes.py from the
GeoNames India postal dump (CC-BY 4.0). ~19k pincodes: state, district,
served areas, centroid. The centroid is COARSE (a pincode spans kilometres);
it locates a *region*, never a door.
"""

import gzip
import json
import os
import re
from functools import lru_cache

from .resolver import _ratio

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "data", "pincode_dir.json.gz")

_SIX_DIGITS = re.compile(r"^\d{6}$")

# GeoNames district names sometimes lag city renamings; accept both directions.
_CITY_EQUIV = {
    "bengaluru": "bangalore", "mumbai": "bombay", "kolkata": "calcutta",
    "chennai": "madras", "prayagraj": "allahabad", "vadodara": "baroda",
}


@lru_cache(maxsize=1)
def _directory() -> dict:
    try:
        with gzip.open(_DIR, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def available() -> bool:
    return bool(_directory())


def lookup(pincode: str | None) -> dict | None:
    """Directory entry for a pincode, or None."""
    if not pincode or not _SIX_DIGITS.match(str(pincode)):
        return None
    return _directory().get(str(pincode))


def _name_match(name: str | None, candidates: list[str]) -> bool:
    """Lenient: 'Bengaluru' should match district 'Bengaluru Urban',
    'Mumbai' should match 'Mumbai Suburban'."""
    if not name:
        return False
    low = name.lower()
    variants = {low, _CITY_EQUIV.get(low, low)}
    for cand in candidates:
        cl = (cand or "").lower()
        for v in variants:
            if v in cl or cl in v or _ratio(v, cl) >= 0.80:
                return True
    return False


def validate(parsed: dict) -> dict:
    """Check a ParsedAddress dict against the directory.

    Returns {available, exists, ...checks, inferred, conflicts}. Every check is
    None when unobservable (field absent on either side), True/False otherwise.
    """
    if not available():
        return {"available": False}

    pin = parsed.get("pincode")
    out: dict = {"available": True, "pincode": pin, "exists": None,
                 "state_consistent": None, "city_consistent": None,
                 "locality_listed": None, "inferred": {}, "conflicts": []}
    if not pin or not _SIX_DIGITS.match(str(pin)):
        return out

    entry = lookup(pin)
    out["exists"] = entry is not None
    if entry is None:
        out["conflicts"].append(f"Pincode {pin} is not in the postal directory.")
        return out

    # NOTE: the directory file carries lat/lon, but GeoNames India coordinates
    # are district-level centroids (every office in a pincode shares one point).
    # Deliberately NOT exposed here -- calling that a "pincode location" would
    # be exactly the confident-but-wrong output this product exists to prevent.
    out["directory"] = {"state": entry["state"], "district": entry["district"],
                        "areas": entry["areas"][:8]}

    state, city, locality = parsed.get("state"), parsed.get("city"), parsed.get("locality")

    if state:
        out["state_consistent"] = _name_match(state, [entry["state"]])
        if out["state_consistent"] is False:
            out["conflicts"].append(
                f"Pincode {pin} is in {entry['state']}, address says {state}.")
    else:
        out["inferred"]["state"] = entry["state"]

    if city:
        # A city matches if it names the district or any served area.
        out["city_consistent"] = _name_match(city, [entry["district"], *entry["areas"]])
        if out["city_consistent"] is False:
            out["conflicts"].append(
                f"Pincode {pin} belongs to {entry['district']} district "
                f"({entry['state']}), address says {city}.")
    else:
        out["inferred"]["district"] = entry["district"]

    if locality:
        out["locality_listed"] = _name_match(locality, entry["areas"])
        # not a conflict when False -- the directory lists post offices, not
        # every colloquial locality name; absence is weak evidence

    return out
