"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import { apiBase, proxyBase, batchAddresses, compareAddresses, fetchReal, getJob, getJobResults, jobCsvUrl, listJobs, parseAddress, submitCsvJob } from "@/lib/api";
import GroupByDigipin from "../map/GroupByDigipin";
import { EXAMPLE_SNIPPETS } from "@/lib/exampleSnippets";

/* Real IFSC records (labelled MICR duplicate pairs + distinct branches) so a
   batch run visibly collapses duplicates. Nothing synthetic. */
const REAL_BATCH = [
  "MADHAVLEELA COMPLEX, 1ST FLOOR, MASKASATH SQUARE, ITWARI",
  "1ST FLOOR, MADHAVLEELA COMPLEX, MASKASATH SQUARE, ITWARI NAGPUR",
  "PLOT NO 7&7A, MYSARI CHAMBERS, SARASWATHI COLONY, LOTHUKUNTA",
  "PT NO.7 AND 7A , MYSARI CHAMBERS, SARAWATHI COLONY, LOTHUKUNTA HYDERABAD-PIN",
  "THE GANDHIDHAM MERCANTILE COOP BANK LTD., GMCB BHAVAN, PLOT NO.12, SECTOR NO.9, GANDHIDHAM - 370 201",
  "GMCB BHAVAN, PLOT NO 12, SECTOR NO 9, BANKING CIRCLE, GANDHIDHAM KUTCH 370 201",
  "3-116, 1ST FLOOR, HANUMANNAGAR COLONY CHAITANYAPURI, DILSUKHNAGAR, HYDERABAD-PIN",
  "DOOR NO.3-116, FIRST FLOOR, HANUMAN NAGAR COLONY, CHAITANYAPURI, DILSUKNAGAR",
  "ICICI BANK LTD., 19B BROAD STREET, KOLKATA, WEST BENGAL.",
  "239-A, NAMDEO PRASAD BUILDING, TAMIL SANGAM ROAD, SION(EAST), MUMBAI, PIN",
];

const Mark = ({ s = 20 }) => (
  <svg width={s} height={s} viewBox="0 0 22 22" aria-hidden>
    <rect x="1.4" y="1.4" width="8" height="8" rx="2.2" fill="none" stroke="var(--navy)" strokeWidth="1.7" />
    <rect x="12.6" y="1.4" width="8" height="8" rx="2.2" fill="var(--blue)" />
    <rect x="1.4" y="12.6" width="8" height="8" rx="2.2" fill="none" stroke="var(--navy)" strokeWidth="1.7" />
    <rect x="12.6" y="12.6" width="8" height="8" rx="2.2" fill="none" stroke="var(--navy)" strokeWidth="1.7" />
  </svg>
);

/* ---------- examples: real IFSC records except the marked demo ---------- */
const EXAMPLES = [
  {
    key: "spacing", tile: "t1", chip: "real",
    name: "Spacing variance", sub: "IFSC dataset · same branch",
    hint: "Real records. HANUMANNAGAR/HANUMAN NAGAR, DILSUKHNAGAR/DILSUKNAGAR.",
    a: "3-116, 1ST FLOOR, HANUMANNAGAR COLONY CHAITANYAPURI, DILSUKHNAGAR, HYDERABAD-PIN",
    b: "DOOR NO.3-116, FIRST FLOOR, HANUMAN NAGAR COLONY, CHAITANYAPURI, DILSUKNAGAR",
  },
  {
    key: "reorder", tile: "t2", chip: "real",
    name: "A miss, on purpose", sub: "Scores 0.73 — below our cut",
    hint: "Real. Same branch, reversed order — lands under the 0.75 threshold. A known miss.",
    a: "ABHAY PRASHAL, 10, RACE COURSE ROAD, INDORE",
    b: "RACECOURSE ROAD, 10, ABHAY PRASHAL, INDORE",
  },
  {
    key: "trap", tile: "t3", chip: "real",
    name: "Near-miss trap", sub: "Shared MICR, different doors",
    hint: "Real, and NOT the same place — both share a MICR code in the dataset.",
    a: "M.C. NO.53, M J MALL, RAILWAY ROAD, RISHIKESH.",
    b: "637 , LAXMAN JHOOLA ROAD , RISHIKESH -, UTTARAKHAND",
  },
  {
    key: "script", tile: "t4", chip: "demo",
    name: "Multi-script", sub: "Constructed — IFSC is Latin-only",
    hint: "Illustrative, not from the dataset. Devanagari vs Hinglish, same house.",
    a: "Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038",
    b: "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८",
  },
];

const FIELD_KEYS = [
  "house_number", "floor", "building", "street", "sublocality",
  "locality", "post_office", "city", "district", "state", "pincode",
];

const SCRIPT_NAMES = { Latn: "Latin", Deva: "Devanagari", Taml: "Tamil",
  Beng: "Bengali", Gujr: "Gujarati", Knda: "Kannada", Telu: "Telugu",
  Mlym: "Malayalam", Guru: "Gurmukhi", Orya: "Odia", Arab: "Perso-Arabic" };
const scriptName = (c) => SCRIPT_NAMES[c] || c;

const BENCH = [
  { m: "Lattice (Sarvam parse + coarse/fine resolution)", p: "1.000", r: "0.625", f: "0.769", win: true },
  { m: "Raw string similarity @ 0.55", p: "0.462", r: "0.750", f: "0.571" },
  { m: "Raw string similarity @ 0.65", p: "0.625", r: "0.625", f: "0.625" },
  { m: "Raw string similarity @ 0.75", p: "0.667", r: "0.500", f: "0.571" },
  { m: "Raw string similarity @ 0.85", p: "0.000", r: "0.000", f: "0.000" },
];

