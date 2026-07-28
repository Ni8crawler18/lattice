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
                CREATE TABLE IF NOT EXISTS api_keys (
                    id         SERIAL PRIMARY KEY,
                    email      TEXT NOT NULL,
                    label      TEXT,
                    api_key    TEXT NOT NULL,
                    revoked    BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS api_keys_email_idx ON api_keys (email);
                CREATE TABLE IF NOT EXISTS usage (
                    key_prefix TEXT PRIMARY KEY,
                    calls      BIGINT DEFAULT 0,
                    last_seen  TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS usage_daily (
                    key_prefix TEXT NOT NULL,
                    day        DATE NOT NULL,
                    endpoint   TEXT NOT NULL,
                    calls      BIGINT DEFAULT 0,
                    PRIMARY KEY (key_prefix, day, endpoint)
                );
            """)
        return "postgres"
    except Exception:
        return "json (postgres unreachable)"


# ---------------------------------------------------------------- json fallback
def _load() -> dict:
    try:
        with open(_JSON_PATH) as fh:
            d = json.load(fh)
        d.setdefault("signups", []); d.setdefault("usage", {}); d.setdefault("keys", [])
        return d
    except (FileNotFoundError, json.JSONDecodeError):
        return {"signups": [], "usage": {}, "keys": []}


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


# ------------------------------------------------------------------ api keys
# One account may hold several keys -- one per environment or per integration,
# so a leaked staging key can be revoked without breaking production. Keys are
# stateless HMAC tokens (see app.py), so this table is a *ledger*, not the
# authority: rows exist so an account can list and label what it minted. Every
# read is scoped by email, and the email is never taken from the browser --
# see the /api/keys route handler in the client, which reads it from the
# signed session. That is what keeps one account from seeing another's keys.

def add_key(email: str, api_key: str, label: str = "") -> dict:
    email = (email or "").strip().lower()
    label = (label or "").strip() or "default"
    row = {"email": email, "label": label, "api_key": api_key,
           "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "revoked": False}
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    """INSERT INTO api_keys (email, label, api_key)
                       VALUES (%s,%s,%s) RETURNING id, created_at""",
                    (email, label, api_key))
                kid, created = cur.fetchone()
            row["id"] = kid
            row["created_at"] = created.isoformat()
            return row
        except Exception:
            pass
    with _LOCK:
        d = _load()
        row["id"] = max([k.get("id", 0) for k in d["keys"]] or [0]) + 1
        d["keys"].append(row)
        _save(d)
    return row


def list_keys(email: str) -> list:
    """Every key this account minted, with what each one has actually done.

    Usage is metered on the first 13 characters of the key (see the _meter
    middleware in app.py), so the join is on that prefix rather than on the
    whole value. Keys that were never used simply report zero -- absence from
    the usage table is not an error."""
    email = (email or "").strip().lower()
    if not email:
        return []
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    """SELECT k.id, k.label, k.api_key, k.revoked, k.created_at,
                              COALESCE(u.calls, 0), u.last_seen
                       FROM api_keys k
                       LEFT JOIN usage u ON u.key_prefix = LEFT(k.api_key, 13)
                       WHERE k.email = %s AND NOT k.revoked
                       ORDER BY k.id""", (email,))
                return [{"id": r[0], "label": r[1], "api_key": r[2],
                         "revoked": r[3], "created_at": r[4].isoformat(),
                         "calls": int(r[5]),
                         "last_seen": r[6].isoformat() if r[6] else None}
                        for r in cur.fetchall()]
        except Exception:
            pass
    usage = _load().get("usage", {})
    out = []
    for k in _load()["keys"]:
        if k["email"] != email or k.get("revoked"):
            continue
        out.append({**k, "calls": int(usage.get(k["api_key"][:13], 0)),
                    "last_seen": None})
    return out


def revoke_key(email: str, key_id: int) -> bool:
    """Revoke only if the key belongs to this account -- the email is part of
    the WHERE clause, so guessing another account's key id achieves nothing."""
    email = (email or "").strip().lower()
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute("UPDATE api_keys SET revoked = TRUE "
                            "WHERE id = %s AND email = %s", (key_id, email))
                return cur.rowcount > 0
        except Exception:
            pass
    with _LOCK:
        d = _load()
        hit = False
        for k in d["keys"]:
            if k.get("id") == key_id and k["email"] == email:
                k["revoked"] = True; hit = True
        if hit:
            _save(d)
        return hit


def record_call(key_prefix: str, endpoint: str = "") -> None:
    """One metered request. `endpoint` is the normalised first path segment
    ("/parse", "/jobs", ...) so a usage page can break calls down by API
    without storing full URLs."""
    endpoint = (endpoint or "other")[:40]
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    """INSERT INTO usage (key_prefix, calls) VALUES (%s, 1)
                       ON CONFLICT (key_prefix) DO UPDATE
                       SET calls = usage.calls + 1, last_seen = NOW()""",
                    (key_prefix,))
                cur.execute(
                    """INSERT INTO usage_daily (key_prefix, day, endpoint, calls)
                       VALUES (%s, CURRENT_DATE, %s, 1)
                       ON CONFLICT (key_prefix, day, endpoint) DO UPDATE
                       SET calls = usage_daily.calls + 1""",
                    (key_prefix, endpoint))
            return
        except Exception:
            pass
    with _LOCK:
        d = _load()
        d["usage"][key_prefix] = d["usage"].get(key_prefix, 0) + 1
        daily = d.setdefault("usage_daily", {})
        dk = f"{key_prefix}|{time.strftime('%Y-%m-%d')}|{endpoint}"
        daily[dk] = daily.get(dk, 0) + 1
        _save(d)


def usage_for(email: str, days: int = 30) -> dict:
    """Everything a usage page needs, scoped to one account's keys:
    total calls, per-endpoint counts, per-day series, per-key stats."""
    keys = list_keys(email)
    prefixes = {k["api_key"][:13]: k for k in keys}
    out = {
        "email": (email or "").strip().lower(),
        "total_calls": sum(k.get("calls", 0) for k in keys),
        "keys": [{"id": k["id"], "label": k["label"],
                  "key_prefix": k["api_key"][:12], "calls": k.get("calls", 0),
                  "last_seen": k.get("last_seen"), "created_at": k.get("created_at")}
                 for k in keys],
        "endpoints": [], "daily": [], "window_days": days,
    }
    if not prefixes:
        return out
    if _pg:
        try:
            with _conn() as c, c.cursor() as cur:
                cur.execute(
                    """SELECT endpoint, SUM(calls) FROM usage_daily
                       WHERE key_prefix = ANY(%s)
                         AND day > CURRENT_DATE - %s::int
                       GROUP BY endpoint ORDER BY 2 DESC""",
                    (list(prefixes), days))
                out["endpoints"] = [{"endpoint": e, "calls": int(n)}
                                    for e, n in cur.fetchall()]
                cur.execute(
                    """SELECT day, SUM(calls) FROM usage_daily
                       WHERE key_prefix = ANY(%s)
                         AND day > CURRENT_DATE - %s::int
                       GROUP BY day ORDER BY day""",
                    (list(prefixes), days))
                out["daily"] = [{"day": d.isoformat(), "calls": int(n)}
                                for d, n in cur.fetchall()]
            return out
        except Exception:
            pass
    daily = _load().get("usage_daily", {})
    eps: dict[str, int] = {}
    byday: dict[str, int] = {}
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
    for dk, n in daily.items():
        try:
            prefix, day, endpoint = dk.split("|", 2)
        except ValueError:
            continue
        if prefix in prefixes and day > cutoff:
            eps[endpoint] = eps.get(endpoint, 0) + n
            byday[day] = byday.get(day, 0) + n
    out["endpoints"] = [{"endpoint": e, "calls": n}
                        for e, n in sorted(eps.items(), key=lambda kv: -kv[1])]
    out["daily"] = [{"day": d, "calls": n} for d, n in sorted(byday.items())]
    return out


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
