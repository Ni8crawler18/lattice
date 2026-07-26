# Lattice — Indian Address Intelligence

> Indian addresses are not addresses. They are directions.
> Lattice turns them into structured, resolvable, machine-usable locations.

Built on the Sarvam stack. Indic-native by design.

---

## 1. The problem

An Indian address is a natural-language wayfinding instruction, not a structured record:

```
Ganesh mandir ke peeche, blue gate wala ghar,
opp SBI ATM, Kothrud, Pune 411038
```

```
2nd cross, 4th main, near Ayyappa temple,
behind Reliance Fresh, BTM 2nd stage, B'lore
```

There is no standard component order, no street numbering discipline, landmarks
substitute for street identity, and the same physical house is written a dozen
different ways by a dozen different people — in English, in Hinglish, or in
Devanagari/Tamil/Bengali script.

Every address system in production assumes Western structured addressing:
`house → street → locality → city → postcode`. Indian addresses do not carry
that structure, so these systems do not fail loudly. **They fail silently** —
returning a confident pin several hundred metres off, or a "valid" verdict on an
undeliverable string.

### What it costs (industry-reported)

| Metric | Figure | Source quality |
|---|---|---|
| RTO (return-to-origin) rate, India | **15–30%**, spiking 40%+ in COD-heavy categories | Industry-reported |
| RTO rate, global benchmark | 2–5% | Industry-reported |
| RTO on COD / non-prepaid orders | ~26% (vs <2% prepaid), FY25 | Shipway ShipNotes FY25 |
| **Share of RTOs caused by incorrect, vague or incomplete addresses** | **>45%** | Industry-reported |
| Failed deliveries as share of orders (growing businesses) | 20–30% | Industry-reported |

> ⚠️ **Source discipline.** These figures circulate across logistics-vendor blogs
> that cite each other; they are *industry-reported*, not primary research. Label
> them that way on any slide. A VC who has done logistics diligence will know the
> range independently — quoting it honestly earns more credibility than a precise
> number you can't defend. Do **not** cite the "₹8,000 crore/year" figure: it
> traces to a single vendor blog with no methodology.

**The compounding metric nobody publishes:** the rate at which a delivery rider
has to phone the customer for directions. Every last-mile and quick-commerce ops
team instruments this internally. It is minutes of paid rider time per order, at
national scale, and its root cause is address ambiguity. Ask any ops lead in the
room for their number — they will have it, and it will be larger than anything
we could have claimed.

### The government agrees the problem is real

On **27 May 2025**, the Department of Posts — with IIT Hyderabad and NRSC/ISRO —
launched **DIGIPIN**, an open, geo-coded, grid-based digital addressing system
assigning a 10-character code to every 4m × 4m cell in India. It exists as Digital
Public Infrastructure precisely because PIN codes (unchanged since 1972) and
free-text addresses cannot support doorstep delivery, emergency response, or
service targeting.

**DIGIPIN defines the destination format. Nobody has built the bridge to it.**
Hundreds of millions of legacy address strings sit in CRMs, loan files, patient
records and order histories. Lattice is that migration layer.

---

## 2. Why this is a *language* problem

This is the part that makes it ours and not a mapping company's.

1. **Landmarks are the primary key.** `mandir ke peeche`, `SBI ke bagal mein`,
   `hospital ke saamne` — resolving these requires parsing Hindi/Marathi/Tamil
   spatial-relational language, not string matching.
2. **Script mixing.** The same address arrives in Latin, Devanagari, Tamil, or
   Bengali script — sometimes mixed within one field.
3. **Romanization variance.** `Kothrud` / `Kothrood`, `Bangalore` / `Bengaluru` /
   `B'lore`, `Nagar` / `Ngr`.
4. **Colloquial locality names** that appear on no map — what residents call an
   area versus its official revenue name.

An English-first geocoder cannot reason over any of this. **Saaras, Mayura and
Sarvam's transliteration stack can.**

---

## 3. Current solutions, and where each breaks

