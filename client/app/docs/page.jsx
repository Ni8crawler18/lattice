"use client";

/* API documentation — a real docs page for the engineering team integrating
   Lattice from any machine. Static content; the live tester lives in the
   console's Agents & API tab. */

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiBase } from "@/lib/api";

const RENDER_URL = "https://lattice-api-96cn.onrender.com";

const mono = { fontFamily: "var(--mono)", fontSize: 11, lineHeight: 1.7, margin: 0,
               padding: "12px 15px", overflowX: "auto", background: "var(--canvas)",
               border: "1px solid var(--line)", color: "var(--ink-2)" };

const SNIP_MINT = `curl -s -X POST ${RENDER_URL}/keys \\
  -H 'Content-Type: application/json' \\
  -d '{"name": "priya-backend"}'
# -> {"api_key": "ltk_…", "shown_once": true}

export LATTICE_KEY=ltk_…            # store it — shown once, masked afterwards`;

const SNIP_PARSE = `curl -s -X POST ${RENDER_URL}/parse \\
  -H 'Content-Type: application/json' \\
  -H "X-API-Key: $LATTICE_KEY" \\
  -d '{"address": "गणेश मंदिराच्या मागे, निळा गेट, कोथरूड, पुणे ४११०३८"}'`;

const SNIP_INPUT = `{
  "address": "MADHAVLEELA COMPLEX, 1ST FLOOR, MASKASATH SQUARE, ITWARI",   // required
  "id":      "rec-01",        // optional — echoed back, for joining to your DB
  "pincode": "440002",        // optional hints: columns your DB already has.
  "city":    "Nagpur",        // They fill what the string doesn't state —
  "district": null,           // never overriding what the address says —
  "state":   null             // and sharply improve geocoding.
}`;

const SNIP_RESPONSE = `{
  "status": "partial",        // "ok" | "partial"
  "message": "Not enough information for a confident result: the address located
              only at locality-level; high delivery-failure risk. Every extractable
              field is returned; the single most valuable addition would be:
              House / flat / door number.",

  // ---- structured components (canonical Latin, whatever the input script) ----
  "house_number": null,  "floor": "1st Floor",  "building": null,
  "street": "Maskasath Square",  "sublocality": null,  "locality": "Itwari",
  "post_office": null,  "city": "Nagpur",  "district": null,  "state": null,
  "pincode": null,
  "landmarks": [ { "name": "…", "relation": "behind|opposite|near|…" } ],
  "visual_descriptor": null,  "occupant": "Madhavleela Complex",
  "hints_used": ["city"],     // which of your hint columns were applied

  // ---- deliverability (Layer 2) ----
  "deliverability": {
    "risk": 0.64, "band": "high", "will_likely_need_call": true,
    "reasons": ["No house or flat number, and no building to fall back on.", "…"],
    "ask_for": { "field": "house_number", "label": "House / flat / door number",
                 "risk_reduction": 0.42 }
  },

  // ---- pincode directory check (offline, 19,238 pins) ----
  "pincode_check": { "exists": true, "state_consistent": true, "inferred": {} },

  // ---- location + DIGIPIN (geocoder-derived; precision is honest) ----
  "location": { "latitude": 21.1569338, "longitude": 79.1102582,
                "precision": "locality-level",       // street | locality | city | district
                "matched_query": "Itwari, Maharashtra",
                "source": "osm-nominatim" },
  "digipin": "3P6-TJJ-JC93",             // full code at the returned coordinates
  "digipin_at_precision": "3P6-TJJ",     // truncated to what the fix supports — use this
  "note": "coordinates are locality-level (osm-nominatim)"
}`;

const SNIP_PY = `import os, requests

BASE = "${RENDER_URL}"
KEY  = os.environ["LATTICE_KEY"]

def lattice_parse(record):
    r = requests.post(f"{BASE}/parse",
                      headers={"X-API-Key": KEY},
                      json=record, timeout=60)
    r.raise_for_status()
    return r.json()

rec = lattice_parse({"address": "H.No 8-2-293/82/A, Road No 12, Banjara Hills, Hyderabad"})
if rec["status"] == "ok":
    print(rec["digipin"], rec["location"]["latitude"], rec["location"]["longitude"])
else:
    print("needs attention:", rec["message"])       # everything extractable is still in rec`;

