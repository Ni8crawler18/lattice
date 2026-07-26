"""Evaluate Layer 1 on REAL addresses with human-verified labels.

Data:   Razorpay open IFSC dataset (real, unmodified)
Labels: assigned by inspection -- see data/labels.py for the reasoning per pair
Villain: raw string similarity, which is what an in-house dedupe script does
"""

import json
import os
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.labels import MICR_LABELS                 # noqa: E402
from server.lattice.resolver import compare         # noqa: E402

PAIRS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "real_pairs_raw.json")


def build():
    data = json.load(open(PAIRS))
    micr = [p for p in data if p["kind"] == "micr_same_branch"]
    negs = [p for p in data if p["kind"] != "micr_same_branch"]

    evalset = []
    for i, p in enumerate(micr):
        if i not in MICR_LABELS:
            continue
        truth, why = MICR_LABELS[i]
        evalset.append({"a": p["a"], "b": p["b"], "truth": truth, "why": why,
                        "src": f"micr#{i}"})
    for j, p in enumerate(negs):
        # different branch in the same district -- reliable negatives
        evalset.append({"a": p["a"], "b": p["b"], "truth": False,
                        "why": "different branch, same district", "src": f"neg#{j}"})
    return evalset


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def run(evalset, predict, name):
    tp = fp = fn = tn = 0
    misses = []
    for e in evalset:
        pred, detail = predict(e)
        if pred and e["truth"]:
            tp += 1
        elif pred and not e["truth"]:
            fp += 1; misses.append(("FP", e, detail))
        elif not pred and e["truth"]:
            fn += 1; misses.append(("FN", e, detail))
        else:
            tn += 1
    p, r, f = prf(tp, fp, fn)
    print(f"  {name:34s} tp={tp:2d} fp={fp:2d} fn={fn:2d} tn={tn:2d}  "
          f"P={p:.3f} R={r:.3f} F1={f:.3f}")
    return misses


if __name__ == "__main__":
    ev = build()
    pos = sum(1 for e in ev if e["truth"])
    print(f"REAL evaluation set: {len(ev)} pairs  ({pos} same-building, {len(ev)-pos} different)")
    print("  addresses: Razorpay open IFSC dataset, unmodified")
    print("  labels:    assigned by inspection (see data/labels.py)\n")

    print("=" * 74)
    misses = run(ev, lambda e: (
        compare(e["a"]["parsed"], e["b"]["parsed"])["score"] >= 0.75,
        compare(e["a"]["parsed"], e["b"]["parsed"])),
        "Lattice (parse + coarse/fine)")

    for th in (0.55, 0.65, 0.75, 0.85):
        run(ev, lambda e, t=th: (
            SequenceMatcher(None, e["a"]["raw"].lower(), e["b"]["raw"].lower()).ratio() >= t,
            None), f"raw string similarity @{th:.2f}")
    print("=" * 74)

    if misses:
        print("\nLattice errors:")
        for kind, e, d in misses:
            print(f"  {kind} [{e['src']}] score={d['score']} veto={d['veto']}")
            print(f"      A: {e['a']['raw'][:88]}")
            print(f"      B: {e['b']['raw'][:88]}")
            print(f"      why: {e['why']}")
