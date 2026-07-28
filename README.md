# Lattice — Indian Address Intelligence

Lattice is an address-intelligence API for Indian addresses. It parses
unstructured address text in the 23 languages Sarvam supports — 13 scripts,
from Devanagari and Tamil to Gurmukhi and Perso-Arabic, plus romanised and
code-mixed text like Hinglish — into structured components, validates them
against an offline postal directory, and returns coordinates and a DIGIPIN
where the address can be located. It can also compare two addresses to decide whether
they refer to the same location, deduplicate a batch into one merged record
per location, and score delivery risk. When an address cannot be fully
resolved, the response says so: `status: partial`, the fields that were
extracted, and a message stating what is missing.

Legacy CRMs can use it to parse and clean the addresses they already hold,
through the batch API. New systems can use it in their forms — `/parse`
behind the address field, or `/stt/parse` for spoken input.

Parsing uses Sarvam `sarvam-105b`, once per address. Resolution, scoring,
clustering and validation are deterministic Python, evaluable offline.

- **API** `https://lattice-api-fs5f.onrender.com` · OpenAPI at `/docs`
- **Console** `https://lattice-labs.vercel.app`
- **MCP** `https://lattice-api-fs5f.onrender.com/mcp`

## Architecture

```
raw string ──► L0 parse    sarvam-105b + LID + transliteration → ParsedAddress
                 ├───────► L1 resolve  compare / cluster / block / match / golden
                 ├───────► L2 score    risk + reasons + ask_for
                 └───────► L3 locate   pincode directory · geocoder → DIGIPIN
```

**Resolution invariant:** coarse signals (pincode, city, locality) gate; fine
signals (house number, building, landmarks, street) score. Locality agreement
alone spans tens of thousands of households, so without door-level evidence
the score is capped at 0.50. Hard vetoes: pincode mismatch, house-number
mismatch, uncorroborated locality mismatch. Cluster threshold 0.75.

### Server modules (`server/`)

| Module | Function |
|---|---|
| `lattice/parser.py` | L0 extraction via `sarvam-105b`: 13 components + landmarks array `{name, relation}` (behind/opposite/near/beside/above/below, keyword table across scripts). Prompt rules: never invent a city, never respell proper nouns. Deterministic fallbacks: landmark recovery from raw segments, transliteration of any field left in native script. |
| `lattice/resolver.py` | L1 pairwise comparison and single-link clustering. Stdlib only. |
| `lattice/matcher.py` | Multi-key blocking (pincode + locality tokens) — O(n²) reduced to shared-key pairs, verified identical clusters; `AddressIndex` for corpus matching. |
| `lattice/golden.py` | Golden records: per-component majority vote, completeness tie-breaks, pooled landmarks, per-field provenance, canonical writeback string. |
| `lattice/scorer.py` | L2 rule-based risk; `ask_for` computed by re-scoring with the missing field filled in. |
| `lattice/pincode.py` | Offline directory, 19,238 pincodes (GeoNames India, CC-BY 4.0): existence, state/city consistency (script-aware: unreadable values are unverifiable, not conflicts), verifiable inference of missing state/district. |
| `lattice/digipin.py` | India Post DIGIPIN grid (verified against the published reference vector): encode, decode, cell bounds, truncate, neighbors, group. Pure arithmetic. |
| `lattice/geocoder.py` | Pluggable adapter (default OSM Nominatim, cached, 1 req/s): segment-drop retry, precision labels (street/locality/city-level), match verification that demotes fuzzy hits. |
| `lattice/sarvam.py` | Sarvam client: chat, LID, transliteration, STT. |
| `lattice_mcp.py` | MCP server, 7 tools, stdio + streamable HTTP (stateless, host-allowlisted, async). |
| `jobs.py` | Async batch jobs: background execution, raw-string parse cache, deduped parsing, blocked clustering, CSV in/out (raw body, no multipart). |
| `users.py` | Accounts + usage, Postgres (JSON fallback): signups, per-account keys with labels/revocation ledger, per-key/endpoint/day metering. |
| `app.py` | FastAPI: auth + metering middleware, 31 endpoints, MCP mount. |

### Sarvam usage

| Capability | Sarvam API | Where |
|---|---|---|
| Address parsing | `sarvam-105b` chat completions — 23 languages, 13 scripts | `parser.py` — the full extraction schema is the system prompt |
| Language/script ID | Text LID | `parser.py` |
| Latin canonicalisation | Transliterate | `parser.py` fallback — resolver/directory/geocoder always see Latin |
| Speech → address | Saaras `saaras:v3` — 23 languages, auto-detect | `/stt`, `/stt/parse` |

## HTTP API

31 endpoints. Auth: `X-API-Key` header (or `?key=`) on all except
`/health`, `/docs`, `/signup`, `/stats`, `/examples/*`.

