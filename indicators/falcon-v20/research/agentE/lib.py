"""agentE shared helpers: per-bar NY clock, ATRs, FX-day (17:00 NY) daily bars, evaluation that
mirrors sim15.evaluate/run_sequential exactly but (a) attaches 'sym' and 'setup' to every trade and
(b) allows a per-setup swap (needed for the carry family, where the carry side EARNS 0.5 pip/night)."""
import os, sys, math, random, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); os.chdir(ROOT)
from common import PIPS, bars
from sim import ny, rollovers
from sim15 import trade, stats, SPREAD, SWAP, SEEN, UNSEEN
ALL = SEEN + UNSEEN
_ctx = {}

def ctx(sym):
    """Per-symbol cached arrays: rows, NY datetimes, ATR24(H1), FX-day index + daily bars + daily avg range20."""
    if sym in _ctx: return _ctx[sym]
    rows = bars(sym, 3600)
    nyt = [ny(r[0]) for r in rows]
    tr = [rows[0][2] - rows[0][3]] + [max(rows[k][2], rows[k - 1][4]) - min(rows[k][3], rows[k - 1][4]) for k in range(1, len(rows))]
    atr = [None] * len(rows); s = 0.0
    for k in range(len(rows)):
        s += tr[k]
        if k >= 24: s -= tr[k - 24]
        if k >= 23: atr[k] = s / 24
    # FX day = NY date of (bar open + 7h): the 17:00-NY bar starts the next day
    from datetime import timedelta
    dkey = [(d + timedelta(hours=7)).date() for d in nyt]
    days = []  # dict(key, first, last, o,h,l,c)
    for k, key in enumerate(dkey):
        r = rows[k]
        if not days or days[-1]["key"] != key:
            days.append(dict(key=key, first=k, last=k, o=r[1], h=r[2], l=r[3], c=r[4]))
        else:
            d = days[-1]; d["last"] = k; d["h"] = max(d["h"], r[2]); d["l"] = min(d["l"], r[3]); d["c"] = r[4]
    # drop tiny "days" (weekend stubs) with < 6 bars
    days = [d for d in days if d["last"] - d["first"] >= 5]
    for j, d in enumerate(days):
        prev = days[max(0, j - 20):j]
        d["avgR20"] = sum(x["h"] - x["l"] for x in prev) / len(prev) if len(prev) == 20 else None
    dayidx = {d["key"]: j for j, d in enumerate(days)}
    mid = rows[len(rows) // 2][0]
    c = dict(rows=rows, ny=nyt, atr=atr, days=days, dayidx=dayidx, dkey=dkey, pip=PIPS[sym], mid=mid, spread=SPREAD[sym])
    _ctx[sym] = c
    return c

def run_seq(rows, setups, pip, spread, swapf=None):
    """Identical to sim15.run_sequential (cooldown=0) but swap may depend on the setup; attaches 'setup'."""
    out, busy = [], -1
    for st in sorted(setups, key=lambda x: x[0]):
        if st[0] < busy: continue
        sw = SWAP if swapf is None else swapf(st)
        tr = trade(rows, st, pip, spread, sw)
        if tr is None: continue
        tr["setup"] = tuple(st); out.append(tr); busy = tr["exit_i"]
    return out

def evaluate(gen, syms=ALL, swapf=None, spread_on=True):
    """gen(sym) -> setups (H1). Returns list of NET trades (with 'sym','setup','grp','half')."""
    out = []
    for sym in syms:
        c = ctx(sym)
        sf = (lambda st, s=sym: swapf(s, st)) if swapf else None
        for t in run_seq(c["rows"], gen(sym), c["pip"], c["spread"] if spread_on else 0.0, sf):
            t["sym"] = sym; t["grp"] = "seen" if sym in SEEN else "unseen"; t["half"] = int(t["time"] >= c["mid"])
            out.append(t)
    return out

def cell(trs, grp=None, half=None):
    return stats([t for t in trs if (grp is None or t["grp"] == grp) and (half is None or t["half"] == half)])

def fmt(s): return f"n={s['n']:4d} w={s['win']:5.1f}% R={s['avgR']:+.3f}±{s['se']:.3f}"

def line(name, trs):
    a = cell(trs); parts = [f"{name:38s} ALL {fmt(a)} PF={a['pf']:.2f}"]
    for g in ("seen", "unseen"):
        for h in (0, 1): parts.append(f"{g[0]}{h+1}: {fmt(cell(trs, g, h))}")
    return " | ".join(parts)

def score(trs):
    """Pre-declared SEEN selection score: min of the two SEEN-half avg R (needs n>=30 per half)."""
    a, b = cell(trs, "seen", 0), cell(trs, "seen", 1)
    if a["n"] < 30 or b["n"] < 30: return -9
    return min(a["avgR"], b["avgR"])

def gross(trs, swapf_gross=None):
    """Re-simulate each NET trade's setup with zero spread and zero swap (same trade set)."""
    out = []
    for t in trs:
        c = ctx(t["sym"]); g = trade(c["rows"], t["setup"], c["pip"], 0.0, 0.0)
        if g: out.append(g)
    return stats(out)

def tpw(trs):
    by = {}
    for t in trs: by[t["sym"]] = by.get(t["sym"], 0) + 1
    return sum(n / ((ctx(s)["rows"][-1][0] - ctx(s)["rows"][0][0]) / 604800) for s, n in by.items())

def hold(trs): return statistics.mean((t["exit_time"] - t["time"]) / 3600 for t in trs) if trs else 0

def control(trs, seeds=5, swapf=None):
    """Random-entry control: for every real trade, a random bar of the same instrument (same NY hour-of-day
    not enforced), random direction, identical stop/target distances (price units, ATR-rescaled) and max_bars.
    Run with the same cost model through run_seq. Pooled over seeds."""
    pooled = []
    for seed in range(seeds):
        rng = random.Random(1000 + seed)
        by = {}
        for t in trs: by.setdefault(t["sym"], []).append(t)
        for sym, ts in by.items():
            c = ctx(sym); rows, atr, pip, sp = c["rows"], c["atr"], c["pip"], c["spread"] * c["pip"]
            setups, used = [], set()
            for t in ts:
                i, d, sl, tp = t["setup"][:4]; mb = t["setup"][4] if len(t["setup"]) > 4 else None
                e = rows[i][4] + (sp if d == 1 else 0)
                rd, wd = abs(e - sl), abs(tp - e)
                for _ in range(50):
                    j = rng.randrange(30, len(rows) - 200)
                    if j not in used and atr[j] and atr[i]: break
                used.add(j); k = atr[j] / atr[i]; dj = rng.choice((1, -1))
                ej = rows[j][4] + (sp if dj == 1 else 0)
                st = (j, dj, ej - dj * rd * k, ej + dj * wd * k) + ((mb,) if mb is not None else ())
                setups.append(st)
            sf = (lambda st, s=sym: swapf(s, st)) if swapf else None
            for tt in run_seq(rows, setups, pip, c["spread"], sf):
                tt["sym"] = sym; pooled.append(tt)
    return stats(pooled), len(pooled) / seeds
