"""Golden-record synthesis: N parsed records for one house -> the one clean record.

cluster() says six CRM rows are the same door; this module produces the merged
best-of record a CRM can actually write back: house number from the row that
had it, pincode from another, all landmarks pooled. Every field carries
provenance -- which source records supplied it and how many agree -- because a
BFSI/ops consumer will not accept a merged value they cannot audit.

Merge policy, per scalar component:
  1. group non-null values by canonical key (resolver._canon -- same key means
     same value modulo spelling/casing/generic tokens)
  2. majority vote on the groups
  3. tie-break: the group whose records are more complete overall
  4. within the winning group, keep the longest string (most information;
     "BTM Layout 2nd Stage" over "btm 2nd stage")

Landmarks are pooled across all members and deduped by canonical name; a
specific relation (behind/opposite/...) always beats None.
"""

from .parser import SCHEMA_KEYS, _WEIGHTS, _normalise_relation, _score
from .resolver import _canon

# occupant is per-record (the shop at the premises), not per-location identity;
# merge it too, but callers should treat it as descriptive.
FIELDS = SCHEMA_KEYS

# Writeback order: door -> navigation -> area -> routing.
_FORMAT_ORDER = ["occupant", "house_number", "floor", "building", "visual_descriptor",
                 "street", "sublocality", "locality", "city", "state", "pincode"]


def _completeness(rec: dict) -> float:
    return sum(w for k, w in _WEIGHTS.items() if rec.get(k))


def _merge_field(field: str, members: list[dict]) -> dict | None:
    groups: dict[str, dict] = {}
    for idx, rec in enumerate(members):
        val = rec.get(field)
        if not val:
            continue
        key = _canon(str(val))
        if not key:
            continue
        g = groups.setdefault(key, {"values": [], "sources": []})
        g["values"].append(str(val))
        g["sources"].append(idx)

    if not groups:
        return None

    def rank(item):
        _, g = item
        votes = len(g["sources"])
        support = sum(_completeness(members[i]) for i in g["sources"])
        return (votes, support)

    key, g = max(groups.items(), key=rank)
    value = max(g["values"], key=len)
    return {
        "value": value,
        "sources": g["sources"],
        "agreement": f"{len(g['sources'])}/{sum(1 for m in members if m.get(field))}",
        "contested": len(groups) > 1,
    }


def _merge_landmarks(members: list[dict]) -> list[dict]:
    pooled: dict[str, dict] = {}
    for idx, rec in enumerate(members):
        for lm in rec.get("landmarks") or []:
            name = lm.get("name")
            if not name:
                continue
            key = _canon(name)
            if not key:
                continue
            e = pooled.setdefault(key, {"name": name, "relation": None, "sources": []})
            e["sources"].append(idx)
            if len(name) > len(e["name"]):
                e["name"] = name
            if e["relation"] is None and lm.get("relation"):
                e["relation"] = _normalise_relation(lm["relation"], name)
    # most-corroborated landmark first
    return sorted(pooled.values(), key=lambda e: -len(e["sources"]))


def format_address(components: dict) -> str:
    """One clean, consistently-ordered writeback string."""
    parts = []
    for k in _FORMAT_ORDER:
        v = components.get(k)
        if not v:
            continue
        if k == "floor" and not str(v).lower().endswith("floor"):
            v = f"{v} Floor"
        parts.append(str(v))
    lms = components.get("landmarks") or []
    if lms:
        lm = lms[0]
        rel = (lm.get("relation") or "near").capitalize()
        # insert after the door-level fields, before the area fields
        pos = min(len(parts), sum(1 for k in _FORMAT_ORDER[:6] if components.get(k)))
        parts.insert(pos, f"{rel} {lm['name']}")
    return ", ".join(parts)


def canonical(members: list[dict]) -> dict:
    """Merge parsed records (assumed same physical location) into one golden record.

    Returns components + per-field provenance + pooled landmarks + writeback text.
    Raises ValueError on an empty member list.
    """
    if not members:
        raise ValueError("canonical() needs at least one record")

    provenance: dict[str, dict] = {}
    components: dict = {}
    for f in FIELDS:
        merged = _merge_field(f, members)
        if merged:
            components[f] = merged["value"]
            provenance[f] = merged

    landmarks = _merge_landmarks(members)
    components["landmarks"] = [{"name": e["name"], "relation": e["relation"]}
                               for e in landmarks]

    completeness, missing = _score(components)
    return {
        "components": components,
        "provenance": provenance,
        "landmark_sources": [e["sources"] for e in landmarks],
        "canonical_text": format_address(components),
        "completeness": completeness,
        "missing": missing,
        "member_count": len(members),
        "contested_fields": [f for f, m in provenance.items() if m["contested"]],
    }
