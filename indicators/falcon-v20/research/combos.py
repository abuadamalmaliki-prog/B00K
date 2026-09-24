"""Pre-registered combinations (fixed parameters, no tuning), same protocol as the agents."""
import sys, bisect, pickle
sys.path.insert(0, "agentA"); sys.path.insert(0, "agentC")
from common import PIPS, bars
import sim15
from sim15 import evaluate, report, SEEN, UNSEEN, SPREAD
import mr, trend
import strategies                       # V7 sweep engine (raw setups)
from sim import run_sequential as v7_run   # V7 simulator (target 300, BE 150)
H1, H4 = 3600, 14400
def ema(x, n):
    a, v, out = 2 / (n + 1), None, []
    for k, c in enumerate(x):
        v = c if v is None else a * c + (1 - a) * v
        out.append(v)
    return out
_tr = {}
def h4_trend(sym):
    """(close_times, trend) of H4 bars: +1 if EMA9 > EMA21 at that bar's close, -1 if below."""
    if sym not in _tr:
        r = bars(sym, H4); c = [x[4] for x in r]; f, s = ema(c, 9), ema(c, 21)
        _tr[sym] = ([x[0] + H4 for x in r], [1 if f[k] > s[k] else -1 for k in range(len(r))])
    return _tr[sym]
def trend_at(sym, t_close):
    ct, tr = h4_trend(sym)
    j = bisect.bisect_right(ct, t_close) - 1          # last H4 bar closed at or before t_close
    return tr[j] if j >= 0 else 0
_sw = {}
def sweep_idx(sym, tf):
    if (sym, tf) not in _sw:
        _sw[(sym, tf)] = strategies.sweep(sym, tf)
    return _sw[(sym, tf)]
def c1(sym, tf):          # trend-aligned sweep (H4), V7 exits
    r = bars(sym, H4)
    return [s for s in sweep_idx(sym, H4) if trend_at(sym, r[s[0]][0] + H4) == s[1]]
def c2(sym, tf):          # trend-aligned RSI2 dip (H1)
    r = bars(sym, H1)
    return [s for s in mr.g_rsi2(10, 2.5, ('atr', 0.5, 10))(sym, H1) if trend_at(sym, r[s[0]][0] + H1) == s[1]]
def c3(sym, tf):          # EMA 9/21 cross (H4, 2R) only after a same-direction sweep within the last 6 H4 bars
    sw = {}
    for s in sweep_idx(sym, H4): sw.setdefault(s[1], []).append(s[0])
    out = []
    for st in trend.gen_ma(sym, dict(tf=H4, fast=9, slow=21, tgt=2.0))[1]:
        lst = sw.get(st[1], []); j = bisect.bisect_right(lst, st[0]) - 1
        if j >= 0 and st[0] - lst[j] <= 6: out.append(st)
    return out
def c4(sym, tf):          # RSI2 dip only within 5 H1 bars after a same-direction sweep
    sw = {}
    for s in sweep_idx(sym, H1): sw.setdefault(s[1], []).append(s[0])
    out = []
    for st in mr.g_rsi2(10, 2.5, ('atr', 0.5, 10))(sym, H1):
        lst = sw.get(st[1], []); j = bisect.bisect_right(lst, st[0]) - 1
        if j >= 0 and st[0] - lst[j] <= 5: out.append(st)
    return out
def eval_v7(gen):
    res = {}
    for grp, group in (("seen", SEEN), ("unseen", UNSEEN)):
        for h in (0, 1): res[(grp, h)] = []
        for sym in group:
            rows = bars(sym, H4); mid = rows[len(rows) // 2][0]
            for t in v7_run(rows, gen(sym, H4), PIPS[sym], spread=SPREAD[sym], swap=0.5):
                t["sym"] = sym; t["win"] = t["pips"] > 0
                res[(grp, int(t["time"] >= mid))].append(t)
    return res
if __name__ == "__main__":
    out = {}
    base = eval_v7(lambda s, tf: sweep_idx(s, H4)); print(report("base  V7 sweep H4 (300/BE150)", base))
    r = eval_v7(c1); out["C1"] = r; print(report("C1 sweep + H4 EMA trend", r))
    r = evaluate(c2, H1); out["C2"] = r; print(report("C2 RSI2 dip + H4 EMA trend", r))
    r = evaluate(c3, H4); out["C3"] = r; print(report("C3 EMA cross after sweep (2R)", r))
    r = evaluate(c4, H1); out["C4"] = r; print(report("C4 RSI2 dip after sweep", r))
    for k, v in out.items():
        tr = [t for cell in v.values() for t in cell]
        pickle.dump(tr, open(f"combo_{k}.pkl", "wb"))
