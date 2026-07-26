"""Layer 1 -- entity resolution. Do two address strings mean the same door?

This is the question Google's Address Validation API does not answer. It
validates one address in isolation; it will not tell you that six records in
your CRM are one physical house.

No external fuzzy-match dependency: difflib is stdlib and good enough at this
scale, and one less thing to break on Render at 3am.
"""

import re
from difflib import SequenceMatcher

# Generic nouns that carry no discriminating signal once the entity is known.
_GENERIC = {
    "mandir", "temple", "masjid", "mosque", "church", "gurudwara", "atm",
    "store", "stores", "supermarket", "market", "hotel", "bank", "hospital",
    "clinic", "school", "college", "metro", "station", "road", "rd", "street",
    "st", "main", "cross", "gali", "lane", "nagar", "layout", "stage", "phase",
    "sector", "block", "apartments", "apartment", "apts", "flats", "chawl",
    "society", "complex", "the", "of", "near", "opp", "opposite", "behind",
}

# Landmark aliases that mean the same institution.
_ALIASES = {
    "sbi": "statebankofindia",
    "statebank": "statebankofindia",
    "statebankofindia": "statebankofindia",
    "hdfc": "hdfcbank",
    "icici": "icicibank",
    "reliancefresh": "reliancefresh",
    "reliancesmart": "reliancefresh",
    "dmart": "dmart",
    "moreretail": "more",
}


def _tokens(s: str | None) -> set[str]:
    if not s:
        return set()
    parts = re.split(r"[^a-z0-9]+", s.lower())
    return {p for p in parts if p and p not in _GENERIC}


def _canon(s: str | None) -> str:
    """Collapse to a comparable key: lowercase, drop generics and punctuation."""
    toks = sorted(_tokens(s))
    key = "".join(toks)
    return _ALIASES.get(key, key)


