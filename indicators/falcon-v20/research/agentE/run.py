"""Run every config of every family (NET, sim15 cost model), print all, select on SEEN only."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from fam import FAMILIES
t0 = time.time(); sel = {}
only = sys.argv[1:] or list(FAMILIES)
for fam in only:
    print(f"== {fam}")
    best = None
    for name, gen, swapf in FAMILIES[fam]:
        trs = lib.evaluate(gen, swapf=swapf)
        sc = lib.score(trs)
        print(lib.line(name, trs), f"| score={sc:+.3f}", flush=True)
        if best is None or sc > best[0]: best = (sc, name)
    print(f"-> SELECTED (max min SEEN-half R): {best[1]} score={best[0]:+.3f}\n"); sel[fam] = best[1]
print(json.dumps(sel, indent=1)); print(f"{time.time()-t0:.0f}s")
