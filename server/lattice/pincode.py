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

# The parser transliterates to Latin, but when a native-script value slips
# through, comparing it against the directory's Latin names is meaningless.
# Rule: an unreadable value is UNVERIFIABLE (None), never a conflict.
# For common state/city names we can do better and actively confirm:
_NATIVE_PLACE = {
    # states -- own script and Hindi
    "தமிழ்நாடு": "tamil nadu", "தமிழ் நாடு": "tamil nadu", "तमिलनाडु": "tamil nadu",
    "महाराष्ट्र": "maharashtra", "कर्नाटक": "karnataka", "ಕರ್ನಾಟಕ": "karnataka",
    "केरल": "kerala", "കേരളം": "kerala", "കേരള": "kerala",
    "आंध्र प्रदेश": "andhra pradesh", "ఆంధ్రప్రదేశ్": "andhra pradesh",
    "तेलंगाना": "telangana", "తెలంగాణ": "telangana",
    "पश्चिम बंगाल": "west bengal", "পশ্চিমবঙ্গ": "west bengal",
    "गुजरात": "gujarat", "ગુજરાત": "gujarat", "राजस्थान": "rajasthan",
    "पंजाब": "punjab", "ਪੰਜਾਬ": "punjab", "उत्तर प्रदेश": "uttar pradesh",
    "मध्य प्रदेश": "madhya pradesh", "बिहार": "bihar",
    "ओडिशा": "odisha", "ଓଡ଼ିଶା": "odisha", "असम": "assam", "অসম": "assam",
    "हरियाणा": "haryana", "झारखंड": "jharkhand", "छत्तीसगढ़": "chhattisgarh",
    "उत्तराखंड": "uttarakhand", "हिमाचल प्रदेश": "himachal pradesh",
    "दिल्ली": "delhi", "தில்லி": "delhi", "डेल्ही": "delhi",
    # major cities
    "மதுரை": "madurai", "சென்னை": "chennai", "கோயம்புத்தூர்": "coimbatore",
    "मुंबई": "mumbai", "पुणे": "pune", "पुण्यात": "pune", "नागपूर": "nagpur",
    "कोलकाता": "kolkata", "কলকাতা": "kolkata", "बेंगलुरु": "bengaluru",
    "ಬೆಂಗಳೂರು": "bengaluru", "हैदराबाद": "hyderabad", "హైదరాబాద్": "hyderabad",
    "लखनऊ": "lucknow", "जयपुर": "jaipur", "अहमदाबाद": "ahmedabad",
    "અમદાવાદ": "ahmedabad", "इंदौर": "indore", "भोपाल": "bhopal",
}

_HAS_LATIN = re.compile(r"[A-Za-z]")


def _comparable(name: str | None) -> str | None:
    """Latin form of a value if we can compare it against the directory:
    the value itself when it contains Latin letters, a known alias when it
    is a recognised native-script name, else None (unverifiable)."""
    if not name:
        return None
    n = str(name).strip()
    if _HAS_LATIN.search(n):
        return n
    return _NATIVE_PLACE.get(n)


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
        s = _comparable(state)
        # unreadable script -> None (unverifiable), never a conflict
        out["state_consistent"] = _name_match(s, [entry["state"]]) if s else None
        if out["state_consistent"] is False:
            out["conflicts"].append(
                f"Pincode {pin} is in {entry['state']}, address says {state}.")
    else:
        out["inferred"]["state"] = entry["state"]

    if city:
        c = _comparable(city)
        # A city matches if it names the district or any served area.
        out["city_consistent"] = (
            _name_match(c, [entry["district"], *entry["areas"]]) if c else None)
        if out["city_consistent"] is False:
            out["conflicts"].append(
                f"Pincode {pin} belongs to {entry['district']} district "
                f"({entry['state']}), address says {city}.")
    else:
        out["inferred"]["district"] = entry["district"]

    if locality:
        loc = _comparable(locality)
        out["locality_listed"] = _name_match(loc, entry["areas"]) if loc else None
        # not a conflict when False -- the directory lists post offices, not
        # every colloquial locality name; absence is weak evidence

    return out
