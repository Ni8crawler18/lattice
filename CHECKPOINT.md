# Lattice — Checkpoint Submission

**Indian Address Intelligence.** Unstructured, multilingual Indian addresses in;
structured, deduplicated, risk-scored records out — over REST, an MCP server, or
a console.

- **Console:** https://lattice-labs.vercel.app
- **API:** https://lattice-api-fs5f.onrender.com · interactive spec at `/docs`
- **Repo:** https://github.com/Ni8crawler18/lattice

---

## 1. Impact of Sarvam's models

**Sarvam is Layer 0. Remove it and there is no product** — every downstream
layer consumes its output.

An Indian address is a natural-language wayfinding instruction, not a record:
*"Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud."* No
standard component order, landmarks instead of street identity, four scripts,
and no canonical spelling. This fails at the **language layer**, not the
formatting layer — which is exactly why regex, postal reference files and
English-first geocoders have never solved it, and why an Indic-native model is
the only thing that can.

| Sarvam surface | Where it runs | What breaks without it |
|---|---|---|
| **sarvam-105b** (chat) | `parser.py` — the entire extraction schema lives in its system prompt | No structure. Layers 1–3 have nothing to consume. |
| **Saaras v3** (STT) | `POST /stt`, `POST /stt/parse` — spoken Hindi/Tamil → address | No voice intake at the form/checkout edge |
| **Language ID** | `parser.py` — script/language detection per record | No script-aware handling of Devanagari/Tamil/Bengali input |
| **Transliteration** | canonical-Latin normalisation | Cross-script records can never be compared |

**The Indic-specific extraction we ask the model to do**, none of which a
Western address parser has a slot for:

- **Landmarks as first-class fields** with spatial relations
  (`behind / opposite / near / beside / above / below`) — including
  postpositional forms where the relation *follows* the name
  (`பழைய தபால் அலுவலகம் எதிரில்` → `{name: "Old Post Office", relation: "opposite"}`)
- **`post_office` and `district`** — the rural chain (VILLAGE → PO → DIST) that
  Western schemas drop entirely
- **`visual_descriptor`** — "blue gate", "green shutter": how the last 20 metres
  actually work in India
- **`occupant`** — a business name at the start is who occupies the premises, not
  a landmark

**Prompt-level safety rules, because confident-wrong is worse than null:** never
invent a city not present in the input; never respell a proper noun. Both were
added after real-data failures — the model was answering "Chennai" for
`PAKKAM KOTTUR` and silently correcting `GAJANAN` to `Gajanand`.

---

## 2. A live, production-ready product

Hosted, authenticated, documented, and usable by anyone right now.

- **26 REST endpoints**, full **OpenAPI 3** spec auto-generated at `/docs`
- **API-key auth** — self-service via `POST /keys`. Keys are **stateless HMAC**
  (`ltk_<rand><hmac(master, rand)>`), so they validate on any deployment sharing
  the master secret and survive restarts on an ephemeral disk. No DB required.
- **Three consumption surfaces:** console (ops teams), REST (systems),
  **MCP server** (AI agents call parse/resolve/dedupe as native tools)
- **Async job pipeline** — CSV in, up to 5,000 addresses, poll for progress,
  CSV out. Job history survives navigation.
- **Degrades instead of failing:** a geocoder outage returns nulls with a stated
  reason, never a 500; per-item errors in a batch go to `rejected` rather than
  aborting the run

**Reliability work driven by measurement, not assumption.** Sarvam intermittently
returns empty completions — we measured **2 failures in 6 runs** on one repeated
address, uncorrelated with temperature (direct calls succeeded 6/6, so it is
upstream, not our prompt). Fixes:

1. **Successful-parse cache** keyed on the normalised raw string. Repeat parses:
   **84s → 0.00s, and 0 failures in 8 consecutive runs.** Failures are never
   cached, so they are always retried.
2. **Retry ladder** escalating 0.1 → 0.8 with backoff, never greedy — at
   temperature 0 a prompt that returns empty returns empty on *every* retry,
   which defeats the purpose of retrying.
3. **Honest UI** — a failed parse says so, instead of rendering empty fields
   under a confident wrong verdict.

---

## 3. Business impact

**The address field is a P&L line, not a data-quality nicety.**

| Metric | Figure | Provenance |
|---|---|---|
| RTO rate, India | 15–30%, past 40% in COD-heavy categories | industry-reported |
| RTO rate, global benchmark | 2–5% | industry-reported |
| **Share of RTOs caused by bad addresses** | **>45%** | industry-reported |

*(Logistics-vendor figures, not primary research. Stated as such rather than
dressed up.)*

**We found the problem inside production banking data.** In Razorpay's open IFSC
dataset, MICR codes are supposed to identify one physical branch. Of 18 record
pairs sharing a MICR, **only 8 were actually the same building.** India's own
banking data cannot keep one building as one record.

**Two revenue motions, one engine:**

