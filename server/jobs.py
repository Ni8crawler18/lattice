"""Async batch jobs -- parse thousands of addresses without holding an HTTP
request open.  (Neon)

/batch is synchronous and capped at 40 because every parse is an LLM round
trip. A job runs in the background instead: submit, poll, download. Clustering
uses matcher.cluster_blocked(), so the O(n^2) wall /batch hits does not apply.

Parses are cached by raw string in server/raw_cache.json -- re-running a job
over the same CRM export costs zero LLM calls the second time, which is the
whole economic argument against per-call pricing.

In-memory job store on purpose: this deploys on Render's free tier with no
database. Jobs die with the process; results are meant to be downloaded, not
archived. Say so in the API docs, not in apologies at 3am.
"""

import csv
import io
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from server.lattice.matcher import cluster_blocked
from server.lattice.parser import parse
from server.lattice.scorer import score, score_batch

MAX_ADDRESSES = 5000
MAX_JOBS_KEPT = 50
_PARSE_WORKERS = 6

_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_cache.json")

# ---------------------------------------------------------------- parse cache

_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_cache_loaded = False


def _load_cache():
    global _cache_loaded
    with _cache_lock:
        if _cache_loaded:
            return
        try:
            with open(_CACHE_PATH) as fh:
                _cache.update(json.load(fh))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        _cache_loaded = True


def _save_cache():
    with _cache_lock:
        tmp = _CACHE_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(_cache, fh, ensure_ascii=False)
        os.replace(tmp, _CACHE_PATH)


def warm_cache(records: dict[str, dict] | list[dict]):
    """Pre-seed from already-parsed records (e.g. server/parsed_cache.json)."""
    _load_cache()
    items = records.values() if isinstance(records, dict) else records
    with _cache_lock:
        for p in items:
            raw = p.get("raw")
            if raw and not p.get("error"):
                _cache.setdefault(raw, p)

# ----------------------------------------------------------------- job store


@dataclass
class Job:
    id: str
    label: str
    status: str = "queued"            # queued | running | done | failed
    total: int = 0
    parsed_done: int = 0
    cache_hits: int = 0
    created: float = field(default_factory=time.time)
    finished: float | None = None
    error: str | None = None
    result: dict | None = None

    def public(self, with_result: bool = False) -> dict:
        out = {
            "id": self.id, "label": self.label, "status": self.status,
            "total": self.total, "parsed_done": self.parsed_done,
            "cache_hits": self.cache_hits, "created": self.created,
            "finished": self.finished, "error": self.error,
        }
        if self.status == "done" and self.result is not None:
            out["summary"] = self.result["summary"]
            if with_result:
                out["result"] = self.result
        return out


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
_runner = ThreadPoolExecutor(max_workers=2)


def _parse_cached(raw: str, job: Job) -> dict:
    with _cache_lock:
        hit = _cache.get(raw)
    if hit is not None:
        job.cache_hits += 1
        p = dict(hit)
    else:
        p = parse(raw).as_dict()
        if not p.get("error"):
            with _cache_lock:
                _cache[raw] = p
    job.parsed_done += 1
    return p


def _run(job: Job, addresses: list[str]):
    job.status = "running"
    try:
        # Dedupe before parsing: a CRM export is exactly where duplicates live.
        unique = list(dict.fromkeys(addresses))
        with ThreadPoolExecutor(max_workers=_PARSE_WORKERS) as ex:
            by_raw = dict(zip(unique, ex.map(lambda r: _parse_cached(r, job), unique)))
        parsed = [dict(by_raw[raw]) for raw in addresses]

        ids = cluster_blocked(parsed)
        for p, c in zip(parsed, ids):
            p["cluster"] = c
            p["deliverability"] = score(p)

        batch = score_batch(parsed)
        job.result = {
            "summary": {
                "addresses": len(addresses),
                "unique_strings": len(unique),
                "unique_locations": len(set(ids)),
                "duplicates_collapsed": len(parsed) - len(set(ids)),
                "parse_errors": sum(1 for p in parsed if p.get("error")),
                "cache_hits": job.cache_hits,
                "bands": batch["bands"],
                "mean_risk": batch["mean_risk"],
                "flagged_pct": batch["flagged_pct"],
            },
            "records": parsed,
        }
        job.status = "done"
        _save_cache()
    except Exception as exc:
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"
    finally:
        job.finished = time.time()


def submit(addresses: list[str], label: str = "") -> Job:
    _load_cache()
    addresses = [a.strip() for a in addresses if a and len(a.strip()) >= 3]
    if not addresses:
        raise ValueError("no usable addresses")
    if len(addresses) > MAX_ADDRESSES:
        raise ValueError(f"max {MAX_ADDRESSES} addresses per job")

    job = Job(id=uuid.uuid4().hex[:12], label=label, total=len(addresses))
    with _jobs_lock:
        _jobs[job.id] = job
        # Retention: drop oldest finished jobs beyond the cap.
        done = [j for j in _jobs.values() if j.status in ("done", "failed")]
        for old in sorted(done, key=lambda j: j.created)[:max(0, len(_jobs) - MAX_JOBS_KEPT)]:
            _jobs.pop(old.id, None)
    _runner.submit(_run, job, addresses)
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def list_jobs() -> list[dict]:
    return [j.public() for j in sorted(_jobs.values(), key=lambda j: -j.created)]

# -------------------------------------------------------------- CSV in / out

_ADDR_HEADERS = {"address", "addr", "full_address", "raw", "raw_address",
                 "shipping_address", "delivery_address"}


def addresses_from_csv(text: str) -> list[str]:
    """Take the column named like an address; else the longest-avg column."""
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    col, body = None, rows[1:]
    for i, h in enumerate(header):
        if h in _ADDR_HEADERS:
            col, body = i, rows[1:]
            break
    if col is None:
        # No recognisable header: score every column over all rows, take the
        # one with the longest average cell -- addresses are long.
        body = rows if not any(h in _ADDR_HEADERS for h in header) else rows[1:]
        ncols = max(len(r) for r in body)
        best, col = -1.0, 0
        for i in range(ncols):
            cells = [r[i] for r in body if i < len(r) and r[i].strip()]
            avg = sum(len(c) for c in cells) / len(cells) if cells else 0
            if avg > best:
                best, col = avg, i
        # If that column's header row cell looks like data (long), keep row 0.
        if header and len(rows[0][col]) < 20:
            body = rows[1:]
    return [r[col].strip() for r in body if col < len(r) and r[col].strip()]


_CSV_FIELDS = ["raw", "cluster", "occupant", "house_number", "floor", "building",
               "visual_descriptor", "street", "landmark", "landmark_relation",
               "sublocality", "locality", "city", "state", "pincode",
               "completeness", "risk", "band", "will_likely_need_call",
               "reasons", "error"]


def results_csv(job: Job) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    w.writeheader()
    for p in job.result["records"]:
        d = p.get("deliverability") or {}
        row = {k: p.get(k) for k in _CSV_FIELDS}
        row.update(risk=d.get("risk"), band=d.get("band"),
                   will_likely_need_call=d.get("will_likely_need_call"),
                   reasons="; ".join(d.get("reasons") or []))
        w.writerow(row)
    return buf.getvalue()
