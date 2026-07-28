"""Signup + usage store — the traction ledger.

Backed by Postgres when DATABASE_URL is set, otherwise a local JSON file, so
the same code runs on Render and on a laptop with nothing installed. Render's
web-service disk is ephemeral, so the JSON fallback is for local dev only —
anything we want to still exist tomorrow needs the database.

Two things are recorded, deliberately kept separate:

  signups  — who asked for a key (name, email, company, when)
  usage    — how many requests each key actually made

The distinction is the whole point. A signup is a claim of interest; a request
is evidence of use. Reporting them apart is what makes "N users" checkable
rather than assertable.
"""

from __future__ import annotations

import json
import os
import threading
import time

DB_URL = (os.getenv("DATABASE_URL") or "").strip()
_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")
_LOCK = threading.Lock()

_pg = None
if DB_URL:
    try:
        import psycopg2
        import psycopg2.extras
        _pg = psycopg2
    except ImportError:
        _pg = None                      # fall through to JSON


def _conn():
    # Render's external URL needs SSL; the internal one tolerates it.
    return _pg.connect(DB_URL, sslmode="require" if "render.com" in DB_URL else "prefer")


def init() -> str:
    """Create tables if needed. Returns the backend actually in use."""
    if not _pg:
        return "json"
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signups (
                    id         SERIAL PRIMARY KEY,
                    email      TEXT UNIQUE NOT NULL,
                    name       TEXT,
                    company    TEXT,
                    use_case   TEXT,
                    api_key    TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS usage (
                    key_prefix TEXT PRIMARY KEY,
                    calls      BIGINT DEFAULT 0,
                    last_seen  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        return "postgres"
    except Exception:
        return "json (postgres unreachable)"


# ---------------------------------------------------------------- json fallback
def _load() -> dict:
    try:
        with open(_JSON_PATH) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"signups": [], "usage": {}}


def _save(d: dict) -> None:
    try:
        tmp = _JSON_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh, indent=1)
        os.replace(tmp, _JSON_PATH)
    except OSError:
        pass


# ---------------------------------------------------------------- public API
def add_signup(email: str, name: str = "", company: str = "",
               use_case: str = "", api_key: str = "") -> dict:
    """Idempotent on email: signing up twice returns the original record."""
    email = email.strip().lower()
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    """INSERT INTO signups (email, name, company, use_case, api_key)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET
                         name = COALESCE(NULLIF(EXCLUDED.name,''), signups.name)
                       RETURNING api_key, (xmax = 0) AS created""",
                    (email, name, company, use_case, api_key))
                key, created = cur.fetchone()
            return {"email": email, "api_key": key, "returning": not created}
        except Exception:
            pass                        # fall through to JSON
    with _LOCK:
        d = _load()
        for s in d["signups"]:
            if s["email"] == email:
                return {"email": email, "api_key": s.get("api_key"), "returning": True}
        d["signups"].append({"email": email, "name": name, "company": company,
                             "use_case": use_case, "api_key": api_key,
                             "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        _save(d)
    return {"email": email, "api_key": api_key, "returning": False}


def record_call(key_prefix: str) -> None:
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    """INSERT INTO usage (key_prefix, calls) VALUES (%s, 1)
                       ON CONFLICT (key_prefix) DO UPDATE
                       SET calls = usage.calls + 1, last_seen = NOW()""",
                    (key_prefix,))
            return
        except Exception:
            pass
    with _LOCK:
        d = _load()
        d["usage"][key_prefix] = d["usage"].get(key_prefix, 0) + 1
        _save(d)


def stats() -> dict:
    """Public traction counters. Signups vs active keys is the honest split."""
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM signups")
                signups = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*), COALESCE(SUM(calls),0) FROM usage WHERE calls > 0")
                active, calls = cur.fetchone()
                cur.execute("""SELECT company FROM signups
                               WHERE COALESCE(company,'') <> ''
                               ORDER BY created_at DESC LIMIT 12""")
                companies = [r[0] for r in cur.fetchall()]
            return {"backend": "postgres", "signups": signups,
                    "active_keys": active, "total_calls": int(calls),
                    "companies": companies}
        except Exception:
            pass
    d = _load()
    usage = d.get("usage", {})
    return {"backend": "json", "signups": len(d.get("signups", [])),
            "active_keys": sum(1 for v in usage.values() if v > 0),
            "total_calls": sum(usage.values()),
            "companies": [s.get("company") for s in d.get("signups", [])
                          if s.get("company")][-12:]}