- **Back-book** — clean the legacy database. Migration revenue.
- **Front door** — voice and local-language intake at forms and checkout, so the
  back-book stops growing. Recurring revenue.

**Who pays:** quick commerce and last-mile (rider-call rate, failed attempts);
**NBFCs and BFSI** (six loan applications from one house under six spellings is a
fraud ring, and address is a KYC field); insurers (one property, one risk
location); healthcare (patient dedupe across facilities, where a missed match
hides an allergy history). These are existing, staffed cost centres — not new
budget lines.

**Why now — two forces crossing.** India Post shipped **DIGIPIN** (May 2025), and
the **DHRUVA "Address-as-a-Service"** framework follows it. The state has
declared addresses to be infrastructure. But DIGIPIN encodes *coordinates*, not
text — and hundreds of millions of legacy free-text records have no coordinates.
**The state builds rails; the bridge onto them is the product.** UPI created
PhonePe. Meanwhile the language layer only just became solvable — this could not
have been built in 2020.

---

## 4. Technical depth

~3,100 lines of server Python across 15 modules. The LLM does extraction; every
decision downstream is deterministic, inspectable Python.

**The core architectural insight — coarse gates, fine scores.**
Locality agreement in an Indian city spans tens of thousands of households.
Treating it as evidence of a door match is the specific bug that produces false
positives. So coarse signals (pincode, city, locality, sublocality) *gate*; fine
signals (house number, building, landmarks, street, visual descriptor) *score*.
With no door-level evidence at all, the score is capped at 0.50 — "same area,
unknown door." **This was found empirically:** the first implementation scored
**1.0 for two different houses** in the same Kothrud locality.

**Engineering beyond API stitching:**

- **`digipin.py`** — India Post's official grid implemented from the spec
  (4×4 anticlockwise-spiral labelling, 10 levels), verified against the published
  reference vector `(28.6139, 77.209) → 39J-438-TJC7` plus 500 random
  round-trips. Pure arithmetic, no data files. Adds `cell()`, `neighbors()`,
  `truncate()` and `group()` — bucketing points into cells for delivery-batch
  consolidation.
- **`matcher.py`** — multi-key blocking (pincode + discriminating locality
  tokens). `cluster_blocked()` is a drop-in for the O(n²) clusterer with
  **verified-identical output on both eval sets** at a fraction of the pairs.
- **`golden.py`** — canonical record synthesis: majority vote per component,
  tie-broken by completeness, landmarks pooled, with **per-field provenance**
  (`sources`, `agreement`, `contested`).
- **`pincode.py`** — offline directory, 19,238 pincodes from the GeoNames dump.
  A *lookup*, so it never violates the parser's never-invent-a-city rule.
- **`geocoder.py`** — pluggable adapter over OSM Nominatim with a **process-wide
  1 req/s gate** (six batch workers each sleeping locally still breach the policy
  together) and a persistent cache.

**Precision honesty as an engineering feature.** Nominatim fuzz-matches: query a
street it does not know and it returns a *different* street at street rank,
confidently. So we verify that the query's discriminating tokens actually appear
in the returned match, and **cap the claimed precision when they do not** — which
in turn caps how many DIGIPIN digits we emit. We would rather claim 1 km honestly
than 4 m falsely.

**Measured, on real records — with the misses published.**

| Method | P | R | F1 |
|---|---|---|---|
| **Lattice** | **1.000** | **0.625** | **0.769** |
| Raw string similarity @0.65 (best baseline) | 0.625 | 0.625 | 0.625 |
| Raw string similarity @0.85 | 0.000 | 0.000 | 0.000 |

36 labelled pairs from Razorpay's open IFSC dataset (182,758 real bank-branch
addresses). **Labels are ours, assigned by reading each pair**, because MICR
proved unreliable as ground truth. Small set (8 positives) and weights were
adjusted after seeing results — so we treat the margin as indicative, not
validated.

**The number that matters is precision 1.000: zero false merges.** In
deduplication a false merge silently fuses two customers into one record. A
missed duplicate costs a second look. We tune for the failure that is cheap.

Two eval harnesses (`eval.py`, `eval_real.py`) run offline from cached parses and
print every FP/FN with its per-signal breakdown — they are the regression suite.

---

## Known limits (stated, not hidden)

- **Recall 0.625** — catches ~5 of every 8 true duplicates. The console ships a
  *"Real: a miss"* example that demonstrates a genuine failure case.
- **36-pair eval set** is small; weights were tuned post-hoc.
- **Text → DIGIPIN depends on geocoder confidence.** Precision is capped rather
  than asserted.
- **No formal field-level parse-accuracy benchmark yet** — Layer 1 numbers are
  end-to-end. A parse failure degrades to *uncertainty*, not to a wrong merge,
  which is why precision holds.
- **Cold parses take ~20s** on a free-tier instance (LLM + geocoding). Repeats
  are cached and instant.
