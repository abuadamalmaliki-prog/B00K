"""V15 research framework: generic trade simulator + evaluation protocol.

Chart prices are BID; ask = bid + spread.
  Long : enters at ask (close + spread); stop/target judged on bid; exits at bid.
  Short: enters at bid (close); stop/target judged on ask (bid + spread); exits at ask.
Stop-first when one bar touches stop and target. Gapped stops fill at the open.
Targets fill at their level (never better). Optional time exit at a bar's close.
Swap: `swap` pips (cost, positive number) per 17:00 New York weekday rollover, Wed x3.

Setup tuple: (i, dir, sl_price, tp_price[, max_bars])   i = bar index of the signal bar (enter at its close)
"""
import math, statistics
from common import PIPS, bars
from sim import rollovers

# Assumed JustMarkets Standard-like spreads (pips). Verify in MT5.
SPREAD = {"EURUSD": 1.2, "GBPUSD": 1.5, "AUDUSD": 1.5, "NZDUSD": 2.0, "USDCAD": 2.0, "GBPAUD": 3.5,
          "USDJPY": 1.5, "EURJPY": 2.0, "GBPJPY": 3.0, "XAUUSD": 3.0, "XAGUSD": 3.0}
SWAP = 0.5
SEEN = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "XAUUSD"]
UNSEEN = ["NZDUSD", "USDCAD", "GBPAUD", "EURJPY", "GBPJPY", "XAGUSD"]

def trade(rows, setup, pip, spread=0.0, swap=SWAP):
    i, d, sl, tp = setup[:4]
    max_bars = setup[4] if len(setup) > 4 else None
    s = spread * pip
    c = rows[i][4]
    entry = c + s if d == 1 else c
    risk = (entry - sl) if d == 1 else (sl - entry)
    reward = (tp - entry) if d == 1 else (entry - tp)
    if risk <= 0 or reward <= 0:
        return None
    k = i
    for k in range(i + 1, len(rows)):
        t, o, h, l, cl, v = rows[k]
        if d == 1:
            if l <= sl: px, why = min(o, sl), "sl"; break
            if h >= tp: px, why = tp, "tp"; break
        else:
            if h + s >= sl: px, why = max(o + s, sl), "sl"; break
            if l + s <= tp: px, why = tp, "tp"; break
        if max_bars is not None and k - i >= max_bars:
            px, why = (cl if d == 1 else cl + s), "time"; break
    else:
        return None
    pips = d * (px - entry) / pip - swap * rollovers(rows[i][0], rows[k][0])
    return dict(i=i, exit_i=k, dir=d, why=why, pips=pips, R=pips / (risk / pip), riskPips=risk / pip,
                rewardPips=reward / pip, time=rows[i][0], exit_time=rows[k][0], win=pips > 0)

def run_sequential(rows, setups, pip, spread=0.0, swap=SWAP, cooldown=0):
    """One position at a time on this instrument; take the next setup once flat."""
    out, busy, last = [], -1, -10**9
    for st in sorted(setups, key=lambda x: x[0]):
        if st[0] < busy or st[0] - last < cooldown:
            continue
        tr = trade(rows, st, pip, spread, swap)
        if tr is None:
            continue
        out.append(tr); busy = tr["exit_i"]; last = st[0]
    return out

def stats(ts):
    n = len(ts)
    if n == 0:
        return dict(n=0, win=0, avgR=0, se=0, pf=0, avgPips=0)
    Rs = [t["R"] for t in ts]
    gw = sum(r for r in Rs if r > 0); gl = -sum(r for r in Rs if r < 0)
    return dict(n=n, win=100 * sum(t["win"] for t in ts) / n, avgR=sum(Rs) / n,
                se=(statistics.pstdev(Rs) / math.sqrt(n)) if n > 1 else 0, pf=(gw / gl) if gl > 0 else float("inf"),
                avgPips=sum(t["pips"] for t in ts) / n)

def evaluate(gen, tf=3600, syms=None, **kw):
    """gen(sym, tf) -> setups. Returns {(group, half): [trades]} for seen/unseen x first/second half."""
    res = {}
    for grp, group in (("seen", SEEN), ("unseen", UNSEEN)):
        for h in (0, 1): res[(grp, h)] = []
        for sym in group:
            if syms and sym not in syms: continue
            rows = bars(sym, tf)
            trs = run_sequential(rows, gen(sym, tf), PIPS[sym], spread=SPREAD[sym], **kw)
            mid = rows[len(rows) // 2][0]
            for t in trs:
                t["sym"] = sym
                res[(grp, int(t["time"] >= mid))].append(t)
    return res

def report(name, res):
    cells = []
    for g in ("seen", "unseen"):
        for h in (0, 1):
            s = stats(res[(g, h)])
            cells.append(f"{g[0]}{h+1}: n={s['n']:4d} win={s['win']:5.1f}% R={s['avgR']:+.3f}±{s['se']:.3f}")
    allt = [t for v in res.values() for t in v]; a = stats(allt)
    pos = sum(1 for v in res.values() if len(v) >= 10 and stats(v)["avgR"] > 0)
    return f"{name:34s} ALL n={a['n']:5d} win={a['win']:5.1f}% R={a['avgR']:+.3f}±{a['se']:.3f} PF={a['pf']:.2f} +cells={pos}/4 | " + " | ".join(cells)
