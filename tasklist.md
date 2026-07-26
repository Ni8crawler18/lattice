# Lattice — Task List

Maintained by **Xenon**, **Neon** and **Argon** (AI pairs on this repo). Status: `[ ]` todo · `[~]` in progress · `[x]` done.
Claim a task by moving it into your sprint section before touching code. Shared files: `server/app.py` (Neon appends a marked section at the END of the file only), `CLAUDE.md`, this file.

## ⚠ RUNNING SERVERS — read before touching any process

**Argon owns process lifecycle.** Exactly one of each runs, started by Argon:
- API: `uvicorn server.app:app --reload --port 8077` — **`--reload` is on**: your
  server-code edits hot-load automatically. You never need to restart it.
- Client: `next dev -p 3000` — HMR hot-loads client edits. Never start a second
  instance: two `next dev` share `client/.next` and corrupt each other
  (routes-manifest ENOENT → 500s on every route). This already bit us.

**Do NOT kill/start either process.** If one looks down or truly needs a restart,
write a line HERE and let Argon cycle it.

- 12:57 **Neon cycled `next dev`** (user-reported breakage, user present and blocked):
  `.next` was corrupt/stale — CSS chunk `/_next/static/css/app/layout.css` 404'd (naked
  HTML) and stale webpack chunks threw `a[d] is not a function` on /dashboard. Killed
  next dev, `rm -rf client/.next`, restarted `next dev -p 3000` (log:
  Neon scratchpad `nextdev.log`). Verified: page + CSS 200, /dashboard and /docs compile.
  API server untouched.

- **Neon → Argon:** at the user's direct request I made one edit in your territory —
  `client/app/dashboard/page.jsx`: split `AgentsView` into UI vs docs. "Agents & API"
  keeps ApiTester + stats row; the doc blocks (links statgrid, MCP tool reference,
  register/config, verified calls) moved to a new `DocsView` behind a new sidebar item
  **Documentation** (new `I.docs` icon; also added the missing `I.mcp` so the Agents nav
  item finally shows its icon). `/docs` route untouched.

**No `next build`/`next start` until final freeze.** A production build at 11:05 froze
the bundle seconds before an edit and silently killed HMR — the console ran stale code.
Argon does ONE production build as the last step before the demo, after code freeze.

## Sprint: 2026-07-26 — Xenon, "the first three"

- [x] **1. DIGIPIN encoder/decoder** — `server/lattice/digipin.py`
  - Official India Post grid algorithm (verified against `INDIAPOST-gov/digipin` technical doc: 4×4 anticlockwise-spiral labelling, bounds 2.5–38.5°N / 63.5–99.5°E): `encode(lat, lon) -> "XXX-XXX-XXXX"`, `decode(code) -> cell centre + bounds`, `canonical(code)`. Pure arithmetic, no API.
  - Verified: reference vector `(28.6139, 77.209) → 39J-438-TJC7` + 500 random round-trips.
  - Endpoints live: `POST /digipin/encode {latitude, longitude}` → `{digipin}`; `POST /digipin/decode {digipin}` → `{digipin, latitude, longitude, bounds}` (422 on bad code).
  - Claims discipline: this is the *algorithm* half of Layer 3. Text → DIGIPIN still needs a geocoder; do not claim it.

- [x] **2. Pincode directory validation** — `server/lattice/pincode.py` + `data/pincode_dir.json.gz`
  - Offline directory built from GeoNames IN postal dump (CC-BY 4.0): 19,238 pincodes → state, district, served areas; 1.0 MB gz. Builder: `data/pincodes.py` (regen instructions in docstring).
  - `lookup(pincode)` and `validate(parsed)` → exists / state-consistent / city-consistent / locality hint + verifiable state/district inference (lookup, never a guess). Degrades gracefully if the data file is absent.
  - Wired into `scorer.py` (nonexistent pin +0.15, pin↔city/state conflict +0.12; only fires on well-formed 6-digit pins so `_ask_for` probes stay undistorted), `/parse` response (`pincode_check`), and `GET /pincode/{pin}`.
  - CAVEAT found & handled: GeoNames India lat/lons are district-level centroids, NOT pincode locations (560076 → 13.23°N, ~30 km off). Kept in the data file, deliberately NOT exposed by `validate()` — do not resurface as "pincode location" without a better source.
  - Deliberately NOT wired into `resolver.py` — coarse-gate changes move the eval numbers; do separately with a threshold sweep.

- [x] **3. Golden-record synthesis** — `server/lattice/golden.py`
  - `canonical(members)`: majority vote per component on `resolver._canon` keys, tie-break by member completeness, longest string wins in-group; landmarks pooled + deduped, specific relation beats None; per-field provenance `{value, sources, agreement, contested}`.
  - `format_address(components)` — ordered writeback string (door → landmark → area → routing).
  - Wired into `/batch`: `golden_records` = one entry per cluster with `cluster`, `members` (indexes into `parsed`), `components`, `provenance`, `canonical_text`, `completeness`, `contested_fields`.

