import math, sys, pickle, statistics
from common import PIPS, bars
from sim import run_sequential
from strategies import STRATS, SPREAD
SEEN = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "XAUUSD"]
UNSEEN = ["NZDUSD", "USDCAD", "GBPAUD", "EURJPY", "GBPJPY", "XAGUSD"]
def cells(name, tf, cost=True, **kw):
    gen = STRATS[name]; res = {}
    for grp, syms in (("seen", SEEN), ("unseen", UNSEEN)):
        for h in (0, 1): res[(grp, h)] = []
        for sym in syms:
            rows = bars(sym, tf); setups = gen(sym, tf)
            trs = run_sequential(rows, setups, PIPS[sym], spread=SPREAD[sym] if cost else 0.0, swap=0.5 if cost else 0.0, **kw)
            mid = rows[len(rows) // 2][0]
            for t in trs: t["sym"] = sym; res[(grp, int(t["time"] >= mid))].append(t)
    return res
def fmt(ts):
    n = len(ts)
    if n < 5: return f"n={n:4d}".ljust(30)
    m = sum(t["R"] for t in ts) / n; sd = statistics.pstdev(t["R"] for t in ts)
    tp = 100 * sum(t["why"] == "tp" for t in ts) / n
    return f"n={n:4d} R={m:+.3f}±{sd/math.sqrt(n):.3f} tp={tp:4.1f}%"
if __name__ == "__main__":
    tfs = eval(sys.argv[1]) if len(sys.argv) > 1 else (14400, 3600)
    kw = eval("dict(" + (sys.argv[2] if len(sys.argv) > 2 else "") + ")")
    store = {}
    for tf in tfs:
        for name in STRATS:
            r = cells(name, tf, **kw); store[(name, tf)] = r
            allt = [t for v in r.values() for t in v]
            if not allt: continue
            pos = sum(1 for v in r.values() if len(v) >= 5 and sum(t["R"] for t in v) > 0)
            print(f"{'H4' if tf==14400 else 'H1'} {name:22s} ALL {fmt(allt)} | +cells {pos}/4 | "
                  + " | ".join(f"{g[0]}{h+1} {fmt(r[(g,h)])}" for g in ('seen','unseen') for h in (0,1)))
    pickle.dump(store, open("bakeoff.pkl", "wb"))
