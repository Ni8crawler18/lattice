"""Lattice API -- Indian Address Intelligence."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.lattice import digipin, sarvam, pincode as pincode_dir   # noqa: E402
from server.lattice.golden import canonical              # noqa: E402
from server.lattice.parser import parse                 # noqa: E402
from server.lattice.resolver import compare, cluster    # noqa: E402
from server.lattice.scorer import score, score_batch     # noqa: E402

app = FastAPI(title="Lattice", description="Indian Address Intelligence")

# --- API-key auth.
# Self-service: engineers mint their own key via `POST /keys {"name": ...}`
# and send it as `X-API-Key: <key>` (or `?key=<key>`). Issued keys are
# STATELESS -- `ltk_<rand><hmac(master, rand)>` -- so they validate on any
# deployment sharing the same LATTICE_API_KEY master secret (Render's disk
# is ephemeral; no DB needed) and survive restarts. server/api_keys.json
# (gitignored) records names for auditing only, never for validation.
# The master key itself always works and is required to list keys.
# If no master key is configured, the API is open (local dev).
import hashlib                                                # noqa: E402
import hmac as hmac_mod                                       # noqa: E402
import secrets                                                # noqa: E402
import time as _t                                             # noqa: E402
import threading                                              # noqa: E402
from dotenv import load_dotenv                                # noqa: E402
load_dotenv()
_MASTER_KEY = (os.getenv("LATTICE_API_KEY") or "").strip().strip('"').strip("'")
_OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/keys",
                "/signup", "/stats"}
_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")
_KEYS_LOCK = threading.Lock()
_RAND_LEN, _SIG_LEN = 12, 20


def _sign(rand: str) -> str:
    return hmac_mod.new(_MASTER_KEY.encode(), rand.encode(),
                        hashlib.sha256).hexdigest()[:_SIG_LEN]


def _mint_key() -> str:
    rand = secrets.token_hex(_RAND_LEN // 2)
    return f"ltk_{rand}{_sign(rand)}"


def _key_valid(k: str) -> bool:
    if not k:
        return False
    if k == _MASTER_KEY:
        return True
    body = k[4:] if k.startswith("ltk_") else ""
    if len(body) != _RAND_LEN + _SIG_LEN:
        return False
    rand, sig = body[:_RAND_LEN], body[_RAND_LEN:]
    return hmac_mod.compare_digest(sig, _sign(rand))


def _load_keys() -> dict:
    try:
        with open(_KEYS_FILE) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_KEYS: dict = _load_keys()          # audit log: masked key -> {name, created}


def _save_keys() -> None:
    try:
        with open(_KEYS_FILE, "w") as fh:
            json.dump(_KEYS, fh, indent=1)
    except OSError:
        pass                        # read-only disk: auditing is best-effort


@app.middleware("http")
async def _meter(request: Request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if (request.method != "OPTIONS" and resp.status_code < 400
            and p not in ("/health", "/stats", "/docs", "/openapi.json", "/signup")
            and not p.startswith("/examples")):
        k = (request.headers.get("x-api-key") or request.query_params.get("key") or "")
        if k:
            try:
                from server import users as _u
                _u.record_call(k[:13])
            except Exception:
                pass
    return resp


@app.middleware("http")
async def _require_api_key(request: Request, call_next):
    if (_MASTER_KEY and request.method != "OPTIONS"
            and request.url.path not in _OPEN_PATHS
            and not request.url.path.startswith("/examples")):  # public quickstart code
        supplied = (request.headers.get("x-api-key")
                    or request.query_params.get("key", ""))
        if not _key_valid(supplied):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={
                "detail": "invalid or missing API key -- generate one via "
                          "POST /keys, then send X-API-Key header or ?key="})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # demo; tighten before anything real
    allow_methods=["*"],
    allow_headers=["*"],
)

REAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "real_sample.json")


def _real() -> list:
    try:
        with open(REAL) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.post("/keys")
def api_key_create(body: KeyIn):
    """Self-service API key for the engineering team. Shown ONCE -- copy it.
    Stateless (HMAC-signed): works against any deployment sharing the same
    master secret, local or Render. Use as `X-API-Key: <key>`."""
    import time
    key = _mint_key()
    with _KEYS_LOCK:
        _KEYS[key[:9] + "…" + key[-4:]] = {"name": body.name.strip(),
                                           "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _save_keys()
    return {"api_key": key, "name": body.name.strip(),
            "shown_once": True,
            "usage": "send header 'X-API-Key: <key>' (or ?key=<key>)"}


@app.get("/keys")
def api_keys_list(request: Request):
    """List minted keys (masked audit log). Master key only."""
    if (request.headers.get("x-api-key") or request.query_params.get("key")) != _MASTER_KEY:
        raise HTTPException(status_code=403, detail="master key required")
    return {"keys": [{"key": k, **v} for k, v in _KEYS.items()],
            "note": "audit log (best-effort on ephemeral disks); validation is stateless"}


# ---------------------------------------------------------------- account keys
# An account may hold several keys (prod / staging / a teammate's laptop), so
# one can be revoked without breaking the others. These three endpoints are
# MASTER-KEY ONLY on purpose: `email` is a parameter here, so anyone who could
# call them directly could read anyone's keys. The only caller is the client's
# /api/keys route handler, which runs server-side and takes the email from the
# signed session cookie rather than from the request. That is the whole
# isolation story -- the browser never gets to name the account.

class AccountKeyIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    label: str = Field(default="", max_length=60)


def _require_master(request: Request) -> None:
    if (request.headers.get("x-api-key") or request.query_params.get("key")) != _MASTER_KEY:
        raise HTTPException(status_code=403, detail="master key required")


@app.post("/account/keys")
def api_account_key_create(body: AccountKeyIn, request: Request):
    """Mint a key owned by one account. Returns the key in full, once."""
    _require_master(request)
    import time
    key = _mint_key()
    row = userstore.add_key(body.email, key, body.label)
    with _KEYS_LOCK:
        _KEYS[key[:9] + "\u2026" + key[-4:]] = {
            "name": (body.label or "").strip() or "account key",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _save_keys()
    return row


@app.get("/account/keys")
def api_account_keys_list(request: Request, email: str = ""):
    """Keys belonging to one account, and only that account."""
    _require_master(request)
    return {"email": email.strip().lower(), "keys": userstore.list_keys(email)}


@app.delete("/account/keys/{key_id}")
def api_account_key_revoke(key_id: int, request: Request, email: str = ""):
    """Revoke a key. The email is part of the match, so an id alone is useless."""
    _require_master(request)
    if not userstore.revoke_key(email, key_id):
        raise HTTPException(status_code=404, detail="no such key on this account")
    return {"revoked": key_id}


class ParseIn(BaseModel):
    address: str = Field(min_length=3, max_length=500)
    # optional context most databases already have in separate columns --
    # used to fill fields the string itself doesn't state (never overriding
    # what the address says), which sharpens geocoding and validation.
    id: str | int | None = None
    pincode: str | None = Field(default=None, max_length=10)
    city: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)


class CompareIn(BaseModel):
    a: str = Field(min_length=3, max_length=500)
    b: str = Field(min_length=3, max_length=500)


class BatchIn(BaseModel):
    addresses: list[str] = Field(min_length=1, max_length=40)


@app.get("/health")
def health():
    return {"ok": True, "real_records": len(_real())}


def _geo_digipin(p: dict, raw: str, inferred: dict | None = None) -> dict:
    """Parsed record -> {location, digipin, ...} via the geocoder adapter.

    Queries the *parsed canonical-Latin* components (so Devanagari/Tamil
    input geocodes) enriched with pincode-directory inference (a directory
    lookup, so the never-invent-a-city rule holds), falling back to the
    raw string. Never raises -- a geocoder outage degrades to nulls with a
    reason, not a 500.
    """
    from server.lattice import geocoder
    fields = [p.get(k) for k in ("street", "sublocality", "locality",
                                 "city", "district", "state")]
    # fill missing city/district/state from the offline pincode directory
    if inferred:
        for k in ("district", "state"):
            if inferred.get(k) and not (p.get("city") or p.get(k)):
                fields.append(inferred[k])
    fields.append(p.get("pincode"))
    canonical_q = ", ".join(str(f) for f in fields if f)
    try:
        hit = geocoder.geocode(canonical_q) if canonical_q else None
        if hit is None:
            hit = geocoder.geocode(raw)
    except Exception as exc:
        hit = None
        geo_err = f"geocoder unreachable: {exc}"
    else:
        geo_err = "geocoder found no match"
    if hit is None:
        # last resort: pincode-directory district centroid (GeoNames --
        # tens of km off, so labelled district-level and truncated hard)
        entry = pincode_dir.lookup(p.get("pincode"))
        if entry and entry.get("lat") is not None:
            hit = {"latitude": entry["lat"], "longitude": entry["lon"],
                   "precision": "district-level",
                   "matched_query": f"pincode {p['pincode']} directory centroid",
                   "display_name": f"{entry['district']}, {entry['state']}",
                   "source": "pincode-directory"}
        else:
            return {"location": None, "digipin": None, "note": geo_err}
    code = digipin.encode(hit["latitude"], hit["longitude"])
    level = {"street-level": 8, "locality-level": 6,
             "city-level": 4, "district-level": 3}[hit["precision"]]
    return {
        "location": hit,
        "digipin": code,
        "digipin_at_precision": digipin.truncate(code, level),
        "note": f"coordinates are {hit['precision']} ({hit['source']})",
    }


def _pipeline(address: str, hints: dict | None = None, rec_id=None) -> dict:
    """The whole Layer 0-3 pipeline for one string: parse -> hints -> score
    -> pincode check -> geocode + DIGIPIN -> plain-language verdict.
    Shared by /parse (typed input) and /stt/parse (spoken input)."""
    hints = hints or {}
    p = parse(address).as_dict()
    hints_used = []
    for k in ("pincode", "city", "district", "state"):
        v = hints.get(k)
        if not v:
            continue
        v = str(v).strip()
        if not p.get(k):
            p[k] = v
            hints_used.append(k)
        elif k == "city" and p["city"].lower() != v.lower():
            # parser sometimes files a locality (e.g. "Itwari") as the city;
            # the caller's city column is authoritative context. Keep the
            # string's own word -- demote it to locality -- and use the hint.
            if not p.get("locality"):
                p["locality"] = p["city"]
            p["city"] = v
            hints_used.append(k)
    pc = pincode_dir.validate(p)
    dl = score(p)
    geo = _geo_digipin(p, address, inferred=pc.get("inferred"))

    # Plain-language verdict. Composed, not templated-scary: say what checks
    # out (city/pincode agree), what is missing and why that blocks delivery,
    # and the single highest-value field to collect. Every extractable field
    # is returned either way.
    precise = bool(geo.get("location")) and geo["location"]["precision"] == "street-level"
    if precise and dl.get("band") != "high":
        status, message = "ok", "Address parsed, validated and located."
    else:
        status = "partial"
        parts = []
        # 1 -- what level the address IS good to
        if not geo.get("location"):
            parts.append("The address could not be placed on the map.")
        else:
            level = geo["location"]["precision"].removesuffix("-level")
            parts.append(f"The address is valid at the {level} level but is not "
                         "precise enough for reliable delivery.")
        # 2 -- acknowledge what is consistent, then name what is missing
        good = []
        conflicts = pc.get("conflicts") or []
        if pc.get("exists") and not conflicts:
            agreed = [n for n, k in (("city", "city_consistent"),
                                     ("state", "state_consistent")) if pc.get(k) is True]
            good.append(f"the pincode is consistent with the stated {' and '.join(agreed)}"
                        if agreed else "the pincode is valid")
        missing = []
        if not p.get("house_number"):
            missing.append("the house/flat/door number is missing")
        if not p.get("locality") and not p.get("building"):
            missing.append("no locality or building name is available")
        if good and missing:
            parts.append(f"{good[0].capitalize()}; however, {' and '.join(missing)}.")
        elif good:
            parts.append(f"{good[0].capitalize()}.")
        elif missing:
            parts.append(f"{' and '.join(missing).capitalize()}.")
        if conflicts:
            parts.append("Directory check: " + " ".join(conflicts))
        # 3 -- landmarks help but don't pinpoint a door
        if p.get("landmarks") and not p.get("house_number"):
            parts.append("Landmarks provide additional context but are not "
                         "sufficient to uniquely identify the destination.")
        # 4 -- the one field that most improves it
        ask = (dl.get("ask_for") or {}).get("label")
        if ask:
            parts.append(f"Adding the {ask.lower()} would substantially "
                         "improve deliverability.")
        message = " ".join(parts)
    out = {"status": status, "message": message,
           **p, "deliverability": dl, "pincode_check": pc, **geo}
    if hints_used:
        out["hints_used"] = hints_used
    if rec_id is not None:
        out["id"] = rec_id
    return out


@app.post("/parse")
def api_parse(body: ParseIn):
    """Unstructured address (any script) -> structured components +
    deliverability + pincode check + lat/lon + DIGIPIN (geocoder-derived).

    Optional hint fields (pincode/city/district/state) fill what the string
    doesn't state. `status` + `message` say plainly how usable the result
    is and what single field would most improve it.
    """
    hints = {k: getattr(body, k) for k in ("pincode", "city", "district", "state")}
    return _pipeline(body.address, hints, body.id)


@app.post("/compare")
def api_compare(body: CompareIn):
    with ThreadPoolExecutor(max_workers=2) as ex:
        pa, pb = list(ex.map(lambda s: parse(s).as_dict(), [body.a, body.b]))
    return {"a": pa, "b": pb, "result": compare(pa, pb)}


@app.post("/batch")
def api_batch(body: BatchIn):
    with ThreadPoolExecutor(max_workers=6) as ex:
        parsed = list(ex.map(lambda s: parse(s).as_dict(), body.addresses))
    ids = cluster(parsed)
    for p, c in zip(parsed, ids):
        p["cluster"] = c
        p["deliverability"] = score(p)
    n_dupes = len(parsed) - len(set(ids))

    members_of: dict[int, list[int]] = {}
    for idx, c in enumerate(ids):
        members_of.setdefault(c, []).append(idx)
    golden = []
    for c, members in sorted(members_of.items()):
        g = canonical([parsed[i] for i in members])
        g["cluster"] = c
        g["members"] = members          # indexes into `parsed`
        golden.append(g)

    return {
        "parsed": parsed,
        "clusters": ids,
        "unique_locations": len(set(ids)),
        "duplicates_collapsed": n_dupes,
        "golden_records": golden,
        "deliverability": score_batch(parsed),
    }


@app.get("/real")
def api_real():
    """Real Indian addresses -- Razorpay's open IFSC dataset, pre-parsed.

    Not synthetic. Source: github.com/razorpay/ifsc (182,758 bank branches).
    """
    records = _real()
    if not records:
        return {"records": [], "source": None}
    records.sort(key=lambda r: -r["score"]["risk"])
    return {
        "records": records,
        "source": "Razorpay open IFSC dataset (github.com/razorpay/ifsc)",
        "count": len(records),
    }


class DigipinEncodeIn(BaseModel):
    latitude: float = Field(ge=digipin.MIN_LAT, le=digipin.MAX_LAT)
    longitude: float = Field(ge=digipin.MIN_LON, le=digipin.MAX_LON)


class DigipinDecodeIn(BaseModel):
    digipin: str = Field(min_length=10, max_length=13)


@app.post("/digipin/encode")
def api_digipin_encode(body: DigipinEncodeIn):
    """Coordinates -> DIGIPIN. The algorithm half of Layer 3.

    Text -> DIGIPIN needs a geocoder, which is not in the loop yet.
    """
    return {"digipin": digipin.encode(body.latitude, body.longitude)}


@app.post("/digipin/decode")
def api_digipin_decode(body: DigipinDecodeIn):
    try:
        d = digipin.decode(body.digipin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"digipin": digipin.canonical(body.digipin), **d}


class DigipinNeighborsIn(BaseModel):
    digipin: str = Field(min_length=1, max_length=13)


@app.post("/digipin/neighbors")
def api_digipin_neighbors(body: DigipinNeighborsIn):
    """Nearest DIGIPINs: the adjacent cells around a code or prefix."""
    try:
        return digipin.neighbors(body.digipin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class DigipinGroupItem(BaseModel):
    id: str | int | None = None
    latitude: float | None = None
    longitude: float | None = None
    digipin: str | None = Field(default=None, max_length=13)


class DigipinGroupIn(BaseModel):
    level: int = Field(default=7, ge=1, le=10)
    points: list[DigipinGroupItem] = Field(min_length=1, max_length=5000)


@app.post("/digipin/group")
def api_digipin_group(body: DigipinGroupIn):
    """Bucket points into DIGIPIN grid cells (6 ~ 1km, 7 ~ 250m, 8 ~ 60m).

    Spatial consolidation: orders in one cell ride in one batch. Needs
    coordinates or DIGIPINs -- text addresses must be geocoded first, which
    Lattice does not do. Malformed items are returned in `rejected`.
    """
    items = [p.model_dump(exclude_none=True) for p in body.points]
    return digipin.group(items, body.level)


class DigipinFromAddressIn(BaseModel):
    address: str = Field(min_length=3, max_length=500)


@app.post("/digipin/from-address")
def api_digipin_from_address(body: DigipinFromAddressIn):
    """Text -> DIGIPIN, via the pluggable geocoder adapter (OSM Nominatim).

    Completes the Layer 3 bridge -- with the geocoder's limits surfaced,
    not hidden: `precision` is street/locality/city-level, and the code is
    truncated to match, so a locality fix never masquerades as a 4m cell.
    """
    from server.lattice import geocoder
    try:
        hit = geocoder.geocode(body.address)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"geocoder unreachable: {exc}")
    if hit is None:
        raise HTTPException(status_code=404,
                            detail="geocoder found nothing for this address")
    try:
        code = digipin.encode(hit["latitude"], hit["longitude"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # honest cell size: locality fix -> level-6 (~1 km); street -> 8 (~60 m)
    level = {"street-level": 8, "locality-level": 6, "city-level": 4}[hit["precision"]]
    truncated = digipin.truncate(code, level)
    return {
        "address": body.address,
        "geocoder": hit,
        "digipin": code,
        "digipin_at_precision": truncated,
        "cell": digipin.cell(truncated),
        "caveat": (f"Coordinates are {hit['precision']} from "
                   f"{hit['source']}; the full 10-symbol code implies more "
                   "precision than the geocoder provides."),
    }


@app.post("/stt")
async def api_stt(request: Request):
    """Spoken address -> text (Sarvam Saaras, language auto-detect).

    Raw audio bytes in the body (audio/webm from MediaRecorder) -- same
    no-multipart convention as /jobs/csv.
    """
    audio = await request.body()
    if not audio or len(audio) < 100:
        raise HTTPException(status_code=422, detail="empty audio body")
    if len(audio) > 10_000_000:
        raise HTTPException(status_code=413, detail="audio too large (10 MB max)")
    try:
        return sarvam.transcribe(audio, request.headers.get("content-type", "audio/webm"))
    except ValueError as exc:
        # bad AUDIO, not a bad service: say so, with the fix
        raise HTTPException(status_code=422, detail=(
            f"{exc} — send a complete audio file (wav/mp3/ogg/webm/m4a) as the "
            "raw request body with a matching Content-Type; a truncated or "
            "headerless recording cannot be decoded."))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"stt failed: {exc}")


@app.post("/stt/parse")
async def api_stt_parse(request: Request):
    """Spoken address -> structured JSON, one call.

    Raw audio in the body (mp3, wav, webm/opus from a live mic recording --
    any format Saaras accepts; set Content-Type accordingly). The transcript
    runs through the full pipeline, so the response is the /parse contract
    plus `transcript` / `spoken_language`.
    """
    audio = await request.body()
    if not audio or len(audio) < 100:
        raise HTTPException(status_code=422, detail="empty audio body")
    if len(audio) > 10_000_000:
        raise HTTPException(status_code=413, detail="audio too large (10 MB max)")
    try:
        heard = sarvam.transcribe(audio, request.headers.get("content-type", "audio/webm"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=(
            f"{exc} — send a complete audio file (wav/mp3/ogg/webm/m4a) as the "
            "raw request body with a matching Content-Type; a truncated or "
            "headerless recording cannot be decoded."))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"stt failed: {exc}")
    transcript = (heard.get("transcript") or "").strip()
    if len(transcript) < 3:
        return {"status": "error",
                "message": "Could not hear an address in the audio -- it came "
                           "back empty. Speak the full address clearly, or "
                           "check the recording.",
                "transcript": transcript,
                "spoken_language": heard.get("language_code")}
    out = _pipeline(transcript)
    return {"transcript": transcript,
            "spoken_language": heard.get("language_code"),
            "language_probability": heard.get("language_probability"),
            **out}


_EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "examples")


@app.get("/examples")
def api_examples_list():
    """Runnable quickstart scripts, served verbatim from the repo."""
    try:
        names = sorted(f for f in os.listdir(_EXAMPLES_DIR)
                       if f.endswith((".py", ".sh")))
    except OSError:
        names = []
    return {"examples": names, "fetch": "/examples/{name}  (plain text)"}


@app.get("/examples/{name}")
def api_example_file(name: str):
    """One example file, plain text — the docs pages render this directly,
    so the documentation is always the exact code in the repo."""
    from fastapi.responses import PlainTextResponse
    if "/" in name or ".." in name or not name.endswith((".py", ".sh")):
        raise HTTPException(status_code=404, detail="no such example")
    path = os.path.join(_EXAMPLES_DIR, name)
    try:
        with open(path, encoding="utf-8") as fh:
            return PlainTextResponse(fh.read())
    except OSError:
        raise HTTPException(status_code=404, detail="no such example")


@app.get("/pincode/{pin}")
def api_pincode(pin: str):
    """Offline postal-directory lookup (GeoNames, CC-BY)."""
    entry = pincode_dir.lookup(pin)
    if entry is None:
        return {"pincode": pin, "exists": False}
    return {"pincode": pin, "exists": True,
            "state": entry["state"], "district": entry["district"],
            "areas": entry["areas"]}


# ---------------------------------------------------------------- signups
# Traction ledger: who asked for a key, and who actually used it. Kept above
# Neon's appended section per tasklist.md convention.  -- Argon
from server import users as userstore                       # noqa: E402

USERS_BACKEND = userstore.init()


class SignupIn(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    name: str = Field(default="", max_length=80)
    company: str = Field(default="", max_length=80)
    use_case: str = Field(default="", max_length=200)


@app.post("/signup")
def api_signup(body: SignupIn):
    """Self-service: email in, working API key out. Shown once."""
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="a valid email is required")
    key = _mint_key()
    rec = userstore.add_signup(email, body.name.strip(), body.company.strip(),
                               body.use_case.strip(), key)
    if rec.get("returning") and rec.get("api_key"):
        key = rec["api_key"]            # same email -> same key, not a new one
    with _KEYS_LOCK:
        _KEYS[key[:9] + "\u2026" + key[-4:]] = {
            "name": body.name.strip() or email, "created": _t.strftime("%Y-%m-%dT%H:%M:%S")}
        _save_keys()
    return {"api_key": key, "email": email, "returning": rec.get("returning", False),
            "usage": "send header 'X-API-Key: <key>' (or ?key=<key>)",
            "docs": "/docs", "quickstart": "/examples"}


@app.get("/stats")
def api_stats():
    """Public traction counters. Signups are interest; calls are use."""
    return {**userstore.stats(), "storage": USERS_BACKEND}


# ======================================================================
# Neon: reference-corpus matching + async batch jobs.
# Appended section by agreement (see tasklist.md) -- keep new Xenon
# endpoints ABOVE this line so parallel edits don't collide.
# ======================================================================

from fastapi import HTTPException, Request                    # noqa: E402
from fastapi.responses import PlainTextResponse               # noqa: E402

from server import jobs as jobstore                           # noqa: E402
from server.lattice.matcher import AddressIndex               # noqa: E402

INDEX = AddressIndex()
for _rec in _real():
    if _rec.get("parsed") and not _rec["parsed"].get("error"):
        INDEX.add(_rec["parsed"], meta={"id": _rec.get("id"), "bank": _rec.get("bank"),
                                        "source": "real_sample"})

_SEED_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parsed_cache.json")
try:
    with open(_SEED_CACHE) as _fh:
        jobstore.warm_cache(json.load(_fh))
except (FileNotFoundError, json.JSONDecodeError):
    pass


class MatchIn(BaseModel):
    address: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class CorpusIn(BaseModel):
    addresses: list[str] = Field(min_length=1, max_length=40)


class JobIn(BaseModel):
    addresses: list[str] = Field(min_length=1, max_length=jobstore.MAX_ADDRESSES)
    label: str = Field(default="", max_length=80)


@app.post("/match")
def api_match(body: MatchIn):
    """Does this incoming address match anything already in the corpus?"""
    p = parse(body.address).as_dict()
    return {
        "query": p,
        "matches": INDEX.match(p, top_k=body.top_k),
        "corpus": INDEX.stats(),
    }


@app.post("/corpus")
def api_corpus_add(body: CorpusIn):
    with ThreadPoolExecutor(max_workers=6) as ex:
        parsed = list(ex.map(lambda s: parse(s).as_dict(), body.addresses))
    ids = [INDEX.add(p, meta={"source": "api"}) for p in parsed if not p.get("error")]
    return {"added": len(ids), "corpus_ids": ids,
            "parse_errors": len(parsed) - len(ids), "corpus": INDEX.stats()}


@app.get("/corpus")
def api_corpus_stats():
    return INDEX.stats()


@app.post("/jobs")
def api_job_submit(body: JobIn):
    try:
        job = jobstore.submit(body.addresses, label=body.label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return job.public()


@app.post("/jobs/csv")
async def api_job_submit_csv(request: Request, label: str = ""):
    """Raw CSV in the request body (text) -- no multipart, no extra deps."""
    text = (await request.body()).decode("utf-8", errors="replace")
    addresses = jobstore.addresses_from_csv(text)
    try:
        job = jobstore.submit(addresses, label=label)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return job.public()


@app.get("/jobs")
def api_jobs_list():
    return {"jobs": jobstore.list_jobs()}


@app.get("/jobs/{job_id}")
def api_job_status(job_id: str):
    job = jobstore.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such job")
    return job.public()


@app.get("/jobs/{job_id}/results")
def api_job_results(job_id: str, format: str = "json"):
    job = jobstore.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no such job")
    if job.status != "done":
        raise HTTPException(status_code=409, detail=f"job is {job.status}")
    if format == "csv":
        return PlainTextResponse(jobstore.results_csv(job), media_type="text/csv")
    return job.public(with_result=True)


# ----------------------------------------------------------------------
# Remote MCP: the same 7 tools, served over streamable HTTP at {api}/mcp.
# No local checkout needed -- register with just the URL and an API key:
#   claude mcp add --transport http lattice \
#     https://lattice-api-fs5f.onrender.com/mcp \
#     --header "X-API-Key: <ltk_key>"
# The existing key middleware guards /mcp like any other endpoint; the MCP
# tools then call this same server over loopback with the master key.
# ----------------------------------------------------------------------

import contextlib                                             # noqa: E402

# lattice_mcp reads LATTICE_API at import: point it at THIS process
# (Render binds $PORT; locally the default 8077 is already right).
os.environ.setdefault("LATTICE_API", f"http://127.0.0.1:{os.environ.get('PORT', '8077')}")
from server.lattice_mcp import mcp as _lattice_mcp            # noqa: E402

# Mounted at root with the MCP app's own /mcp route (a prefix mount would
# 307-redirect "/mcp" -> "/mcp/", which MCP clients don't follow on POST).
# Last route, so it only sees paths nothing above matched.
app.mount("/", _lattice_mcp.streamable_http_app())


@contextlib.asynccontextmanager
async def _mcp_lifespan(app):
    # FastMCP's session manager must be running for the mounted app to
    # serve; Starlette does not run a sub-app's lifespan on its own.
    async with _lattice_mcp.session_manager.run():
        yield

app.router.lifespan_context = _mcp_lifespan