- [x] **4. Group-by-DIGIPIN** — `server/lattice/digipin.py` + `POST /digipin/group` (Xenon)
  - `truncate(code, level)`, `cell(code)` (bounds/centre/size for any 1–10-symbol prefix), `format_code()`, `group(items, level)`: bucket points (lat/lon or existing DIGIPINs) into grid cells at a chosen level (6 ≈ 1 km, 7 ≈ 250 m, 8 ≈ 60 m) — delivery-batch consolidation by cell. Malformed items go to `rejected`, never abort the batch.
  - Endpoint: `POST /digipin/group {level (1–10, default 7), points[{id?, latitude+longitude | digipin}]}` (≤5000) → `{level, cell_size_approx, groups[{cell, count, members[{id, digipin, latitude, longitude}], centre, bounds}] (largest first), rejected[{id, error}]}`. Members carry their full code's cell centre so a UI can plot dots from codes alone; DIGIPIN inputs accepted in any case, hyphenated or not.
  - `neighbors(code)` + `POST /digipin/neighbors {digipin}` → the "nearest DIGIPINs": up to 8 adjacent cells at the same level (fewer at the national bounding-box edge), `{cell, level, cell_size_approx, neighbors[{direction, digipin}]}`.
  - Verified: hierarchy containment over 200 random points across levels 3/6/8, neighbor symmetry (every neighbor's neighbors include the origin), corner cells (SW → 3, NE → 3, W edge → 5), mixed digipin+lat/lon grouping with rejection, existing encode/decode contract untouched, both evals identical, live-endpoint smoke on :8077.
  - Honesty: operates on coordinates/codes only; text addresses still need a geocoder first.
  - **Xenon → Argon:** shapes above. Level-10 `group` doubles as a bulk lat/lon→code converter (each member returns its full `digipin`). Client component `client/app/map/GroupByDigipin.jsx` (map overlay + CSV import + converter, used by `/map` and the dashboard "Group by DIGIPIN" tab) is drafted but Argon owns client integration/build from here — Xenon is off client files until the user re-opens them.

- [x] **Regression check** — both eval scripts identical after all changes (seed P/R/F1 = 1.000/1.000/1.000; real = 1.000/0.625/0.769). Endpoints smoke-tested via TestClient with `parse` stubbed from `parsed_cache.json` (zero LLM cost).
- [x] **Docs** — CLAUDE.md updated (Layer 3 wording, digipin/pincode/golden bullets, endpoint list, pincode data file) + tasklist statuses.

  **Xenon → Argon (A4):** `/digipin/*` and `/pincode/{pin}` shapes are in task 1/2 notes above. In `/batch`, render `golden_records[].canonical_text` as the cluster's merged record and badge `contested_fields`; `provenance[field].agreement` is a display-ready `"2/3"` string. Thanks for the `_ask_for` hotfix — confirmed, and my scorer tests pass on top of it.

## Sprint: 2026-07-26 — Neon

- [x] **N1. Blocking + reference-corpus match** — `server/lattice/matcher.py` (new file)
  - Multi-key blocking (pincode + discriminating locality/sublocality tokens via `resolver._tokens`); records compared only when they share ≥1 key; keyless records compared against all.
  - `cluster_blocked(parsed)` — same union-find semantics as `resolver.cluster()`, restricted to candidate pairs. `resolver.py` itself is NOT touched.
  - `AddressIndex` — in-memory corpus with `add`/`match(top_k)`; `/match` answers "does this incoming address match anything we've seen?" Seeded at startup from `data/real_sample.json` (pre-parsed, zero LLM cost).
  - Endpoints: `POST /match`, `POST /corpus`, `GET /corpus`.

- [x] **N2. Async batch jobs + CSV** — `server/jobs.py` (new file)
  - `POST /jobs` (JSON list, ≤5000) and `POST /jobs/csv` (raw CSV text body — no python-multipart dep); poll `GET /jobs/{id}`; `GET /jobs/{id}/results?format=json|csv`.
  - Parse cache keyed on raw string (`server/raw_cache.json`), deduped parsing, background ThreadPoolExecutor; results use `cluster_blocked` so jobs scale past the `/batch` 40-cap.
  - `/batch` itself left untouched — Xenon is wiring golden records into it.

- [x] **N-regression** — both eval scripts pass identically (seed P/R/F1 = 1.000/1.000/1.000; real = 1.000/0.625/0.769). `cluster_blocked` verified identical to `cluster` on seed (18/190 pairs compared) and real_sample (108/666).
- [x] **N-docs** — CLAUDE.md Architecture bullets updated (matcher.py, jobs.py, new endpoints, app.py append convention).

  **Neon → Argon (A4):** `/match`, `/corpus`, `/jobs` are live and smoke-tested over HTTP. Shapes: `POST /match {address, top_k}` → `{query, matches[{corpus_id, raw, meta, score, verdict, veto, matched_landmarks}], corpus}`; `GET /jobs/{id}` → `{status, total, parsed_done, cache_hits, summary?}` (poll until `status=="done"`); `GET /jobs/{id}/results?format=csv` for download. `POST /jobs/csv` takes the CSV as the raw request body (not multipart).

## Sprint: 2026-07-26 — Argon (console/client only — no server file edits)

- [~] **A1. Overview de-vague** — `client/app/dashboard/page.jsx` + `client/app/globals.css`
  - Information-dense ops Overview: pipeline strip (Layer 0→1→2 with live numbers), risk
    histogram computed client-side from `/real`, dataset provenance card, existing band
    bars + risk drivers retained. No new endpoints; no server changes.
- [~] **A2. Batch dedupe view** — same files
  - New "Batch" view in the console sidebar over the EXISTING `/batch` endpoint (which
    Xenon is extending with golden records — UI renders `golden` fields behind a guard,
    so their change appears automatically; `/batch` itself untouched by Argon).
  - Prefill uses real IFSC strings (the labelled MICR duplicate pairs) so clustering
    visibly collapses records; no synthetic data.
- [x] **A-hotfix. `scorer._ask_for` landmarks probe** — one-line fix to an Argon-era latent
  bug (`["placeholder"]` string list crashed `score()` via `l.get()`); surfaced as a 500 in
  `/batch` once golden wiring exercised the probe path. Xenon: `scorer.py` is otherwise untouched.
- [ ] **A3. Parse playground view** (after A1/A2)
- [x] **A-schema. `district` + `post_office` fields** — parser.py schema extension (file
  unclaimed this sprint): rural chains (VILLAGE X, PO Y, DIST Z) were losing the district
  entirely and mis-filing the post office as a landmark. Additive; cached eval parses
  untouched, resolver signals unchanged, so P/R/F1 unaffected.
- [x] **A5. MCP server** — `server/lattice_mcp.py` (new file): 7 tools (parse, compare,
  dedupe, match, pincode, digipin encode/decode) bridging to the REST API via LATTICE_API.
  Handshake + live calls verified; registered project-scope in `.mcp.json`. OpenAPI was
  already free via FastAPI (`/docs`, 16 paths). Text→DIGIPIN deliberately not offered.
- [ ] **A4. Console views for `/match`, `/jobs`, `/digipin` as Neon/Xenon land them**

## Sprint: 2026-07-26 — Claude (mentor requirements, pre-1pm)

- [x] **C1. API-key auth + self-service keys** — `server/app.py` (above Neon section)
  - Middleware: master key from `.env` `LATTICE_API_KEY`; open paths /health, /docs, /keys.
  - `POST /keys {name}` mints `ltk_…` (persisted `server/api_keys.json`, gitignored);
    `GET /keys` (master only) lists masked. Header `X-API-Key` or `?key=`.
  - Client sends the key everywhere: `lib/api.js` (`apiKey()`/`apiHeaders()`), GroupByDigipin.
- [x] **C2. Geocoder adapter + text→DIGIPIN** — `server/lattice/geocoder.py` (new)
  - OSM Nominatim, progressive segment-drop fallback, honest `precision`
    (street/locality/city-level). `POST /digipin/from-address`; `/parse` now returns
    `location` + `digipin` + `digipin_at_precision` (truncated to geocoder precision),
    geocoding the parsed canonical-Latin components so Indic-script input resolves.
    Geocoder failure degrades to nulls + `note`, never a 500.
- [x] **C3. STT** — `sarvam.transcribe()` (saaras:v3, lang auto) + `POST /stt`
  (raw audio body, no multipart dep — same convention as /jobs/csv). UI mic deferred.
- [x] **C4. Integration doc + sample DB** — `API.md` (auth, /parse contract, curl,
  batch/jobs) + `data/sample_input.json` (12 multilingual records).
  - Verified via TestClient: 401 without/with bad key, mint→parse 200; Devanagari
    input → Latin components + landmarks + lat/lon + DIGIPIN (`4FP-4CK-5L65`).
  - **Note to Argon:** client fetches now attach `X-API-Key`; if the console 401s
    after a restart, the key fallback lives in `lib/api.js` (`DEV_KEY`).

## Backlog (agreed order, not started)

- [ ] `/transliterate` endpoint (client code exists in `sarvam.py`, unused)
- [ ] Offline unit tests for `resolver.py` / `scorer.py` using `parsed_cache.json` fixtures
- [ ] Threshold sweep in `eval.py` (P/R curve; 0.75 is hardcoded in three places)
- [ ] Geocoder adapter interface (stub + optional OSM Nominatim) to complete text → DIGIPIN
- [ ] Call-risk model calibration against real outcomes (Layer 2 roadmap item)
