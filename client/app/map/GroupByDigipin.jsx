"use client";

/* Group-by-DIGIPIN map overlay (Xenon). Shared by the standalone /map route
   and the console's "Group by DIGIPIN" tab.
   Leaflet + OSM tiles load from CDN at runtime; if either fails (offline,
   CSP), the group table below still renders — the map is progressive
   enhancement, not a dependency. */

import { useEffect, useRef, useState } from "react";
import { proxyBase } from "@/lib/api";

const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";

/* One hue for cells (identity = position on the map; no categorical cycling).
   Count is magnitude -> fill opacity carries it, sequential-style. */
const CELL = "#2a78d6";

const LEVELS = [
  { v: 5, label: "5 — ~3.9 km" },
  { v: 6, label: "6 — ~1 km" },
  { v: 7, label: "7 — ~250 m" },
  { v: 8, label: "8 — ~60 m" },
];

/* Demo: nearby DIGIPINs — a Kothrud (Pune) cluster ~100m apart, one ~500m off
   in the adjacent cell, and a BTM (Bengaluru) pair. Illustrative grid points,
   not geocoded customer addresses. */
const DEMO = `ord-1, 4FP-4CK-6L24
ord-2, 4FP-4CK-645F
ord-3, 4FP-4CK-P82J
ord-4, 4FP-4C4-C5L7
ord-5, 4P3-JM4-M295
ord-6, 4P3-JM4-M675
ord-7, 4FP-4CK-6L8L`;

/* Addresses for the geocode path. Deliberately mixed: the first two resolve to
   street level, the third only to its locality -- so the precision column shows
   two different truncations rather than a uniform, flattering one. */
const ADDR_DEMO = `Shivneri Apartments, Kothrud, Pune 411038
Connaught Place, New Delhi 110001
Ganesh mandir ke peeche, Kothrud, Pune 411038`;

const DIGIPIN_RE = /^[23456789CFJKLMPT]{10}$/i;

function parseLines(text) {
  const points = [];
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    const parts = t.split(",").map((s) => s.trim());
    const bare = parts[0].replace(/-/g, "");
    if (parts.length === 1 && DIGIPIN_RE.test(bare)) {
      points.push({ id: parts[0], digipin: parts[0] });
    } else if (parts.length === 2 && DIGIPIN_RE.test(parts[1].replace(/-/g, ""))) {
      points.push({ id: parts[0], digipin: parts[1] });
    } else if (parts.length === 2) {
      points.push({ latitude: Number(parts[0]), longitude: Number(parts[1]) });
    } else if (parts.length >= 3) {
      points.push({ id: parts[0], latitude: Number(parts[1]), longitude: Number(parts[2]) });
    }
  }
  return points;
}

