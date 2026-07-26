"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

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
            <Link href="/dashboard" className="btn">Open console</Link>
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
              <Link href="/dashboard" className="btn big">Open console</Link>
              <Link href="/dashboard" className="btn big ghost">See it on real data</Link>
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
            <div className="lterm dark">
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

      {/* ---------------- close ---------------- */}
      <section className="lclose">
        <div className="lwrap lclose-in">
          <Mark s={30} />
          <h2>See it work on your addresses.</h2>
          <Link href="/dashboard" className="btn big">Open console</Link>
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