const SNIP_JS = `const BASE = "${RENDER_URL}";

async function latticeParse(record) {
  const r = await fetch(\`\${BASE}/parse\`, {
    method: "POST",
    headers: { "Content-Type": "application/json",
               "X-API-Key": process.env.LATTICE_KEY },
    body: JSON.stringify(record),
  });
  if (!r.ok) throw new Error(\`lattice \${r.status}\`);
  return r.json();
}

const rec = await latticeParse({ address: "opp railway station, near big bazaar, Kanpur" });
console.log(rec.status, rec.digipin_at_precision, rec.message);`;

const SNIP_BATCH = `# up to 40 addresses — parse + dedupe + golden records, synchronous
curl -s -X POST ${RENDER_URL}/batch \\
  -H 'Content-Type: application/json' -H "X-API-Key: $LATTICE_KEY" \\
  -d '{"addresses": ["…", "…"]}'

# whole DBs (≤5000) — async job; CSV goes in the raw body
curl -s -X POST "${RENDER_URL}/jobs/csv?label=crm-export" \\
  -H 'Content-Type: text/csv' -H "X-API-Key: $LATTICE_KEY" \\
  --data-binary @addresses.csv
# poll GET /jobs/{id} until "done", then GET /jobs/{id}/results?format=csv`;

const ENDPOINTS = [
  ["POST /keys", "mint an API key (name required) — open, shown once", "no"],
  ["POST /parse", "unstructured address → components + risk + lat/long + DIGIPIN", "yes"],
  ["POST /compare", "{a, b} → same door or not, per-signal evidence + vetoes", "yes"],
  ["POST /batch", "≤40 addresses → clusters, golden records, risk", "yes"],
  ["POST /jobs · /jobs/csv", "≤5000 async; poll status; JSON/CSV results", "yes"],
  ["POST /match", "incoming address vs the seen-address corpus", "yes"],
  ["POST /digipin/from-address", "geocode + DIGIPIN, no LLM parse", "yes"],
  ["POST /digipin/encode · /decode", "coordinates ↔ DIGIPIN (India Post grid)", "yes"],
  ["POST /digipin/group · /neighbors", "grid-cell delivery batches · adjacent cells", "yes"],
  ["POST /stt", "spoken address (raw audio body) → transcript", "yes"],
  ["POST /stt/parse", "audio (mp3/wav/live mic) → transcript → full /parse contract", "yes"],
  ["GET /pincode/{pin}", "offline postal-directory lookup", "yes"],
  ["GET /health", "liveness + record count", "no"],
];

function Section({ title, right, children }) {
  return (
    <div className="block">
      <div className="block-head"><h3>{title}</h3>{right && <span className="right">{right}</span>}</div>
      <div className="block-body">{children}</div>
    </div>
  );
}

const P = ({ children }) => (
  <p style={{ fontSize: 13, lineHeight: 1.7, color: "var(--ink-2)", margin: "0 0 12px", maxWidth: "78ch" }}>{children}</p>
);