function CountUp({ value, decimals = 2, duration = 650 }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let raf, t0;
    const step = (t) => {
      if (!t0) t0 = t;
      const k = Math.min(1, (t - t0) / duration);
      setN(value * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return <>{n.toFixed(decimals)}</>;
}

/* ------------------------------- icons ------------------------------- */
const I = {
  overview: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2 8.5 8 3l6 5.5M4 7.5V13h8V7.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  resolve: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="5" cy="8" r="2.6"/><circle cx="11" cy="8" r="2.6"/></svg>,
  deliver: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M8 14s-4.5-3.6-4.5-7A4.5 4.5 0 0 1 8 2.5 4.5 4.5 0 0 1 12.5 7c0 3.4-4.5 7-4.5 7Z"/><circle cx="8" cy="7" r="1.4"/></svg>,
  evidence: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3 13V8M8 13V3M13 13v-3" strokeLinecap="round"/></svg>,
  batch: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2.5 5 8 2.5 13.5 5 8 7.5 2.5 5ZM2.5 8 8 10.5 13.5 8M2.5 11 8 13.5l5.5-2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  parse: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M5.5 2.5c-1.6 0-1.6 1.5-1.6 2.6S3.6 7.6 2.5 8c1.1.4 1.4 1.8 1.4 2.9s0 2.6 1.6 2.6M10.5 2.5c1.6 0 1.6 1.5 1.6 2.6s.3 2.5 1.4 2.9c-1.1.4-1.4 1.8-1.4 2.9s0 2.6-1.6 2.6" strokeLinecap="round"/></svg>,
  digipin: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2.5 2.5h11v11h-11zM2.5 8h11M8 2.5v11" strokeLinecap="round"/></svg>,
  mcp: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="2.5" y="2.5" width="4.5" height="4.5" rx="1"/><rect x="9" y="9" width="4.5" height="4.5" rx="1"/><path d="M7 11.2H4.8a1 1 0 0 1-1-1V8.8M9 4.8h2.2a1 1 0 0 1 1 1V7" strokeLinecap="round"/></svg>,
  docs: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M4 2.5h5.5l3 3V13.5H4z" strokeLinejoin="round"/><path d="M9.5 2.5v3h3M6 8.5h4M6 11h4" strokeLinecap="round"/></svg>,
  rest: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M6 4 3 8l3 4M10 4l3 4-3 4" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  mic: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="6" y="2" width="4" height="7" rx="2"/><path d="M3.5 8a4.5 4.5 0 0 0 9 0M8 12.5V14" strokeLinecap="round"/></svg>,
  key: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="5.5" cy="6" r="3"/><path d="M8 8.5 13.5 14M11 11.5l2-2M12.5 13l1.5-1.5" strokeLinecap="round"/></svg>,
};

/* ---------------------------- shared visuals ---------------------------- */

function Steps({ items }) {
  return (
    <div className="steps" aria-label="How to use this screen">
      {items.map((t, i) => (
        <span key={i} className="step"><b>{i + 1}</b>{t}</span>
      ))}
    </div>
  );
}

const FLOW = [
  { name: "Address", sub: "free text, any script" },
  { name: "Read it", sub: "sarvam-105b pulls the fields out" },
  { name: "Tidy up", sub: "one consistent spelling per field" },
  { name: "Check the PIN", sub: "against a 19,238-pin directory" },
  { name: "Map cell", sub: "DIGIPIN · needs coordinates" },
  { name: "Line them up", sub: "area must agree before the door counts" },
  { name: "Verdict", sub: "same door or not, and the risk" },
];

function FlowStrip() {
  return (
    <div className="block flow">
      {FLOW.map((f, i) => (
        <div key={f.name} className={`fstep${i === 4 ? " dim" : ""}`}>
          <span className="fnum">{i + 1}</span>
          <div className="fname">{f.name}</div>
          <div className="fsub">{f.sub}</div>
        </div>
      ))}
    </div>
  );
}

function RiskHistogram({ records }) {
  const bins = Array.from({ length: 10 }, () => 0);
  records.forEach((r) => bins[Math.min(9, Math.floor(r.score.risk * 10))]++);
  const max = Math.max(...bins, 1);
  const color = (i) => (i < 2.8 ? "var(--green)" : i < 5.5 ? "var(--amber)" : "var(--magenta)");
  const W = 700, H = 190, bw = W / 10;
  return (
    <svg viewBox={`0 0 ${W} ${H + 30}`} style={{ width: "100%" }} role="img"
         aria-label="Distribution of deliverability risk across records">
      {bins.map((v, i) => {
        const h = (v / max) * (H - 24);
        return (
          <g key={i}>
            <rect x={i * bw + 5} y={H - h} width={bw - 10} height={Math.max(h, v ? 3 : 0)}
                  fill={color(i)} opacity="0.85" />
            {v > 0 && (
              <text x={i * bw + bw / 2} y={H - h - 7} textAnchor="middle"
                    fontSize="12" fill="var(--muted)">{v}</text>
            )}
          </g>
        );
      })}
      <line x1="0" y1={H + 1} x2={W} y2={H + 1} stroke="var(--line-2)" />
      <text x="2" y={H + 20} fontSize="11.5" fill="var(--muted)">0.0 — routes clean</text>
      <text x={W - 2} y={H + 20} fontSize="11.5" fill="var(--muted)" textAnchor="end">1.0 — undeliverable</text>
    </svg>
  );
}

/* ------------------------------ overview ------------------------------ */

function Overview({ real, go }) {
  const stats = useMemo(() => {
    const recs = real?.records || [];
    const bands = { low: 0, medium: 0, high: 0 };
    recs.forEach((r) => bands[r.score.band]++);
    const calls = recs.filter((r) => r.score.will_likely_need_call).length;
    return { n: recs.length, bands, calls };
  }, [real]);

  const pct = (x) => (stats.n ? Math.round((100 * x) / stats.n) : 0);

  const drivers = useMemo(() => {
    const recs = real?.records || [];
    const buckets = [
      ["No house or flat number", /house or flat number/i],
      ["Nothing below locality level", /street nor building/i],
      ["No locality identified", /No locality/i],
      ["No pincode on record", /No pincode/i],
      ["Rural / administrative addressing", /Rural\/administrative/i],
      ["Landmark-only address", /Landmark-only/i],
    ];
    const out = buckets.map(([label, rx]) => ({
      label,
      n: recs.filter((r) => r.score.reasons.some((x) => rx.test(x))).length,
    })).filter((d) => d.n > 0).sort((a, b) => b.n - a.n);
    const max = out[0]?.n || 1;
    return { out, max };
  }, [real]);

  return (
    <div className="view">
      <FlowStrip />

      <div className="block statgrid">
        <div className="scell">
          <div className="k">Dedupe precision — real pairs</div>
          <div className="v" style={{ color: "var(--blue)" }}><CountUp value={1.0} decimals={3} /></div>
          <div className="d"><span className="delta up">▲ 0 false merges</span> on 36 labelled IFSC pairs</div>
        </div>
        <div className="scell">
          <div className="k">F1 vs best baseline</div>
          <div className="v">0.769</div>
          <div className="d"><span className="delta up">▲ +0.144</span> vs raw string matching (0.625)</div>
        </div>
        <div className="scell">
          <div className="k">Records analysed</div>
          <div className="v">{stats.n || "—"}</div>
          <div className="d">sampled from 182,758 branch addresses</div>
        </div>
        <div className="scell">
          <div className="k">Will likely need a rider call</div>
          <div className="v" style={{ color: "var(--magenta)" }}>{pct(stats.calls)}%</div>
          <div className="d"><span className="delta down">▼ flagged pre-dispatch</span> {stats.calls} of {stats.n} records</div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Deliverability risk, by band</h3>
          <span className="right">Razorpay open IFSC dataset · unmodified</span>
        </div>
        {["high", "medium", "low"].map((band) => (
          <div key={band} className={`brow ${band.slice(0, 2)}`}>
            <div className="name" style={{ textTransform: "capitalize" }}>
              {band}
              <small>{band === "high" ? "rider call likely" : band === "medium" ? "friction expected" : "routes clean"}</small>
            </div>
            <div className="track"><i style={{ width: `${pct(stats.bands[band])}%` }} /></div>
            <div className="val">{stats.bands[band]} · {pct(stats.bands[band])}%</div>
          </div>
        ))}
      </div>

      <div className="duo">
        <div className="block">
          <div className="block-head">
            <h3>Risk distribution</h3>
            <span className="right">{stats.n} records, binned by score</span>
          </div>
          <div className="block-body">
            <RiskHistogram records={real?.records || []} />
          </div>
        </div>
        <div className="block">
          <div className="block-head"><h3>Dataset & provenance</h3></div>
          <div className="block-body prov">
            <div><b>Source</b><span>Razorpay open IFSC dataset — 182,758 Indian bank branch addresses, used unmodified</span></div>
            <div><b>Sample</b><span>{stats.n || "—"} records, one per district, spread across states</span></div>
            <div><b>Ground truth</b><span>36 pairs labelled by inspection — MICR codes proved unreliable (8 true of 18 shared)</span></div>
            <div><b>Method</b><span>LLM parse (sarvam-105b) → deterministic coarse/fine resolution → rule-based scoring</span></div>
            <div><b>Scripts</b><span>Latin, Devanagari, Tamil and Bengali inputs resolve to one canonical Latin record</span></div>
            <div><b>Known limits</b><span>8 positive pairs; weights tuned post-hoc. Full caveats in Evidence.</span></div>
          </div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Top risk drivers</h3>
          <span className="right">why addresses fail, ranked — computed from this sample</span>
        </div>
        {drivers.out.map((d) => (
          <div key={d.label} className="brow">
            <div className="name" style={{ gridColumn: "1 / 2" }}>{d.label}</div>
            <div className="track"><i style={{ width: `${Math.round((100 * d.n) / drivers.max)}%` }} /></div>
            <div className="val">{d.n} records</div>
          </div>
        ))}
      </div>

      <div className="block statgrid three">
        <button className="scell act" onClick={() => go("resolve")}>
          <div className="k">Layer 1</div>
          <div className="qtitle">Compare two addresses →</div>
          <div className="d">Same door, or different door? Live, via Sarvam.</div>
        </button>
        <button className="scell act" onClick={() => go("batch")}>
          <div className="k">Batch</div>
          <div className="qtitle">Deduplicate a file →</div>
          <div className="d">Real records in, unique doors and golden records out.</div>
        </button>
        <button className="scell act" onClick={() => go("evidence")}>
          <div className="k">Evaluation</div>
          <div className="qtitle">See the evidence →</div>
          <div className="d">Benchmarks, provenance, and the honest caveats.</div>
        </button>
      </div>
    </div>
  );
}

/* -------------------------------- parse --------------------------------- */

const PARSE_EXAMPLES = [
  { key: "landmark", tile: "t1", chip: "real", name: "Landmark-led",
    sub: "temple as the reference point",
    text: "GROUND FLOOR, SUDHAMA BUILDING, DAULAT BHAI ROAD, NEAR JAGANATH, TEMPLE, NANICHHIPWAD, VALSAD" },
  { key: "khasra", tile: "t2", chip: "real", name: "Revenue-record address",
    sub: "khasra / khewat + a metro pillar",
    text: "KHEWAT NO. 50 4, KHATA NO.55, KHASRA NO 397, OPP. METRO PILLAR NO 908, SANKHOL, BAHADURGARH" },
  { key: "rural", tile: "t3", chip: "real", name: "Village chain",
    sub: "village → post office → district",
    text: "VILLAGE DHANORA, PO HANODA, DIST DURG, CHATTISGARH" },
  { key: "script", tile: "t4", chip: "demo", name: "Multi-script",
    sub: "constructed — Devanagari input",
    text: "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८" },
];

function ParseView() {
  const [text, setText] = useState(PARSE_EXAMPLES[0].text);
  const [active, setActive] = useState("landmark");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState(null);

  const run = async () => {
    if (text.trim().length < 3) return;
    setBusy(true); setErr("");
    try {
      setRes(await parseAddress(text.trim()));
    } catch (e) {
      setErr(`Request failed: ${e.message}. Is the API reachable?`);
    } finally {
      setBusy(false);
    }
  };

  const d = res?.deliverability;
  const pc = res?.pincode_check;
  const riskColor = d
    ? d.band === "high" ? "var(--magenta)" : d.band === "medium" ? "var(--amber)" : "var(--green)"
    : "var(--ink)";

  return (
    <div className="view play">
      <div>
        <Steps items={["Pick a real example on the right (or type your own)", "Press Parse", "Read the fields, the risk, and what to ask the customer"]} />
        <div className="block" style={{ padding: 22 }}>
          <label htmlFor="parse-in">One address — any script, any structure</label>
          <textarea id="parse-in" value={text}
                    onChange={(e) => { setText(e.target.value); setActive(null); }} />
          <div className="controls">
            <button className="btn" onClick={run} disabled={busy}>
              {busy ? "Extracting…" : "Extract fields"}
            </button>
            {busy && <span className="hint"><span className="spin" />language ID + structured extraction</span>}
          </div>
          {err && <div className="error">{err}</div>}

          {res && (
            <div className="verdict">
              <div className="vhead">
                <div className="vscore" style={{ color: riskColor }}>
                  {d ? d.risk.toFixed(2) : "—"}
                </div>
                {d && <span className={`stamp ${d.band === "high" ? "different" : d.band === "medium" ? "likely" : "same"}`}>
                  {d.band} risk
                </span>}
                <div className="vsum">
                  {d?.will_likely_need_call
                    ? "This address will likely cost a rider phone call."
                    : "This address routes without intervention."}
                  {res.script_code ? ` Input script: ${scriptName(res.script_code)}${
                    res.language_code ? ` · language guess: ${res.language_code}` : ""}.` : ""}
                </div>
              </div>
              <div className="vbody">
                <label>Structured components</label>
                <div className="fields">
                  {FIELD_KEYS.map((k) => (
                    <div key={k} className={`f${res[k] ? "" : " empty"}`}>
                      <div className="k">{k.replace(/_/g, " ")}</div>
                      <div className="v">{res[k] || "—"}</div>
                    </div>
                  ))}
                </div>
                <div>
                  {(res.landmarks || []).map((l, i) => (
                    <span key={i} className="lm-pill"><i>{l.relation || "near"}</i>{l.name}</span>
                  ))}
                </div>

                {pc?.exists != null && (
                  <div className="chips" style={{ marginTop: 14 }}>
                    <span className={`chip${pc.exists ? " hit" : " miss"}`}>
                      PIN {res.pincode}: {pc.exists ? "exists in postal directory" : "not in postal directory"}
                    </span>
                    {pc.exists && pc.state_consistent === false &&
                      <span className="chip miss">state conflicts with pincode</span>}
                    {pc.exists && pc.city_consistent === false &&
                      <span className="chip miss">city conflicts with pincode</span>}
                  </div>
                )}

                {d?.reasons?.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <label>Why</label>
                    {d.reasons.slice(0, 4).map((x, i) => (
                      <div key={i} style={{ fontSize: 12.5, color: "var(--ink-2)", padding: "5px 0 5px 12px",
                                            borderLeft: "2px solid var(--line-2)", marginBottom: 4 }}>{x}</div>
                    ))}
                  </div>
                )}
                {d?.ask_for && (
                  <div style={{ marginTop: 12, fontSize: 12.5, color: "var(--sage)" }}>
                    <span className="lm-pill"><i>ask for</i>{d.ask_for.label}</span>
                    −{d.ask_for.risk_reduction} risk if answered
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="rail">
        <label style={{ margin: "4px 0 2px" }}>Real address patterns</label>
        {PARSE_EXAMPLES.map((ex) => (
          <button key={ex.key} className={`ex${active === ex.key ? " on" : ""}`}
            onClick={() => { setText(ex.text); setActive(ex.key); setRes(null); }}>
            <span className={`ex-tile ${ex.tile}`} aria-hidden />
            <span>
              <span className="ex-name">{ex.name}</span><br />
              <span className="ex-sub">{ex.sub}</span>
            </span>
            <span className={`ex-chip ${ex.chip}`}>{ex.chip}</span>
          </button>
        ))}
        <div className="note" style={{ marginTop: 8 }}>
          The landmark is not noise to strip — in India it <b>is</b> the address.
          Lattice extracts every reference point with its spatial relation, and
          keeps a separate slot for the property&apos;s own visual identity.
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ resolve ------------------------------ */

function Resolve() {
  const [a, setA] = useState(EXAMPLES[0].a);
  const [b, setB] = useState(EXAMPLES[0].b);
  const [active, setActive] = useState("spacing");
  const [hint, setHint] = useState(EXAMPLES[0].hint);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState(null);

  const run = useCallback(async () => {
    if (a.trim().length < 3 || b.trim().length < 3) return;
    setBusy(true); setErr("");
    try {
      setRes(await compareAddresses(a.trim(), b.trim()));
    } catch (e) {
      setErr(`Request failed: ${e.message}. Is the API reachable?`);
    } finally {
      setBusy(false);
    }
  }, [a, b]);

  const r = res?.result;
  const summary = r && {
    same: "These two strings describe the same physical door.",
    likely: "Probably the same door — needs a human look.",
    different: "Different doors.",
  }[r.verdict];

  return (
    <div className="view play">
      <div>
        <Steps items={["Pick an example — each shows a different real-world trap", "Press Resolve", "The verdict: are these two records one physical door?"]} />
        <div className="block" style={{ padding: 22 }}>
          <div className="two">
            <div>
              <label htmlFor="addr-a">Address A</label>
              <textarea id="addr-a" value={a} onChange={(e) => { setA(e.target.value); setActive(null); }} />
            </div>
            <div>
              <label htmlFor="addr-b">Address B</label>
              <textarea id="addr-b" value={b} onChange={(e) => { setB(e.target.value); setActive(null); }} />
            </div>
          </div>
          <div className="controls">
            <button className="btn" onClick={run} disabled={busy}>
              {busy ? "Comparing…" : "Compare"}
            </button>
            <span className="hint">{busy ? <><span className="spin" />two parses + resolution</> : hint}</span>
          </div>
          {err && <div className="error">{err}</div>}

          {res && (res.a?.error || res.b?.error) && (
            <div className="error" style={{ marginTop: 14, padding: "10px 14px",
                 background: "var(--magenta-soft)", border: "1px solid #edc7d8" }}>
              Parse failed on address {res.a?.error ? "A" : "B"} — the model returned
              nothing after 5 attempts. The verdict below is not meaningful; press
              Resolve again.
            </div>
          )}
          {r && !res.a?.error && !res.b?.error && (
            <div className="verdict">
              <div className="vhead">
                <div className="vscore" style={{
                  color: r.verdict === "same" ? "var(--green)"
                       : r.verdict === "likely" ? "var(--amber)" : "var(--magenta)",
                }}>
                  <CountUp value={r.score} />
                </div>
                <span className={`stamp ${r.verdict}`}>{r.verdict === "same" ? "same door" : r.verdict}</span>
                <div className="vsum">{summary}</div>
              </div>
              <div className="vbody">
                <div className="gauges">
                  <div className="gauge">
                    <div className="gt">Coarse — same neighbourhood?</div>
                    <div className="gv">{r.coarse == null ? "—" : r.coarse.toFixed(2)}</div>
                    <div className="track"><div className="fill" style={{ width: `${Math.round((r.coarse || 0) * 100)}%` }} /></div>
                    <div className="gd">pincode · city · locality · sublocality</div>
                  </div>
                  <div className="gauge fine">
                    <div className="gt">Fine — same door?</div>
                    <div className="gv">{r.fine == null ? "none" : r.fine.toFixed(2)}</div>
                    <div className="track">
                      <div className="fill" style={{ width: `${Math.round((r.fine || 0) * 100)}%` }} />
                      <div className="tick" style={{ left: "75%" }} title="decision threshold 0.75" />
                    </div>
                    <div className="gd">house no · building · landmarks · street — <b>0.75+ means same door</b></div>
                  </div>
                </div>
                <div className="chips">
                  {Object.entries(r.signals)
                    .filter(([k]) => r.observed.includes(k))
                    .map(([k, v]) => (
                      <span key={k} className={`chip${v >= 0.85 ? " hit" : v < 0.4 ? " miss" : ""}`}>
                        {k.replace(/_/g, " ")} <b>{v.toFixed(2)}</b>
                      </span>
                    ))}
                </div>
                {r.matched_landmarks?.length > 0 && (
                  <div className="lmmatch"><b>Landmarks agreed:</b> {r.matched_landmarks.join(", ")}</div>
                )}
                {r.veto && <div className="veto">Deal-breaker — {r.veto === "no door-level evidence" ? "no house number, building or landmark to compare — same area is not proof of same door" : r.veto}</div>}

                <div className="two" style={{ marginTop: 22 }}>
                  {[["A", res.a], ["B", res.b]].map(([tag, p]) => (
                    <div key={tag}>
                      <label>{tag} — parsed{p.script_code ? ` · ${p.script_code}` : ""}</label>
                      <div className="fields">
                        {FIELD_KEYS.map((k) => (
                          <div key={k} className={`f${p?.[k] ? "" : " empty"}`}>
                            <div className="k">{k.replace(/_/g, " ")}</div>
                            <div className="v">{p?.[k] || "—"}</div>
                          </div>
                        ))}
                      </div>
                      <div>
                        {(p?.landmarks || []).map((l, i) => (
                          <span key={i} className="lm-pill"><i>{l.relation || "near"}</i>{l.name}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="rail">
        <label style={{ margin: "4px 0 2px" }}>Examples</label>
        {EXAMPLES.map((ex) => (
          <button key={ex.key} className={`ex${active === ex.key ? " on" : ""}`}
            onClick={() => { setA(ex.a); setB(ex.b); setHint(ex.hint); setActive(ex.key); setRes(null); }}>
            <span className={`ex-tile ${ex.tile}`} aria-hidden />
            <span>
              <span className="ex-name">{ex.name}</span><br />
              <span className="ex-sub">{ex.sub}</span>
            </span>
            <span className={`ex-chip ${ex.chip}`}>{ex.chip}</span>
          </button>
        ))}
        <div className="note" style={{ marginTop: 8 }}>
          Validation APIs check one address in isolation. Resolution answers the
          operational question: <b>are these two records one door?</b> That is what
          collapses duplicate CRM rows — and what surfaces six loan applications
          filed from one house.
        </div>
      </div>
    </div>
  );
}

/* ---------------------------- deliverability ---------------------------- */

function Deliver() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState(null);

  const run = async () => {
    const addr = text.trim();
    if (addr.length < 3) { setErr("Type an address first."); return; }
    setBusy(true); setErr(""); setRes(null);
    try {
      const d = await parseAddress(addr);
      if (!d.deliverability) throw new Error("no score returned");
      setRes({ raw: addr, parsed: d, s: d.deliverability });
    } catch (e) { setErr(`Could not score that: ${e.message}`); }
    finally { setBusy(false); }
  };

  const s = res?.s;

  return (
    <div className="view">
      <div className="block">
        <div className="block-head">
          <h3>Score an address before you dispatch</h3>
          <span className="right">any script &middot; any format</span>
        </div>
        <div className="block-body">
          <p style={{ fontSize: 13.5, color: "var(--ink-2)", maxWidth: "64ch", marginBottom: 14 }}>
            Paste an address exactly as a customer typed it. You get a risk band,
            the reasons behind it, and the single field worth asking for.
          </p>
          <textarea
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(); }}
            placeholder="Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038"
            style={{ width: "100%", fontFamily: "var(--mono)", fontSize: 12.5 }}
          />
          <div style={{ display: "flex", gap: 16, marginTop: 12, alignItems: "center", flexWrap: "wrap" }}>
            <button className="btn" onClick={run} disabled={busy}>
              {busy ? "Scoring…" : "Score this address"}
            </button>
            <span style={{ fontSize: 11.5, color: "var(--muted)" }}>
              first call on a cold address takes a few seconds
            </span>
          </div>
          {err && <div className="error" style={{ marginTop: 12 }}>{err}</div>}
        </div>
      </div>

      {s && (
        <>
          <div className="block statgrid three">
            <div className="scell">
              <div className="k">Risk band</div>
              <div className="qtitle"><span className={`band ${s.band}`}>{s.band}</span></div>
              <div className="d">{s.band === "high" ? "likely to fail or need a rider call"
                : s.band === "medium" ? "deliverable, but expect friction"
                : "enough to find the door"}</div>
            </div>
            <div className="scell">
              <div className="k">Risk score</div>
              <div className="qtitle" style={{ fontFamily: "var(--mono)" }}>{s.risk.toFixed(2)}</div>
              <div className={`riskbar ${s.band}`} style={{ marginTop: 6 }}>
                <div className="track"><i style={{ width: `${Math.round(s.risk * 100)}%` }} /></div>
              </div>
            </div>
            <div className="scell">
              <div className="k">Ask the customer for</div>
              <div className="qtitle" style={{ fontSize: 14 }}>
                {s.ask_for ? s.ask_for.label : "nothing — it is complete"}
              </div>
              <div className="d">
                {s.ask_for ? `would cut risk by ${s.ask_for.risk_reduction}` : "no single field improves it"}
              </div>
            </div>
          </div>

          <div className="block">
            <div className="block-head">
              <h3>Why</h3>
              <span className="right">rule-based, so every point is checkable</span>
            </div>
            <div className="block-body">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.9 }}>
                {(s.reasons || []).map((r, i) => <li key={i}>{r}</li>)}
                {!(s.reasons || []).length && <li>No risk signals fired on this address.</li>}
              </ul>
            </div>
          </div>

          <div className="block">
            <div className="block-head">
              <h3>What was read out of it</h3>
              <span className="right">the fields the score is computed from</span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead><tr><th>Field</th><th>Value</th></tr></thead>
                <tbody>
                  {["house_number", "building", "street", "sublocality", "locality",
                    "city", "district", "state", "pincode"].map((f) => (
                    <tr key={f}>
                      <td style={{ width: 190, color: "var(--muted)" }}>{f.replace(/_/g, " ")}</td>
                      <td className="mono">
                        {res.parsed[f] || <span style={{ color: "var(--muted)" }}>&mdash;</span>}
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td style={{ color: "var(--muted)" }}>landmarks</td>
                    <td className="mono">
                      {(res.parsed.landmarks || []).length
                        ? res.parsed.landmarks.map((l) => `${l.relation} ${l.name}`).join(", ")
                        : <span style={{ color: "var(--muted)" }}>&mdash;</span>}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <div className="note">
        Rule-based on purpose &mdash; an ops team can&apos;t action a black-box number.
        Every score names the missing field, and <b>ask-for</b> is computed by
        re-scoring with that field filled in: the one question that most reduces risk.
      </div>
    </div>
  );
}

/* -------------------------------- batch --------------------------------- */

function BatchView() {
  const [text, setText] = useState(REAL_BATCH.join("\n"));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState(null);
  const [job, setJob] = useState(null);        // {id,status,total,parsed_done}
  const [jobRows, setJobRows] = useState(null);
  const [jobErr, setJobErr] = useState("");
  const [history, setHistory] = useState([]);

  const refreshHistory = useCallback(() => {
    listJobs().then((js) => setHistory(js.sort((a, b) => b.created - a.created))).catch(() => {});
  }, []);
  useEffect(() => { refreshHistory(); }, [refreshHistory]);

  const openJob = async (j) => {
    setJob(j); setJobRows(null); setJobErr("");
    if (j.status === "done") {
      try { setJobRows((await getJobResults(j.id)).result?.records || []); }
      catch (e) { setJobErr(e.message); }
    }
  };

  const importCsv = async (file) => {
    setJobErr(""); setJobRows(null);
    try {
      const txt = await file.text();
      const j = await submitCsvJob(txt, file.name);
      setJob(j); refreshHistory();
      const tick = async () => {
        try {
          const cur = await getJob(j.id);
          setJob(cur);
          if (cur.status === "done") {
            const r = await getJobResults(j.id);
            setJobRows(r.result?.records || []);
            refreshHistory();
          } else if (cur.status === "error") {
            setJobErr(cur.error || "job failed");
          } else {
            setTimeout(tick, 1500);
          }
        } catch (e) { setJobErr(e.message); }
      };
      setTimeout(tick, 1200);
    } catch (e) { setJobErr(`Import failed: ${e.message}`); }
  };

  const lines = text.split("\n").map((s) => s.trim()).filter((s) => s.length >= 3);

  const run = async () => {
    if (!lines.length || lines.length > 40) return;
    setBusy(true); setErr(""); setRes(null);
    try {
      setRes(await batchAddresses(lines));
    } catch (e) {
      setErr(`Request failed: ${e.message}. Is the API reachable?`);
    } finally {
      setBusy(false);
    }
  };

  const groups = useMemo(() => {
    if (!res) return [];
    const g = {};
    res.parsed.forEach((p, i) => {
      (g[p.cluster] = g[p.cluster] || []).push({ ...p, idx: i });
    });
    return Object.entries(g)
      .map(([cid, members]) => {
        const golden =
          res.golden_records?.find((x) => String(x.cluster) === String(cid)) ||
          members.find((m) => m.golden)?.golden || null;
        return { cid, members, golden };
      })
      .sort((a, b) => b.members.length - a.members.length);
  }, [res]);

  return (
    <div className="view">
      <Steps items={["Run the prefilled sample, or import your own CSV", "Watch duplicates collapse into doors", "Download the cleaned file"]} />
      <div className="block" style={{ padding: 22 }}>
        <label htmlFor="batch-in">
          Addresses — one per line, up to 40 · prefilled with real IFSC records containing duplicates
        </label>
        <textarea id="batch-in" style={{ minHeight: 190 }} value={text}
                  onChange={(e) => setText(e.target.value)} />
        <div className="controls">
          <button className="btn" onClick={run} disabled={busy || !lines.length || lines.length > 40}>
            {busy ? "Deduplicating…" : `Run dedupe on ${lines.length} addresses`}
          </button>
          <button className="btn ghost" onClick={() => { setText(REAL_BATCH.join("\n")); setRes(null); }} disabled={busy}>
            Reset to sample
          </button>
          <label htmlFor="csvfile" className="btn ghost" style={{ cursor: "pointer" }}>
            Import CSV…
          </label>
          <input id="csvfile" type="file" accept=".csv,text/csv" style={{ display: "none" }}
                 onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])} />
          <span className="hint">
            {busy
              ? <><span className="spin" />parsing {lines.length} addresses via Sarvam — roughly 2s each</>
              : lines.length > 40 ? "40 max here — CSV import handles up to 5,000" : "CSV: one address per row, up to 5,000"}
          </span>
        </div>
        {err && <div className="error">{err}</div>}
        {jobErr && <div className="error">{jobErr}</div>}

        {job && (
          <div className="verdict" style={{ marginTop: 18 }}>
            <div className="vhead">
              <div className="vscore" style={{ fontSize: 30, color: job.status === "done" ? "var(--green)" : "var(--blue)" }}>
                {job.status === "done" ? "done" : <><span className="spin" />{job.parsed_done}/{job.total}</>}
              </div>
              <div className="vsum">
                Job <span style={{ fontFamily: "var(--mono)" }}>{job.id}</span> · {job.label || "csv import"}
                {job.cache_hits > 0 ? ` · ${job.cache_hits} cache hits` : ""}
              </div>
              {job.status === "done" && (
                <a className="btn ghost" href={jobCsvUrl(job.id)} target="_blank" rel="noreferrer"
                   style={{ textDecoration: "none" }}>Download results CSV</a>
              )}
            </div>
            {jobRows && (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead><tr><th>Address (as written)</th><th>Cluster</th><th>Locality / City</th><th>Risk</th><th>Ask for</th></tr></thead>
                  <tbody>
                    {jobRows.slice(0, 50).map((r, i) => {
                      const dl = r.deliverability || {};
                      return (
                        <tr key={i}>
                          <td style={{ maxWidth: 380 }}><span className="mono">{r.raw}</span></td>
                          <td className="num">{r.cluster}</td>
                          <td style={{ fontSize: 12.5 }}>{[...new Set([r.locality, r.city].filter(Boolean))].join(", ") || "—"}</td>
                          <td>
                            <div className={`riskbar ${dl.band || "low"}`}>
                              <div className="track"><i style={{ width: `${Math.round((dl.risk || 0) * 100)}%` }} /></div>
                              <b>{dl.risk != null ? dl.risk.toFixed(2) : "—"}</b>
                            </div>
                          </td>
                          <td style={{ fontSize: 12 }}>{dl.ask_for?.label || "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {jobRows.length > 50 && (
                  <div style={{ padding: "10px 22px", fontSize: 12, color: "var(--muted)" }}>
                    Showing 50 of {jobRows.length} — full set in the CSV download.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {history.length > 0 && (
        <div className="block">
          <div className="block-head">
            <h3>Job history</h3>
            <span className="right">in-memory store — survives until the API restarts</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Job</th><th>Label</th><th>Status</th><th>Progress</th><th>Cache hits</th><th></th></tr></thead>
              <tbody>
                {history.slice(0, 8).map((j) => (
                  <tr key={j.id} style={{ cursor: j.status === "done" ? "pointer" : "default" }}
                      onClick={() => j.status === "done" && openJob(j)}>
                    <td className="num">{j.id.slice(0, 8)}</td>
                    <td style={{ fontSize: 12.5 }}>{j.label || "—"}</td>
                    <td><span className={`band ${j.status === "done" ? "low" : j.status === "error" ? "high" : "medium"}`}>{j.status}</span></td>
                    <td className="num">{j.parsed_done}/{j.total}</td>
                    <td className="num">{j.cache_hits}</td>
                    <td style={{ fontSize: 12 }}>
                      {j.status === "done" && (
                        <a href={jobCsvUrl(j.id)} target="_blank" rel="noreferrer"
                           onClick={(e) => e.stopPropagation()}
                           style={{ color: "var(--blue)", fontWeight: 600 }}>CSV ↓</a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {res && (
        <>
          <div className="note" style={{ borderStyle: "solid", background: "var(--blue-soft)", borderColor: "#c6d6f2", fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>
            {res.parsed.length} addresses went in — they describe {res.unique_locations} real doors.{" "}
            {res.duplicates_collapsed > 0 ? `${res.duplicates_collapsed} were the same place written differently.` : "No duplicates found."}
          </div>
          <div className="block statgrid">
            <div className="scell"><div className="k">Records in</div><div className="v">{res.parsed.length}</div></div>
            <div className="scell"><div className="k">Unique locations</div><div className="v" style={{ color: "var(--blue)" }}>{res.unique_locations}</div></div>
            <div className="scell">
              <div className="k">Duplicates collapsed</div>
              <div className="v" style={{ color: "var(--green)" }}>{res.duplicates_collapsed}</div>
              <div className="d">same door, written differently</div>
            </div>
            <div className="scell">
              <div className="k">Mean call risk</div>
              <div className="v">{res.deliverability?.mean_risk?.toFixed(2) ?? "—"}</div>
              <div className="d">{res.deliverability ? `${res.deliverability.flagged_pct}% high-risk` : ""}</div>
            </div>
          </div>

          <div className="clusters-grid">
            {groups.map(({ cid, members, golden }) => (
              <div key={cid} className={`clus${members.length > 1 ? " multi" : ""}`}>
                <div className="clus-head">
                  <span className="clus-n">
                    {members.length > 1 ? `${members.length} records → 1 door` : "1 record"}
                  </span>
                  <span className="clus-loc">
                    {[...new Set([members[0].locality, members[0].city].filter(Boolean))].join(", ") || "unresolved area"}
                  </span>
                </div>
                {members.map((m) => (
                  <div key={m.idx} className="clus-raw">
                    <i className={`banddot ${m.deliverability?.band || "low"}`} aria-hidden />
                    {m.raw}
                  </div>
                ))}
                {golden && (
                  <div className="golden">
                    <span>
                      golden record — one clean merged address · agreed from {golden.member_count ?? members.length} records
                      {golden.contested_fields?.length
                        ? ` · contested: ${golden.contested_fields.join(", ")}` : ""}
                    </span>
                    {golden.canonical_text || golden.formatted ||
                      JSON.stringify(golden.components || golden)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------- evidence ------------------------------- */

function Evidence() {
  return (
    <div className="view">
      <div className="block">
        <div className="block-head">
          <h3>Entity resolution vs the incumbent</h3>
          <span className="right">36 real pairs · 8 same-building · labels by inspection</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>Method</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead>
            <tbody>
              {BENCH.map((row) => (
                <tr key={row.m} className={row.win ? "win" : ""}>
                  <td>{row.m}</td>
                  <td className="num">{row.p}</td>
                  <td className="num">{row.r}</td>
                  <td className="num">{row.f}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="note">
        <b>Provenance.</b> Addresses are real and unmodified — Razorpay&apos;s open
        IFSC dataset, 182,758 bank branches. Labels are ours, assigned by reading
        each pair, because MICR codes are <i>not</i> reliable ground truth: of 18
        records sharing a MICR, only 8 were actually the same building. Stale
        duplicates inside a production banking dataset — the exact problem this
        product exists to solve.
      </div>
      <div className="note">
        <b>Limits.</b> 36 pairs, 8 positives — small. Signal weights were adjusted
        after seeing these results, so treat the margin as indicative, not
        validated. The number that matters for enterprise use is{" "}
        <b>precision 1.000</b>: Lattice merged nothing it shouldn&apos;t have,
        while raw matching produced 2–7 false merges depending on threshold. In
        dedupe, a false merge means two customers silently become one record.
      </div>
    </div>
  );
}

/* ------------------------------ agents / mcp ----------------------------- */

const MCP_TOOLS = [
  ["parse_address", "One messy address, any script → structured components + risk + pincode check."],
  ["compare_addresses", "Two strings → same door or not, with per-signal evidence and vetoes."],
  ["dedupe_batch", "Up to 40 addresses → clusters, golden records, per-address risk."],
  ["match_address", "Incoming address vs the reference corpus — seen before, under any spelling?"],
  ["check_pincode", "6-digit PIN → exists, state, district, served areas. Offline directory."],
  ["digipin_encode", "Coordinates → DIGIPIN code on India Post's official grid."],
  ["digipin_decode", "DIGIPIN code → cell centre and bounds."],
];

const MCP_REMOTE_CMD = `claude mcp add --transport http lattice \
  {api}/mcp \
  --header "X-API-Key: ltk_your-key"`;

const MCP_REMOTE_JSON = `{
  "mcpServers": {
    "lattice": {
      "type": "http",
      "url": "{api}/mcp",
      "headers": { "X-API-Key": "ltk_your-key" }
    }
  }
}`;
/* The docs render the static copies shipped with the build
   (lib/exampleSnippets.js, generated from examples/*). Deliberately NOT
   fetched live from GET /examples/{name}: the deployed API can lag the repo
   and would overwrite these with stale code. Regenerate the module after
   editing examples/ (see tasklist.md). */
function useExampleCode(name) {
  return EXAMPLE_SNIPPETS[name] || `# examples/${name}`;
}

const API_SAMPLES = [
  ["Devanagari", { address: "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८" }],
  ["Hinglish", { address: "Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038" }],
  ["IFSC + hints", { id: "rec-01", address: "MADHAVLEELA COMPLEX, 1ST FLOOR, MASKASATH SQUARE, ITWARI", city: "Nagpur" }],
];

const maskKey = (k) => (k ? k.slice(0, 9) + "*".repeat(Math.max(4, k.length - 9)) : "");

function ApiTester({ goKeys }) {
  const [body, setBody] = useState(JSON.stringify(API_SAMPLES[0][1], null, 2));
  const [resp, setResp] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const send = async () => {
    setBusy(true); setErr(""); setResp(null);
    try {
      const r = await fetch(proxyBase() + "/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      setResp({ status: r.status, data: await r.json() });
    } catch (e) { setErr(`Request failed: ${e.message}`); }
    finally { setBusy(false); }
  };

  const curl = `curl -s -X POST ${apiBase()}/parse \\
  -H 'Content-Type: application/json' \\
  -H "X-API-Key: $LATTICE_KEY" \\
  -d '${body.replace(/\n\s*/g, " ")}'`;

  const mono = { fontFamily: "var(--mono)", fontSize: 11.5, lineHeight: 1.65 };
  return (
    <div className="block">
      <div className="block-head">
        <h3>Test it — one record, live</h3>
        <span className="right">POST /parse · unstructured in, structured + DIGIPIN + lat/lon out</span>
      </div>
      <div className="block-body">
        <div className="two">
          <div>
            <label>Request body</label>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} spellCheck={false}
                      style={{ minHeight: 130 }} />
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              {API_SAMPLES.map(([name, sample]) => (
                <button key={name} className="chip-btn"
                        onClick={() => { setBody(JSON.stringify(sample, null, 2)); setResp(null); }}>
                  {name}
                </button>
              ))}
              <button className="btn" style={{ marginLeft: "auto", height: 34, padding: "0 22px", fontSize: 12.5 }}
                      onClick={send} disabled={busy}>
                {busy ? <><span className="spin" />Parsing…</> : "Send →"}
              </button>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 12 }}>as curl:</div>
            <pre style={{ ...mono, fontSize: 10.5, margin: "6px 0 0", padding: "10px 13px", overflowX: "auto",
                          background: "var(--canvas)", border: "1px solid var(--line)", color: "var(--ink-2)" }}>
{curl}
            </pre>
          </div>
          <div>
            <label>Response {resp && <span style={{ color: resp.status === 200 ? "var(--green)" : "var(--magenta)" }}>· HTTP {resp.status}</span>}</label>
            <pre style={{ ...mono, margin: 0, padding: "12px 14px", minHeight: 130, maxHeight: 420, overflow: "auto",
                          background: "var(--canvas)", border: "1px solid var(--line)", color: "var(--ink-2)" }}>
{resp ? JSON.stringify(resp.data, null, 2) : "—  send a record to see the structured output"}
            </pre>
            {err && <div className="error">{err}</div>}
          </div>
        </div>
        <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 12 }}>
          Requests are authenticated with this console's key. Need your own?{" "}
          {goKeys
            ? <button className="expand" style={{ padding: 0 }} onClick={goKeys}>Generate one under API keys →</button>
            : "Generate one under API keys."}
        </div>
      </div>
    </div>
  );
}

const REQ_SHAPE = `POST {api}/parse
Content-Type: application/json
X-API-Key: <your key>

{
  "address": "Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038",

  // optional \u2014 fills what the string doesn't state.
  // Never overrides something the address itself says.
  "pincode":  "411038",
  "city":     "Pune",
  "district": "Pune",
  "state":    "Maharashtra",

  // optional \u2014 echoed back as "id", so you can match
  // responses to your own rows in a batch.
  "id": "cust_10482"
}`;

const RESP_SHAPE = `200 OK

{
  // ---- how usable is this, in one word ----
  "status":  "partial",          // ok | partial | unusable
  "message": "Locality and pincode agree; however, no house or flat
              number is present. Adding the house / flat / door number
              would substantially improve deliverability.",

  // ---- the components, null when the address doesn't say ----
  "occupant":      null,
  "house_number":  null,
  "building":      null,
  "street":        null,
  "sublocality":   null,
  "locality":      "Kothrud",
  "post_office":   null,
  "city":          "Pune",
  "district":      null,
  "state":         "Maharashtra",
  "pincode":       "411038",

  // ---- landmarks keep their spatial relation ----
  "landmarks": [
    { "name": "Ganesh Mandir", "relation": "behind"   },
    { "name": "SBI ATM",       "relation": "opposite" }
  ],

  "completeness": 0.44,
  "missing": ["house_number", "street"],

  // ---- layer 2: risk before dispatch ----
  "deliverability": {
    "risk": 0.66,
    "band": "high",                     // low | medium | high
    "will_likely_need_call": true,
    "reasons": [
      "No house or flat number \u2014 rider must identify the door from
       the building name or landmark alone.",
      "Landmark-only address \u2014 resolvable by someone who already
       knows the area, not by a first-time rider."
    ],
    "ask_for": {                        // the ONE field worth asking for
      "field": "house_number",
      "label": "House / flat / door number",
      "why":   "the single highest-value field \u2014 it is what identifies the door",
      "risk_reduction": 0.44
    }
  },

  // ---- offline postal-directory check ----
  "pincode_check": {
    "exists": true,
    "state_consistent": true,
    "city_consistent": true,
    "locality_listed": true,
    "conflicts": [],
    "directory": { "state": "Maharashtra", "district": "Pune",
                   "areas": ["Kothrud", "Bhusari Colony"] }
  },

  // ---- coordinates, with their honest precision ----
  "location": {
    "latitude": 18.5072618, "longitude": 73.8056676,
    "precision": "street-level",        // never claimed finer than earned
    "source": "osm-nominatim"
  },
  "digipin": "4FP-4CK-5L2",

  "error": null
}`;

const FIELD_NOTES = [
  ["status", "ok \u00b7 partial \u00b7 unusable", "Read this before anything else. It is the single field that says whether you can dispatch on this address."],
  ["null fields", "null, never empty", "A field is null when the address does not state it. We never guess a city or respell a proper noun \u2014 a confident wrong value is worse than a missing one."],
  ["landmarks[]", "{name, relation}", "relation \u2208 behind, opposite, near, beside, above, below. Kept as data, not flattened into a string, because the relation is what makes it navigable."],
  ["deliverability.band", "low \u00b7 medium \u00b7 high", "Route high-band records to a confirmation step instead of a courier."],
  ["ask_for", "one field", "Computed by re-scoring with that field filled in. Ask the customer this and nothing else."],
  ["location.precision", "rooftop \u2192 district", "Capped at what the input earns. A locality-only address never returns a rooftop pin."],
  ["error", "null on success", "Non-null means the parse itself failed; every other field is then unreliable."],
];

function RestApiView({ go }) {
  return (
    <div className="view">
      <ApiTester goKeys={() => go("keys")} />

      <div className="duo">
        <div className="block">
          <div className="block-head">
            <h3>Request</h3>
            <span className="right">POST /parse &middot; address is the only required field</span>
          </div>
          <div className="block-body">
            <div className="curlbox codepane"><pre>{REQ_SHAPE.replace("{api}", apiBase())}</pre></div>
          </div>
        </div>

        <div className="block">
          <div className="block-head">
            <h3>Response</h3>
            <span className="right">structure + risk + coordinates in one call</span>
          </div>
          <div className="block-body">
            <div className="curlbox codepane"><pre>{RESP_SHAPE}</pre></div>
          </div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Reading the response</h3>
          <span className="right">the seven fields that carry the meaning</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>Field</th><th>Values</th><th>What it means</th></tr></thead>
            <tbody>
              {FIELD_NOTES.map(([f, v, why]) => (
                <tr key={f}>
                  <td className="mono" style={{ whiteSpace: "nowrap", fontWeight: 600 }}>{f}</td>
                  <td className="mono" style={{ whiteSpace: "nowrap", fontSize: 11.5, color: "var(--muted)" }}>{v}</td>
                  <td style={{ fontSize: 12.5 }}>{why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="note">
        <b>The contract in one line.</b> Unstructured address in — any script, spoken or
        typed — structured components, deliverability risk, lat/long and DIGIPIN out,
        with an honest <b>status</b> + <b>message</b> when the input isn't enough. Full
        guide under <b>Documentation</b>; keys under <b>API keys</b>.
      </div>
    </div>
  );
}

/* ------------------------------ speech → json ------------------------------ */

const STT_CURL = `# request — raw audio bytes in the body, format in Content-Type
curl -s -X POST {api}/stt/parse \\
  -H 'Content-Type: audio/mpeg' \\
  -H "X-API-Key: $LATTICE_KEY" \\
  --data-binary @spoken_address.mp3

# accepted: mp3, wav, m4a, ogg, webm/opus (live mic) · max 10 MB
# language is auto-detected — Hindi, Marathi, Tamil, Bengali, English…`;

const STT_RESP = `{
  // ---- what was heard ----
  "transcript": "गणेश मंदिराच्या मागे, निळा गेट, कोथरूड, पुणे ४११०३८",
  "spoken_language": "mr-IN",
  "language_probability": 0.98,

  // ---- then the standard /parse contract, unchanged ----
  "status": "partial",
  "message": "The address is valid at the locality level but …",
  "locality": "Kothrud",  "city": "Pune",  "pincode": "411038",
  "landmarks": [ { "name": "Ganesh Mandir", "relation": "behind" } ],
  "deliverability": { "risk": 0.55, "band": "medium", "ask_for": { … } },
  "location": { "latitude": 18.5072, "longitude": 73.8056,
                "precision": "street-level", "source": "osm-nominatim" },
  "digipin": "4FP-4CK-5L65",
  "digipin_at_precision": "4FP-4CK-5L"
}

// nothing intelligible in the audio -> no guessing:
{ "status": "error", "transcript": "",
  "message": "Could not hear an address in the audio -- it came back empty. …" }`;

const STT_FIELD_NOTES = [
  ["transcript", "the words heard", "Returned verbatim, in the script that was spoken. Show it back to the caller \u2014 it is how they catch a mishearing before it becomes a failed delivery."],
  ["spoken_language", "mr-IN, hi-IN, ta-IN\u2026", "Auto-detected. You do not pass a language hint, and you do not need to know it in advance."],
  ["language_probability", "0.0 \u2013 1.0", "Confidence in that detection. Low values usually mean noise or code-mixing, and are worth a re-record prompt."],
  ["status", "ok \u00b7 partial \u00b7 unusable \u00b7 error", "error means nothing intelligible was heard \u2014 the transcript is empty and no address was guessed from silence."],
  ["everything else", "same as /parse", "Components, landmarks, deliverability, pincode_check, location and digipin are identical to the typed endpoint. One integration covers both."],
  ["Content-Type", "audio/mpeg, audio/wav\u2026", "The audio bytes are the raw request body. No multipart, no form fields \u2014 POST /stt returns the transcript alone if that is all you need."],
];

function SttView() {
  const [rec, setRec] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resp, setResp] = useState(null);
  const [err, setErr] = useState("");
  const mrRef = useRef(null);
  const fileRef = useRef(null);
  const mono = { fontFamily: "var(--mono)", fontSize: 11.5, lineHeight: 1.65 };

  const sendAudio = async (blob, type) => {
    setBusy(true); setErr(""); setResp(null);
    try {
      const r = await fetch(proxyBase() + "/stt/parse", {
        method: "POST",
        headers: { "Content-Type": type || "audio/webm" },
        body: blob,
      });
      setResp({ status: r.status, data: await r.json() });
    } catch (e) { setErr(`Request failed: ${e.message}`); }
    finally { setBusy(false); }
  };

  const start = async () => {
    setErr(""); setResp(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      const chunks = [];
      mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        setRec(false);
        const type = mr.mimeType || "audio/webm";
        sendAudio(new Blob(chunks, { type }), type);
      };
      mr.start();
      mrRef.current = mr;
      setRec(true);
    } catch (e) { setErr(`Microphone unavailable: ${e.message}`); }
  };

  const stop = () => mrRef.current?.state === "recording" && mrRef.current.stop();

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (f) sendAudio(f, f.type || "audio/mpeg");
    e.target.value = "";
  };

  const d = resp?.data;
  return (
    <div className="view">
      <div className="block">
        <div className="block-head">
          <h3>Speak an address — any language</h3>
          <span className="right">POST /stt/parse · Saaras STT → full parse pipeline → JSON</span>
        </div>
        <div className="block-body">
          <div className="two" style={{ alignItems: "start" }}>
            <div>
              <label>Input</label>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <button className="btn" style={{ background: rec ? "var(--magenta)" : undefined, borderColor: rec ? "var(--magenta)" : undefined }}
                        onClick={rec ? stop : start} disabled={busy}>
                  {rec ? "■ Stop & transcribe" : "● Record live"}
                </button>
                <button className="chip-btn" onClick={() => fileRef.current?.click()} disabled={busy || rec}>
                  Upload mp3 / wav
                </button>
                <input ref={fileRef} type="file" accept=".mp3,.wav,.m4a,.ogg,audio/*" onChange={onFile} hidden />
                {busy && <span className="hint"><span className="spin" />transcribing &amp; parsing…</span>}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 14, lineHeight: 1.7, maxWidth: "48ch" }}>
                Say it the way a customer would: <i>"Ganesh mandir ke peeche, blue gate wala
                ghar, Kothrud, Pune char one one zero three eight"</i> — Hindi, Marathi,
                Tamil, Bengali or English. The transcript runs through the same pipeline
                as typed input: components, risk, lat/long, DIGIPIN.
              </div>
              {d?.transcript !== undefined && (
                <div style={{ marginTop: 16 }}>
                  <label>Heard</label>
                  <div style={{ ...mono, fontSize: 13, padding: "10px 13px", background: "var(--canvas)",
                                border: "1px solid var(--line)", color: "var(--ink)" }}>
                    {d.transcript || "—"}
                    {d.spoken_language && <span style={{ color: "var(--muted)" }}>  · {d.spoken_language}</span>}
                  </div>
                </div>
              )}
            </div>
            <div>
              <label>Response {resp && <span style={{ color: resp.status === 200 ? "var(--green)" : "var(--magenta)" }}>· HTTP {resp.status}</span>}</label>
              <pre style={{ ...mono, margin: 0, padding: "12px 14px", minHeight: 170, maxHeight: 460, overflow: "auto",
                            background: "var(--canvas)", border: "1px solid var(--line)", color: "var(--ink-2)" }}>
{d ? JSON.stringify(d, null, 2) : "—  record or upload audio to see the structured output"}
              </pre>
              {err && <div className="error">{err}</div>}
            </div>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 12 }}>
            Requests are authenticated with this console's key — same auth as every endpoint.
            Engineers integrate with their own key from the <b>API keys</b> page.
          </div>
        </div>
      </div>

      <div className="duo">
        <div className="block">
          <div className="block-head">
            <h3>Request</h3>
            <span className="right">POST /stt/parse · raw audio body · X-API-Key</span>
          </div>
          <div className="block-body">
            <div className="curlbox codepane"><pre>{STT_CURL.replace("{api}", apiBase())}</pre></div>
          </div>
        </div>
        <div className="block">
          <div className="block-head">
            <h3>Response</h3>
            <span className="right">transcript + the standard /parse contract</span>
          </div>
          <div className="block-body">
            <div className="curlbox codepane"><pre>{STT_RESP}</pre></div>
          </div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Reading the response</h3>
          <span className="right">what voice adds on top of the /parse contract</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>Field</th><th>Values</th><th>What it means</th></tr></thead>
            <tbody>
              {STT_FIELD_NOTES.map(([f, v, why]) => (
                <tr key={f}>
                  <td className="mono" style={{ whiteSpace: "nowrap", fontWeight: 600 }}>{f}</td>
                  <td className="mono" style={{ whiteSpace: "nowrap", fontSize: 11.5, color: "var(--muted)" }}>{v}</td>
                  <td style={{ fontSize: 12.5 }}>{why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="note">
        <b>Why voice.</b> The next hundred million users speak their address — they don't
        drop pins or type in Latin script. <span style={{ fontFamily: "var(--mono)" }}>POST /stt/parse</span> accepts
        mp3, wav or a live mic recording as the raw request body and returns the standard
        /parse contract plus the transcript and detected language — one call from speech
        to a structured, geocoded, DIGIPIN-coded record.
      </div>
    </div>
  );
}

/* -------------------------------- api keys -------------------------------- */

function Avatar({ user, className = "avatar" }) {
  const [broken, setBroken] = useState(false);
  const initial = (user?.name || user?.email || "?")[0].toUpperCase();
  // Google's avatar CDN rejects requests that carry a referrer, which is what
  // left a broken-image glyph here. no-referrer fixes the common case; onError
  // covers the rest, because an initial always beats a broken icon.
  if (!user?.image || broken) {
    return <span className={`${className} ph`}>{initial}</span>;
  }
  return (
    <img src={user.image} alt="" className={className}
         referrerPolicy="no-referrer" onError={() => setBroken(true)} />
  );
}

function KeysView() {
  const { data: session } = useSession();
  const [keys, setKeys] = useState(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState(null);
  const [copied, setCopied] = useState(null);
  const [err, setErr] = useState("");
  const mono = { fontFamily: "var(--mono)" };

  // Keys are fetched from this app's own /api/keys, not from the Lattice API.
  // That route reads the account from the signed session server-side, so the
  // browser cannot ask for someone else's keys -- there is no email to tamper
  // with in the request.
  const load = useCallback(async () => {
    setErr("");
    try {
      const r = await fetch("/api/keys", { cache: "no-store" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      setKeys(d.keys || []);
    } catch (e) { setErr(e.message); setKeys([]); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch("/api/keys", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: label.trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      setFresh(d); setLabel(""); await load();
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const revoke = async (id) => {
    setErr("");
    try {
      const r = await fetch(`/api/keys?id=${id}`, { method: "DELETE" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      if (fresh?.id === id) setFresh(null);
      await load();
    } catch (e) { setErr(e.message); }
  };

  // Copying is the last time the full key is shown. It is stored hashed-by-
  // signature, not looked up, so we genuinely cannot show it again -- clearing
  // it here makes that visible instead of leaving a live key on a shared
  // screen. The list below shows only a masked prefix.
  const copy = async (text, id) => {
    try { await navigator.clipboard.writeText(text); } catch {}
    setCopied(id);
    setTimeout(() => { setCopied(null); if (id === "fresh") setFresh(null); }, 1200);
  };

  const mask = (k) => `${k.slice(0, 12)}${"•".repeat(12)}${k.slice(-4)}`;
  const totalCalls = (keys || []).reduce((n, k) => n + (k.calls || 0), 0);
  // Usage is metered per key, so "never used" is a real and useful state --
  // it is usually a key someone generated and then lost.
  const ago = (iso) => {
    if (!iso) return null;
    const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
    return `${Math.floor(mins / 1440)}d ago`;
  };

  return (
    <div className="view">
      <div className="block statgrid three">
        <div className="scell">
          <div className="k">Account</div>
          <div className="qtitle" style={{ fontSize: 14 }}>{session?.user?.email || "—"}</div>
          <div className="d">Keys below belong to this account only</div>
        </div>
        <div className="scell">
          <div className="k">How to send it</div>
          <div className="qtitle" style={{ ...mono, fontSize: 13 }}>X-API-Key: {"<key>"}</div>
          <div className="d">An HTTP header on every request</div>
        </div>
        <div className="scell">
          <div className="k">Calls made</div>
          <div className="v">{keys === null ? "\u2014" : totalCalls.toLocaleString()}</div>
          <div className="d">
            {keys === null ? "loading" : `across ${keys.length} key${keys.length === 1 ? "" : "s"} on this account`}
          </div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Generate an API key</h3>
          <span className="right">as many as you need</span>
        </div>
        <div className="block-body">
          <p style={{ fontSize: 13.5, color: "var(--ink-2)", maxWidth: "64ch", marginBottom: 14 }}>
            Give each key a name so you know what to revoke later &mdash; one per
            environment or per integration means a leaked staging key never
            takes production down with it.
          </p>
          <div className="row" style={{ gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !busy) generate(); }}
              placeholder="production, staging, my-laptop…"
              maxLength={60}
              style={{ flex: "1 1 260px", minWidth: 220 }}
            />
            <button className="btn" onClick={generate} disabled={busy}>
              {busy ? "Generating…" : "Generate API key"}
            </button>
          </div>
          {err && <div className="error" style={{ marginTop: 12 }}>{err}</div>}

          {fresh && (
            <div style={{ marginTop: 18 }}>
              <div className="k" style={{ marginBottom: 6 }}>
                New key &mdash; {fresh.label}. Copy it now.
              </div>
              <div className="keybox">
                <code>{fresh.api_key}</code>
                <button className="btn ghost" onClick={() => copy(fresh.api_key, "fresh")}>
                  {copied === "fresh" ? "Copied" : "Copy"}
                </button>
              </div>
              <div className="curlbox" style={{ marginTop: 14 }}>
                <div className="curl-label">Try it</div>
                <pre>{`curl -X POST ${apiBase()}/parse \\
  -H "X-API-Key: ${fresh.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{"address":"Ganesh mandir ke peeche, blue gate, Kothrud, Pune 411038"}'`}</pre>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Your keys</h3>
          <span className="right">{keys === null ? "loading…" : `${keys.length} active`}</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr><th>Name</th><th>Key</th><th>Calls</th><th>Last used</th><th>Created</th><th /></tr>
            </thead>
            <tbody>
              {keys === null && (
                <tr><td colSpan={6} style={{ color: "var(--muted)" }}>Loading&hellip;</td></tr>
              )}
              {keys?.length === 0 && (
                <tr><td colSpan={6} style={{ color: "var(--muted)" }}>
                  No keys yet &mdash; generate one above.
                </td></tr>
              )}
              {keys?.map((k) => (
                <tr key={k.id}>
                  <td style={{ fontWeight: 600 }}>{k.label}</td>
                  <td>
                    <span className="mono" style={{ fontSize: 11.5 }}>{mask(k.api_key)}</span>
                  </td>
                  <td className="mono" style={{ fontSize: 12.5, fontVariantNumeric: "tabular-nums" }}>
                    {(k.calls || 0).toLocaleString()}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--muted)" }}>
                    {ago(k.last_seen) || (k.calls ? "\u2014" : "never used")}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--muted)" }}>
                    {(k.created_at || "").slice(0, 10)}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn ghost" style={{ padding: "2px 10px", fontSize: 11 }}
                            onClick={() => revoke(k.id)}>Revoke</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="note">
        Usage is counted per key, which is what makes a key worth naming: a
        key with calls is in something, a key that says <b>never used</b> is
        safe to revoke. A key is shown in full once, when you generate it — copy it then, because
        this list only ever shows a masked prefix. Lost one? Generate another and
        revoke the old. Signing in with a different Google account shows that
        account&apos;s keys and nothing else.
      </div>
    </div>
  );
}

function McpView() {
  const api = apiBase();
  return (
    <div className="view">
      <div className="block statgrid three">
        <div className="scell">
          <div className="k">Tools</div>
          <div className="v" style={{ color: "var(--blue)" }}>7</div>
          <div className="d">extract · compare · dedupe · match · validate · DIGIPIN</div>
        </div>
        <div className="scell">
          <div className="k">Transport</div>
          <div className="v" style={{ fontSize: 22, paddingTop: 4 }}>HTTP</div>
          <div className="d">hosted — nothing to install, nothing to clone</div>
        </div>
        <div className="scell">
          <div className="k">Auth</div>
          <div className="qtitle" style={{ fontFamily: "var(--mono)", fontSize: 13 }}>X-API-Key</div>
          <div className="d">your own key, sent as a header</div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Add it to your agent</h3>
          <span className="right">one command, no checkout</span>
        </div>
        <div className="block-body">
          <p style={{ fontSize: 13.5, color: "var(--ink-2)", maxWidth: "64ch", marginBottom: 14 }}>
            Lattice is served as a hosted MCP server, so an agent connects to it
            over HTTP the way it would any other remote tool. Generate a key
            under <b>API keys</b>, drop it into the header, and the seven tools
            below appear in your agent&apos;s toolbox.
          </p>
          <div className="curlbox"><pre>{MCP_REMOTE_CMD.replace("{api}", api)}</pre></div>
          <div style={{ fontSize: 11.5, color: "var(--muted)", margin: "14px 0 8px" }}>
            Or, for a client that reads a config file — Claude Desktop, Cursor,
            or a checked-in <span style={{ fontFamily: "var(--mono)" }}>.mcp.json</span>:
          </div>
          <div className="curlbox"><pre>{MCP_REMOTE_JSON.replace("{api}", api)}</pre></div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Tools an agent can call</h3>
          <span className="right">verified live against {"{api}"}/mcp</span>
        </div>
        {MCP_TOOLS.map(([name, desc]) => (
          <div key={name} className="brow" style={{ gridTemplateColumns: "180px 1fr" }}>
            <div className="name" style={{ fontFamily: "var(--mono)", fontSize: 12.5 }}>{name}</div>
            <div style={{ fontSize: 12.5, color: "var(--muted)" }}>{desc}</div>
          </div>
        ))}
      </div>

      <div className="note">
        <b>Why this exists.</b> The next generation of ops software is agentic — and an
        agent booking a delivery or reviewing a loan file needs the same three answers a
        human does: what does this address say, is it the one we already have, will it
        deliver. Lattice exposes exactly those as tools any MCP-capable agent can call.
      </div>
    </div>
  );
}

function DocsView() {
  const createkeyCode = useExampleCode("createkey.sh");
  const usageCode = useExampleCode("usage.py");
  return (
    <div className="view">
      <div className="block statgrid three">
        <div className="scell">
          <div className="k">Step 1</div>
          <div className="qtitle">Get a key</div>
          <div className="d">Self-service, shown once. Send it as <code style={{ fontFamily: "var(--mono)" }}>X-API-Key</code>.</div>
        </div>
        <div className="scell">
          <div className="k">Step 2</div>
          <div className="qtitle">Use the REST API</div>
          <div className="d">POST an address, get structured fields, risk and DIGIPIN back.</div>
        </div>
        <div className="scell">
          <div className="k">Step 3</div>
          <div className="qtitle">Use speech → JSON</div>
          <div className="d">Post audio of a spoken address; Saaras transcribes, Lattice parses.</div>
        </div>
      </div>

      <div className="duo">
        <div className="block">
          <div className="block-head">
            <h3>1 · Get a key</h3>
            <span className="right">examples/createkey.sh · in this repo</span>
          </div>
          <div className="block-body">
            <pre style={{ margin: 0, fontFamily: "var(--mono)", fontSize: 10.5, lineHeight: 1.65,
                          color: "var(--ink-2)", overflowX: "auto", background: "var(--canvas)",
                          border: "1px solid var(--line)", borderRadius: 10, padding: "10px 13px" }}>
{createkeyCode}
            </pre>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 10 }}>
              Keys are self-service and shown once. No arguments needed — it defaults to the
              deployed API; pass a URL to mint against a local server.
            </div>
          </div>
        </div>

        <div className="block">
          <div className="block-head">
            <h3>2 · Use the API</h3>
            <span className="right">examples/usage.py · stdlib only, nothing to install</span>
          </div>
          <div className="block-body">
            <pre style={{ margin: 0, fontFamily: "var(--mono)", fontSize: 10.5, lineHeight: 1.65,
                          color: "var(--ink-2)", overflowX: "auto", maxHeight: 420, overflowY: "auto",
                          background: "var(--canvas)", border: "1px solid var(--line)",
                          borderRadius: 10, padding: "10px 13px" }}>
{usageCode}
            </pre>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 10 }}>
              The curl request in Python. Set{" "}
              <span style={{ fontFamily: "var(--mono)" }}>URL</span>,{" "}
              <span style={{ fontFamily: "var(--mono)" }}>KEY</span> and{" "}
              <span style={{ fontFamily: "var(--mono)" }}>ADDRESS</span> at the top, run{" "}
              <span style={{ fontFamily: "var(--mono)" }}>python3 examples/usage.py</span> — it
              prints the full JSON response.
            </div>
          </div>
        </div>

        <div className="block">
          <div className="block-head">
            <h3>3 · Speech → JSON</h3>
            <span className="right">examples/stt.py · stdlib only, nothing to install</span>
          </div>
          <div className="block-body">
            <pre style={{ margin: 0, fontFamily: "var(--mono)", fontSize: 10.5, lineHeight: 1.65,
                          color: "var(--ink-2)", overflowX: "auto", maxHeight: 420, overflowY: "auto",
                          background: "var(--canvas)", border: "1px solid var(--line)",
                          borderRadius: 10, padding: "10px 13px" }}>
{useExampleCode("stt.py")}
            </pre>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 10 }}>
              The spoken version: set{" "}
              <span style={{ fontFamily: "var(--mono)" }}>URL</span> and{" "}
              <span style={{ fontFamily: "var(--mono)" }}>KEY</span> at the top; it asks for the
              audio file path (wav/mp3/ogg/webm), posts the raw audio to{" "}
              <span style={{ fontFamily: "var(--mono)" }}>/stt/parse</span>, and prints the full
              JSON — transcript, spoken language, and the parsed address.
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}

/* --------------------------------- usage --------------------------------- */

function UsageView({ goKeys }) {
  const [u, setU] = useState(null);
  const [err, setErr] = useState("");
  const mono = { fontFamily: "var(--mono)" };

  useEffect(() => {
    fetch("/api/usage?days=30", { cache: "no-store" })
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
        setU(d);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const ago = (iso) => {
    if (!iso) return "never used";
    const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
    return `${Math.floor(mins / 1440)}d ago`;
  };
  const mask = (p) => `${p}${"•".repeat(10)}`;

  if (err) return <div className="view"><div className="error">{err}</div></div>;
  if (!u) return <div className="view"><div style={{ color: "var(--muted)", fontSize: 13 }}>Loading usage…</div></div>;

  const windowCalls = u.endpoints.reduce((n, e) => n + e.calls, 0);
  const maxEp = Math.max(1, ...u.endpoints.map((e) => e.calls));
  const busiest = u.daily.reduce((b, d) => (d.calls > (b?.calls || 0) ? d : b), null);
  const maxDay = Math.max(1, ...u.daily.map((d) => d.calls));
  // render a continuous 30-day strip, zero-filling days with no calls
  const days = [];
  for (let i = 29; i >= 0; i--) {
    const day = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    days.push({ day, calls: u.daily.find((d) => d.day === day)?.calls || 0 });
  }

  return (
    <div className="view">
      <div className="block statgrid">
        <div className="scell">
          <div className="k">Calls · last 30 days</div>
          <div className="v" style={{ color: "var(--blue)" }}>{windowCalls.toLocaleString()}</div>
          <div className="d">{u.total_calls.toLocaleString()} all-time on this account</div>
        </div>
        <div className="scell">
          <div className="k">APIs used</div>
          <div className="v">{u.endpoints.length}</div>
          <div className="d">{u.endpoints[0] ? `most called: ${u.endpoints[0].endpoint}` : "no calls yet"}</div>
        </div>
        <div className="scell">
          <div className="k">Keys</div>
          <div className="v">{u.keys.length}</div>
          <div className="d">{u.keys.filter((k) => k.calls > 0).length} with recorded traffic</div>
        </div>
        <div className="scell">
          <div className="k">Busiest day</div>
          <div className="v" style={{ fontSize: 22, paddingTop: 4 }}>
            {busiest ? busiest.day.slice(5) : "—"}
          </div>
          <div className="d">{busiest ? `${busiest.calls.toLocaleString()} calls` : "no traffic in window"}</div>
        </div>
      </div>

      <div className="duo">
        <div className="block">
          <div className="block-head">
            <h3>Calls by API</h3>
            <span className="right">last 30 days</span>
          </div>
          <div className="block-body">
            {u.endpoints.length === 0 && (
              <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
                No calls recorded yet — send a request with one of your keys and it
                will appear here within a second.
              </div>
            )}
            {u.endpoints.map((e) => (
              <div key={e.endpoint} style={{ display: "grid", gridTemplateColumns: "110px 1fr 64px",
                                             gap: 10, alignItems: "center", padding: "7px 0" }}>
                <span style={{ ...mono, fontSize: 12.5 }}>{e.endpoint}</span>
                <div style={{ height: 8, background: "var(--canvas)", borderRadius: 99, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(100 * e.calls) / maxEp}%`,
                                background: "var(--blue)", borderRadius: 99 }} />
                </div>
                <span style={{ ...mono, fontSize: 12, textAlign: "right", color: "var(--ink-2)" }}>
                  {e.calls.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="block">
          <div className="block-head">
            <h3>Daily activity</h3>
            <span className="right">one bar per day · 30 days</span>
          </div>
          <div className="block-body">
            <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 120 }}>
              {days.map((d) => (
                <div key={d.day} title={`${d.day}: ${d.calls} calls`}
                     style={{ flex: 1, minWidth: 4, borderRadius: 2,
                              height: `${Math.max(3, (100 * d.calls) / maxDay)}%`,
                              background: d.calls ? "var(--blue)" : "var(--line-2)" }} />
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8,
                          fontSize: 10.5, color: "var(--muted)", fontFamily: "var(--mono)" }}>
              <span>{days[0].day}</span><span>today</span>
            </div>
          </div>
        </div>
      </div>

      <div className="block">
        <div className="block-head">
          <h3>Per key</h3>
          <span className="right">usage is metered per key</span>
        </div>
        {u.keys.length === 0 && (
          <div className="block-body" style={{ fontSize: 12.5, color: "var(--muted)" }}>
            No keys on this account yet.{" "}
            <button className="expand" style={{ padding: 0 }} onClick={goKeys}>
              Generate one under API keys →
            </button>
          </div>
        )}
        {u.keys.map((k) => (
          <div key={k.id} className="brow" style={{ gridTemplateColumns: "160px 1fr 90px 110px" }}>
            <div className="name" style={{ fontSize: 12.5 }}>{k.label}</div>
            <div style={{ ...mono, fontSize: 12, color: "var(--muted)" }}>{mask(k.key_prefix)}</div>
            <div style={{ ...mono, fontSize: 12.5, textAlign: "right" }}>{k.calls.toLocaleString()}</div>
            <div style={{ fontSize: 11.5, color: "var(--muted)", textAlign: "right" }}>{ago(k.last_seen)}</div>
          </div>
        ))}
      </div>

      <div className="note">
        Counts cover every authenticated call made with this account&apos;s keys —
        console, curl, scripts and MCP agents alike. The console&apos;s shared demo key
        is not attributed to your account, so playground clicks here don&apos;t inflate
        your numbers.
      </div>
    </div>
  );
}

/* --------------------------------- shell --------------------------------- */

const VIEWS = {
  // Named for what the user does, not for the layer it happens to be. Someone
  // seeing this console for the first time should not have to learn our
  // vocabulary before they can find the thing they came for.
  parse: { title: "Extract", icon: I.parse, stage: null,
           sub: "turn one messy address into clean, labelled fields" },
  resolve: { title: "Compare", icon: I.resolve, stage: null,
             sub: "do these two addresses point at the same door?" },
  batch: { title: "Deduplicate", icon: I.batch, stage: null,
           sub: "upload a file, get one clean record per real location" },
  deliver: { title: "Score", icon: I.deliver, stage: null,
             sub: "how likely is this to fail, and what should you ask for?" },
  digipin: { title: "Group by DIGIPIN", icon: I.digipin, stage: null,
             sub: "bucket points into map cells — one cell, one delivery run" },
  rest: { title: "REST API", icon: I.rest, stage: null,
          sub: "one call: address in, structured JSON out" },
  stt: { title: "Speech → JSON", icon: I.mic, stage: null,
         sub: "a spoken address — mp3 or live mic — through the same pipeline" },
  mcp: { title: "MCP", icon: I.mcp, stage: null,
         sub: "the same tools, callable by an AI agent" },
  keys: { title: "API keys", icon: I.key, stage: null,
          sub: "generate and revoke keys for your account" },
  usage: { title: "Usage", icon: I.evidence, stage: null,
           sub: "what your keys actually did — calls, APIs, days" },
  docs: { title: "Documentation", icon: I.docs, stage: null,
          sub: "how to get a key, call the API, and send audio" },
};
const INTEGRATE_KEYS = ["rest", "stt", "mcp", "keys", "usage", "docs"];
const FLOW_KEYS = ["parse", "resolve", "batch", "deliver", "digipin"];

export default function Page() {
  const { data: session } = useSession();
  const [view, setView] = useState("parse");
  const [real, setReal] = useState(null);

  useEffect(() => {
    fetchReal().then(setReal).catch(() => {});
  }, []);

  return (
    <div className="shell">
      <aside className="side">
        <Link href="/" className="brand">
          <Mark />
          <span>
            <span className="brand-name">lattice</span>
            <div className="brand-sub">Indian Address Intelligence</div>
          </span>
        </Link>
        <div className="nav-group">The flow</div>
        {FLOW_KEYS.map((k) => [k, VIEWS[k]]).map(([k, v]) => (
          <button key={k} className={`nav-item${view === k ? " on" : ""}`} onClick={() => setView(k)}>
            {v.icon}{v.title}
          </button>
        ))}
        <div className="nav-group">Integrate</div>
        {INTEGRATE_KEYS.map((k) => [k, VIEWS[k]]).map(([k, v]) => (
          <button key={k} className={`nav-item${view === k ? " on" : ""}`} onClick={() => setView(k)}>
            {v.icon}{v.title}
          </button>
        ))}

        <div className="side-foot">
          {session?.user && (
            <div className="whoami">
              <Avatar user={session.user} />
              <span className="who">
                <b>{session.user.name || "Signed in"}</b>
                <em>{session.user.email}</em>
              </span>
            </div>
          )}
          <button className="signout" onClick={() => signOut({ callbackUrl: "/" })}>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor"
                 strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 14H3.5A1.5 1.5 0 0 1 2 12.5v-9A1.5 1.5 0 0 1 3.5 2H6M10.5 11 14 8l-3.5-3M14 8H6" />
            </svg>
            Sign out
          </button>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <h1>{VIEWS[view].title}</h1>
          <span className="topbar-sub">{VIEWS[view].sub}</span>
          {session?.user && (
            <div className="top-right">
              <span className="userchip" title={session.user.email}>
                <Avatar user={session.user} className="chipimg" />
                <span>{session.user.name?.split(" ")[0] || "Signed in"}</span>
              </span>
            </div>
          )}
        </div>
        <div className="content">
          {view === "parse" && <ParseView />}
          {view === "resolve" && <Resolve />}
          {view === "batch" && <BatchView />}
          {view === "deliver" && <Deliver />}
          {view === "digipin" && <div className="view"><GroupByDigipin /></div>}
          {view === "rest" && <RestApiView go={setView} />}
          {view === "stt" && <SttView />}
          {view === "mcp" && <McpView />}
          {view === "keys" && <KeysView />}
          {view === "usage" && <UsageView goKeys={() => setView("keys")} />}
          {view === "docs" && <DocsView />}
        </div>
      </div>
    </div>
  );
}
