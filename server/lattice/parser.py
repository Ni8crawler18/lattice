"""Layer 0 -- messy Indian address string -> structured components.

The Indian-specific move: `landmark` is a first-class field with an explicit
spatial *relation* (behind / opposite / near / above / beside). Western address
schemas have no slot for this, which is why they drop the most load-bearing part
of an Indian address on the floor.
"""

import json
import re
import time
from dataclasses import asdict, dataclass, field

from . import sarvam

# Relations, normalised. Keys are what people actually write.
RELATIONS = {
    "behind": ["behind", "peeche", "pichhe", "back side", "backside", "back of", "magé",
               "magi", "pichhe", "मागे", "पीछे", "pase", "backsid",
               "பின்னால்", "பின்புறம்", "pinnal"],
    "opposite": ["opposite", "opp", "saamne", "samne", "in front of", "front of",
                 "समोर", "सामने", "எதிரில்", "எதிரே", "edhiril", "ethiril"],
    "near": ["near", "nr", "paas", "pass", "ke paas", "close to", "besides", "nearby",
             "जवळ", "पास", "కి దగ్గర", "কাছে", "koло",
             "அருகில்", "அருகே", "arugil", "aruge"],
    "beside": ["beside", "next to", "bagal", "bagal mein", "adjacent", "side of",
               "பக்கத்தில்", "pakkathil"],
    "above": ["above", "upar", "over", "top of", "1st floor above", "மேலே"],
    "below": ["below", "under", "neeche", "ground floor of", "கீழே"],
}

_REL_LOOKUP = {kw.lower(): rel for rel, kws in RELATIONS.items() for kw in kws}

SCHEMA_KEYS = [
    "occupant", "house_number", "floor", "building", "visual_descriptor",
    "street", "sublocality", "locality", "post_office", "city", "district",
    "state", "pincode",
]

SYSTEM = """You are an expert on Indian postal addresses. You extract structure \
from messy, colloquial, multi-script Indian address strings.

Return ONLY a JSON object. No prose, no markdown fences.

Keys (use null when genuinely absent -- never invent):
  occupant           bank/company/shop name occupying the premises, if the address
                     opens with one. NOT a landmark.
  house_number       flat/house/plot/door number, e.g. "45", "#12", "B-14", "Room no 4"
  floor              floor if stated
  building           building/apartment/chawl name, e.g. "Shivneri Apartments"
  visual_descriptor  a physical identifying feature of the property itself,
                     e.g. "blue gate", "green shutter", "corner house". NOT a landmark.
  street             street/road/cross/main/gali, e.g. "4th Main Road", "Gali No 6"
  sublocality        sector/stage/phase/block sub-unit, e.g. "2nd Stage", "Sector 4"
  locality           the main locality/area/village name, e.g. "Kothrud", "BTM Layout".
                     "VILLAGE DHANORA" -> locality "Dhanora"
  post_office        the PO in rural chains: "PO HANODA" / "P.O. Sirsa" -> "Hanoda".
                     Postal routing, NOT a landmark -- never put a PO in landmarks.
  city               city, expanded to its common full form
  district           district when stated: "DIST DURG" / "DISTT ALWAR" / "ZILLA X"
                     -> "Durg". A district is NOT a city -- do not copy it there.
  state              state if stated or confidently inferable from city
  pincode            6-digit PIN, digits only

  landmarks          ARRAY of EVERY reference point mentioned. Do not pick one --
                     list them all. Each item:
                       {"name": "...", "relation": "behind|opposite|near|beside|above|below|null"}
                     Strip the relation word from the name:
                       "behind Ganesh mandir"  -> {"name":"Ganesh Mandir","relation":"behind"}
                       "opp SBI ATM"           -> {"name":"SBI ATM","relation":"opposite"}
                     Expand the name to its full common form: "mndir"->"Mandir",
                     "SBI"->"SBI", "Reliance Fresh"->"Reliance Fresh".
                     Landmarks appear in ANY script and the relation word may
                     FOLLOW the name (Tamil/Telugu/Kannada postpositions):
                       "பெரியார் பேருந்து நிலையம் அருகில்"
                         -> {"name":"Periyar Bus Stand","relation":"near"}
                       "பழைய தபால் அலுவலகம் எதிரில்"
                         -> {"name":"Old Post Office","relation":"opposite"}
                     A bus stand, temple, post office, school, hospital or shop
                     used as a reference point is a landmark -- never drop it.

HARD RULES -- violating these is worse than returning null:
- NEVER infer, guess or supply a city that is not written in the input. If no
  city appears, city MUST be null. A confidently wrong city is worse than none.
  ("PAKKAM KOTTUR, PIN" has NO city -> null. Do not answer "Chennai".)
- NEVER correct the spelling of a proper noun. Building, street, locality and
  landmark names are preserved AS WRITTEN. "GAJANAN COMPLEX" stays
  "Gajanan Complex", never "Gajanand". Only fix casing.
- A bank / company / shop name at the START of the address is the OCCUPANT of
  the premises, not a landmark and not a building name. Put it in `occupant`.
  A business named as a reference point ("opposite HDFC Bank") IS a landmark.

Rules:
- TRANSLITERATE every value into Latin script, whatever script the input used.
- Expand abbreviations: B'lore->Bengaluru, Ngr->Nagar, Rd->Road, Nr->Near,
  opp->opposite, mndir->Mandir, Hyd->Hyderabad, St->Street.
- Normalise ONLY the well-known city renamings (Bangalore->Bengaluru,
  Bombay->Mumbai, Calcutta->Kolkata, Madras->Chennai). Nothing else.
- Keep compound door numbers whole: "2 BY 76 F" -> "2/76-F", "5-5-155" as is.
- Convert Devanagari/Tamil/Bengali digits to Latin digits.
- Split a compound locality: "BTM 2nd stage" -> locality "BTM Layout",
  sublocality "2nd Stage".
- Normalise temple/store names consistently: "Ganesh Temple" and "Ganesh Mandir"
  should BOTH be emitted as "Ganesh Mandir". Prefer the Indian-language form
  (Mandir, Masjid, Gurudwara) over the English one."""


