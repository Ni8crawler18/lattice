"""Geocoder adapter -- the missing half of the text -> DIGIPIN bridge.

Pluggable by design: `geocode(text)` is the whole interface. The default
backend is OSM Nominatim (free, no key), which resolves Indian addresses
at locality/street precision far more often than at building precision.
That limit is surfaced honestly in `precision` -- never present the pin
as a rooftop fix. Swap in a commercial geocoder by replacing `_query`.

Messy Indian strings rarely match whole; we retry, dropping leading
segments (house/floor/building first -- Nominatim doesn't know them)
until something resolves, and report which query actually matched.
"""

from __future__ import annotations

import re

import httpx

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "lattice-address-intelligence/0.1 (hackathon demo)"
TIMEOUT = 12.0

_PIN_RE = re.compile(r"\b\d{6}\b")

# place_rank -> honest label. Nominatim ranks: 30 building, 26+ street-ish,
# ~19-25 suburb/locality, below that town/city/district.
def _precision(rank: int | None, addresstype: str | None) -> str:
    if addresstype in ("building", "house", "residential") or (rank or 0) >= 26:
        return "street-level"
    if (rank or 0) >= 19:
        return "locality-level"
    return "city-level"


def _query(q: str) -> dict | None:
    r = httpx.get(
        NOMINATIM,
        params={"q": q, "format": "jsonv2", "limit": 1,
                "countrycodes": "in", "addressdetails": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    hits = r.json()
    return hits[0] if hits else None


def _candidates(text: str) -> list[str]:
    """Full string first, then drop leading segments (down to the last one
    alone -- a bare locality like 'Itwari' often resolves when the noisy
    door-level prefix never will); pincode as last resort."""
    segs = [s.strip() for s in re.split(r"[,\n]", text) if s.strip()]
    out = [", ".join(segs)]
    for i in range(1, len(segs)):
        out.append(", ".join(segs[i:]))
    pin = _PIN_RE.search(text)
    if pin:
        out.append(f"{pin.group(0)}, India")
    # dedupe, preserve order
    seen, uniq = set(), []
    for c in out:
        if c.lower() not in seen:
            seen.add(c.lower())
            uniq.append(c)
    return uniq


_CACHE: dict[str, dict | None] = {}


def geocode(text: str) -> dict | None:
    """Free-text address -> {latitude, longitude, precision, matched_query,
    display_name, source} or None.

    Resilient by design: one failing candidate (429 rate-limit, timeout)
    moves on to the next instead of aborting; queries are cached; attempts
    are spaced to respect Nominatim's 1 req/s policy. Raises only if every
    candidate errored (so the caller can distinguish outage from no-match).
    """
    import time

    errors, clean_misses = 0, 0
    for i, q in enumerate(_candidates(text)):
        ck = q.lower()
        if ck in _CACHE:
            hit = _CACHE[ck]
        else:
            if i:
                time.sleep(1.05)          # Nominatim usage policy: 1 req/s
            try:
                hit = _query(q)
            except httpx.HTTPError:
                errors += 1
                continue
            _CACHE[ck] = hit
        if hit:
            return {
                "latitude": float(hit["lat"]),
                "longitude": float(hit["lon"]),
                "precision": _precision(hit.get("place_rank"), hit.get("addresstype")),
                "matched_query": q,
                "display_name": hit.get("display_name", ""),
                "source": "osm-nominatim",
            }
        clean_misses += 1
    if errors and not clean_misses:
        raise httpx.HTTPError(f"all {errors} geocoder attempts failed")
    return None