| Solution | What it does | Where it breaks |
|---|---|---|
| **Google Address Validation API (India)** | ML-based parser built for Indian address formats | **In preview / pre-GA for India.** Per-call pricing and rate limits make full-database processing impractical; Maps Platform terms restrict storing and caching results, which is exactly what enterprises need. Validates *one* address — does not tell you two records are the same house. |
| **Google Address Descriptors (India)** | Landmark-based descriptors generated *by Google* for a location | Generates landmarks **from Google's data outward**. Does not parse *your* messy user-entered Hindi landmark text inward. Opposite direction from the enterprise need. |
| **Zippr** (Hyderabad, f. 2013) | Proprietary short address codes / digital door numbers | Requires universal adoption of a **new code** by consumers. Adoption-dependent, and now competing with a government standard (DIGIPIN) that is free and open. |
| **PostGrid / GeoPostcodes / generic AV vendors** | Reference-database address validation | Built on postal reference files. Indian addresses substantially aren't *in* those files, and none handle Indic scripts or landmark semantics. |
| **LogiNext and last-mile platforms** | Route optimisation, dispatch, tracking | Adjacent, not competing — they consume address quality, they don't produce it. **Potential channel partners.** |
| **In-house regex + manual ops teams** | The actual incumbent at most companies | Address-cleanup staff and customer-care calls placed purely to resolve bad addresses. **This is the job Lattice replaces.** |

### The honest competitive read

Google is **actively in this space for India** and must be addressed directly in
the pitch, not avoided. Three things survive that:

1. **You cannot run Google over your own database.** Cost, rate limits, and terms
   restricting result storage are hard constraints at enterprise volume. The need
   is batch normalisation over data you own.
2. **Google validates; it does not resolve entities.** "Are these six records the
   same physical house?" is a different question, and it's the one that powers
   both delivery consolidation and lending fraud detection.
3. **Google will not bridge to DIGIPIN.** It competes with their own Plus Codes.
   An open, government-backed standard is a structural opening.

---

## 4. Who needs this

**Primary — quick commerce & last-mile**
Zepto, Swiggy Instamart, Blinkit, Dunzo-likes, Delhivery, Shadowfax, Ecom Express,
Porter. Buying trigger: RTO rate, rider-call rate, first-attempt delivery success.

**Lending & BFSI**
Address is a KYC field *and* a risk signal. Deduplication surfaces fraud rings —
six loan applications, one physical house, six spellings. Field-verification
agent visits can be pre-screened rather than dispatched blind.

**Healthcare**
Patient record deduplication across hospital branches. Same patient, different
address spellings, different MRNs — so an allergy recorded at one site is
invisible at another. That is a patient-safety failure, not a data-hygiene one.

**Insurance**
Property risk rating requires knowing the actual structure. Address ambiguity
means mispriced policies and disputed claims.

**Regulators & public bodies**
Registered-office verification (MCA), GST premises verification, drug-licence
premises, factory-licence location, ration-shop and PDS outlet mapping.
Same primitive: is this string a real, unique, locatable place — and is it the
same place as that other string?

**Utilities & emergency services**
Response-time reduction is DIGIPIN's own stated rationale.

---

## 5. What we build

Core first, layers on top.

### Layer 0 — the Sarvam core (build this first)
Messy multilingual address string → structured components.
- Script/language detection → normalisation across scripts
- Component extraction: house, floor, building, street, landmark, locality, city, pincode
- **Landmark isolated as a first-class field** — this is the Indian-specific move
- Confidence score per component

### Layer 1 — entity resolution
Do two address strings refer to the same physical location?
Normalised-space matching + landmark agreement + locality/pincode consistency.
Output: cluster ID, match confidence.

### Layer 2 — deliverability scoring
Predict, before dispatch, whether this address will need a rider phone call.
Signals: missing components, landmark-only addressing, pincode/locality conflict,
ambiguous locality name.

### Layer 3 — DIGIPIN bridge *(not built; scoped honestly)*
DIGIPIN is already live. It encodes **GPS coordinates → 10-character code** —
pure grid arithmetic, and an open algorithm. What it does *not* do is turn a
messy text address into a location, and legacy CRM rows have no coordinates.