@dataclass
class ParsedAddress:
    raw: str
    language_code: str | None = None
    script_code: str | None = None
    occupant: str | None = None
    house_number: str | None = None
    floor: str | None = None
    building: str | None = None
    visual_descriptor: str | None = None
    street: str | None = None
    landmarks: list[dict] = field(default_factory=list)
    landmark: str | None = None          # primary, for display
    landmark_relation: str | None = None
    sublocality: str | None = None
    locality: str | None = None
    post_office: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    completeness: float = 0.0
    missing: list[str] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _extract_json(text: str | None) -> dict:
    """LLMs fence JSON even when told not to. Be tolerant."""
    if not text:
        raise ValueError("empty completion")
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def _clean(v):
    if v is None:
        return None
    s = str(v).strip().strip(",.-").strip()
    if not s or s.lower() in {"null", "none", "n/a", "na", "-"}:
        return None
    return s


def _normalise_relation(rel, raw: str) -> str | None:
    """Trust the model, but fall back to scanning the raw string."""
    if rel:
        r = str(rel).strip().lower()
        if r in RELATIONS:
            return r
        if r in _REL_LOOKUP:
            return _REL_LOOKUP[r]
    low = raw.lower()
    for kw, rel_name in sorted(_REL_LOOKUP.items(), key=lambda kv: -len(kv[0])):
        if kw in low:
            return rel_name
    return None


def _parse_landmarks(data: dict, raw: str) -> list[dict]:
    """Normalise the landmarks array; tolerate a bare string or a single object."""
    items = data.get("landmarks") or []
    if isinstance(items, (str, dict)):
        items = [items]
    out, seen = [], set()
    for it in items:
        if isinstance(it, str):
            name, rel = _clean(it), None
        elif isinstance(it, dict):
            name, rel = _clean(it.get("name")), it.get("relation")
        else:
            continue
        if not name:
            continue
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "relation": _normalise_relation(rel, raw)})
    return out


# Fields that actually determine whether a rider finds the door.
_WEIGHTS = {
    "house_number": 0.22, "building": 0.12, "street": 0.16, "landmark": 0.14,
    "sublocality": 0.06, "locality": 0.16, "city": 0.08, "pincode": 0.06,
}


def _score(d: dict) -> tuple[float, list[str]]:
    total = sum(w for k, w in _WEIGHTS.items() if d.get(k))
    missing = [k for k in ("house_number", "street", "locality", "city", "pincode")
               if not d.get(k)]
    return round(total, 3), missing


# --- successful-parse cache -------------------------------------------
# Sarvam intermittently returns empty completions (measured: ~2 in 6 on a
# repeated address, uncorrelated with temperature). Retrying helps but cannot
# guarantee a live demo. Caching by raw string means any address parses at
# most once: the second call is instant AND cannot fail. Only successes are
# cached, so a failure is always retried rather than memoised.
import os as _os

_PCACHE_FILE = _os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "parse_cache.json")
_PCACHE_LOCK = __import__("threading").Lock()


def _pcache_load() -> dict:
    try:
        with open(_PCACHE_FILE) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_PCACHE: dict = _pcache_load()


