"""Extra checks + deliverables for agentB: proper portfolio trades/week, gross (pre-cost) R, per-symbol,
controls for the highest-win-rate config of each family, pickle of best non-passing strategy."""
import sys, os, pickle, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fam
from fam import bars, PIPS, SPREAD, trade
from sim15 import stats
HERE = os.path.dirname(os.path.abspath(__file__))

def tpw(trs):
    by = {}
    for t in trs: by[t["sym"]] = by.get(t["sym"], 0) + 1
    return sum(n / ((bars(s, 3600)[-1][0] - bars(s, 3600)[0][0]) / 604800) for s, n in by.items())

def gross(trs, tf):
    out = []
    for t in trs:
        g = trade(bars(t["sym"], tf), t["setup"], PIPS[t["sym"]], spread=0.0, swap=0.0)
        if g: out.append(g)
    return stats(out)

def ctl(gen, tf, mode):
    pooled = []
    for seed in range(10):
        r, _ = fam.evaluate(fam.control(gen, tf, mode, seed), tf)
        pooled += [t for v in r.values() for t in v]
    return stats(pooled), len(pooled) / 10

CASES = [("F1 H4 tp1.0R T12 (selected)", fam.f1(14400, 1.0, 12)), ("F1 H4 tp0.5R noT (max win)", fam.f1(14400, 0.5, None)),
         ("F2 opp tp0.5W noT (selected)", fam.f2("opp", 0.5, None)),
         ("F3 tp1.0R strong flat16 (selected)", fam.f3(1.0, True, 16)), ("F3 tp0.5R strong noT (max win)", fam.f3(0.5, True, None)),
         ("F4 tp1.0R swing T24 (selected)", fam.f4(1.0, "swing", 24)), ("F4 tp0.5R swing noT (max win)", fam.f4(0.5, "swing", None))]
for name, (gen, tf) in CASES:
    res, _ = fam.evaluate(gen, tf)
    allt = [t for v in res.values() for t in v]
    s, g = stats(allt), gross(allt, tf)
    hold = statistics.mean((t["exit_time"] - t["time"]) / 3600 for t in allt)
    cr, nr = ctl(gen, tf, "rand"); cd, nd = ctl(gen, tf, "dir")
    print(f"{name:36s} net win {s['win']:.1f}% R {s['avgR']:+.3f}±{s['se']:.3f} | GROSS win {g['win']:.1f}% R {g['avgR']:+.3f} | "
          f"{tpw(allt):.1f} tr/wk hold {hold:.1f}h | CTL rand {cr['win']:.1f}% {cr['avgR']:+.3f}±{cr['se']:.3f} (n/seed {nr:.0f}) "
          f"| CTL same-bar-randdir {cd['win']:.1f}% {cd['avgR']:+.3f}±{cd['se']:.3f}")
    if name.startswith("F2"):
        best = (allt, res)

allt, res = best
print("\nF2 best per symbol:")
for sym in fam.SEEN + fam.UNSEEN:
    s = stats([t for t in allt if t["sym"] == sym]); print(f"  {sym} n={s['n']} win={s['win']:.1f}% R={s['avgR']:+.3f}±{s['se']:.3f}")
assert all("setup" in t and "sym" in t for t in allt)
pickle.dump(allt, open(os.path.join(HERE, "F2_london_opp_tp05W.pkl"), "wb"))
print("saved", len(allt), "trades; first:", allt[0])
