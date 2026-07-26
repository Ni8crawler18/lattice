# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Lattice parses messy, multilingual Indian address strings into structured components (Layer 0), resolves whether two strings refer to the same physical door (Layer 1), and scores deliverability risk (Layer 2). Parsing is done by Sarvam's `sarvam-105b` LLM; resolution and scoring are deterministic Python. Layer 3 (DIGIPIN bridge): the DIGIPIN grid *algorithm* (coordinates ↔ code) is implemented in `server/lattice/digipin.py`, but text → DIGIPIN needs a geocoder that is not in the loop — **never claim the system converts addresses to DIGIPIN.**

## Commands

The Python venv lives at `env/` (Python 3.11). There is no test framework, linter, or Makefile. Requires `SARVAM_API_KEY` in `.env` at the repo root (not committed) or in the environment — but only for code paths that parse: the API's `/parse`, `/compare`, `/batch`, and `eval.py --refresh`. `eval.py` (cached), `eval_real.py`, and all resolver/scorer work run offline with no key.

```bash
# backend API (http://127.0.0.1:8077)
env/bin/python3 -m uvicorn server.app:app --reload --port 8077

# frontend — Next.js 15 app in client/ (the README's http.server line is stale)
cd client && npm run dev

# evaluate Layer 1 on the hand-built seed set (uses server/parsed_cache.json)
env/bin/python3 server/eval.py
# --refresh re-parses all seed addresses via the Sarvam API (costs API calls)
env/bin/python3 server/eval.py --refresh

# evaluate Layer 1 on real Razorpay IFSC addresses with human labels
env/bin/python3 server/eval_real.py
```

Run all Python scripts from the repo root — `server/app.py`, `eval.py`, and `eval_real.py` insert the repo root into `sys.path` and import as `server.lattice.*` / `data.*`.

The eval scripts are the de-facto regression suite. After changing `resolver.py`, `scorer.py`, or the parser prompt, run both `eval.py` (no `--refresh` needed unless the prompt changed) and `eval_real.py`, and compare P/R/F1 against the Status table in the README. Both scripts print each FP/FN with its per-signal breakdown and veto, which is how to diagnose a regression.

Deploy: `render.yaml` runs the API on Render (`SARVAM_API_KEY` set in the dashboard); the client deploys to Vercel.

## Architecture

**Pipeline:** raw string → `parser.parse()` (LLM) → `ParsedAddress` dict → `resolver.compare()/cluster()` and `scorer.score()` (pure Python, no API calls).

