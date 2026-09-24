import math, sys
from common import *
V3 = dict(partials=False, beAfterTp1=True, trailTp2=False, tp1Pips=150, tp2Pips=200, noReverse=True)
def last(sym): return bars(sym, 3600)[-1][4]
def pip_value_and_margin(sym, lev):
    eu, gu, au, uj, uc = last("EURUSD"), last("GBPUSD"), last("AUDUSD"), last("USDJPY"), last("USDCAD")
    px = last(sym)
    table = {
        "EURUSD": (10, 1e5 * eu), "GBPUSD": (10, 1e5 * gu), "AUDUSD": (10, 1e5 * au), "NZDUSD": (10, 1e5 * px),
        "USDJPY": (1000 / uj, 1e5), "USDCAD": (10 / uc, 1e5), "EURJPY": (1000 / uj, 1e5 * eu), "GBPJPY": (1000 / uj, 1e5 * gu),
        "GBPAUD": (10 * au, 1e5 * gu), "XAUUSD": (10, 100 * px), "XAGUSD": (50, 5000 * px)}
    v, notional = table[sym]
    return v, notional / lev
def size(policy, B, k, s, V, M, goal):
    maxlots = B / (s * V + 0.5 * M)                     # SL must be hit before a 50% margin stop-out
    if policy == "optimal":                              # launch-pad rule (matches the DP optimum)
        pad = goal / (1 + 300 * V / (s * V + 0.5 * M))
        aim = goal if B >= pad else min(2 * pad, goal)
        lots = max(math.ceil((aim - B) / (300 * V) * 100 - 1e-9) / 100, 0.01)
    elif policy == "bold":
        want = (goal - B) / (300 * V)
        lots = math.ceil(want * 100 - 1e-9) / 100
    elif policy == "even":
        g = (goal / B) ** (1 / k)
        lots = round(B * (g - 1) / (300 * V), 2)
    else:
        lots = 0.01
    lots = min(lots, math.floor(maxlots * 100) / 100)
    return lots if lots >= 0.01 else 0.0
def simulate(trades, sym, policy, start=30.0, goal=500.0, n=3, lev=500):
    V, M = pip_value_and_margin(sym, lev)
    done = [t for t in trades if not t.get("open")]
    res = []
    for s0 in range(len(done) - n + 1):
        B = start
        for j in range(n):
            t = done[s0 + j]
            lots = size(policy, B, n - j, t["riskPips"], V, M, goal)
            if lots == 0: break
            B += lots * V * t["pips"]
            if B >= goal: break
        res.append(B)
    ok = sum(b >= goal for b in res)
    bust = sum(b < 5 for b in res)
    return len(res), ok, bust
if __name__ == "__main__":
    lev = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print(f"leverage 1:{lev}")
    for tf in (14400, 3600):
        for sym in PIPS:
            rows, tr = run(sym, tf, **V3)
            out = []
            for pol in ("optimal", "bold", "min"):
                n, ok, bust = simulate(tr, sym, pol, lev=lev)
                out.append(f"{pol}: {100*ok/n:5.1f}% win / {100*bust/n:4.0f}% bust")
            tp = 100 * sum(t["hit"][2] for t in tr) / len(tr)
            print(f"{'H4' if tf==14400 else 'H1'} {sym} trades={len(tr):3d} TP300={tp:4.1f}% medSL={statistics.median(t['riskPips'] for t in tr):3.0f}p | " + " | ".join(out))