def _ratio(a: str | None, b: str | None) -> float:
    ka, kb = _canon(a), _canon(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    # containment: "btm" vs "btmlayout"
    if ka in kb or kb in ka:
        return 0.92
    return SequenceMatcher(None, ka, kb).ratio()


def _token_overlap(a: str | None, b: str | None) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _landmark_score(la: list[dict], lb: list[dict]) -> tuple[float, list[str]]:
    """Best-match overlap between two landmark SETS.

    Sets, not single values: the same house gets described via different
    landmarks by different people, so we need any-overlap, not equality.
    """
    if not la or not lb:
        return 0.0, []
    matched, best_total = [], 0.0
    for x in la:
        best, who = 0.0, None
        for y in lb:
            r = _ratio(x.get("name"), y.get("name"))
            if r > best:
                best, who = r, y
        if best >= 0.85 and who:
            matched.append(x["name"])
            # agreeing relations corroborate; disagreeing ones don't veto,
            # since "near" and "behind" are often used interchangeably
            if x.get("relation") and x["relation"] == who.get("relation"):
                best = min(1.0, best + 0.05)
        best_total = max(best_total, best)
    coverage = len(matched) / min(len(la), len(lb))
    return round(min(1.0, 0.6 * best_total + 0.4 * coverage), 3), matched


def _num_key(s: str | None) -> str | None:
    if not s:
        return None
    m = re.findall(r"[a-z]?-?\d+", s.lower().replace("#", ""))
    return m[0].strip("-") if m else None


# Two tiers, and the distinction is the whole trick.
#
# COARSE signals answer "same neighbourhood?". FINE signals answer "same door?".
# Agreement on pincode + city + locality means two records are in the same
# locality -- which in an Indian city can be tens of thousands of households.
# It is necessary evidence, never sufficient. So coarse GATES and fine SCORES.
COARSE = {"pincode": 0.40, "city": 0.15, "locality": 0.35, "sublocality": 0.10}
# building carries far more weight in India than in Western addressing: a named
# complex ("Mysari Chambers", "Gayatri Towers", "Abhay Prashal") IS the door
# identifier, often the only stable one, since street naming is inconsistent.
FINE = {"house_number": 0.26, "building": 0.26, "landmarks": 0.24,
        "street": 0.18, "visual_descriptor": 0.06}

# Without any door-level evidence, this is the ceiling: "same area, unknown door".
NO_FINE_CEILING = 0.50


def compare(a: dict, b: dict) -> dict:
    """Score two parsed addresses. Returns verdict + per-signal breakdown."""
    sig: dict[str, float] = {}

    sig["pincode"] = 1.0 if (a.get("pincode") and a["pincode"] == b.get("pincode")) else 0.0
    sig["city"] = _ratio(a.get("city"), b.get("city"))
    # Nested Indian localities (Chaitanyapuri sits inside Dilsukhnagar) get
    # assigned to different slots by the parser, so compare across both.
    la = [a.get("locality"), a.get("sublocality")]
    lb = [b.get("locality"), b.get("sublocality")]
    sig["locality"] = max((_ratio(x, y) for x in la for y in lb), default=0.0)
    sig["sublocality"] = _ratio(a.get("sublocality"), b.get("sublocality"))
    sig["street"] = _token_overlap(a.get("street"), b.get("street"))

    lm_score, lm_matched = _landmark_score(a.get("landmarks") or [], b.get("landmarks") or [])
    sig["landmarks"] = lm_score

    sig["building"] = _ratio(a.get("building"), b.get("building"))
    sig["visual_descriptor"] = _ratio(a.get("visual_descriptor"), b.get("visual_descriptor"))

    na, nb = _num_key(a.get("house_number")), _num_key(b.get("house_number"))
    sig["house_number"] = (1.0 if na == nb else 0.0) if (na and nb) else 0.0

    observable = {
        "pincode": bool(a.get("pincode") and b.get("pincode")),
        "city": bool(a.get("city") and b.get("city")),
        "locality": bool(a.get("locality") and b.get("locality")),
        "sublocality": bool(a.get("sublocality") and b.get("sublocality")),
        "street": bool(a.get("street") and b.get("street")),
        "landmarks": bool((a.get("landmarks") or []) and (b.get("landmarks") or [])),
        "house_number": bool(na and nb),
        "building": bool(a.get("building") and b.get("building")),
        "visual_descriptor": bool(a.get("visual_descriptor") and b.get("visual_descriptor")),
    }

    def _weighted(group):
        live = {k: w for k, w in group.items() if observable[k]}
        if not live:
            return None
        return sum(sig[k] * w for k, w in live.items()) / sum(live.values())

    coarse = _weighted(COARSE)
    fine = _weighted(FINE)

    veto = None
    if fine is None:
        # No door-level evidence on either side. Same area at best.
        score = min(NO_FINE_CEILING, coarse if coarse is not None else 0.0)
        veto = "no door-level evidence"
    else:
        base = coarse if coarse is not None else 0.5
        score = 0.35 * base + 0.65 * fine
        # Strong fine agreement shouldn't be dragged down by a coarse signal
        # the parser got wrong -- but it must never rescue a coarse mismatch.
        if fine >= 0.85 and base >= 0.6:
            score = max(score, 0.78)

    # --- vetoes -------------------------------------------------------
    if observable["pincode"] and sig["pincode"] == 0.0:
        veto = "pincode mismatch"
        score = min(score, 0.35)
    if observable["house_number"] and sig["house_number"] == 0.0:
        veto = "house number mismatch"
        score = min(score, 0.40)
    if observable["locality"] and sig["locality"] < 0.55:
        # A locality mismatch is usually real -- but when the pincode agrees AND
        # door-level evidence agrees, it's a parse artifact (one record kept the
        # sublocality, the other the metro-station area name). Don't veto then.
        corroborated = (observable["pincode"] and sig["pincode"] == 1.0
                        and fine is not None and fine >= 0.8)
        if not corroborated:
            veto = "different locality"
            score = min(score, 0.35)

    score = round(max(0.0, min(1.0, score)), 3)
    verdict = "same" if score >= 0.75 else "likely" if score >= 0.55 else "different"

    return {
        "score": score,
        "verdict": verdict,
        "signals": {k: round(v, 3) for k, v in sig.items()},
        "coarse": round(coarse, 3) if coarse is not None else None,
        "fine": round(fine, 3) if fine is not None else None,
        "observed": [k for k, v in observable.items() if v],
        "matched_landmarks": lm_matched,
        "veto": veto,
    }


def cluster(parsed: list[dict], threshold: float = 0.75) -> list[int]:
    """Single-link clustering over compare(). Returns a cluster id per record."""
    n = len(parsed)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(n):
        for j in range(i + 1, n):
            if compare(parsed[i], parsed[j])["score"] >= threshold:
                union(i, j)

    roots, out = {}, []
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        out.append(roots[r])
    return out
