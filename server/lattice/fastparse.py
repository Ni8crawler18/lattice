"""Deterministic fast path for Indian addresses -- no reasoning model in the loop.

WHY THIS EXISTS
Sarvam's chat models are reasoning models: measured, `sarvam-105b` spends ~4000
characters of hidden chain-of-thought answering "what is the capital of Bhutan"
(17.7s), and ~1500 completion tokens on a single address parse (20-50s). That
cost is unconditional -- no prompt, temperature or max_tokens avoids it, and
truncating mid-thought returns EMPTY content, which is the intermittent parse
failure we chased for hours.

But most of an Indian address does not need reasoning. A pincode is a regex. A
district is a lookup in the 19,238-entry postal directory we already ship. A
landmark relation is a keyword from a table we already maintain in six
languages. Those are decidable in microseconds.

So: rules first, LLM only for what rules genuinely cannot decide. Sarvam's FAST
models stay in the loop where they are irreplaceable -- script detection and
transliteration for non-Latin input (measured 1.11s and 0.53s, because they are
not reasoning models).

`rule_parse()` returns (fields, confidence). The caller escalates to the LLM
when confidence is low, so accuracy degrades to the old behaviour rather than
to garbage.
"""

from __future__ import annotations

import re

from .parser import _REL_LOOKUP

# --- component vocabularies ------------------------------------------------

_BUILDING_WORDS = (
    "complex", "towers", "tower", "apartments", "apartment", "apts", "flats",
    "bhavan", "bhawan", "building", "bldg", "chambers", "plaza", "arcade",
    "residency", "heights", "enclave", "mansion", "chawl", "niwas", "sadan",
    "house", "villa", "court", "centre", "center", "mall",
)

_STREET_WORDS = (
    "road", "rd", "street", "st", "main", "cross", "gali", "galli", "marg",
    "lane", "path", "avenue", "highway", "nh", "bypass", "chowk", "circle",
)

_SUBLOCALITY_WORDS = (
    "sector", "stage", "phase", "block", "layout", "extension", "extn",
)

# "3-116", "12B", "#45", "No.7", "Flat 9C", "H.No 45", "Plot 22", "2/76-F"
_HOUSE_RE = re.compile(
    r"(?:flat|door|house|h\.?\s*no|plot|shop|room|unit|no|#)\s*\.?\s*(?P<a>[a-z]?[-\d][\w\-/]*)"
    r"|(?P<b>\d+[-/]\d+[\w\-/]*)"
    r"|\b(?P<c>\d{1,4}[a-z]?)(?=\s*,)",
    re.I,
)
_FLOOR_RE = re.compile(
    r"\b((?:ground|first|second|third|fourth|fifth|top|\d+(?:st|nd|rd|th))\s*floor|g\.?f\.?|gf)\b",
    re.I,
)
_PIN_RE = re.compile(r"\b(\d{6})\b")
_PIN_SPACED_RE = re.compile(r"\b(\d{3})\s+(\d{3})\b")
_PO_RE = re.compile(r"\b(?:p\.?\s*o\.?|post\s+office)\s*[-:]?\s*([A-Za-z][\w\s]{1,28}?)(?=[,\-]|$)", re.I)
_DIST_RE = re.compile(r"\b(?:district|distt|dist|zilla)\s*\.?\s*[-:]?\s*([A-Za-z][\w\s]{1,28}?)(?=[,\-]|$)", re.I)
_VILLAGE_RE = re.compile(r"(?:^|[,\s])(?:village|vill|gram)\s*\.?\s*[-:]?\s*([A-Za-z][\w\s]{1,28}?)(?=[,\-]|$)", re.I)
# "BUDDARAM VILLAGE" — name precedes the word
_VILLAGE_SUFFIX_RE = re.compile(r"([A-Za-z][\w\s]{1,28}?)\s+(?:village|gram)\b", re.I)

# Longest relation keywords first so "ke paas" wins over "paas".
_RELATION_KEYS = sorted(_REL_LOOKUP, key=len, reverse=True)

_TITLE_SKIP = {"of", "the", "and", "no", "nr"}

# A state is not a locality. Trailing bare "PIN" is a placeholder, not data.
_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "chattisgarh", "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand",
    "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "orissa", "punjab",
    "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura", "uttarakhand",
    "uttar pradesh", "west bengal", "delhi", "new delhi", "jammu and kashmir",
    "ladakh", "puducherry", "chandigarh", "a.p.", "u.p.", "m.p.",
}


def _clean_seg(seg: str) -> str:
    seg = re.sub(r"\bPIN\b\.?\s*$", "", seg, flags=re.I)
    return seg.strip(" .,-")


