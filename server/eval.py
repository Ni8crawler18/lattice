"""Parse the seed set once, cache it, then evaluate Layer 1 against ground truth.

Also runs naive baselines so the demo has a villain: raw string similarity is
what an in-house dedupe script actually does today.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.seed import SEED, pairs                      # noqa: E402
from server.lattice.parser import parse                # noqa: E402
from server.lattice.resolver import compare, cluster   # noqa: E402

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parsed_cache.json")


def load_parsed(refresh=False) -> dict:
    if os.path.exists(CACHE) and not refresh:
        with open(CACHE) as fh:
            return json.load(fh)
    print(f"parsing {len(SEED)} addresses via Sarvam...", flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda r: parse(r["raw"]).as_dict(), SEED))
    out = {rec["id"]: p for rec, p in zip(SEED, results)}
    with open(CACHE, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return out


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def evaluate(parsed: dict):
    rows = []
    tp = fp = fn = tn = 0
    for a, b, truth in pairs():
        res = compare(parsed[a["id"]], parsed[b["id"]])
        pred = res["score"] >= 0.75
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
            rows.append(("FP", a["id"], b["id"], res))
        elif not pred and truth:
            fn += 1
            rows.append(("FN", a["id"], b["id"], res))
        else:
            tn += 1
    return (tp, fp, fn, tn), rows


def baseline(threshold=0.75):
    """What an in-house dedupe script does: raw string similarity."""
    tp = fp = fn = tn = 0
    for a, b, truth in pairs():
        s = SequenceMatcher(None, a["raw"].lower(), b["raw"].lower()).ratio()
        pred = s >= threshold
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and truth:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


if __name__ == "__main__":
    parsed = load_parsed(refresh="--refresh" in sys.argv)

    errs = [i for i, p in parsed.items() if p.get("error")]
    if errs:
        print("PARSE ERRORS:", errs)

    print("\n" + "=" * 62)
    print("LAYER 1 -- entity resolution vs ground truth")
    print("=" * 62)

    (tp, fp, fn, tn), rows = evaluate(parsed)
    p, r, f = _prf(tp, fp, fn)
    print(f"  Lattice   tp={tp:2d} fp={fp:2d} fn={fn:2d} tn={tn:3d}   "
          f"P={p:.3f} R={r:.3f} F1={f:.3f}")

    for th in (0.55, 0.65, 0.75, 0.85):
        btp, bfp, bfn, btn = baseline(th)
        bp, br, bf = _prf(btp, bfp, bfn)
        print(f"  raw@{th:.2f}  tp={btp:2d} fp={bfp:2d} fn={bfn:2d} tn={btn:3d}   "
              f"P={bp:.3f} R={br:.3f} F1={bf:.3f}")

    if rows:
        print("\n  misses:")
        for kind, ai, bi, res in rows:
            print(f"    {kind} {ai}~{bi} score={res['score']} veto={res['veto']} "
                  f"sig={res['signals']}")

    print("\n" + "=" * 62)
    print("CLUSTERS")
    print("=" * 62)
    ids = [rec["id"] for rec in SEED]
    cl = cluster([parsed[i] for i in ids])
    groups: dict[int, list[str]] = {}
    for i, c in zip(ids, cl):
        groups.setdefault(c, []).append(i)
    truth_of = {rec["id"]: rec["truth"] for rec in SEED}
    for c, members in sorted(groups.items()):
        truths = {truth_of[m] for m in members}
        mark = "OK " if len(truths) == 1 else "MIX"
        print(f"  [{mark}] cluster {c}: {members}  truth={sorted(truths)}")
