"""Layer 2 -- deliverability scoring.

Predicts, at order time, whether an address will cost the rider a phone call or
a failed attempt -- before dispatch, not at the doorstep.

Rule-based on purpose. An ops team will not action a black-box number; they need
to know WHICH field is missing, because the lever they actually control is the
checkout form. So every score comes with reasons and a single highest-value
prompt: the one question that would most reduce risk.
"""

import re

from . import pincode as pincode_dir

# Each rule: (key, penalty, human-readable reason)
# Penalties are additive risk, capped at 1.0.

_RURAL = re.compile(r"\b(village|vill|gram|po |p\.o|post office|dist |distt|tehsil|"
                    r"taluk|taluka|mandal|panchayat|block)\b", re.I)
_PLOT_ONLY = re.compile(r"\b(khasra|khewat|khata|survey no|s\.no|plot no)\b", re.I)


def score(p: dict) -> dict:
    """p is a ParsedAddress dict. Returns risk + reasons + the field to ask for."""
    raw = (p.get("raw") or "")
    reasons: list[str] = []
    risk = 0.0

    has_house = bool(p.get("house_number"))
    has_street = bool(p.get("street"))
    has_building = bool(p.get("building"))
    has_landmark = bool(p.get("landmarks"))
    has_locality = bool(p.get("locality"))
    has_pincode = bool(p.get("pincode"))
    has_city = bool(p.get("city"))

    # --- door-level identification ------------------------------------
    if not has_house:
        if has_building or has_landmark:
            risk += 0.28
            reasons.append("No house or flat number — rider must identify the door "
                           "from the building name or landmark alone.")
        else:
            risk += 0.42
            reasons.append("No house or flat number, and no building to fall back on.")

    if not has_street and not has_building:
        risk += 0.22
        reasons.append("Neither street nor building named — nothing to navigate to "
                       "below locality level.")

    # Landmark-only addressing: the classic Indian pattern, and the classic
    # reason a rider calls. It is navigable by a local, opaque to everyone else.
    if has_landmark and not has_house and not has_street:
        risk += 0.16
        reasons.append("Landmark-only address — resolvable by someone who already "
                       "knows the area, not by a first-time rider.")

    # --- coarse locatability ------------------------------------------
    if not has_locality:
        risk += 0.20
        reasons.append("No locality identified.")
    if not has_pincode:
        risk += 0.12
        reasons.append("No pincode — serviceability and routing cannot be confirmed.")
    if not has_city:
        risk += 0.10
        reasons.append("No city identified.")

    # --- pincode directory checks ---------------------------------------
    # Only for well-formed pins: _ask_for probes with "placeholder", which must
    # not trip a directory miss and distort the risk-reduction estimate.
    # A directory miss is not one more penalty to add up -- it is disqualifying.
    # The resolver already works this way (hard vetoes cap the score); the scorer
    # needs the mirror image, a FLOOR. An address whose pincode does not exist
    # cannot be sorted, however complete the rest of it looks: house number,
    # street and locality do not help a sorting machine that has no such bin.
    # Without this floor a fully-specified address on a fictional pin scored
    # 0.21 "low risk" while its own reasons said routing would fail.
    floor = 0.0
    if has_pincode and re.fullmatch(r"\d{6}", str(p["pincode"] or "")):
        v = pincode_dir.validate(p)
        if v.get("exists") is False:
            risk += 0.15
            floor = max(floor, 0.70)
            reasons.insert(0, f"Pincode {p['pincode']} does not exist in the postal "
                              "directory — routing will fail at sorting.")
        elif v.get("conflicts"):
            risk += 0.12
            floor = max(floor, 0.45)
            reasons.extend(v["conflicts"])

    # --- structural signals from the raw string ------------------------
    if _RURAL.search(raw):
        risk += 0.12
        reasons.append("Rural/administrative addressing (village, post office, "
                       "tehsil) — no street-level grid to route on.")
    if _PLOT_ONLY.search(raw):
        risk += 0.10
        reasons.append("Revenue-record identifiers (khasra/khewat/survey number) — "
                       "a land record, not a navigable address.")

    # Repeated segments signal a broken form submission or a copy-paste error.
    segs = [s.strip().lower() for s in re.split(r"[,\n]", raw) if len(s.strip()) > 3]
    if len(segs) != len(set(segs)):
        risk += 0.08
        reasons.append("Duplicated segments in the address — likely a form or "
                       "data-entry error.")

    if len(raw) < 30:
        risk += 0.10
        reasons.append("Very short address string.")

    # Vague-only landmark relations give direction but no distance.
    rels = {l.get("relation") for l in (p.get("landmarks") or [])}
    if rels and rels <= {"near", None}:
        risk += 0.06
        reasons.append('Landmark relation is only "near" — direction is '
                       "unspecified.")

    if p.get("error"):
        risk = 1.0
        reasons = ["Address could not be parsed."]

    risk = round(min(1.0, max(risk, floor)), 3)
    band = "high" if risk >= 0.55 else "medium" if risk >= 0.28 else "low"

    return {
        "risk": risk,
        "band": band,
        "will_likely_need_call": risk >= 0.55,
        "reasons": reasons,
        "ask_for": _ask_for(p, risk),
        "completeness": p.get("completeness", 0.0),
    }


# What to prompt the customer for, in order of how much risk it removes.
_ASK = [
    ("house_number", "House / flat / door number",
     "the single highest-value field — it is what identifies the door"),
    ("locality", "Locality or area name", "needed to route below city level"),
    ("street", "Street, road or cross", "gives the rider something to navigate to"),
    ("pincode", "Pincode", "confirms serviceability and routing"),
    ("landmarks", "A nearby landmark",
     "how the last 200 metres are actually navigated in India"),
    ("building", "Building or apartment name", "narrows the door within a street"),
]


def _pin_is_bad(p: dict) -> bool:
    """True when a well-formed pincode is not in the postal directory."""
    pin = str(p.get("pincode") or "")
    if not re.fullmatch(r"\d{6}", pin):
        return False
    return pincode_dir.validate(p).get("exists") is False


def _ask_for(p: dict, risk: float) -> dict | None:
    if risk < 0.28:
        return None
    for key, label, why in _ASK:
        present = bool(p.get(key))
        # A pincode that is present but absent from the directory is worse than
        # a missing one, and previously could never be asked for -- the loop
        # only ever offered fields that were blank.
        if key == "pincode" and present and _pin_is_bad(p):
            present = False
        if not present:
            # Estimate the gain by re-scoring with the field filled in.
            probe = dict(p)
            # landmarks must be a list of dicts -- score() reads l.get("relation")
            probe[key] = ([{"name": "placeholder", "relation": "near"}]
                          if key == "landmarks" else "placeholder")
            gain = round(risk - score(probe)["risk"], 3)
            if gain <= 0:
                continue
            return {"field": key, "label": label, "why": why, "risk_reduction": gain}
    return None


def score_batch(parsed: list[dict]) -> dict:
    scored = [score(p) for p in parsed]
    bands = {"low": 0, "medium": 0, "high": 0}
    for s in scored:
        bands[s["band"]] += 1
    n = len(scored) or 1
    return {
        "scored": scored,
        "bands": bands,
        "mean_risk": round(sum(s["risk"] for s in scored) / n, 3),
        "flagged_pct": round(100 * bands["high"] / n, 1),
    }