- `server/lattice/sarvam.py` — thin Sarvam client (chat, language ID, transliteration), shared by everything.
- `server/lattice/parser.py` — Layer 0. The entire extraction schema lives in the `SYSTEM` prompt. Landmarks are a first-class field: an array of `{name, relation}` where relation ∈ behind/opposite/near/beside/above/below. Retries up to 3× on empty/unparseable completions; `_extract_json` tolerates fenced output.
- `server/lattice/resolver.py` — Layer 1. **The core design invariant: coarse signals (pincode, city, locality, sublocality) gate; fine signals (house_number, building, landmarks, street, visual_descriptor) score.** Locality agreement in an Indian city spans tens of thousands of households — treating it as door-match evidence is the specific bug that produces false positives, and this split exists to prevent it. Without any fine (door-level) evidence, scores are capped at `NO_FINE_CEILING` (0.50). Hard vetoes cap the score: pincode mismatch, house-number mismatch, locality mismatch (unless corroborated by pincode + strong fine agreement). Match threshold is 0.75; `cluster()` is single-link over `compare()`.
- `server/lattice/scorer.py` — Layer 2. Rule-based on purpose: every risk score carries human-readable reasons plus `ask_for`, the single field whose addition most reduces risk (computed by re-scoring with a placeholder). Don't replace with an opaque model. Directory-backed signals (nonexistent pincode, pincode↔city/state conflict) come from `pincode.py` and only fire on well-formed 6-digit pins so `_ask_for` probes aren't distorted.
- `server/lattice/digipin.py` — Layer 3, algorithm half. India Post's official DIGIPIN grid (4×4 anticlockwise-spiral labelling, bounds 2.5–38.5°N / 63.5–99.5°E, 10 levels), verified against the published reference vector `(28.6139, 77.209) → 39J-438-TJC7`. Beyond encode/decode: `cell()` (bounds for 1–10-symbol prefixes), `truncate()`, `neighbors()` (adjacent cells), and `group()` (bucket points into cells at a chosen level — 6 ≈ 1 km, 7 ≈ 250 m; per-item errors go to `rejected`, never abort). Pure arithmetic, no data files. Text → DIGIPIN still needs a geocoder.
- `server/lattice/pincode.py` — offline postal-directory validation: does the pincode exist, is it consistent with stated city/state, what does it imply when they're absent (a lookup, so it doesn't violate the parser's never-invent-a-city rule). Degrades gracefully (`available()` false) if the data file is missing. GeoNames India lat/lons are district-level centroids — deliberately not exposed as "pincode location".
- `server/lattice/golden.py` — golden-record synthesis: `canonical(members)` merges records of one cluster via majority vote on `resolver._canon` keys (tie-break by member completeness, longest string wins within a group), pools landmarks, and emits per-field provenance (`sources`, `agreement`, `contested`) plus a `canonical_text` writeback string.
- `server/lattice/matcher.py` — blocking + reference-corpus matching. Multi-key blocking (pincode + non-positional locality/sublocality tokens); records are only `compare()`d when they share a key, keyless records compare against all. `cluster_blocked()` is a drop-in for `resolver.cluster()` with identical output (verified on both eval sets) at a fraction of the pairs; `AddressIndex` is the in-memory corpus behind `/match`, seeded at startup from `data/real_sample.json`.
- `server/jobs.py` — async batch jobs. Background ThreadPoolExecutor, in-memory job store (deliberately no DB — Render free tier; jobs die with the process), parse cache keyed on raw string in `server/raw_cache.json` (gitignored; warmed from `parsed_cache.json` at startup), CSV ingest without python-multipart (raw text body) and CSV export.
- `server/app.py` — FastAPI endpoints: `/parse` (now includes `pincode_check`), `/compare`, `/batch` (parse + cluster + score + one `golden_records` entry per cluster, ≤40 addresses), `/digipin/encode`, `/digipin/decode`, `/digipin/neighbors`, `/digipin/group` (≤5000 points), `/pincode/{pin}`, `/real` (serves pre-parsed `data/real_sample.json`), `/health`; plus the Neon section appended at the end of the file: `/match`, `/corpus` (POST/GET), `/jobs` (POST JSON ≤5000 / POST CSV / list / status / results). Multi-agent convention: Neon's endpoints stay in the marked section at the END of `app.py`; add other new endpoints above it (see `tasklist.md`).

**Data / evaluation:**

- `data/seed.py` — 20 hand-built addresses; records sharing a `truth` id are the same physical location. Metrics on this set are tuned-to-itself; the defensible claim is the architecture, not the F1 of 1.0.
- `data/real.py` — samplers over Razorpay's open IFSC dataset. Requires the raw CSV, path via `IFSC_CSV` env var (the default points at an expired scratchpad path). MICR-code sharing suggests same-branch pairs but is **not** reliable ground truth.
- `data/labels.py` — human-verified truth for the MICR pairs, with per-pair reasoning; indexes into `data/real_pairs_raw.json`.
- `server/parsed_cache.json` — cached LLM parses of the seed set, so `eval.py` runs offline; only `--refresh` regenerates it.
- `data/pincode_dir.json.gz` — offline pincode directory (~19k pins: state, district, served areas) built from the GeoNames India postal dump (CC-BY 4.0) by `data/pincodes.py` (regeneration instructions in its docstring).

**Client** (`client/`, Next.js 15 / React 19, plain JS): pages in `app/page.jsx` and `app/dashboard/page.jsx`; all backend calls go through `lib/api.js`. Backend URL resolution order: `?api=<url>` query param (repointable from the URL bar during a demo), then `NEXT_PUBLIC_LATTICE_API`, then localhost:8077 in dev, then the Render URL.

## Parser prompt invariants

When editing the `SYSTEM` prompt in `parser.py`, preserve its hard rules: never invent a city that isn't in the input; never respell proper nouns (casing fixes only); a business name at the start of an address is `occupant`, not a landmark or building. These exist because confident wrong output is worse than null — the failure mode this product sells against.

## Claims discipline

The README doubles as pitch material and is deliberate about provenance: seed-set metrics are labeled hand-built, RTO figures are industry-reported not primary research, and the address labels are ours (MICR is not ground truth). When touching README or demo copy, keep those qualifiers — do not upgrade a claim's confidence.
