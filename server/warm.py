"""Warm the parse cache, and measure where address-parsing time actually goes.

    env/bin/python3 server/warm.py            # warm every demo address, timed
    env/bin/python3 server/warm.py --bench    # stage breakdown + cold vs cached
    env/bin/python3 server/warm.py --stats    # what is cached right now

Why this exists: Sarvam's chat models are REASONING models -- a single address
parse emits ~1500 hidden chain-of-thought tokens (`reasoning_content`) before
the JSON. That is the ~10-20s, and when reasoning runs long `content` comes
back EMPTY, which is the intermittent parse failure. `max_tokens` makes it
worse (truncates mid-thought -> always empty). The fix is not a faster prompt;
it is not parsing the same address twice. Cached parses are ~0.00s and cannot
fail, so warming these addresses makes every demo interaction instant.
"""

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.lattice.parser import parse, _PCACHE_FILE          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Everything the console can put in front of a judge.
CONSOLE_EXAMPLES = [
    "3-116, 1ST FLOOR, HANUMANNAGAR COLONY CHAITANYAPURI, DILSUKHNAGAR, HYDERABAD-PIN",
    "DOOR NO.3-116, FIRST FLOOR, HANUMAN NAGAR COLONY, CHAITANYAPURI, DILSUKNAGAR",
    "ABHAY PRASHAL, 10, RACE COURSE ROAD, INDORE",
    "RACECOURSE ROAD, 10, ABHAY PRASHAL, INDORE",
    "M.C. NO.53, M J MALL, RAILWAY ROAD, RISHIKESH.",
    "637 , LAXMAN JHOOLA ROAD , RISHIKESH -, UTTARAKHAND",
    "Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038",
    "गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८",
    "GROUND FLOOR, SUDHAMA BUILDING, DAULAT BHAI ROAD, NEAR JAGANATH, TEMPLE, NANICHHIPWAD, VALSAD",
    "KHEWAT NO. 50 4, KHATA NO.55, KHASRA NO 397, OPP. METRO PILLAR NO 908, SANKHOL, BAHADURGARH",
    "VILLAGE DHANORA, PO HANODA, DIST DURG, CHATTISGARH",
]


def demo_addresses() -> list[str]:
    out = list(CONSOLE_EXAMPLES)
    csv_path = os.path.join(ROOT, "data", "sample_import.csv")
    if os.path.exists(csv_path):
        with open(csv_path) as fh:
            out += [r["address"] for r in csv.DictReader(fh) if r.get("address")]
    real = os.path.join(ROOT, "data", "real_sample.json")
    if os.path.exists(real):
        out += [r["raw"] for r in json.load(open(real)) if r.get("raw")]
    seen, uniq = set(), []
    for a in out:
        k = " ".join(a.split()).lower()
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq


def cached_count() -> int:
    try:
        return len(json.load(open(_PCACHE_FILE)))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def warm(workers: int = 8):
    addrs = demo_addresses()
    before = cached_count()
    print(f"warming {len(addrs)} addresses ({before} already cached), {workers} workers\n")

    t0 = time.time()
    done = {"n": 0, "ok": 0, "err": 0, "cold": 0.0, "hot": 0.0}

    def one(a):
        t = time.time()
        p = parse(a)
        dt = time.time() - t
        done["n"] += 1
        if p.error:
            done["err"] += 1
            flag = f"FAIL {p.error[:38]}"
        else:
            done["ok"] += 1
            flag = f"{p.locality or p.city or '-'}"
        if dt < 0.05:
            done["hot"] += dt
        else:
            done["cold"] += dt
        print(f"  [{done['n']:3d}/{len(addrs)}] {dt:6.2f}s  {flag:34s} {a[:46]}", flush=True)
        return p

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, addrs))

    total = time.time() - t0
    print(f"\n  wall clock : {total:.0f}s")
    print(f"  cached     : {done['ok']} ok, {done['err']} failed")
    print(f"  cache now  : {cached_count()} entries")
    print("\n  Re-run this and every line should read 0.00s.")


def bench():
    """Stage breakdown on one address, then cold vs cached."""
    from server.lattice import sarvam, pincode as pd, geocoder
    from server.lattice.parser import SYSTEM

    A = ("FLAT 12B, MEERA APARTMENTS, 7TH CROSS, NEAR GANESH TEMPLE, "
         "INDIRANAGAR, BENGALURU 560038")
    print(f"benchmark address:\n  {A}\n")

    t = time.time(); sarvam.identify_language(A); t_lid = time.time() - t

    t = time.time()
    r = sarvam.client().chat.completions(
        model=sarvam.CHAT_MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": A}],
        temperature=0.2)
    t_llm = time.time() - t
    msg = r.choices[0].message
    think = getattr(msg, "reasoning_content", None) or ""
    out = msg.content or ""

    p = parse(A, use_cache=False).as_dict()
    t = time.time(); pd.validate(p); t_pin = time.time() - t

    q = ", ".join(str(p[k]) for k in ("street", "locality", "city", "state", "pincode") if p.get(k))
    geocoder._CACHE.pop(q.lower(), None)
    t = time.time()
    try:
        geocoder.geocode(q)
    except Exception:
        pass
    t_geo = time.time() - t

    print("  stage breakdown")
    print(f"    language ID     {t_lid:7.2f}s")
    print(f"    LLM parse       {t_llm:7.2f}s   <-- the cost")
    print(f"    pincode check   {t_pin:7.4f}s  (offline)")
    print(f"    geocode         {t_geo:7.2f}s")
    print()
    print("  why the LLM is slow — it is a reasoning model")
    print(f"    prompt tokens       {r.usage.prompt_tokens:6d}")
    print(f"    completion tokens   {r.usage.completion_tokens:6d}")
    print(f"    hidden reasoning    {len(think):6d} chars")
    print(f"    visible JSON        {len(out):6d} chars")
    if out:
        ratio = len(think) / max(len(out), 1)
        print(f"    -> {ratio:.0f}x more thinking than answer")
    else:
        print("    -> content EMPTY: reasoning ran long. This is the intermittent failure.")

    print("\n  cold vs cached")
    fresh = A.replace("12B", "34C")
    t = time.time(); parse(fresh); c1 = time.time() - t
    t = time.time(); parse(fresh); c2 = time.time() - t
    print(f"    first  (live API)  {c1:7.2f}s")
    print(f"    second (cached)    {c2:7.4f}s")
    print(f"    speedup            {c1 / max(c2, 1e-6):,.0f}x")


def stats():
    n = cached_count()
    print(f"cache: {n} entries at {_PCACHE_FILE}")
    if n:
        d = json.load(open(_PCACHE_FILE))
        for k in list(d)[:8]:
            print(f"  {k[:72]}")
        if n > 8:
            print(f"  ... and {n - 8} more")
    missing = [a for a in demo_addresses()
               if " ".join(a.split()).lower() not in (json.load(open(_PCACHE_FILE)) if n else {})]
    print(f"\ndemo addresses not yet cached: {len(missing)}")


if __name__ == "__main__":
    if "--bench" in sys.argv:
        bench()
    elif "--stats" in sys.argv:
        stats()
    else:
        warm()
