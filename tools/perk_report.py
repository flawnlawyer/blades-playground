#!/usr/bin/env python3
"""
perk_report.py — paired per-perk analysis of docs/balance/perk_test.csv (from balance_bot --perk-test).

Every condition is compared with its reference ON THE SAME SEEDS (identical arena/spawns), so only
the perk differs.  Plain perks are compared with the no-perk baseline; evolutions with their own
prerequisites alone.  Reports mean paired difference in waves survived, a 95% interval, and win/loss.
"""
import csv, math, statistics as st, sys
path = sys.argv[1] if len(sys.argv) > 1 else "docs/balance/perk_test.csv"
rows = list(csv.DictReader(open(path)))
by = {}
for r in rows:
    by.setdefault(r["condition"], {})[int(r["seed"])] = r

def paired(cond, ref):
    seeds = sorted(set(by[cond]) & set(by[ref]))
    d = [int(by[cond][s]["wave"]) - int(by[ref][s]["wave"]) for s in seeds]
    ds = [int(by[cond][s]["score"]) - int(by[ref][s]["score"]) for s in seeds]
    return d, ds

def line(label, cond, ref):
    d, ds = paired(cond, ref)
    mean = st.mean(d); se = st.stdev(d) / math.sqrt(len(d)); ci = 1.96 * se
    w, l = sum(x > 0 for x in d), sum(x < 0 for x in d)
    verdict = "helps" if mean - ci > 0 else ("HURTS" if mean + ci < 0 else "no clear effect")
    print(f"{label:22s} {mean:+5.2f} waves  (95%: {mean - ci:+5.2f}..{mean + ci:+5.2f})  W/L {w:2d}/{l:2d}   score {st.mean(ds):+8.0f}   {verdict}")

b = [int(r["wave"]) for r in by["baseline"].values()]
print(f"baseline (no perks, average bot): median wave {st.median(b)}, mean {st.mean(b):.1f}, n={len(b)}\n")
print("== base perks vs no-perk baseline (same seeds) ==")
res = []
for c in by:
    if c == "baseline" or "prereqs" in c: continue
    d, _ = paired(c, "baseline"); res.append((st.mean(d), c))
for _, c in sorted(res, reverse=True): line(c, c, "baseline")
print("\n== evolutions vs their own prerequisites alone (same seeds) ==")
for c in sorted(k for k in by if k.endswith("(+prereqs)")):
    name = c.split("(")[0]; line(name, c, f"prereqs-for-{name}")
