"""Layer 3 (algorithm half) -- DIGIPIN encode/decode.

DIGIPIN is India Post's open geo-coded addressing grid (with IIT Hyderabad and
NRSC/ISRO, launched 27 May 2025): every ~4m x 4m cell in India gets a
10-character code by recursive 4x4 subdivision of a fixed bounding box.

This module is pure grid arithmetic ported from the officially published
algorithm -- no API, no data files. What it does NOT do is turn a text address
into coordinates; that needs a geocoder, which is not in the loop yet. So
Lattice implements the DIGIPIN *algorithm*, not text -> DIGIPIN. Say it that way.
"""

# Official 4x4 symbol grid, row 0 = northernmost band.
_GRID = [
    ["F", "C", "9", "8"],
    ["J", "3", "2", "7"],
    ["K", "4", "5", "6"],
    ["L", "M", "P", "T"],
]
_POS = {ch: (r, c) for r, row in enumerate(_GRID) for c, ch in enumerate(row)}

# Official bounding box covering India.
MIN_LAT, MAX_LAT = 2.5, 38.5
MIN_LON, MAX_LON = 63.5, 99.5

LEVELS = 10


def encode(lat: float, lon: float) -> str:
    """(lat, lon) -> 10-character DIGIPIN, hyphenated XXX-XXX-XXXX."""
    if not (MIN_LAT <= lat <= MAX_LAT):
        raise ValueError(f"latitude {lat} outside DIGIPIN bounds [{MIN_LAT}, {MAX_LAT}]")
    if not (MIN_LON <= lon <= MAX_LON):
        raise ValueError(f"longitude {lon} outside DIGIPIN bounds [{MIN_LON}, {MAX_LON}]")

    lat_lo, lat_hi = MIN_LAT, MAX_LAT
    lon_lo, lon_hi = MIN_LON, MAX_LON
    out = []
    for level in range(1, LEVELS + 1):
        lat_div = (lat_hi - lat_lo) / 4
        lon_div = (lon_hi - lon_lo) / 4

        # Row 0 is the TOP band, so index from the northern edge downward.
        row = 3 - int((lat - lat_lo) / lat_div)
        col = int((lon - lon_lo) / lon_div)
        row = max(0, min(row, 3))
        col = max(0, min(col, 3))

        out.append(_GRID[row][col])
        if level in (3, 6):
            out.append("-")

        lat_hi = lat_lo + lat_div * (4 - row)
        lat_lo = lat_lo + lat_div * (3 - row)
        lon_lo = lon_lo + lon_div * col
        lon_hi = lon_lo + lon_div
    return "".join(out)


# Approximate cell width per code length, from the official spec table.
CELL_SIZE_APPROX = {1: "1000 km", 2: "250 km", 3: "62.5 km", 4: "15.6 km",
                    5: "3.9 km", 6: "1 km", 7: "250 m", 8: "60 m",
                    9: "15 m", 10: "3.8 m"}


