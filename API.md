# Lattice API — integration contract

Base URL: `http://127.0.0.1:8077` (local) · `https://lattice-api-96cn.onrender.com` (hosted)

Sample DB to test with: [`data/sample_input.json`](data/sample_input.json) — 12
unstructured records (English, Hinglish, Devanagari), real Razorpay IFSC strings
plus multi-script examples.

Ready-made scripts (stdlib only, nothing to install):
[`examples/createkey.sh`](examples/createkey.sh) mints a key and prints the
export line; [`examples/usage.py`](examples/usage.py) runs `/parse`,
`/compare` and an async CSV dedupe job end to end. Both honour `LATTICE_API`
(base URL) and `LATTICE_KEY` (usage.py mints one if absent).

## 1. Authentication — generate your own key

Every engineer mints their own key. It is **shown once** — copy it immediately;
afterwards only a masked form (`ltk_518e2*****`) appears anywhere:

```bash
curl -s -X POST https://lattice-api-96cn.onrender.com/keys \
  -H 'Content-Type: application/json' \
  -d '{"name": "your-name"}'
# -> {"api_key": "ltk_…", "shown_once": true}
export LATTICE_KEY=ltk_…
```

Send it on every request as the `X-API-Key` header (or `?key=<key>`).
Missing/invalid/tampered key → `401`.

Keys are **stateless**: HMAC-signed against the server's master secret
(`LATTICE_API_KEY`, set in `.env` locally and in the Render dashboard for the
hosted API). The same key works on localhost, Render, and every replica, and
survives restarts — there is no key database to lose. Rotating the master
secret revokes all issued keys at once.

## 2. Core call — unstructured address in, structured JSON out

**`POST /parse`** — input, any language/script. Only `address` is required;
the optional fields are context your database likely already has in separate
columns — they fill what the string doesn't state (never overriding it) and
sharply improve geocoding:

```json
{
  "address": "गणेश मंदिराच्या मागे, निळा गेट, कोथरूड, पुणे ४११०३८",
  "id": "rec-10",
  "pincode": "411038",
  "city": "Pune",
  "state": "Maharashtra"
}
```

Every response opens with a plain-language verdict — the API always returns
everything it could extract, and says what's missing when that isn't enough:

```json
{ "status": "partial",
  "message": "Not enough information for a confident result: the address located only at locality-level; high delivery-failure risk. Every extractable field is returned; the single most valuable addition would be: House / flat / door number." }
```

`status` is `ok` (parsed, validated, street-level fix) or `partial`. Location
falls back gracefully: OSM geocode of the canonical parsed fields → raw
string → pincode-directory district centroid (labelled `district-level`) —
so any record with a real pincode always gets *some* lat/long + DIGIPIN,
truncated to its honest precision.

```bash
curl -s -X POST http://127.0.0.1:8077/parse \
  -H 'Content-Type: application/json' -H "X-API-Key: $KEY" \
  -d '{"address": "गणेश मंदिराच्या मागे, निळा गेट, कोथरूड, पुणे ४११०३८"}'
```

Response (abridged — every field always present, `null` when absent from input):

```json
{
  "house_number": null,
  "floor": null,
  "building": null,
  "street": null,
  "sublocality": null,
  "locality": "Kothrud",
  "post_office": null,
  "city": "Pune",
  "district": null,
  "state": "Maharashtra",
  "pincode": "411038",
  "landmarks": [ { "name": "Ganesh Mandir", "relation": "behind" } ],
  "visual_descriptor": "blue gate",
  "occupant": null,
  "deliverability": { "risk": 0.55, "band": "medium",
                      "reasons": ["No house or flat number …"],
                      "ask_for": "house_number",
                      "will_likely_need_call": true },
  "pincode_check": { "exists": true, "state_consistent": true },
  "location": { "latitude": 18.5072618, "longitude": 73.8056676,
                "precision": "street-level",
                "matched_query": "Kothrud, Pune, Maharashtra, 411038",
                "source": "osm-nominatim" },
  "digipin": "4FP-4CK-5L65",
  "digipin_at_precision": "4FP-4CK-5L",
  "note": "coordinates are street-level (osm-nominatim)"
}
```

Field notes:
- Structured components are **canonical Latin** regardless of input script;
  proper nouns are never respelled beyond casing, and a city is never invented
  if it isn't in the input.
- `location` + `digipin` come from a geocoder (OSM Nominatim). `precision` is
  honest: `street-level` / `locality-level` / `city-level`.
  `digipin_at_precision` truncates the code to match — use it, not the full
  code, unless you have building-level coordinates of your own.
- If the geocoder is unreachable or finds nothing, `location`/`digipin` are
  `null` and `note` says why — parsing still succeeds.

## 3. Batches and whole DBs

**`POST /batch`** (≤40 — parse + dedupe clusters + golden records + risk):

```json
{ "addresses": ["MADHAVLEELA COMPLEX, 1ST FLOOR, MASKASATH SQUARE, ITWARI",
                "1ST FLOOR, MADHAVLEELA COMPLEX, MASKASATH SQUARE, ITWARI NAGPUR"] }
```

Returns `parsed[]`, `clusters[]` (same id = same physical door),
`golden_records[]` (one merged record per cluster) and `deliverability`.

**`POST /jobs`** (≤5000, async) → `{"id": …}`; poll `GET /jobs/{id}` until
`"status": "done"`, fetch `GET /jobs/{id}/results` (add `?format=csv` for CSV).

Run the sample DB through `/parse` one record at a time:

```bash
jq -c '.records[]' data/sample_input.json | while read -r rec; do
  curl -s -X POST http://127.0.0.1:8077/parse \
    -H 'Content-Type: application/json' -H "X-API-Key: $KEY" \
    -d "$(jq -c '{address}' <<< "$rec")"
done
```

## 4. Other endpoints (same auth)

| Endpoint | In → Out |
|---|---|
| `POST /compare` | `{a, b}` → same-door verdict with per-signal evidence |
| `POST /match` | `{address}` → matches against the seen-address corpus |
| `POST /digipin/from-address` | `{address}` → geocode + DIGIPIN (no LLM parse) |
| `POST /digipin/encode` | `{latitude, longitude}` → `{digipin}` |
| `POST /digipin/decode` | `{digipin}` → cell centre + bounds |
| `POST /digipin/group` | points → grid-cell delivery batches |
| `POST /stt` | raw audio body (webm/wav) → `{transcript, language_code}` |
| `GET /pincode/{pin}` | offline postal-directory lookup |
| `GET /health` | no auth — liveness + record count |

Interactive docs: `http://127.0.0.1:8077/docs`.
