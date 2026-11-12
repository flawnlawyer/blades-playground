#!/usr/bin/env python3
"""balance_report.py — summarise balance_bot CSV output.   python tools/balance_report.py a.csv [b.csv ...]"""
import csv, collections, statistics as st, sys

def load(paths):
    rows = []
    for p in paths:
        with open(p) as fh:
            for r in csv.DictReader(fh):
                for k in ("seed", "wave", "score", "kills", "hits", "died"):
                    r[k] = int(r[k])
                r["seconds"] = float(r["seconds"]); rows.append(r)
    return rows

def survival(rows, maxw=20):
    """% of runs that REACHED each wave, and the wave-to-wave drop (where the difficulty bites)."""
    n = len(rows); out = []; prev = 100.0
    for w in range(2, maxw + 1):
        reached = 100.0 * sum(r["wave"] >= w for r in rows) / n
        out.append((w, reached, prev - reached)); prev = reached
        if reached == 0: break
    return out

def main():
    rows = load(sys.argv[1:])
    by = collections.defaultdict(list)
    for r in rows: by[(r["condition"], r["skill"])].append(r)
    for (cond, skill), rs in sorted(by.items()):
        waves = [r["wave"] for r in rs]; died = [r for r in rs if r["died"]]
        print(f"\n== {cond} / {skill}: {len(rs)} runs | waves median {st.median(waves)} mean {st.mean(waves):.1f} "
              f"| died {len(died)}/{len(rs)} | mean hits {st.mean(r['hits'] for r in rs):.1f}")
        print("   wave reached%  (drop):  " + "  ".join(f"{w}:{p:.0f}%(-{d:.0f})" for w, p, d in survival(rs, 16)))
        causes = collections.Counter(r["cause"] for r in died)
        print("   killed by:", ", ".join(f"{c} {n}" for c, n in causes.most_common()))
        bosses = collections.Counter(b for r in rs for b in r["bosses"].split("|") if b)
        print("   bosses defeated:", dict(bosses) or "none")

if __name__ == "__main__":
    main()