def _compact(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def _walk(pin: str, original: str) -> tuple[float, float, float, float]:
    """Consume a validated 1..10-symbol prefix, return its cell bounds."""
    lat_lo, lat_hi = MIN_LAT, MAX_LAT
    lon_lo, lon_hi = MIN_LON, MAX_LON
    for ch in pin:
        if ch not in _POS:
            raise ValueError(f"invalid DIGIPIN symbol {ch!r} in {original!r}")
        row, col = _POS[ch]
        lat_div = (lat_hi - lat_lo) / 4
        lon_div = (lon_hi - lon_lo) / 4
        lat_hi = lat_lo + lat_div * (4 - row)
        lat_lo = lat_lo + lat_div * (3 - row)
        lon_lo = lon_lo + lon_div * col
        lon_hi = lon_lo + lon_div
    return lat_lo, lat_hi, lon_lo, lon_hi


def cell(code: str) -> dict:
    """Cell centre + bounds for a full DIGIPIN or any 1..10-symbol prefix.

    A prefix names a LARGER cell: 6 symbols ~ 1 km, 7 ~ 250 m, 8 ~ 60 m.
    """
    pin = _compact(code)
    if not 1 <= len(pin) <= LEVELS:
        raise ValueError(f"DIGIPIN prefix must be 1..{LEVELS} symbols, got {code!r}")
    lat_lo, lat_hi, lon_lo, lon_hi = _walk(pin, code)
    return {
        "code": format_code(pin),
        "level": len(pin),
        "cell_size_approx": CELL_SIZE_APPROX[len(pin)],
        "latitude": round((lat_lo + lat_hi) / 2, 6),
        "longitude": round((lon_lo + lon_hi) / 2, 6),
        "bounds": {
            "min_latitude": round(lat_lo, 6), "max_latitude": round(lat_hi, 6),
            "min_longitude": round(lon_lo, 6), "max_longitude": round(lon_hi, 6),
        },
    }


def decode(code: str) -> dict:
    """Full DIGIPIN -> centre of its ~4m cell, plus the cell bounds.

    Accepts with or without hyphens, any case. Requires all 10 symbols;
    use cell() for prefixes.
    """
    pin = _compact(code)
    if len(pin) != LEVELS:
        raise ValueError(f"DIGIPIN must be {LEVELS} characters, got {len(pin)!r} from {code!r}")
    c = cell(pin)
    return {"latitude": c["latitude"], "longitude": c["longitude"], "bounds": c["bounds"]}


def truncate(code: str, level: int) -> str:
    """Parent cell of a DIGIPIN at the given level (1..10), hyphenated."""
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1..{LEVELS}, got {level}")
    pin = _compact(code)
    if len(pin) < level:
        raise ValueError(f"cannot truncate {code!r} to level {level}: only {len(pin)} symbols")
    for ch in pin:
        if ch not in _POS:
            raise ValueError(f"invalid DIGIPIN symbol {ch!r} in {code!r}")
    return format_code(pin[:level])


def format_code(code: str) -> str:
    """Standard hyphenation (after symbols 3 and 6) for any prefix length."""
    pin = _compact(code)
    return "-".join(s for s in (pin[:3], pin[3:6], pin[6:]) if s)


def canonical(code: str) -> str:
    """Re-hyphenate a full DIGIPIN into the standard XXX-XXX-XXXX form."""
    return format_code(code)


_DIRECTIONS = [("N", 1, 0), ("NE", 1, 1), ("E", 0, 1), ("SE", -1, 1),
               ("S", -1, 0), ("SW", -1, -1), ("W", 0, -1), ("NW", 1, -1)]


def neighbors(code: str) -> dict:
    """The adjacent DIGIPIN cells around a code (or prefix), same level.

    "What are the nearest DIGIPINs?" -- up to 8 cells sharing an edge or
    corner with this one; fewer at the edge of the national bounding box.
    """
    c = cell(code)
    b = c["bounds"]
    lat_span = b["max_latitude"] - b["min_latitude"]
    lon_span = b["max_longitude"] - b["min_longitude"]
    out = []
    for name, dr, dc in _DIRECTIONS:
        lat = c["latitude"] + dr * lat_span
        lon = c["longitude"] + dc * lon_span
        if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
            continue
        out.append({"direction": name, "digipin": truncate(encode(lat, lon), c["level"])})
    return {"cell": c["code"], "level": c["level"],
            "cell_size_approx": c["cell_size_approx"], "neighbors": out}


def group(items: list[dict], level: int) -> dict:
    """Bucket points into DIGIPIN grid cells at the given level.

    Each item needs either "digipin" or "latitude"+"longitude" (and may carry
    an "id"; the list index is used otherwise). This is spatial consolidation
    -- orders in one ~250m cell ride in one batch -- and it needs coordinates
    or codes as input: a text address must be geocoded first, which Lattice
    does not do. Malformed items land in "rejected", they never abort the batch.

    Returns {"groups": [...largest first], "rejected": [...]}.
    """
    if not 1 <= level <= LEVELS:
        raise ValueError(f"level must be 1..{LEVELS}, got {level}")

    cells: dict[str, list[dict]] = {}
    rejected = []
    for i, item in enumerate(items):
        ident = item.get("id", i)
        try:
            if item.get("digipin"):
                pin = _compact(str(item["digipin"]))
                key = truncate(pin, level)
                full = format_code(pin) if len(pin) == LEVELS else None
            elif item.get("latitude") is not None and item.get("longitude") is not None:
                full = encode(float(item["latitude"]), float(item["longitude"]))
                key = truncate(full, level)
            else:
                raise ValueError("item needs either digipin or latitude+longitude")
        except (ValueError, TypeError) as exc:
            rejected.append({"id": ident, "error": str(exc)})
            continue
        member = {"id": ident, "digipin": full}
        if full:
            # cell centre of the full code, so callers can plot members
            d = decode(full)
            member["latitude"], member["longitude"] = d["latitude"], d["longitude"]
        cells.setdefault(key, []).append(member)

    groups = []
    for key in sorted(cells, key=lambda k: (-len(cells[k]), k)):
        c = cell(key)
        groups.append({"cell": key, "count": len(cells[key]), "members": cells[key],
                       "centre": {"latitude": c["latitude"], "longitude": c["longitude"]},
                       "bounds": c["bounds"]})
    return {"level": level, "cell_size_approx": CELL_SIZE_APPROX[level],
            "groups": groups, "rejected": rejected}