export default function GroupByDigipin() {
  const [text, setText] = useState(DEMO);
  const [addrText, setAddrText] = useState(ADDR_DEMO);
  const [addrBusy, setAddrBusy] = useState(null);   // "3/7" while running
  const [addrNote, setAddrNote] = useState(null);
  const [level, setLevel] = useState(6);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [leafletOk, setLeafletOk] = useState(null); // null = loading
  const mapEl = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const fileRef = useRef(null);

  /* Load Leaflet from CDN once; degrade to table-only if it fails. */
  useEffect(() => {
    if (window.L) { setLeafletOk(true); return; }
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = LEAFLET_CSS;
    document.head.appendChild(css);
    const js = document.createElement("script");
    js.src = LEAFLET_JS;
    js.onload = () => setLeafletOk(true);
    js.onerror = () => setLeafletOk(false);
    document.head.appendChild(js);
  }, []);

  /* Init map once Leaflet is up; tear down on unmount (tab switches). */
  useEffect(() => {
    if (!leafletOk || mapRef.current || !mapEl.current) return;
    const L = window.L;
    const map = L.map(mapEl.current).setView([20.6, 78.9], 5);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => { map.remove(); mapRef.current = null; layerRef.current = null; };
  }, [leafletOk]);

  /* Draw cells whenever a result lands. */
  useEffect(() => {
    if (!result || !mapRef.current) return;
    const L = window.L;
    const layer = layerRef.current;
    layer.clearLayers();
    const maxCount = Math.max(...result.groups.map((g) => g.count), 1);
    const allBounds = [];
    for (const g of result.groups) {
      const b = g.bounds;
      const rect = [[b.min_latitude, b.min_longitude], [b.max_latitude, b.max_longitude]];
      allBounds.push(rect[0], rect[1]);
      L.rectangle(rect, {
        color: CELL, weight: 2,
        fillColor: CELL, fillOpacity: 0.12 + 0.45 * (g.count / maxCount),
      })
        .bindTooltip(
          `<b>${g.cell}</b> &middot; ${g.count} point${g.count > 1 ? "s" : ""}<br>` +
            g.members.slice(0, 6).map((m) => m.id).join(", ") +
            (g.members.length > 6 ? ` +${g.members.length - 6} more` : ""),
          { sticky: true },
        )
        .addTo(layer);
    }
    /* Dots for the members — the API returns each full code's cell centre. */
    for (const g of result.groups) {
      for (const m of g.members) {
        if (m.latitude != null) {
          L.circleMarker([m.latitude, m.longitude], {
            radius: 5, color: "#fff", weight: 2, fillColor: CELL, fillOpacity: 1,
          }).bindTooltip(`${m.id} — ${m.digipin}`).addTo(layer);
        }
      }
    }
    if (allBounds.length) mapRef.current.fitBounds(allBounds, { padding: [40, 40], maxZoom: 15 });
  }, [result]); // eslint-disable-line react-hooks/exhaustive-deps

  async function post(path, body) {
    const r = await fetch(proxyBase() + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const points = parseLines(text);
      if (!points.length) throw new Error("No parseable lines. Use `id, lat, lon` or `id, DIGIPIN`.");
      setResult(await post("/digipin/group", { level, points }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  /* lat/lon lines -> DIGIPIN lines, via the server algorithm (one call:
     level-10 grouping returns each point's full code). */
  async function convert() {
    setBusy(true);
    setError(null);
    try {
      const points = parseLines(text);
      const coords = points.filter((p) => p.latitude != null);
      if (!coords.length) throw new Error("No lat/lon lines to convert.");
      const res = await post("/digipin/group", { level: 10, points });
      const codeOf = {};
      for (const g of res.groups) for (const m of g.members) codeOf[m.id] = m.digipin;
      const lines = points.map((p, i) => {
        const id = p.id ?? i;
        const code = p.digipin ?? codeOf[id];
        return code ? `${id}, ${code}` : null;
      }).filter(Boolean);
      const dropped = points.length - lines.length;
      setText(lines.join("\n"));
      if (res.rejected?.length || dropped) {
        setError(`Converted ${lines.length}; dropped ${res.rejected?.length || dropped} unparseable/out-of-bounds line(s).`);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  /* Addresses -> DIGIPIN, one call each through the geocoder adapter.
     Sequential on purpose: the geocoder is OSM Nominatim, which rate-limits,
     and a burst here drops otherwise-good addresses to a coarser fallback.

     A DIGIPIN is ten symbols -- always. Shortening one to signal a coarse
     geocode produced a string that was not a DIGIPIN at all, and the grid
     already has a proper place to express uncertainty: the CELL LEVEL. So the
     full code is written out, and the coarsest precision any address earned
     selects the grouping level, which is what the cells on the map actually
     mean. A locality-only geocode therefore lands in a ~1 km cell without its
     code ever pretending to be something else. */
  async function fromAddresses() {
    setError(null);
    setAddrNote(null);
    const lines = addrText.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) { setError("No addresses to convert."); return; }

    const out = [];
    const precision = {};
    const failed = [];
    for (let i = 0; i < lines.length; i++) {
      setAddrBusy(`${i + 1}/${lines.length}`);
      // "id | address" if a pipe is given, else auto-numbered -- addresses are
      // full of commas, so a comma cannot delimit the id here.
      const bar = lines[i].indexOf("|");
      const id = bar > -1 ? lines[i].slice(0, bar).trim() : `addr-${i + 1}`;
      const address = bar > -1 ? lines[i].slice(bar + 1).trim() : lines[i];
      try {
        const r = await post("/digipin/from-address", { address });
        const prec = r.geocoder?.precision || "unknown";
        precision[prec] = (precision[prec] || 0) + 1;
        out.push(`${id}, ${r.digipin}`);
      } catch {
        failed.push(id);
      }
    }
    setAddrBusy(null);
    if (out.length) {
      setText(out.join("\n"));
      setResult(null);
    }
    const mix = Object.entries(precision)
      .map(([k, n]) => `${n} ${k.replace("-level", "")}`).join(", ");
    // Grouping finer than the worst geocode would invent precision on the map.
    // Clamped to what the selector actually offers (5-8); a city-only geocode
    // would otherwise set a level the dropdown cannot show.
    const coarsest = precision["city-level"] ? 5
      : precision["locality-level"] ? 6
      : 8;
    if (out.length) setLevel(coarsest);
    const size = { 5: "~3.9 km", 6: "~1 km", 8: "~60 m" }[coarsest];
    setAddrNote(
      `${out.length} geocoded (${mix}). Codes are full 10-symbol DIGIPINs. ` +
      `Cell level set to ${coarsest} (${size}) — the coarsest any of these earned, ` +
      `because grouping tighter than that would show precision the geocoder never gave.` +
      (failed.length ? ` ${failed.length} not found: ${failed.join(", ")}.` : ""),
    );
  }

  /* Import a CSV/TXT: one point per line, `id, lat, lon` or `id, DIGIPIN`.
     Read client-side into the textarea -- nothing uploads until Group. */
  function importFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const lines = String(reader.result).split(/\r?\n/)
        .filter((l) => l.trim() && !/^(id|name|label)\s*,/i.test(l));
      setText(lines.join("\n"));
      setResult(null);
      setError(null);
    };
    reader.readAsText(f);
    e.target.value = "";
  }

  return (
    <div className="dgmap">
      <style>{`
        .dgmap .note { font-size: 13px; opacity: 0.75; margin: 6px 0 18px; max-width: 68ch; }
        .dgmap .panel { display: grid; grid-template-columns: minmax(260px, 340px) 1fr; gap: 18px; }
        @media (max-width: 760px) { .dgmap .panel { grid-template-columns: 1fr; } }
        .dgmap textarea { width: 100%; min-height: 170px; font: 12.5px/1.5 ui-monospace, monospace;
          padding: 10px; border: 1px solid #d0d0cc; border-radius: 8px; resize: vertical; }
        .dgmap .row { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
        .dgmap select, .dgmap button { font: inherit; padding: 7px 12px; border-radius: 8px;
          border: 1px solid #d0d0cc; background: #fff; }
        .dgmap button.go { background: ${CELL}; border-color: ${CELL}; color: #fff; cursor: pointer; }
        .dgmap button.go[disabled] { opacity: 0.6; cursor: default; }
        .dgmap .maparea { height: 460px; border-radius: 10px; border: 1px solid #d0d0cc; overflow: hidden; }
        .dgmap .fallback { height: 100%; display: grid; place-items: center; font-size: 13px; opacity: 0.7; }
        .dgmap table { border-collapse: collapse; width: 100%; margin-top: 18px; font-size: 13.5px; }
        .dgmap th, .dgmap td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #e6e6e2; }
        .dgmap th { font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.65; }
        .dgmap td.cellcode { font-family: ui-monospace, monospace; }
        .dgmap .err { color: #b3261e; font-size: 13.5px; margin-top: 10px; }
        .dgmap .rej { font-size: 12.5px; opacity: 0.75; margin-top: 8px; }
        .dgmap .addrbox { border: 1px solid #d0d0cc; border-radius: 10px; padding: 14px 16px; margin-bottom: 18px; }
        .dgmap .addrbox label { display: block; font-size: 11px; font-weight: 700; letter-spacing: 0.07em;
          text-transform: uppercase; opacity: 0.6; margin-bottom: 8px; }
        .dgmap .addrbox textarea { min-height: 0; }
        .dgmap .hint { font-size: 12px; opacity: 0.7; }
      `}</style>

      <p className="note">
        Buckets points into DIGIPIN grid cells — one cell, one delivery batch. Paste or
        import your own points (<code>id, DIGIPIN</code> or <code>id, lat, lon</code>, one
        per line); any valid DIGIPIN works, and lat/lon lines can be converted to codes
        with the button below. Text addresses work too — they go through the geocoder
        adapter. Codes are always full DIGIPINs; how much precision the geocoder
        actually gave is carried by the cell level, not by shortening the code.
      </p>

      <div className="addrbox">
        <label htmlFor="dg-addr">Start from addresses</label>
        <textarea id="dg-addr" value={addrText} onChange={(e) => setAddrText(e.target.value)}
          spellCheck={false} rows={3}
          aria-label="One address per line, optionally prefixed with an id and a pipe" />
        <div className="row">
          <button className="go" onClick={fromAddresses} disabled={!!addrBusy || busy}>
            {addrBusy ? `Geocoding ${addrBusy}…` : "Addresses \u2192 DIGIPIN"}
          </button>
          <span className="hint">
            one per line &middot; <code>id | address</code> to name them
          </span>
        </div>
        {addrNote && <div className="rej">{addrNote}</div>}
      </div>

      <div className="panel">
        <div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false}
            aria-label="Points, one per line: id, lat, lon — or id, DIGIPIN" />
          <div className="row">
            <label htmlFor="dg-level">Cell level</label>
            <select id="dg-level" value={level} onChange={(e) => setLevel(Number(e.target.value))}>
              {LEVELS.map((l) => <option key={l.v} value={l.v}>{l.label}</option>)}
            </select>
            <button className="go" onClick={run} disabled={busy}>{busy ? "Grouping…" : "Group"}</button>
          </div>
          <div className="row">
            <button onClick={() => fileRef.current?.click()} disabled={busy}>Import CSV</button>
            <button onClick={convert} disabled={busy} title="Rewrite lat/lon lines as DIGIPIN codes">
              lat/lon &rarr; DIGIPIN
            </button>
            <input ref={fileRef} type="file" accept=".csv,.txt" onChange={importFile} hidden />
          </div>
          {error && <div className="err">{error}</div>}
          {result?.rejected?.length > 0 && (
            <div className="rej">
              Rejected: {result.rejected.map((r) => `${r.id} (${r.error})`).join("; ")}
            </div>
          )}
        </div>

        <div className="maparea">
          {leafletOk === false
            ? <div className="fallback">Map unavailable (CDN blocked) — groups render in the table below.</div>
            : <div ref={mapEl} style={{ height: "100%" }} aria-label="Map of DIGIPIN cell groups" />}
        </div>
      </div>

      {result && (
        <table>
          <thead>
            <tr><th>Cell</th><th>Points</th><th>Members</th><th>Centre</th></tr>
          </thead>
          <tbody>
            {result.groups.map((g) => (
              <tr key={g.cell}>
                <td className="cellcode">{g.cell}</td>
                <td>{g.count}</td>
                <td>{g.members.map((m) => m.id).join(", ")}</td>
                <td className="cellcode">{g.centre.latitude}, {g.centre.longitude}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