So the missing half is exactly Layers 0–1: text → resolved location → (geocode)
→ DIGIPIN. Layer 3 itself is trivial once coordinates exist; we have not built
it because we have no geocoder in the loop. **Do not claim we output DIGIPIN.**

---

## Status

| Layer | State |
|---|---|
| 0 — parse | ✅ built, running on Sarvam-105B + LID |
| 1 — entity resolution | ✅ built, F1 1.000 on the seed set vs 0.353 baseline |
| 2 — deliverability scoring | ◻ completeness score exists; call-risk model not built |
| 3 — DIGIPIN bridge | ◻ needs a geocoder first |

### Measured (20 records, 190 pairs, hand-built seed)

| Method | P | R | F1 |
|---|---|---|---|
| **Lattice** | **1.000** | **1.000** | **1.000** |
| Raw string similarity @0.55 | 0.500 | 0.273 | 0.353 |
| Raw string similarity @0.75 | 0.500 | 0.091 | 0.154 |

> Say "20 records, hand-built" out loud. It is a seed set, not a benchmark, and
> we wrote it — so it is tuned to itself. The defensible claim is the
> architecture, not the 1.0.

**The architecture claim:** coarse signals (pincode, city, locality) *gate*;
fine signals (house number, street, landmarks, building) *score*. Locality
agreement in an Indian city spans tens of thousands of households — treating it
as evidence of a door match is the specific bug that makes naive matching fail.
That bug produced 4 false positives at score 1.0 before the split was
introduced.

---

## Run it

```bash
# backend  (http://127.0.0.1:8077)
env/bin/python3 -m uvicorn server.app:app --reload --port 8077

# frontend (http://127.0.0.1:8078)
cd client && python3 -m http.server 8078

# re-parse the seed set and re-run the evaluation
env/bin/python3 server/eval.py --refresh
```

The client picks its backend from `?api=<url>` first, so it can be repointed
from the URL bar on stage without a redeploy.

**Deploy:** `render.yaml` for the API (set `SARVAM_API_KEY` in the dashboard —
it is not in the repo), `client/vercel.json` for the static frontend.

---

## 6. Demo

Two strings. Same house. Written completely differently, in different scripts.

Every string matcher on earth says *different*.
Lattice says **same location, confidence 0.94.**

Then: a batch of fifty real addresses scored for call-risk, with the failures
ranked. The buyer already tracks this number — they just have no lever on it.

---

## 7. Sources

- RTO and failed-delivery figures: [Shadowfax](https://www.shadowfax.in/blogs/how-to-reduce-rto-in-e-commerce), [eShipz](https://www.eshipz.com/blog/rto-in-ecommerce/), [Amazon Shipping India](https://shipping.amazon.in/blog/what-is-rto-how-to-reduce-return-to-origin), [Busy](https://busy.in/ecommerce-reconciliation/rto-meaning-in-ecommerce-india-causes-charges-and-18-ways-to-reduce/) — *industry-reported, not primary research*
- DIGIPIN: [PIB press release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2131707&reg=3&lang=2), [India Post](https://www.indiapost.gov.in/digipin), [Business Standard](https://www.business-standard.com/india-news/india-post-digipin-pincode-explained-125061000618_1.html)
- Google Maps Platform India: [Address Validation for India](https://mapsplatform.google.com/resources/blog/announcing-address-validation-api-with-machine-learning-for-india/), [Address Descriptors India](https://mapsplatform.google.com/resources/blog/announcing-expanded-coverage-and-new-features-for-address-descriptors/), [coverage status](https://developers.google.com/maps/documentation/address-validation/coverage)
- Zippr: [Forbes India](https://www.forbesindia.com/article/hidden-gems-2017/zippr-in-the-right-direction/47987/1), [zippr.co](https://zippr.co/)

**Unverified — check before it goes on a slide:** exact Google Maps Platform
caching/storage terms, current Address Validation API India GA status, and any
rider-call-rate figure.