| Group | Endpoints |
|---|---|
| Pipeline | `POST /parse` (components + risk + `pincode_check` + location + `digipin_at_precision` + composed status/message; optional DB hints `id/pincode/city/district/state`) · `POST /compare` · `POST /batch` (≤40, golden records) |
| Batch | `POST /jobs` (≤5000, async) · `POST /jobs/csv` (raw CSV body) · `GET /jobs`, `/jobs/{id}`, `/jobs/{id}/results?format=json|csv` |
| Matching | `POST /match` (top-k vs corpus) · `POST/GET /corpus` |
| Location | `GET /pincode/{pin}` · `POST /digipin/encode`, `/decode`, `/from-address`, `/neighbors`, `/group` (≤5000 points, level 6 ≈ 1 km / 7 ≈ 250 m) |
| Speech | `POST /stt` (raw audio ≤10 MB → transcript) · `POST /stt/parse` (audio → full parse contract) |
| Keys & accounts | `POST /keys` (self-service, shown once) · `GET /keys` (master) · `POST /signup` · `POST/GET/DELETE /account/keys` · `GET /account/usage` · `GET /stats` |
| Misc | `GET /health` · `GET /real` · `GET /examples/{name}` |

**Auth model:** keys are stateless HMAC tokens (`ltk_<rand><hmac>`), signed
against a master secret — valid on any deployment sharing the secret, no key
database. Account endpoints are master-key-only; the console's server-side
routes are the only callers and take the account email from the signed
session, never from the browser.

**Metering:** middleware records each successful authenticated call per key
prefix, per endpoint, per day (Postgres `usage` / `usage_daily`).

## MCP

Seven tools mirroring the REST API 1:1: `parse_address`, `compare_addresses`,
`dedupe_batch`, `match_address`, `check_pincode`, `digipin_encode`,
`digipin_decode`. Text→DIGIPIN is not offered — DIGIPIN tools take
coordinates only.

```bash
# hosted (no checkout)
claude mcp add --transport http lattice \
  https://lattice-api-fs5f.onrender.com/mcp \
  --header "X-API-Key: <ltk_key>"

# local stdio
claude mcp add lattice \
  --env LATTICE_API=<api-url> --env LATTICE_KEY=<ltk_key> \
  -- python -m server.lattice_mcp
```

## Console (`client/`, Next.js 15 / React 19)

Google sign-in (NextAuth). Views: Extract, Compare, Deduplicate (CSV →
clusters + golden records), Score, Group-by-DIGIPIN (map); REST API tester,
Speech→JSON (mic + file), MCP setup, API keys (mint/label/revoke, shown-once),
Usage (30-day calls, per-endpoint, daily series, per-key), Documentation.
Responsive to phone widths; backend repointable via `?api=<url>&key=<key>`.

`examples/` — stdlib-only scripts, verified against the deployed API:
`createkey.sh`, `usage.py` (`/parse`), `stt.py` (`/stt/parse`).

## Evaluation

Offline regression via `server/eval.py` and `server/eval_real.py`.

| Set | Size | P | R | F1 |
|---|---|---|---|---|
| Hand-built seed | 20 records / 190 pairs | 1.000 | 1.000 | 1.000 |
| Real IFSC pairs, human-labelled | 36 pairs | 1.000 | 0.625 | 0.769 |
| Raw string similarity (best threshold) | 36 pairs | 0.625 | 0.625 | 0.625 |

Provenance: the seed set is hand-built and tuned to itself. The real addresses
are unmodified (Razorpay open IFSC dataset, 182,758 branches); the labels are
ours, by inspection — shared MICR codes are not reliable ground truth (10 of
18 shared-MICR pairs are different buildings). Precision 1.000 = no false
merges on either set.

DIGIPIN precision: the grid algorithm is exact; the geocoder is not. Results
carry a `precision` label and `digipin_at_precision` truncates the code to the
cell size the fix supports.

## Data

- `data/pincode_dir.json.gz` — 19,238-pin directory, built by `data/pincodes.py`.
- `data/real_sample.json` / `real_pairs_raw.json` / `labels.py` — real IFSC
  addresses, pre-parsed, with labelled pairs.
- `data/seed.py` — 20-record multilingual seed with ground truth.
- `server/parsed_cache.json` — cached parses; evals run offline.

## Run

```bash
# API (http://127.0.0.1:8077) — SARVAM_API_KEY in .env
env/bin/python3 -m uvicorn server.app:app --reload --port 8077

# console (http://localhost:3000)
cd client && npm run dev

# regression
env/bin/python3 server/eval.py
env/bin/python3 server/eval_real.py
```

Push to `main` deploys automatically: API → Render, console → Vercel,
accounts/usage → Postgres.