export default function DocsPage() {
  // apiBase() differs between SSR (Render URL) and a localhost browser -- resolve
  // it after mount so the server and first client render agree (hydration).
  const [base, setBase] = useState(RENDER_URL);
  useEffect(() => { setBase(apiBase()); }, []);
  return (
    <div className="main" style={{ maxWidth: 1060, margin: "0 auto" }}>
      <div className="topbar">
        <h1>Lattice — API documentation</h1>
        <span className="topbar-sub">integrate from any machine · hosted on Render</span>
        <div className="top-right">
          <a className="chip-btn" href={base + "/docs"} target="_blank" rel="noreferrer">OpenAPI / Swagger</a>
          <Link className="chip-btn dark" href="/dashboard">← Console</Link>
        </div>
      </div>

      <div className="content">
        <Section title="Base URLs">
          <pre style={mono}>{`production    ${RENDER_URL}
console       repoints via ?api=<url>&key=<key> in the URL bar`}</pre>
          <P>
            Every endpoint except <code>/health</code>, <code>/docs</code> and <code>POST /keys</code> requires
            an API key — header <code>X-API-Key</code> (or <code>?key=</code>). Missing, wrong or tampered key → <code>401</code>.
          </P>
        </Section>

        <Section title="1 · Authentication" right="self-service · stateless keys">
          <P>
            Each engineer mints their own key. It is returned <b>once</b> — copy it then; every later
            display is masked (<code>ltk_518e2*****</code>). Keys are HMAC-signed against the server's
            master secret, so there is no key database: the same key validates on localhost, on Render,
            and on every replica, and survives restarts. Rotating <code>LATTICE_API_KEY</code> in the Render
            dashboard revokes all issued keys at once.
          </P>
          <pre style={mono}>{SNIP_MINT}</pre>
        </Section>

        <Section title="2 · Quickstart — one call">
          <pre style={mono}>{SNIP_PARSE}</pre>
        </Section>

        <Section title="3 · POST /parse — the contract" right="unstructured in → structured + DIGIPIN + lat/long out">
          <P><b>Input.</b> Only <code>address</code> is required — any language, any script, any mess. The
            optional fields are context your database already holds in separate columns:</P>
          <pre style={mono}>{SNIP_INPUT}</pre>
          <P style={{ marginTop: 12 }}><b>Response.</b> Opens with a plain-language verdict; every extractable field is always
            returned, even on <code>partial</code>:</P>
          <pre style={mono}>{SNIP_RESPONSE}</pre>
          <P>
            <b>How location is found.</b> The geocoder queries the parsed canonical-Latin components
            (why Devanagari input still resolves), then progressively trimmed variants, then the raw
            string, and finally falls back to the pincode directory's district centroid. Each source is
            labelled in <code>precision</code>, and <code>digipin_at_precision</code> truncates the code to
            match — a locality fix is never sold as a 4-metre cell. A parser rule worth knowing:
            a city that is not in the input is never invented; supply the <code>city</code> hint if your
            records are locality-only.
          </P>
        </Section>

        <Section title="4 · Batches and whole databases">
          <pre style={mono}>{SNIP_BATCH}</pre>
        </Section>

        <Section title="5 · Client code">
          <div className="two" style={{ alignItems: "start" }}>
            <div>
              <label>Python</label>
              <pre style={mono}>{SNIP_PY}</pre>
            </div>
            <div>
              <label>JavaScript</label>
              <pre style={mono}>{SNIP_JS}</pre>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <label>Ready-made scripts — in the repo, stdlib only, nothing to install</label>
            <pre style={mono}>{`./examples/createkey.sh [name] [api-url]   # mint a key, prints the export line
python3 examples/usage.py                  # the three questions, end to end:
                                           #   POST /parse    what does this address say?
                                           #   POST /compare  are these two the same door?
                                           #   POST /jobs/csv dedupe a whole file, async

# both honour:  LATTICE_API  (base URL, default = production)
#               LATTICE_KEY  (usage.py mints one for you if absent)`}</pre>
          </div>
        </Section>

        <Section title="6 · Endpoint reference" right={`interactive spec at {api}/docs`}>
          <table>
            <thead><tr><th>Endpoint</th><th>What it does</th><th>Auth</th></tr></thead>
            <tbody>
              {ENDPOINTS.map(([ep, desc, auth]) => (
                <tr key={ep}>
                  <td className="mono" style={{ fontFamily: "var(--mono)", fontSize: 12, whiteSpace: "nowrap" }}>{ep}</td>
                  <td style={{ fontSize: 12.5, color: "var(--ink-2)" }}>{desc}</td>
                  <td style={{ fontSize: 12.5 }}>{auth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section title="7 · Deploy / operate">
          <P>
            The API runs anywhere Python 3.11 does. Render deploys from <code>render.yaml</code>; set two
            environment variables in the dashboard: <code>SARVAM_API_KEY</code> (LLM parsing + STT) and
            <code> LATTICE_API_KEY</code> (auth master secret). No database required — jobs are in-memory
            (they die with the process on the free tier), key validation is stateless, and the pincode
            directory ships as a data file. Point any client at your instance with the base URL alone.
          </P>
        </Section>
      </div>
    </div>
  );
}
