"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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

const SEATS = 50;

export default function GetAccess() {
  const { data: session } = useSession();
  const [form, setForm] = useState({ name: "", email: "", company: "", use_case: "" });
  const [key, setKey] = useState(null);
  const [returning, setReturning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [taken, setTaken] = useState(null);
  const [copied, setCopied] = useState(false);

  // Google sign-in only pre-fills the form; it never gates access.
  useEffect(() => {
    if (session?.user) {
      setForm((f) => ({
        ...f,
        name: f.name || session.user.name || "",
        email: f.email || session.user.email || "",
      }));
    }
  }, [session]);

  useEffect(() => {
    fetch(`${apiBase()}/stats`)
      .then((r) => r.json())
      .then((d) => setTaken(d.signups ?? 0))
      .catch(() => {});
  }, []);

  const submit = async (e) => {
    e?.preventDefault();
    if (!form.email.includes("@")) { setErr("A valid email, please."); return; }
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${apiBase()}/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setKey(d.api_key);
      setReturning(d.returning);
      setTaken((t) => (d.returning ? t : (t ?? 0) + 1));
    } catch (e2) {
      setErr(`Could not issue a key: ${e2.message}`);
    } finally {
      setBusy(false);
    }
  };

  const left = taken == null ? null : Math.max(0, SEATS - taken);

  return (
    <div className="land">
      <header className="lnav">
        <div className="lwrap lnav-in">
          <Link href="/" className="brand-lg" style={{ textDecoration: "none", color: "inherit" }}>
            <Mark /><span className="brand-name">lattice</span>
          </Link>
          <nav className="lnav-links"><Link href="/dashboard">Console</Link></nav>
        </div>
      </header>

      <section className="lsec" style={{ paddingTop: 60 }}>
        <div className="lwrap acc-wrap">
          {/* ---------------- left: what you get ---------------- */}
          <div>
            <div className="px-tag">Founding developers</div>
            <h2 style={{ marginBottom: 14 }}>Free API access,<br />in exchange for the truth.</h2>
            <p className="lsec-sub" style={{ marginBottom: 26 }}>
              The first {SEATS} developers keep Lattice free permanently. We don&apos;t
              want money from you — we want to know which addresses break it.
            </p>

            {left != null && (
              <div className="seatbar">
                <div className="seatgrid" aria-hidden>
                  {Array.from({ length: SEATS }).map((_, i) => (
                    <span key={i} className={`seat${i < (taken ?? 0) ? " on" : ""}`} />
                  ))}
                </div>
                <div className="seatnote">
                  <b>{taken}</b> claimed · <b>{left}</b> of {SEATS} left
                </div>
              </div>
            )}

            <ul className="lticks" style={{ marginTop: 28 }}>
              <li><b>Every endpoint.</b> Parse, resolve, deduplicate, score, voice, DIGIPIN — no tiering.</li>
              <li><b>The console too.</b> Drop a CSV, watch duplicates collapse into doors.</li>
              <li><b>MCP server.</b> Point Claude or Cursor at it and let an agent call it.</li>
              <li><b>All we ask</b> is that you tell us where it broke.</li>
            </ul>
          </div>

          {/* ---------------- right: claim ---------------- */}
          <div className="lterm" style={{ padding: 0 }}>
            {key ? (
              <div style={{ padding: 30 }}>
                <div className="px-tag" style={{ color: "var(--green)" }}>
                  {returning ? "Welcome back" : "Seat claimed"}
                </div>
                <h3 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 8px" }}>
                  {returning ? "You already had a key." : "Here's your API key."}
                </h3>
                <p style={{ fontSize: 13.5, color: "var(--ink-2)", marginBottom: 16 }}>
                  Shown once — copy it now. Same email always returns the same key.
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
                  <Link href="/dashboard" className="btn">Open the console →</Link>
                  <a className="btn ghost" href={`${apiBase()}/docs`} target="_blank" rel="noreferrer">API docs</a>
                </div>
              </div>
            ) : (
              <div style={{ padding: 30 }}>
                <h3 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 6px" }}>Claim a seat</h3>
                <p style={{ fontSize: 13.5, color: "var(--ink-2)", marginBottom: 20 }}>
                  One click with Google, or just type it. Either way you get a
                  working key on this page.
                </p>

                <button className="gbtn" onClick={() => signIn("google")}>
                  <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden>
                    <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-2.8-.4-4H24v7.3h12.1c-.2 2-1.6 5-4.5 7l-.1.3 6.5 5 .5.1c4.1-3.8 6.6-9.4 6.6-15.7z"/>
                    <path fill="#34A853" d="M24 46c5.9 0 10.9-2 14.5-5.3l-6.9-5.4c-1.9 1.3-4.4 2.2-7.6 2.2-5.8 0-10.7-3.8-12.4-9.1l-.3quad0z"/>
                    <path fill="#FBBC05" d="M11.6 28.4A13.6 13.6 0 0 1 10.9 24c0-1.5.3-3 .7-4.4l-.02-.3-6.6-5.1-.2.1A22 22 0 0 0 2 24c0 3.6.9 7 2.4 10l7.2-5.6z"/>
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
                  <input className="fld" placeholder="What would you use it for? (optional)" value={form.use_case}
                         onChange={(e) => setForm({ ...form, use_case: e.target.value })} />
                  <button className="btn" type="submit" disabled={busy} style={{ width: "100%", marginTop: 6 }}>
                    {busy ? "Issuing your key…" : left != null ? `Hold my seat — #${(taken ?? 0) + 1} of ${SEATS}` : "Get my API key"}
                  </button>
                </form>
                {err && <div className="error">{err}</div>}
                <p style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 14 }}>
                  We email you once, when something you reported gets fixed. Nothing else.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