def _title(s: str) -> str:
    """Title-case without mangling ALL-CAPS acronyms or door numbers."""
    out = []
    for w in s.split():
        if len(w) <= 3 and w.isupper():          # SBI, KV, NH
            out.append(w)
        elif any(ch.isdigit() for ch in w):      # 3-116, 19B
            out.append(w.upper() if len(w) <= 4 else w)
        elif w.lower() in _TITLE_SKIP and out:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


_GLUED_PIN = re.compile(r"([A-Za-z])(\d{6})\b")


def _segments(text: str) -> list[str]:
    text = _GLUED_PIN.sub(r"\1, \2", text)
    return [s.strip(" .-") for s in re.split(r"[,\n;]+", text) if s.strip(" .-")]


def _find_landmarks(segs: list[str]) -> tuple[list[dict], set[int]]:
    """A segment containing a relation keyword is a landmark reference."""
    found, used = [], set()
    for i, seg in enumerate(segs):
        low = seg.lower()
        for kw in _RELATION_KEYS:
            if kw in low:
                name = re.sub(re.escape(kw), " ", low, flags=re.I)
                name = re.sub(r"\s+", " ", name).strip(" .,-")
                if len(name) >= 3:
                    found.append({"name": _title(name), "relation": _REL_LOOKUP[kw]})
                    used.add(i)
                break
    return found, used


def rule_parse(text: str, pincode_lookup=None) -> tuple[dict, float]:
    """Extract components with rules only. Returns (fields, confidence 0-1)."""
    fields: dict = {}
    segs = _segments(text)
    used: set[int] = set()

    # --- pincode (and the free city/district/state it unlocks) ----------
    text = _GLUED_PIN.sub(r"\1 \2", text)
    m = _PIN_RE.search(text) or _PIN_SPACED_RE.search(text.replace("  ", " "))
    if m:
        pin = "".join(m.groups()) if m.re is _PIN_SPACED_RE else m.group(1)
        if len(pin) == 6:
            fields["pincode"] = pin
            if pincode_lookup:
                entry = pincode_lookup(pin)
                if entry:
                    fields.setdefault("district", entry.get("district"))
                    fields.setdefault("state", entry.get("state"))

    # --- explicit administrative markers --------------------------------
    for rx, key in ((_PO_RE, "post_office"), (_DIST_RE, "district"),
                    (_VILLAGE_RE, "locality"), (_VILLAGE_SUFFIX_RE, "locality")):
        mm = rx.search(text)
        if mm:
            val = _title(mm.group(1).strip())
            if val and len(val) > 1:
                fields[key] = val

    # --- landmarks (before other segment classification) ----------------
    lms, lm_idx = _find_landmarks(segs)
    if lms:
        fields["landmarks"] = lms
    used |= lm_idx

    # --- floor / house number -------------------------------------------
    fm = _FLOOR_RE.search(text)
    if fm:
        fields["floor"] = _title(fm.group(1))
    hm = _HOUSE_RE.search(text)
    if hm:
        val = next((g for g in hm.groups() if g), None)
        if val and not (len(val) == 6 and val.isdigit()):
            fields["house_number"] = val.upper().strip(".")

    # --- building / street / sublocality by suffix ----------------------
    for i, seg in enumerate(segs):
        if i in used:
            continue
        low = seg.lower()
        words = set(re.findall(r"[a-z]+", low))
        if "building" not in fields and words & set(_BUILDING_WORDS):
            fields["building"] = _title(seg); used.add(i)
        elif "street" not in fields and words & set(_STREET_WORDS):
            fields["street"] = _title(seg); used.add(i)
        elif "sublocality" not in fields and words & set(_SUBLOCALITY_WORDS):
            fields["sublocality"] = _title(seg); used.add(i)

    # --- locality: the last unclaimed alphabetic segment ----------------
    if "locality" not in fields:
        for i in range(len(segs) - 1, -1, -1):
            if i in used:
                continue
            seg = _clean_seg(re.sub(r"\b\d{6}\b", "", segs[i]))
            if seg.lower() in _STATES:
                fields.setdefault("state", _title(seg)); used.add(i); continue
            if len(seg) >= 3 and re.search(r"[A-Za-z]{3}", seg) and not seg.isdigit():
                fields["locality"] = _title(seg)
                used.add(i)
                break

    # --- confidence -----------------------------------------------------
    # Door-level evidence is what the resolver actually scores on, so weight it.
    score = 0.0
    if fields.get("pincode"):     score += 0.25
    if fields.get("locality"):    score += 0.25
    if fields.get("house_number"): score += 0.20
    if fields.get("building"):    score += 0.15
    if fields.get("street"):      score += 0.15
    if fields.get("landmarks"):   score += 0.10
    if fields.get("district") or fields.get("state"): score += 0.05

    return {k: v for k, v in fields.items() if v}, min(1.0, round(score, 3))
