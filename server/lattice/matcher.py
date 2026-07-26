"""Blocking + reference-corpus matching -- Layer 1 at scale.  (Neon)

`resolver.cluster()` is O(n^2) compare() calls: fine for a 40-address demo,
unusable over a CRM table. Blocking cuts the pair space: two records are only
compared when they share at least one blocking key, and in an Indian address
the pincode IS the natural block.

Multi-key blocking, because real records are missing fields. A record blocks
on every key it can produce (pincode + each discriminating locality token),
so one record writing "BTM 2nd stage" and another "BTM Layout" still meet on
the token "btm" even though neither string matches the other. A record that
yields no keys at all is compared against everything -- rare, and correctness
beats speed there.

resolver.py is deliberately untouched: same compare(), same threshold, same
union-find semantics. Blocking only decides which pairs get compared.
"""

import re
import threading
from collections import defaultdict
from itertools import combinations

from .resolver import _tokens, compare

# "2nd", "4th", "11" -- ordinals and bare numbers name a position inside a
# locality, not the locality; as blocking keys they'd glue every "2nd Stage"
# in the country into one block.
_POSITIONAL = re.compile(r"^\d+(st|nd|rd|th)?$")


def blocking_keys(p: dict) -> set[str]:
    keys = set()
    if p.get("pincode"):
        keys.add("pin:" + p["pincode"])
    for field in ("locality", "sublocality"):
        for tok in _tokens(p.get(field)):
            if not _POSITIONAL.match(tok):
                keys.add("loc:" + tok)
    return keys


def candidate_pairs(parsed: list[dict]) -> set[tuple[int, int]]:
    """Pairs worth scoring: share a blocking key, or one side is keyless."""
    by_key: dict[str, list[int]] = defaultdict(list)
    keyless = []
    for i, p in enumerate(parsed):
        keys = blocking_keys(p)
        if not keys:
            keyless.append(i)
            continue
        for k in keys:
            by_key[k].append(i)

    pairs: set[tuple[int, int]] = set()
    for members in by_key.values():
        if len(members) > 1:
            pairs.update(combinations(members, 2))
    for i in keyless:
        for j in range(len(parsed)):
            if i != j:
                pairs.add((min(i, j), max(i, j)))
    return pairs


def cluster_blocked(parsed: list[dict], threshold: float = 0.75) -> list[int]:
    """Drop-in for resolver.cluster(), restricted to candidate pairs."""
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

    for i, j in sorted(candidate_pairs(parsed)):
        if compare(parsed[i], parsed[j])["score"] >= threshold:
            union(i, j)

    roots: dict[int, int] = {}
    out = []
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        out.append(roots[r])
    return out


class AddressIndex:
    """In-memory reference corpus: add parsed records, match incoming ones.

    Answers the onboarding question -- "does this address match anything we
    have already seen?" -- without re-scoring the whole corpus: only records
    sharing a blocking key with the query are compared.
    """

    def __init__(self):
        self._records: list[dict] = []       # {"parsed": ..., "meta": ...}
        self._by_key: dict[str, list[int]] = defaultdict(list)
        self._keyless: list[int] = []
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._records)

    def add(self, parsed: dict, meta: dict | None = None) -> int:
        with self._lock:
            idx = len(self._records)
            self._records.append({"parsed": parsed, "meta": meta or {}})
            keys = blocking_keys(parsed)
            if not keys:
                self._keyless.append(idx)
            for k in keys:
                self._by_key[k].append(idx)
            return idx

    def match(self, parsed: dict, top_k: int = 5, floor: float = 0.55) -> list[dict]:
        cand: set[int] = set(self._keyless)
        keys = blocking_keys(parsed)
        if keys:
            for k in keys:
                cand.update(self._by_key.get(k, []))
        else:
            cand = set(range(len(self._records)))

        hits = []
        for idx in cand:
            rec = self._records[idx]
            res = compare(parsed, rec["parsed"])
            if res["score"] >= floor:
                hits.append({
                    "corpus_id": idx,
                    "raw": rec["parsed"].get("raw"),
                    "meta": rec["meta"],
                    "score": res["score"],
                    "verdict": res["verdict"],
                    "veto": res["veto"],
                    "matched_landmarks": res["matched_landmarks"],
                })
        hits.sort(key=lambda h: -h["score"])
        return hits[:top_k]

    def stats(self) -> dict:
        return {
            "records": len(self._records),
            "blocking_keys": len(self._by_key),
            "keyless_records": len(self._keyless),
        }
