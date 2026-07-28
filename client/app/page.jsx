"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { signIn, useSession } from "next-auth/react";
import { apiBase } from "@/lib/api";

const Mark = ({ s = 22 }) => (
  <svg width={s} height={s} viewBox="0 0 22 22" aria-hidden>
    <rect x="1.4" y="1.4" width="8" height="8" rx="2.2" fill="none" stroke="var(--navy)" strokeWidth="1.7" />
    <rect x="12.6" y="1.4" width="8" height="8" rx="2.2" fill="var(--blue)" />
    <rect x="1.4" y="12.6" width="8" height="8" rx="2.2" fill="none" stroke="var(--navy)" strokeWidth="1.7" />
    <rect x="12.6" y="12.6" width="8" height="8" rx="2.2" fill="none" stroke="var(--navy)" strokeWidth="1.7" />
  </svg>
);

function Reveal({ children, className = "", delay = 0 }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && (el.classList.add("in"), io.disconnect()),
      { threshold: 0.12 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={`fx ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

const CAPS = [
  {
    tag: "parse",
    title: "Structure from free text",
    body: "House number, building, street, locality, pincode — and landmarks as first-class fields with spatial relations. Multi-script in, canonical structure out.",
    mono: '"behind Ganesh mandir, blue gate" → { landmark: "Ganesh Mandir", relation: "behind" }',
  },
  {
    tag: "resolve",
    title: "One door, one record",
    body: "Entity resolution across spelling, script and word-order variance. Coarse signals gate the neighbourhood; fine signals decide the door. Zero false merges on labelled real pairs.",
    mono: "compare(A, B) → { score: 0.97, verdict: same }",
  },
  {
    tag: "score",
    title: "Risk before dispatch",
    body: "Deliverability scored at order time, not at the doorstep. Every flag names the missing field and the single question that most reduces risk.",
    mono: 'risk: 0.66 → ask_for: "house number" (−0.28)',
  },
];

const SECTORS = [
  ["Quick commerce & logistics", "Cut rider calls and failed attempts. Consolidate duplicate drop points before routing."],
  ["Lending & BFSI", "Six applications, one house, six spellings — surfaced as one address. Field verification, pre-screened."],
  ["Healthcare", "Patient record deduplication across facilities, where a missed match hides an allergy history."],
  ["Insurance", "Property records resolved to a single risk location before pricing or claim assessment."],
];

const SEATS = 50;

function Access() {
  const { data: session } = useSession();
  const [form, setForm] = useState({ name: "", email: "", company: "", use_case: "" });
  const [key, setKey] = useState(null);
  const [returning, setReturning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [taken, setTaken] = useState(null);
  const [copied, setCopied] = useState(false);
  const [next, setNext] = useState("/dashboard");

  useEffect(() => {
    const cb = new URLSearchParams(window.location.search).get("callbackUrl");
    if (cb) setNext(cb);
  }, []);

  useEffect(() => {
    if (session?.user) {
      setForm((f) => ({ ...f, name: f.name || session.user.name || "",
                             email: f.email || session.user.email || "" }));
    }
  }, [session]);

  useEffect(() => {
    fetch(`${apiBase()}/stats`).then((r) => r.json())
      .then((d) => setTaken(d.signups ?? 0)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e?.preventDefault();
    if (!form.email.includes("@")) { setErr("A valid email, please."); return; }
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${apiBase()}/signup`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setKey(d.api_key); setReturning(d.returning);
      setTaken((t) => (d.returning ? t : (t ?? 0) + 1));
    } catch (e2) { setErr(`Could not issue a key: ${e2.message}`); }
    finally { setBusy(false); }
  };

  const left = taken == null ? null : Math.max(0, SEATS - taken);

  return (
    <section className="lsec alt" id="access">
      <div className="lwrap acc-wrap">
        <div>
          <div className="px-tag">Founding developers</div>
          <h2 style={{ marginBottom: 14 }}>Free access,<br />in exchange for the truth.</h2>
          <p className="lsec-sub" style={{ marginBottom: 26 }}>
            The first {SEATS} developers keep Lattice free permanently. We don&apos;t
            want money — we want to know which addresses break it.
          </p>
          {left != null && (
            <div className="seatbar">
              <div className="seatgrid" aria-hidden>
                {Array.from({ length: SEATS }).map((_, i) => (
                  <span key={i} className={`seat${i < (taken ?? 0) ? " on" : ""}`} />
                ))}
              </div>
              <div className="seatnote"><b>{taken}</b> claimed · <b>{left}</b> of {SEATS} left</div>
            </div>
          )}
          <ul className="lticks" style={{ marginTop: 28 }}>
            <li><b>Every endpoint.</b> Parse, resolve, deduplicate, score, voice, DIGIPIN — no tiering.</li>
            <li><b>The console.</b> Drop a CSV, watch duplicates collapse into doors.</li>
            <li><b>MCP server.</b> Point Claude or Cursor at it and let an agent call it.</li>
            <li><b>All we ask</b> is that you tell us where it broke.</li>
          </ul>
        </div>

        <div className="lterm" style={{ padding: 0 }}>
          {session?.user && !key ? (
            <div style={{ padding: 30 }}>
              <div className="px-tag" style={{ color: "var(--green)" }}>Signed in</div>
              <h3 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 8px" }}>
                You&apos;re in, {session.user.name?.split(" ")[0] || "there"}.
              </h3>
              <p style={{ fontSize: 13.5, color: "var(--ink-2)", marginBottom: 18 }}>
                Open the console, or claim an API key to call it from code.
              </p>
              <div className="controls" style={{ marginTop: 0, marginBottom: 22 }}>
                <Link href={next} className="btn">Open the console →</Link>
              </div>
              <div className="ordiv"><span>or get an api key</span></div>
              <form onSubmit={submit}>
                <input className="fld" placeholder="Company (optional)" value={form.company}
                       onChange={(e) => setForm({ ...form, company: e.target.value })} />
                <input className="fld" placeholder="What would you use it for? (optional)" value={form.use_case}
                       onChange={(e) => setForm({ ...form, use_case: e.target.value })} />
                <button className="btn ghost" type="submit" disabled={busy} style={{ width: "100%" }}>
                  {busy ? "Issuing your key…" : "Issue my API key"}
                </button>
              </form>
              {err && <div className="error">{err}</div>}
            </div>
          ) : key ? (
            <div style={{ padding: 30 }}>
              <div className="px-tag" style={{ color: "var(--green)" }}>
                {returning ? "Welcome back" : "Seat claimed"}
              </div>
              <h3 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 8px" }}>
                {returning ? "You already had a key." : "Here's your API key."}
              </h3>
              <p style={{ fontSize: 13.5, color: "var(--ink-2)", marginBottom: 16 }}>
                Shown once — copy it now. The same email always returns the same key.
              </p>
              <div className="keybox">
                <code>{key}</code>
                <button className="btn ghost" onClick={() => {
                  navigator.clipboard?.writeText(key);
                  setCopied(true); setTimeout(() => setCopied(false), 1800);
                }}>{copied ? "Copied" : "Copy"}</button>
              </div>
              <div className="curlbox">
                <div className="curl-label">Try it now</div>
                <pre>{`curl -X POST ${apiBase()}/parse \\
  -H "X-API-Key: ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{"address":"Ganesh mandir ke peeche, blue gate, Kothrud, Pune 411038"}'`}</pre>
              </div>
              <div className="controls" style={{ marginTop: 18 }}>
                <Link href={next} className="btn">Open the console →</Link>
                <a className="btn ghost" href={`${apiBase()}/docs`} target="_blank" rel="noreferrer">API docs</a>
              </div>
            </div>
          ) : (
            <div style={{ padding: 30 }}>
              <h3 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 6px" }}>Claim a seat</h3>
              <p style={{ fontSize: 13.5, color: "var(--ink-2)", marginBottom: 20 }}>
                Sign in to open the console, or just take an API key.
              </p>
              <button className="gbtn" onClick={() => signIn("google", { callbackUrl: next })}>
                <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden>
                  <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-2.8-.4-4H24v7.3h12.1c-.2 2-1.6 5-4.5 7l6.9 5.4c4.1-3.8 6.6-9.4 6.6-15.7z"/>
                  <path fill="#34A853" d="M24 46c5.9 0 10.9-2 14.5-5.3l-6.9-5.4c-1.9 1.3-4.4 2.2-7.6 2.2-5.8 0-10.7-3.8-12.4-9.1l-7.2 5.6C8 41 15.4 46 24 46z"/>
                  <path fill="#FBBC05" d="M11.6 28.4A13.6 13.6 0 0 1 10.9 24c0-1.5.3-3 .7-4.4l-7.2-5.6A22 22 0 0 0 2 24c0 3.6.9 7 2.4 10l7.2-5.6z"/>
                  <path fill="#EA4335" d="M24 9.5c4.1 0 6.9 1.8 8.5 3.3l6.2-6C34.9 3.3 29.9 1 24 1 15.4 1 8 6 4.4 13.3l7.2 5.6C13.3 13.6 18.2 9.5 24 9.5z"/>
                </svg>
                Continue with Google
              </button>
              <div className="ordiv"><span>or just tell us</span></div>
              <form onSubmit={submit}>
                <input className="fld" placeholder="Your name" value={form.name}
                       onChange={(e) => setForm({ ...form, name: e.target.value })} />
                <input className="fld" placeholder="Work email" type="email" required value={form.email}
                       onChange={(e) => setForm({ ...form, email: e.target.value })} />
                <input className="fld" placeholder="Company (optional)" value={form.company}
                       onChange={(e) => setForm({ ...form, company: e.target.value })} />
                <button className="btn" type="submit" disabled={busy} style={{ width: "100%", marginTop: 6 }}>
                  {busy ? "Issuing your key…" : left != null ? `Hold my seat — #${(taken ?? 0) + 1} of ${SEATS}` : "Get my API key"}
                </button>
              </form>
              {err && <div className="error">{err}</div>}
              <p style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 14 }}>
                An API key alone won&apos;t open the console — that needs sign-in.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <div className="land">
      {/* ---------------- nav ---------------- */}
      <header className="lnav">
        <div className="lwrap lnav-in">
          <span className="brand-lg">
            <Mark />
            <span className="brand-name">lattice</span>
          </span>
          <nav className="lnav-links">
            <a href="#platform">Platform</a>
            <a href="#flow">How it works</a>
            <a href="#evidence">Evidence</a>
            <a href="/slides.html">Slides</a>
          </nav>
          <div className="lnav-cta">
            <a href="#access" className="btn">Open console</a>
          </div>
        </div>
      </header>

      {/* ---------------- hero ---------------- */}
      <section className="lhero">
        <div className="lhero-grid" aria-hidden />
        <div className="lhero-glow" aria-hidden />
        <div className="lwrap lhero-in">
          <div>
            <div className="px-tag rise d1">Indian address intelligence</div>
            <h1 className="rise d2">
              Every Indian address,<br />
              <span className="grad">resolved to a door.</span>
            </h1>
            <p className="lsub rise d3">
              Free-text addresses are the last unstructured field in Indian
              operations. Lattice parses them, deduplicates them to physical
              locations, and scores delivery risk before dispatch — over your own
              data, through one API.
            </p>
            <div className="lcta rise d4">
              <a href="#access" className="btn big">Open console</a>
              <a href="#access" className="btn big ghost">See it on real data</a>
            </div>
            <div className="lmetrics rise d4">
              <div><b>1.000</b><span>dedupe precision, real pairs</span></div>
              <div><b>15–30%</b><span>RTO rate in India¹</span></div>
              <div><b>&gt;45%</b><span>of RTOs: bad addresses¹</span></div>
            </div>
          </div>

          <div className="lterm rise d3" aria-label="API response example">
            <div className="lterm-bar">
              <span /><span /><span />
              <em>POST /compare</em>
            </div>
            <pre>
{`{
  "a": "3-116, 1ST FLOOR, HANUMANNAGAR COLONY
        CHAITANYAPURI, DILSUKHNAGAR, HYDERABAD",
  "b": "DOOR NO.3-116, FIRST FLOOR, HANUMAN NAGAR
        COLONY, CHAITANYAPURI, DILSUKNAGAR"
}
`}<span className="dim">{`──────────────────────────────────────────`}</span>{`
{
  "score":   `}<span className="ok">0.971</span>{`,
  "verdict": `}<span className="ok">"same door"</span>{`,
  "coarse":  1.00,   // neighbourhood
  "fine":    0.94    // the door itself
}`}
            </pre>
          </div>
        </div>
      </section>

      {/* ---------------- capabilities ---------------- */}
      <section className="lsec" id="platform">
        <div className="lwrap">
          <Reveal><div className="px-tag">Platform</div></Reveal>
          <Reveal delay={60}><h2>Three layers. One pipeline.</h2></Reveal>
          <Reveal delay={120}>
            <p className="lsec-sub">
              Built Indic-first on the Sarvam stack — because Indian addresses fail
              Western parsers at the language layer, not the formatting layer.
            </p>
          </Reveal>
          <div className="lcaps">
            {CAPS.map((c, i) => (
              <Reveal key={c.tag} delay={i * 90}>
                <div className="lcap">
                  <div className="px-chip">{c.tag}</div>
                  <h3>{c.title}</h3>
                  <p>{c.body}</p>
                  <code>{c.mono}</code>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- how it works ---------------- */}
      <section className="lsec alt" id="flow">
        <div className="lwrap">
          <Reveal><div className="px-tag">How it works</div></Reveal>
          <Reveal delay={60}><h2>One pipeline, seven steps.</h2></Reveal>
          <Reveal delay={140}>
            <div className="lflow">
              {["Address", "LLM parse", "Normalise", "PIN check", "DIGIPIN", "Similarity", "Confidence"].map((n, i) => (
                <div key={n} className="lflow-step">
                  <span>{String(i + 1).padStart(2, "0")}</span>{n}
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={200}>
            <p className="lfine" style={{ marginTop: 18 }}>
              Free text in, structured record out — normalised across scripts, validated
              against the postal directory, resolved against your corpus, scored for risk.
              DIGIPIN cell assignment operates on coordinates; free text reaches it once a
              geocoder is in the loop.
            </p>
          </Reveal>

          <Reveal delay={240}>
            <div className="lsvc">
              {[
                ["Parsing & standardisation", "POST /parse", "Any script, any structure → one canonical record. Landmarks kept as first-class fields."],
                ["Delivery-risk score", "POST /parse", "Call-risk before dispatch, with reasons and the one field to ask the customer for."],
                ["Address similarity", "POST /compare", "Two records → same door or not, with per-signal evidence and vetoes."],
                ["File deduplication", "POST /batch", "Duplicates collapsed to physical doors; one golden record per door, with provenance."],
                ["Corpus match", "POST /match", "Does an incoming address match anything you have already seen? Top-k, scored."],
                ["Bulk jobs & CSV", "POST /jobs", "Up to 5,000 addresses per job, cached parsing, CSV in and out."],
                ["Pincode validation", "GET /pincode", "Does the PIN exist; does it agree with the stated city and state. Offline directory."],
                ["DIGIPIN utilities", "POST /digipin", "Encode, decode and group coordinates on India Post's official grid."],
              ].map(([name, ep, desc]) => (
                <div key={name} className="lsvc-cell">
                  <div className="lsvc-name">{name}</div>
                  <code>{ep}</code>
                  <p>{desc}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------------- integrate ---------------- */}
      <section className="lsec alt" id="integrate">
        <div className="lwrap lint">
          <div>
            <Reveal><div className="px-tag">Integration</div></Reveal>
            <Reveal delay={60}><h2>Built for production data pipelines.</h2></Reveal>
            <Reveal delay={120}>
              <ul className="lticks">
                <li><b>Batch-first.</b> Normalise and deduplicate an existing CRM, LOS or OMS — not one lookup at a time.</li>
                <li><b>Multi-script.</b> Devanagari, Tamil, Bengali and code-mixed Hinglish resolve to one canonical record.</li>
                <li><b>DIGIPIN-ready.</b> Structured output designed to bridge legacy records onto India&apos;s new geo-addressing standard.</li>
                <li><b>Explainable.</b> Every verdict ships its per-signal evidence. No black-box scores in an ops queue.</li>
                <li><b>Agent-ready.</b> Full OpenAPI spec at <code style={{ fontFamily: "var(--mono)", fontSize: "12px" }}>/docs</code>, and an MCP server so AI agents call parse, resolve and dedupe as native tools.</li>
              </ul>
            </Reveal>
          </div>
          <Reveal delay={150}>
            <div className="lterm">
              <div className="lterm-bar"><span /><span /><span /><em>batch dedupe</em></div>
              <pre>
{`curl -X POST $LATTICE/batch \\
  -H "Content-Type: application/json" \\
  -d '{ "addresses": [ ...your CRM rows ] }'

`}<span className="ok">{`→ 40 records
→ 31 unique locations
→ 9 duplicates collapsed`}</span>
              </pre>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------------- evidence ---------------- */}
      <section className="lsec" id="evidence">
        <div className="lwrap">
          <Reveal><div className="px-tag">Evidence</div></Reveal>
          <Reveal delay={60}><h2>Measured on real records, not demos.</h2></Reveal>
          <div className="lev">
            <Reveal delay={80}>
              <div className="lev-card">
                <b>182,758</b>
                <span>real branch addresses — the open IFSC dataset our evaluation samples from</span>
              </div>
            </Reveal>
            <Reveal delay={140}>
              <div className="lev-card">
                <b>1.000 / 0.769</b>
                <span>precision / F1 on labelled real pairs — best string-matching baseline reaches 0.625</span>
              </div>
            </Reveal>
            <Reveal delay={200}>
              <div className="lev-card">
                <b>0</b>
                <span>false merges. In deduplication, a false merge silently fuses two customers into one.</span>
              </div>
            </Reveal>
          </div>
          <Reveal delay={220}>
            <p className="lfine">
              Evaluation set: 36 labelled pairs, 8 same-building. Full provenance,
              methodology and known misses are published in the console —{" "}
              <Link href="/dashboard">including the failure cases</Link>.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ---------------- sectors ---------------- */}
      <section className="lsec alt">
        <div className="lwrap">
          <Reveal><div className="px-tag">Where it lands</div></Reveal>
          <Reveal delay={60}><h2>Built for regulated, high-volume operations.</h2></Reveal>
          <div className="lsect">
            {SECTORS.map(([t, d], i) => (
              <Reveal key={t} delay={i * 70}>
                <div className="lsect-card"><h3>{t}</h3><p>{d}</p></div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <Access />

      {/* ---------------- close ---------------- */}
      <section className="lclose">
        <div className="lwrap lclose-in">
          <Mark s={30} />
          <h2>See it work on your addresses.</h2>
          <a href="#access" className="btn big">Open console</a>
        </div>
      </section>

      <footer className="lfoot">
        <div className="lwrap lfoot-in">
          <span className="brand-lg"><Mark s={16} /><span className="brand-name" style={{ fontSize: 13 }}>lattice</span></span>
          <span>Built on the Sarvam stack · Indic-native by design</span>
          <span className="lfoot-note">¹ Industry-reported figures for COD-heavy Indian e-commerce; sources in console.</span>
        </div>
      </footer>
    </div>
  );
}