def _pcache_put(key: str, value: dict) -> None:
    with _PCACHE_LOCK:
        _PCACHE[key] = value
        try:
            tmp = _PCACHE_FILE + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(_PCACHE, fh, ensure_ascii=False)
            _os.replace(tmp, _PCACHE_FILE)
        except OSError:
            pass                      # read-only disk: stay in-memory


def parse(raw: str, use_cache: bool = True) -> ParsedAddress:
    key = " ".join(raw.split()).lower()
    if use_cache and key in _PCACHE:
        return ParsedAddress(**_PCACHE[key])
    out = ParsedAddress(raw=raw)

    try:
        lid = sarvam.identify_language(raw)
        out.language_code = lid.get("language_code")
        out.script_code = lid.get("script_code")
    except Exception:
        pass  # LID is advisory; the LLM transliterates regardless

    # Empty completions are the dominant failure here, and they CLUSTER: at
    # temperature 0 the sampler is deterministic, so a prompt that returns
    # empty once returns empty every retry. Measured 1-in-3 end-to-end failures
    # on a demo pair before this. So never sample greedily, escalate the
    # temperature each attempt (a different sample is the whole point of a
    # retry), and give the upstream a moment between tries.
    data, last_err = None, None
    _TEMPS = (0.1, 0.2, 0.35, 0.55, 0.8)
    for attempt, temp in enumerate(_TEMPS):
        try:
            text = sarvam.chat(
                [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": raw}],
                temperature=temp,
            )
            data = _extract_json(text)
            break
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < len(_TEMPS) - 1:
                time.sleep(0.4 * (attempt + 1))
    if data is None:
        out.error = last_err
        return out

    for k in SCHEMA_KEYS:
        setattr(out, k, _clean(data.get(k)))

    out.landmarks = _parse_landmarks(data, raw)
    if not out.landmarks:
        out.landmarks = _landmarks_from_raw(raw)
    _ensure_latin(out)
    if out.landmarks:
        out.landmark = out.landmarks[0]["name"]
        out.landmark_relation = out.landmarks[0]["relation"]
    if out.pincode:
        digits = re.sub(r"\D", "", out.pincode)
        out.pincode = digits if len(digits) == 6 else None

    out.completeness, out.missing = _score(out.as_dict())
    if not out.error:
        _pcache_put(key, out.as_dict())
    return out


def _landmarks_from_raw(raw: str) -> list[dict]:
    """Deterministic fallback when the model returns NO landmarks.

    Model recall on landmark extraction is flaky, especially for non-Latin
    input ("சரவணா ஸ்டோர்ஸ் எதிரில்" comes back empty on some completions).
    But an address segment containing a spatial-relation keyword IS a landmark
    phrase -- so comma-split the raw string, and where a segment carries a
    relation keyword, strip the keyword and keep the remainder as the name.
    Names come out as-written (no expansion); _ensure_latin transliterates.
    """
    out, seen = [], set()
    for seg in re.split(r"[,\n;]", raw):
        seg = seg.strip()
        if len(seg) < 4:
            continue
        low = seg.lower()
        hit = None
        for kw, rel in sorted(_REL_LOOKUP.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", low):
                hit = (kw, rel)
                break
        if not hit:
            continue
        kw, rel = hit
        name = re.sub(rf"(?i)(?<!\w){re.escape(kw)}(?!\w)", " ", seg)
        name = re.sub(r"^\s*(to|ke|se|the)\s+", "", name.strip(" ,.-"), flags=re.I)
        name = re.sub(r"\s+", " ", name).strip(" ,.-")
        key = re.sub(r"[^\w]", "", name.lower())
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "relation": rel})
    return out


_INDIC = re.compile(r"[ऀ-෿]")   # Devanagari .. Sinhala blocks


def _ensure_latin(out: ParsedAddress) -> None:
    """Safety net for the prompt's TRANSLITERATE rule.

    The model occasionally leaves a field in the input's native script; every
    downstream consumer (resolver canon keys, pincode directory, geocoder)
    assumes canonical Latin, so a native-script value silently breaks matching
    and validation. Transliterate just those values. Best-effort: no LID code
    or a failed call leaves the original in place.
    """
    if not out.language_code or out.language_code.startswith("en"):
        return

    def to_latin(value: str) -> str:
        if not _INDIC.search(value):
            return value
        try:
            return sarvam.transliterate(value, source=out.language_code) or value
        except Exception:
            return value

    for k in SCHEMA_KEYS:
        v = getattr(out, k)
        if v:
            setattr(out, k, to_latin(v))
    for lm in out.landmarks:
        if lm.get("name"):
            lm["name"] = to_latin(lm["name"])
