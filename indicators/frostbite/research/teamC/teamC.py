"""Frostbite research, Team C: BREAKOUTS and SESSION timing on M1-M15 (XAUUSD).

Run from research/:   <venv python> teamC/teamC.py            (tune on DISC, then report every period)
                      <venv python> teamC/teamC.py --disc-only (tuning tables only, nothing out of sample)
                      <venv python> teamC/teamC.py ORB ASIA    (only these families)

Protocol (identical for every family)
  Stage 1  signal variants (<= 24), scored on DISC with a fixed default order:
           default stop rule x1.0, TP1 1.0R, TP2 2.0R, max_hold 120, be=False.
  Stage 2  on the best stage-1 variant, in this order, each step keeping the best so far:
           a) TP1 {0.5,1.0,1.5} x TP2 {2.0,3.0} x be {False,True} at hold 120   (12 combos)
           b) max_hold {60,240}                                                (2 combos)
           c) stop multiplier {0.67, 1.33} x the default stop rule              (2 combos)
  "Best" = highest DISC avgR with >= 0.5 trades per trading day (if no variant reaches the frequency,
  the highest avgR is kept and the family is marked as failing the frequency rule).
  Combos per family = len(stage 1) + 16 <= 40.  Nothing outside DISC is looked at while tuning:
  signals are cut to DISC before they are simulated.
  The frozen variant is then reported unchanged on VAL, Y2025 and HOLD, with a VAL random control
  (same stop rule, targets, hold and be; 20 runs) and a VAL stress test (spread 0.45, slip 0.05).

Lookahead rules used everywhere
  - signals are evaluated on CLOSED bars of the chart timeframe; the engine enters at the next 1m open;
  - session ranges (Asian, opening ranges) are only used by bars that START after the range window ends;
  - prior-day high/low/ATR come from the previous trading day (17:00 NY boundary), fully known;
  - higher-timeframe values come from frost.htf_on_ltf (last completed H1 bar);
  - the time-of-day drift family fits its hours on DISC only.
"""
import os, sys, math, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
sys.path.insert(0, RESEARCH)
os.chdir(RESEARCH)
import frost  # noqa: E402

DEFAULT = dict(t1=1.0, t2=2.0, hold=120, be=False, sm=1.0)
ORDER_GRID = [dict(t1=t1, t2=t2, be=be) for t1 in (0.5, 1.0, 1.5) for t2 in (2.0, 3.0) for be in (False, True)]
HOLD_GRID = (60, 240)
SM_GRID = (0.67, 1.33)
MIN_PER_DAY = 0.5

# session masks (bar START time, New York minutes)
SESS = {"all": (18 * 60, 16 * 60), "act": (2 * 60, 12 * 60)}


# ─── data helpers ────────────────────────────────────────────────────────────
_C = {}


def B(tf):
    """Bid bars of tf minutes with ATR14 (Wilder) attached."""
    if tf not in _C:
        b = frost.bars(tf)
        b["atr"] = frost.atr(b, 14)
        _C[tf] = b
    return _C[tf]


def in_window(nm, a, z):
    """ny_min within [a, z) on the 24h clock, wrapping past midnight when a > z."""
    return (nm >= a) & (nm < z) if a < z else (nm >= a) | (nm < z)


def daily():
    """Trading-day (17:00 NY) bars and the PRIOR day's high, low and ATR14 for each trading day."""
    if "D" in _C:
        return _C["D"]
    d = frost.m1()
    g = pd.DataFrame({"tday": d.tday.values, "o": d.o.values, "h": d.h.values, "l": d.l.values, "c": d.c.values,
                      "n": 1}).groupby("tday", sort=True).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                                                              c=("c", "last"), n=("n", "sum"))
    pc = g.c.shift(1).values
    tr = np.nanmax(np.c_[g.h - g.l, np.abs(g.h - pc), np.abs(g.l - pc)], axis=1)
    g["atr"] = frost.rma(tr, 14)
    g["pdh"], g["pdl"], g["patr"] = g.h.shift(1), g.l.shift(1), g.atr.shift(1)
    _C["D"] = g
    return g


def utc_min(frame):
    return (frame.time.values // 60) % 1440


def session_range(start, length, clock="ny"):
    """High/low/open/close per trading day of the 1m bars in [start, start+length) minutes of the
    New York clock (or the UTC clock). A day's range needs at least half of its minutes present."""
    key = ("R", start, length, clock)
    if key in _C:
        return _C[key]
    d = frost.m1()
    mins = d.ny_min.values if clock == "ny" else utc_min(d)
    m = in_window(mins, start, (start + length) % 1440)
    g = pd.DataFrame({"tday": d.tday.values[m], "o": d.o.values[m], "h": d.h.values[m], "l": d.l.values[m],
                      "c": d.c.values[m], "n": 1}).groupby("tday").agg(
        o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("n", "sum"))
    g = g[g.n >= 0.5 * length]
    _C[key] = g
    return g


def map_day(b, s):
    """Per-bar value of a per-trading-day series (NaN where missing)."""
    return s.reindex(b.tday.values).values


def htf_trend(b, n):
    """+1/-1: last completed H1 close above/below its EMA(n) (known at each bar close)."""
    key = ("H", n)
    if key not in _C:
        h1 = B(60)
        _C[key] = np.sign(h1.c.values - frost.ema(h1.c.values, n))
    return frost.htf_on_ltf(b, B(60), _C[key])


def ffill(x):
    return pd.Series(x).ffill().values


def first_per(keys, idx):
    """Keep the first index for each key (idx must be sorted)."""
    if len(idx) == 0:
        return idx
    _, first = np.unique(keys, return_index=True)
    return np.sort(idx[first])


class Setup:
    """Signals of one variant: bars, signal-bar indices, directions and the per-bar stop rule (price units)."""

    def __init__(self, b, idx, d, stop_bar):
        idx = np.asarray(idx, np.int64); d = np.asarray(d, np.int64)
        ok = np.isfinite(stop_bar[idx]) & (stop_bar[idx] > 0)
        self.b, self.idx, self.d, self.stop_bar = b, idx[ok], d[ok], stop_bar

    def sig(self, t1, t2, sm=1.0):
        return frost.levels(self.b, self.idx, self.d, sm * self.stop_bar[self.idx], t1, t2)


def atr_stop(b, k=1.5):
    return k * b.atr.values


def range_stop(b, width, frac=0.5, cap=3.0):
    """frac x range width, bounded to [0.5, cap] x ATR so the stop is never inside the spread noise.
    frac=0.5 ~ stop at the range midpoint, frac=1.0 ~ stop at the opposite side (breakout closes sit at the edge)."""
    a = b.atr.values
    return np.clip(frac * width, 0.5 * a, cap * a)


def stop_rule(b, width, kind):
    if kind == "atr":
        return atr_stop(b)
    if kind == "rng":
        return range_stop(b, width, 0.5)
    if kind == "opp":  # opposite side of the range, risk floored at 0.5 and capped at 1.5 ATR (scout: XAU Pro)
        return range_stop(b, width, 1.0, 1.5)
    raise ValueError(kind)


# ─── families ────────────────────────────────────────────────────────────────
def breakout_of_range(b, hi, lo, win_mask, per_dir=False, only_dir=None):
    """First bar in the window (per trading day) that closes beyond a known range, crossing it from inside.
    hi/lo are per-bar levels (NaN where the range is not yet complete); only_dir (+1/-1/0 per bar) restricts direction."""
    c = b.c.values; pc = np.r_[np.nan, c[:-1]]
    up = win_mask & (c > hi) & (pc <= hi)
    dn = win_mask & (c < lo) & (pc >= lo)
    if only_dir is not None:
        up &= only_dir > 0; dn &= only_dir < 0
    idx = np.flatnonzero(up | dn)
    d = np.where(up[idx], 1, -1)
    keys = b.tday.values[idx] * 10 + (d > 0 if per_dir else 0)
    keep = first_per(keys, idx)
    return keep, np.where(up[keep], 1, -1)


# 1) Asian range (18:00-02:00 NY) breakout in London / London-NY
def fam_asia(p):
    b = B(p["tf"])
    a0 = p.get("start", 18 * 60)
    rg = session_range(a0, (2 * 60 - a0) % 1440)
    buf = p.get("buf", 0.0) * b.atr.values
    hi, lo = map_day(b, rg.h), map_day(b, rg.l)
    w = hi - lo
    nm = b.ny_min.values
    win = in_window(nm, p.get("ws", 2 * 60), p["end"])
    if p.get("wmax"):      # skip days whose Asian range is wider than wmax x the prior day's daily ATR
        win &= w <= p["wmax"] * map_day(b, daily().patr)
    if p.get("wmax_atr"):  # skip while the Asian range is wider than wmax_atr x chart ATR14 (scout: XAU Pro)
        win &= w <= p["wmax_atr"] * b.atr.values
    idx, d = breakout_of_range(b, hi + buf, lo - buf, win, per_dir=p.get("per_dir", False))
    # per-bar stop rule, also defined outside the window for the random control (last known Asian range)
    wbar = ffill(np.where(in_window(nm, 2 * 60, 18 * 60), w, np.nan))
    return Setup(b, idx, d, stop_rule(b, wbar, p["stop"]))


ASIA_GRID = [dict(tf=tf, end=end, stop=st, wmax=wm) for tf in (5, 15) for end in (5 * 60, 11 * 60 + 30)
             for st in ("atr", "rng") for wm in (None, 1.0)]
# scout reference (Mrshahidali420/ORB-Multi-Model-Indicator, XAU_Pro_Indicator.pine, Setup A), as published:
# Asian range 19:00-02:00 NY, trade 03:00-11:30, close beyond range +/- 0.05 ATR, skip if range > 2 x ATR14,
# stop at the opposite side capped at 1.5 ATR and floored at 0.5 ATR, M5 chart.
ASIA_GRID += [dict(tf=tf, start=19 * 60, ws=3 * 60, end=11 * 60 + 30, stop="opp", wmax=None, wmax_atr=2.0, buf=0.05)
              for tf in (5, 15)]
ASIA_EXTRA = [dict(per_dir=True)]

# 2) Opening range breakouts: London 03:00, COMEX 08:20, US equities 09:30
ORB_SESS = {"LDN": 3 * 60, "CMX": 8 * 60 + 20, "US": 9 * 60 + 30}


def fam_orb(p):
    b = B(p["tf"])
    nm = b.ny_min.values
    names = list(ORB_SESS) if p["sess"] == "ALL" else [p["sess"]]
    all_idx, all_d = [], []
    wbar = np.full(len(b), np.nan)
    for k, name in enumerate(names):
        s = ORB_SESS[name]; L = p["L"]
        rg = session_range(s, L)
        hi, lo = map_day(b, rg.h), map_day(b, rg.l)
        win = in_window(nm, s + L, p.get("wend", s + L + 120))
        ocd = np.sign(map_day(b, rg.c - rg.o)) if p.get("ocd") else None
        idx, d = breakout_of_range(b, hi, lo, win, only_dir=ocd)
        all_idx.append(idx); all_d.append(d)
        after = in_window(nm, s + L, 16 * 60 + 50)
        wbar = np.where(after, hi - lo, wbar)
    idx = np.concatenate(all_idx); d = np.concatenate(all_d); o = np.argsort(idx, kind="stable")
    return Setup(b, idx[o], d[o], stop_rule(b, ffill(wbar), p["stop"]))


ORB_GRID = [dict(tf=5, sess=s, L=L, stop=st) for s in ("LDN", "CMX", "US", "ALL") for L in (15, 30)
            for st in ("atr", "rng")]
# scout #5 as published (Mrshahidali420/ORB-Multi-Model-Indicator, XAU_Pro setup B; Crabel 1990, Zarattini & Aziz 2023):
# 15-minute range after 09:30 or after the 08:20 COMEX open, trade only in the OR candle's direction,
# stop at the opposite side (0.5-1.5 ATR), no new entries after 12:00 NY.
ORB_GRID += [dict(tf=5, sess=s, L=15, stop="opp", ocd=True, wend=12 * 60) for s in ("US", "CMX")]
# ocd = trade only in the direction of the opening range's own move (Zarattini & Aziz 2023 opening-candle rule,
# via scout: Mrshahidali420/ORB-Multi-Model-Indicator ORB Pro / XAU Pro Setup B); opp = stop at the opposite OR side.
ORB_EXTRA = [dict(tf=1), dict(ocd=True), dict(stop="opp")]


# 3) Prior-day high / low breakout with a close beyond
def fam_pdhl(p):
    b = B(p["tf"])
    D = daily()
    hi, lo = map_day(b, D.pdh), map_day(b, D.pdl)
    c = b.c.values; pc = np.r_[np.nan, c[:-1]]
    win = in_window(b.ny_min.values, *SESS[p["sess"]])
    up = win & (c > hi) & (pc <= hi)
    dn = win & (c < lo) & (pc >= lo)
    if p["htf"]:
        tr = htf_trend(b, 50); up &= tr > 0; dn &= tr < 0
    idx = np.flatnonzero(up | dn); d = np.where(up[idx], 1, -1)
    if p["first"]:
        idx = first_per(b.tday.values[idx] * 10 + (d > 0), idx); d = np.where(up[idx], 1, -1)
    return Setup(b, idx, d, atr_stop(b))


PDHL_GRID = [dict(tf=tf, sess=s, htf=h, first=f) for tf in (5, 15) for s in ("all", "act") for h in (False, True)
             for f in (False, True)]


# 4) Volatility squeeze (Bollinger 20,2 inside Keltner 20,m) then release
def linreg_last(y, n):
    """ta.linreg(y, n, 0): least-squares line over the last n values, evaluated at the newest point."""
    y = np.asarray(y, float); bad = ~np.isfinite(y); y0 = np.where(bad, 0.0, y)
    x = np.arange(n, dtype=float); sx, sxx = x.sum(), (x * x).sum()
    sy = np.convolve(y0, np.ones(n))[:len(y0)]
    sxy = np.convolve(y0, np.arange(n - 1, -1, -1, dtype=float))[:len(y0)]
    # sxy[t] = sum_j (n-1-j) * y[t-j]  ==  sum_k k * y[t-n+1+k]
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    icpt = (sy - slope * sx) / n
    out = icpt + slope * (n - 1)
    nb = pd.Series(bad.astype(float)).rolling(n).sum().values
    out[~(nb == 0)] = np.nan
    return out


def fam_sqz(p):
    b = B(p["tf"])
    c, h, l = b.c.values, b.h.values, b.l.values
    n = 20
    basis = frost.sma(c, n); dev = 2.0 * frost.stdev(c, n)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1); tr[0] = h[0] - l[0]
    kb = frost.ema(c, n); kr = frost.ema(tr, n)
    on = (basis + dev < kb + p["kcm"] * kr) & (basis - dev > kb - p["kcm"] * kr)
    # squeeze length before each bar
    run = np.zeros(len(c), np.int64)
    for i in range(1, len(c)):
        run[i] = run[i - 1] + 1 if on[i - 1] else 0
    fire = (~on) & (run >= p.get("minrun", 6))  # released after >= minrun squeeze bars (run = squeeze bars ending at i-1)
    win = in_window(b.ny_min.values, *SESS[p["sess"]])
    tr_ok = htf_trend(b, 50) if p.get("htf") else np.zeros(len(c))
    idx, d = [], []
    if p["dir"] == "alorse":  # Alorse TTM Squeeze strategy entry: momentum turning up below zero + RSI(14) crossing 30
        hh = pd.Series(h).rolling(n).max().values; ll = pd.Series(l).rolling(n).min().values
        osc = linreg_last(c - ((hh + ll) / 2 + basis) / 2, n)
        r = frost.rsi(c, 14); r1 = np.r_[np.nan, r[:-1]]
        o1 = np.r_[np.nan, osc[:-1]]; o2 = np.r_[np.nan, np.nan, osc[:-2]]
        buy = (osc < 0) & (o1 < osc) & (o2 < osc) & (r > 30) & (r1 <= 30)
        sell = (osc > 0) & (o1 > osc) & (o2 > osc) & (r < 70) & (r1 >= 70)
        ii = np.flatnonzero((buy | sell) & win)
        return Setup(b, ii, np.where(buy[ii], 1, -1), atr_stop(b))
    if p["dir"] == "mom":
        hh = pd.Series(h).rolling(n).max().values; ll = pd.Series(l).rolling(n).min().values
        mom = linreg_last(c - ((hh + ll) / 2 + basis) / 2, n)
        for i in np.flatnonzero(fire & win & np.isfinite(mom) & (mom != 0)):
            dd = 1 if mom[i] > 0 else -1
            if p.get("htf") and tr_ok[i] != dd:
                continue
            idx.append(i); d.append(dd)
    else:  # box: first close beyond the squeeze's high/low within 6 bars after the release
        fires = np.flatnonzero(fire)
        for f in fires:
            a = f - run[f]
            bh, bl = h[a:f].max(), l[a:f].min()
            for j in range(f, min(f + 6, len(c))):
                if on[j] and j > f:
                    break
                dd = 1 if c[j] > bh else (-1 if c[j] < bl else 0)
                if dd:
                    if win[j] and (not p.get("htf") or tr_ok[j] == dd):
                        idx.append(j); d.append(dd)
                    break
    return Setup(b, np.array(idx, np.int64), np.array(d, np.int64), atr_stop(b))


SQZ_GRID = [dict(tf=tf, dir=dr, sess=s, kcm=k) for tf in (5, 15) for dr in ("mom", "box") for s in ("all", "act")
            for k in (1.5, 2.0)]
# scout #14 (Alorse/pinescript-strategies "TTM Squeeze"; concept J. Carter, Mastering the Trade):
#   classic = Keltner 1.0 x EMA(TR) as in Alorse's script, fire on any release, direction = TTM momentum sign;
#   alorse  = the published strategy entry (momentum turn + RSI 30/70 cross), all hours.
SQZ_GRID += [dict(tf=tf, dir="mom", sess="all", kcm=1.0, minrun=1) for tf in (5, 15)]
SQZ_GRID += [dict(tf=tf, dir="alorse", sess="all", kcm=1.0) for tf in (5, 15)]
SQZ_EXTRA = [dict(htf=True)]


# 5) Inside bar / NR4 / NR7 breakouts
def fam_nr(p):
    b = B(p["tf"])
    c, h, l = b.c.values, b.h.values, b.l.values
    r = h - l
    if p["pat"] == "IB":
        pat = np.r_[False, (h[1:] <= h[:-1]) & (l[1:] >= l[:-1])]
    else:
        k = 4 if p["pat"] == "NR4" else 7
        pat = r <= pd.Series(r).rolling(k).min().values
        pat &= r > 0
    win = in_window(b.ny_min.values, *SESS[p["sess"]])
    tr = htf_trend(b, 50) if p["htf"] else None
    idx, d = [], []
    act_h = act_l = np.nan; exp = -1
    for j in range(len(c)):
        if j <= exp:
            dd = 1 if c[j] > act_h else (-1 if c[j] < act_l else 0)
            if dd:
                if win[j] and (tr is None or tr[j] == dd):
                    idx.append(j); d.append(dd)
                exp = -1
        if pat[j]:
            act_h, act_l, exp = h[j], l[j], j + 3
    return Setup(b, np.array(idx, np.int64), np.array(d, np.int64), atr_stop(b))


NR_GRID = [dict(tf=tf, pat=pt, htf=hf, sess=s) for tf in (5, 15) for pt in ("IB", "NR4", "NR7")
           for hf in (False, True) for s in ("all", "act")]


# 6) Time-of-day drift: fixed direction per New York hour, hours fitted on DISC only
DRIFT_HOURS = [19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]


def drift_table():
    """Per NY hour, the mean and t-stat of (close at hour end - open at hour start) on DISC 1m data."""
    if "DRIFT" in _C:
        return _C["DRIFT"]
    d = frost.m1()
    m = frost.in_period(d, "DISC").values
    g = pd.DataFrame({"tday": d.tday.values[m], "h": d.ny_h.values[m], "o": d.o.values[m], "c": d.c.values[m]})
    hr = g.groupby(["tday", "h"]).agg(o=("o", "first"), c=("c", "last"))
    hr["r"] = hr.c - hr.o
    t = hr.groupby(level="h").r.agg(["mean", "std", "count"])
    t["t"] = t["mean"] / (t["std"] / np.sqrt(t["count"]))
    t = t.loc[[h for h in DRIFT_HOURS if h in t.index]]
    _C["DRIFT"] = t
    return t


def fam_drift(p):
    b = B(5)
    t = drift_table()
    score = t["t"].abs() if p["score"] == "t" else t["mean"].abs()
    hours = list(score.sort_values(ascending=False).index[:p["k"]])
    nm = b.ny_min.values
    idx, d = [], []
    for hh in hours:
        sb = (hh * 60 - 5) % 1440  # last M5 bar of the previous hour -> entry at hh:00
        ii = np.flatnonzero(nm == sb)
        idx.append(ii); d.append(np.full(len(ii), int(np.sign(t.loc[hh, "mean"]))))
    idx = np.concatenate(idx); d = np.concatenate(d); o = np.argsort(idx, kind="stable")
    stop = 1.5 * frost.htf_on_ltf(b, B(15), B(15).atr.values)  # 1.5 x ATR(M15)
    return Setup(b, idx[o], d[o], stop)


DRIFT_GRID = [dict(k=k, score=s) for k in (1, 2, 3, 4, 6) for s in ("t", "mean")]

# 7) US data-release times (08:30, 10:00 NY): momentum after the release bar
def fam_news(p):
    b = B(p["tf"])
    nm = b.ny_min.values
    c, o, h, l = b.c.values, b.o.values, b.h.values, b.l.values
    atr_prev = np.r_[np.nan, b.atr.values[:-1]]
    times = [8 * 60 + 30] + ([10 * 60] if p["times"] == "B" else [])
    m = np.isin(nm, times) & (np.abs(c - o) >= p["x"] * atr_prev) & (c != o) & np.isfinite(atr_prev)
    idx = np.flatnonzero(m); d = np.where(c[idx] > o[idx], 1, -1)
    if p["stop"] == "atr":
        stop = 1.5 * atr_prev
    else:  # the release bar's own range, bounded to [0.5, 4] x ATR
        stop = np.clip(h - l, 0.5 * atr_prev, 4.0 * atr_prev)
    return Setup(b, idx, d, stop)


NEWS_GRID = [dict(times=tm, tf=tf, x=x, stop=st) for tm in ("A", "B") for tf in (1, 5) for x in (0.0, 0.75, 1.5)
             for st in ("atr", "bar")]


# 8) Donchian channel breakouts with an H1 trend filter
def fam_don(p):
    b = B(p["tf"])
    c, h, l = b.c.values, b.h.values, b.l.values
    N = p["N"]
    hh = pd.Series(h).rolling(N).max().shift(1).values  # channel of the N bars BEFORE this one
    ll = pd.Series(l).rolling(N).min().shift(1).values
    pc = np.r_[np.nan, c[:-1]]; phh = np.r_[np.nan, hh[:-1]]; pll = np.r_[np.nan, ll[:-1]]
    win = in_window(b.ny_min.values, *SESS[p["sess"]])
    up = win & (c > hh) & (pc <= phh)
    dn = win & (c < ll) & (pc >= pll)
    if p["htf"]:
        tr = htf_trend(b, p["htf"]); up &= tr > 0; dn &= tr < 0
    idx = np.flatnonzero(up | dn)
    return Setup(b, idx, np.where(up[idx], 1, -1), atr_stop(b))


DON_GRID = [dict(tf=tf, N=N, htf=hf, sess=s) for tf in (5, 15) for N in (20, 55) for hf in (0, 50, 200)
            for s in ("all", "act")]


# 9) Two-session boxes with an H1 EMA50/200 filter (scout #6, Andresfcarreno/forja- XAUUSD_SessionBreakout.pine)
#    as published on the UTC clock: box A 00:00-07:00 traded 07:00-11:00, box B 11:00-13:30 traded 13:30-17:00;
#    close beyond box +/- $0.20, H1 EMA50 vs EMA200 trend, box 0.5-3 x ATR14, at most 2 ATR beyond the prior-day
#    high/low, one trade per box per day, stop 1.5 ATR (published TP 4R is outside our grid).
SESS2_BOX = {"A": (0, 7 * 60, 7 * 60, 11 * 60), "B": (11 * 60, 150, 13 * 60 + 30, 17 * 60)}


def htf_cross(b, fast, slow):
    key = ("X", fast, slow)
    if key not in _C:
        c = B(60).c.values
        _C[key] = np.sign(frost.ema(c, fast) - frost.ema(c, slow))
    return frost.htf_on_ltf(b, B(60), _C[key])


def fam_sess2(p):
    b = B(p["tf"])
    c, a = b.c.values, b.atr.values
    um = utc_min(b)
    D = daily(); pdh, pdl = map_day(b, D.pdh), map_day(b, D.pdl)
    tr = htf_cross(b, 50, 200) if p.get("trend", True) else np.zeros(len(b))
    all_idx, all_d = [], []
    for name in p["sess"]:
        s0, L, ws, we = SESS2_BOX[name]
        rg = session_range(s0, L, "utc")
        hi, lo = map_day(b, rg.h), map_day(b, rg.l)
        size = hi - lo
        ok = in_window(um, ws, we) & np.isfinite(size)
        if p["atrf"]:
            ok &= (size / a >= 0.5) & (size / a <= 3.0)
        up = ok & (c > hi + 0.2) & (c - pdh <= 2 * a)
        dn = ok & (c < lo - 0.2) & (pdl - c <= 2 * a)
        if p.get("trend", True):
            up &= tr > 0; dn &= tr < 0
        idx = np.flatnonzero(up | dn)
        idx = first_per(b.tday.values[idx], idx)
        all_idx.append(idx); all_d.append(np.where(up[idx], 1, -1))
    idx = np.concatenate(all_idx); d = np.concatenate(all_d); o = np.argsort(idx, kind="stable")
    return Setup(b, idx[o], d[o], atr_stop(b, 1.5))


SESS2_GRID = [dict(tf=tf, sess=s, atrf=af) for tf in (5, 15) for s in ("AB", "A", "B") for af in (True, False)]
SESS2_EXTRA = [dict(trend=False)]


# 10) Dual Thrust (scout #8, je-suis-tm/quant-trading "Dual Thrust backtest.py", attributed to M. Chalek):
#     range R = max(HH - LC, HC - LL) over the 5 PRIOR trading days; buy the first close above open + k R,
#     sell the first close below open - k R (each side once per day). Anchor: the trading-day open (18:00 NY,
#     traded until 16:00) or, as in the source, a London open (03:00 NY, traded until 12:00).
def fam_dt(p):
    b = B(p["tf"])
    D = daily()
    N = 5
    hh, ll = D.h.rolling(N).max().shift(1), D.l.rolling(N).min().shift(1)
    hc, lc = D.c.rolling(N).max().shift(1), D.c.rolling(N).min().shift(1)
    R = map_day(b, np.maximum(hh - lc, hc - ll))
    nm = b.ny_min.values
    if p["anchor"] == "D":
        op = map_day(b, D.o); win = in_window(nm, 18 * 60, 16 * 60)
    else:
        op = map_day(b, session_range(3 * 60, 1).o); win = in_window(nm, 3 * 60, 12 * 60)
    up_l, dn_l = op + p["k"] * R, op - p["k"] * R
    c = b.c.values; pc = np.r_[np.nan, c[:-1]]
    up = win & (c > up_l) & (pc <= up_l)
    dn = win & (c < dn_l) & (pc >= dn_l)
    idx = np.flatnonzero(up | dn); d = np.where(up[idx], 1, -1)
    idx = first_per(b.tday.values[idx] * 10 + (d > 0), idx)
    return Setup(b, idx, np.where(up[idx], 1, -1), atr_stop(b))


DT_GRID = [dict(tf=tf, anchor=an, k=k) for tf in (5, 15) for an in ("D", "L") for k in (0.2, 0.35, 0.5)]


# 11) Donchian-30 breakout with ADX / DI / EMA50 (scout #11, n30dyn4m1c/gold-pro-scalper
#     XAU_Quant_Reversion_Breakout.mq5 "Trend Breakout"): close beyond the prior 30-bar high/low, ADX14 >= thr,
#     |DI+ - DI-| >= 5 in the trade direction, close on the right side of EMA50. Published on M1 with a fixed
#     $10 stop and trailing exit; here the stop follows our ATR rule and the fixed SL/TP1/TP2 order grid.
def rma_nan(x, n):
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    ok = np.flatnonzero(np.isfinite(x))
    if len(ok) == 0:
        return out
    f = ok[0]
    out[f:] = frost.rma(np.nan_to_num(x[f:]), n)
    return out


def dmi(b, n=14):
    """ta.dmi(n, n): DI+, DI-, ADX (TradingView definitions)."""
    h, l, c = b.h.values, b.l.values, b.c.values
    up = np.r_[np.nan, h[1:] - h[:-1]]; dn = np.r_[np.nan, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    trur = frost.rma(tr, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus = 100 * frost.rma(pdm, n) / trur; minus = 100 * frost.rma(mdm, n) / trur
        sm = plus + minus
        dx = np.abs(plus - minus) / np.where(sm == 0, 1, sm)
    return plus, minus, 100 * rma_nan(dx, n)


def fam_dcadx(p):
    b = B(p["tf"])
    c, h, l = b.c.values, b.h.values, b.l.values
    N = 30
    hh = pd.Series(h).rolling(N).max().shift(1).values
    ll = pd.Series(l).rolling(N).min().shift(1).values
    plus, minus, adx = dmi(b)
    e50 = frost.ema(c, 50)
    trend = (adx >= p["adx"]) & (np.abs(plus - minus) >= 5)
    up = trend & (c > hh) & (plus > minus) & (c > e50)
    dn = trend & (c < ll) & (minus > plus) & (c < e50)
    if p["cross"]:
        pc = np.r_[np.nan, c[:-1]]
        up &= pc <= np.r_[np.nan, hh[:-1]]; dn &= pc >= np.r_[np.nan, ll[:-1]]
    idx = np.flatnonzero(up | dn)
    return Setup(b, idx, np.where(up[idx], 1, -1), atr_stop(b))


DCADX_GRID = [dict(tf=tf, adx=ax, cross=cr) for tf in (1, 5) for ax in (25, 30) for cr in (False, True)]


# 12) 08:30 NY news straddle (scout #19, nopponkaeward-max/EA_ATR_news EA_ATR_News.mq5): at 08:30 levels at
#     the 08:29 close +/- k x ATR14(atf); the first close beyond a level within 60 minutes is the signal
#     (a chart indicator cannot rest stop orders, so the close confirms the break); stop 1 x ATR14(atf).
def fam_strad(p):
    b = B(p["tf"])
    d1 = B(1)
    a_src = frost.htf_on_ltf(d1, B(p["atf"]), B(p["atf"]).atr.values)
    m = d1.ny_min.values == 8 * 60 + 29
    ref = pd.Series(d1.c.values[m], index=d1.tday.values[m])
    A = pd.Series(a_src[m], index=d1.tday.values[m])
    ref, A = ref[~ref.index.duplicated()], A[~A.index.duplicated()]
    r, a = map_day(b, ref), map_day(b, A)
    up_l, dn_l = r + p["k"] * a, r - p["k"] * a
    c = b.c.values; pc = np.r_[np.nan, c[:-1]]
    win = in_window(b.ny_min.values, 8 * 60 + 30, 9 * 60 + 30)
    up = win & (c > up_l) & (pc <= up_l)
    dn = win & (c < dn_l) & (pc >= dn_l)
    idx = np.flatnonzero(up | dn); d = np.where(up[idx], 1, -1)
    idx = first_per(b.tday.values[idx] * 10 + (d > 0), idx)
    stop = 1.0 * frost.htf_on_ltf(b, B(p["atf"]), B(p["atf"]).atr.values)
    return Setup(b, idx, np.where(up[idx], 1, -1), stop)


STRAD_GRID = [dict(tf=tf, k=k, atf=af) for tf in (1, 5) for k in (0.5, 1.0) for af in (5, 15)]

FAMILIES = {
    "ASIA": ("Asian-range breakout (London)", fam_asia, ASIA_GRID, ASIA_EXTRA),
    "ORB": ("Opening-range breakout 03:00/08:20/09:30", fam_orb, ORB_GRID, ORB_EXTRA),
    "SESS2": ("Two-session boxes + H1 EMA50/200 (scout #6)", fam_sess2, SESS2_GRID, SESS2_EXTRA),
    "DT": ("Dual Thrust (scout #8)", fam_dt, DT_GRID, []),
    "PDHL": ("Prior-day high/low close-beyond", fam_pdhl, PDHL_GRID, []),
    "SQZ": ("BB-inside-KC squeeze release", fam_sqz, SQZ_GRID, SQZ_EXTRA),
    "NR": ("Inside-bar / NR4 / NR7 breakout", fam_nr, NR_GRID, []),
    "DRIFT": ("Time-of-day drift (DISC-fitted hours)", fam_drift, DRIFT_GRID, []),
    "NEWS": ("08:30/10:00 data-release momentum", fam_news, NEWS_GRID, []),
    "DON": ("Donchian breakout + H1 EMA filter", fam_don, DON_GRID, []),
    "DCADX": ("Donchian-30 + ADX/DI/EMA50 (scout #11)", fam_dcadx, DCADX_GRID, []),
    "STRAD": ("08:30 ATR news straddle (scout #19)", fam_strad, STRAD_GRID, []),
}


# ─── evaluation ──────────────────────────────────────────────────────────────
def disc_days():
    a, z = frost.PERIODS["DISC"]
    return frost.trading_days(frost._ts(a), frost._ts(z))


def only(sig, period):
    t = frost.m1().time.values[sig.i.values]
    a, z = frost.PERIODS[period]
    return sig[(t >= frost._ts(a)) & (t < frost._ts(z))]


def run(S, o, period=None, **kw):
    sig = S.sig(o["t1"], o["t2"], o["sm"])
    if period:
        sig = only(sig, period)
    return frost.simulate(sig, be=o["be"], max_hold=o["hold"], **kw)


def disc_score(S, o):
    t = run(S, o, "DISC")
    s = frost.stats(t, "DISC", disc_days())
    return s


def better(s, best):
    """Highest avgR among variants with >= 0.5 trades/day; frequency-eligible beats ineligible."""
    if best is None:
        return True
    if s.get("n", 0) == 0:
        return False
    if best.get("n", 0) == 0:
        return True
    e1, e0 = s["per_day"] >= MIN_PER_DAY, best["per_day"] >= MIN_PER_DAY
    if e1 != e0:
        return e1
    return s["avgR"] > best["avgR"]


def tune(code, verbose=True):
    name, gen, grid, extra = FAMILIES[code]
    log = []
    best = None
    o = dict(DEFAULT)
    for p in grid:
        s = disc_score(gen(p), o)
        log.append(("S1", p, dict(o), s))
        if better(s, best):
            best, bp = s, p
    for e in extra:  # tweaks of the best factorial variant
        p = {**bp, **e}
        s = disc_score(gen(p), o)
        log.append(("S1+", p, dict(o), s))
        if better(s, best):
            best, bp = s, p
    S = gen(bp)
    bo = dict(o)
    for g in ORDER_GRID:
        oo = {**o, **g}
        s = disc_score(S, oo)
        log.append(("S2a", bp, oo, s))
        if better(s, best):
            best, bo = s, oo
    for hd in HOLD_GRID:
        oo = {**bo, "hold": hd}
        s = disc_score(S, oo)
        log.append(("S2b", bp, oo, s))
        if better(s, best):
            best, bo = s, oo
    base_o = dict(bo)
    for sm in SM_GRID:
        oo = {**base_o, "sm": sm}
        s = disc_score(S, oo)
        log.append(("S2c", bp, oo, s))
        if better(s, best):
            best, bo = s, oo
    if verbose:
        print(f"\n=== {code}: {name} — DISC tuning ({len(log)} combos) ===")
        for st, p, oo, s in log:
            print(f"{st:4s} {fmt_p(p):48s} {fmt_o(oo):34s} n={s.get('n', 0):4d} pd={s.get('per_day', 0):5.2f} "
                  f"avgR={s.get('avgR', float('nan')):+.4f} se={s.get('se', float('nan')):.4f} win={s.get('win', 0)}")
        print(f"FROZEN {code}: {fmt_p(bp)} | {fmt_o(bo)} | DISC n={best['n']} avgR={best['avgR']:+.4f}")
    return dict(code=code, name=name, p=bp, o=bo, disc=best, combos=len(log))


def fmt_p(p):
    return ",".join(f"{k}={v}" for k, v in p.items())


def fmt_o(o):
    return f"TP1={o['t1']} TP2={o['t2']} hold={o['hold']} be={o['be']} stopx={o['sm']}"


def y2025_complete():
    return os.path.exists(os.path.join(frost.DATA, "XAUUSD_2025_m1.csv.gz"))


def evaluate(res, verbose=True):
    code, p, o = res["code"], res["p"], res["o"]
    gen = FAMILIES[code][1]
    S = gen(p)
    t = run(S, o)
    rows = {r["label"]: r for r in frost.by_period(t)}
    # VAL random control: same stop rule, targets, hold and be
    sig = S.sig(o["t1"], o["t2"], o["sm"])
    tt = frost.m1().time.values[sig.i.values]
    a, z = frost.PERIODS["VAL"]
    vm = (tt >= frost._ts(a)) & (tt < frost._ts(z))
    vidx = S.idx[vm]
    sb, sm = S.stop_bar, o["sm"]
    rc = frost.random_control(vidx, S.b, lambda b, i: sm * sb[i], o["t1"], o["t2"], n_runs=20,
                              max_hold=o["hold"], be=o["be"])
    rc = np.array([x for x in rc if np.isfinite(x)])
    stress = frost.simulate(sig[vm], spread=0.45, slip=0.05, be=o["be"], max_hold=o["hold"])
    ss = frost.stats(stress, "STRESS")
    v = rows["VAL"]
    y = rows["Y2025"]
    rmed = float(np.median(rc)) if len(rc) else float("nan")
    r5, r95 = (float(np.percentile(rc, 5)), float(np.percentile(rc, 95))) if len(rc) else (np.nan, np.nan)
    checks = {
        "val>0 & t>=1": v.get("n", 0) > 1 and v["avgR"] > 0 and v["avgR"] / v["se"] >= 1.0,
        "y2025>0": (y.get("n", 0) > 0 and y["avgR"] > 0) if y2025_complete() else True,
        "val-rand>=0.05": v.get("n", 0) > 0 and v["avgR"] - rmed >= 0.05,
        "stress>=0": ss.get("n", 0) > 0 and ss["avgR"] >= 0,
        "per_day>=0.5": v.get("n", 0) > 0 and v["per_day"] >= MIN_PER_DAY,
    }
    res.update(rows=rows, rand=(rmed, r5, r95), stress=ss, checks=checks, passed=all(checks.values()),
               monthly=frost.monthly(t))
    if verbose:
        print(f"\n=== {code}: {res['name']} — frozen: {fmt_p(p)} | {fmt_o(o)} ===")
        print(frost.fmt(list(rows.values()) + [ss]))
        print(f"VAL random control (20 runs): median {rmed:+.4f}  5-95% [{r5:+.4f}, {r95:+.4f}]")
        print("checks:", {k: bool(x) for k, x in checks.items()}, "->", "PASS" if res["passed"] else "FAIL")
        print("monthly:", " ".join(f"{m}:{r['count']}/{r['mean']:+.3f}" for m, r in res["monthly"].iterrows()))
    return res


def table(results):
    hdr = ("| family | best params | combos | DISC avgR / n | VAL n | VAL /day | VAL win% | VAL TP1% | VAL TP2% | "
           "VAL avgR ± se | VAL PF | Y2025 avgR | HOLD avgR | rand median [5–95%] | stress avgR | PASS/FAIL |")
    lines = [hdr, "|" + "---|" * 16]
    for r in results:
        v, y, h = r["rows"]["VAL"], r["rows"]["Y2025"], r["rows"]["HOLD"]
        g = lambda s, k, f="{:+.4f}": f.format(s[k]) if s.get("n", 0) else "–"
        rm, r5, r95 = r["rand"]
        ytxt = g(y, "avgR") + ("" if y2025_complete() else " (partial)")
        lines.append(
            f"| {r['code']} {r['name']} | {fmt_p(r['p'])}; {fmt_o(r['o'])} | {r['combos']} | "
            f"{r['disc']['avgR']:+.4f} / {r['disc']['n']} | {v.get('n', 0)} | {g(v, 'per_day', '{:.2f}')} | "
            f"{g(v, 'win', '{}')} | {g(v, 'tp1', '{}')} | {g(v, 'tp2', '{}')} | "
            f"{g(v, 'avgR')} ± {g(v, 'se', '{:.4f}')} | {g(v, 'pf', '{}')} | {ytxt} | {g(h, 'avgR')} | "
            f"{rm:+.4f} [{r5:+.4f}, {r95:+.4f}] | {g(r['stress'], 'avgR')} | "
            f"{'PASS' if r['passed'] else 'FAIL: ' + ', '.join(k for k, x in r['checks'].items() if not x)} |")
    return "\n".join(lines)


# ─── best technique for the lead ─────────────────────────────────────────────
# Filled in after the single final run (the highest VAL avgR among passing families, else the highest VAL avgR).
# No family passed; the highest VAL avgR is PDHL (prior-day high/low close-beyond on M15 with the H1 EMA50 side filter,
# first break per side per trading day, stop 1.5 x ATR14(M15), TP1 1.5R, TP2 3.0R, split, max_hold 120).
BEST = dict(code="PDHL", p=dict(tf=15, sess="all", htf=True, first=True),
            o=dict(t1=1.5, t2=3.0, hold=120, be=False, sm=1.0))


def best_signals():
    """sig DataFrame (frost.levels format) of Team C's single best technique, all periods.
    Simulate with frost.simulate(sig, be=BEST['o']['be'], max_hold=BEST['o']['hold'])."""
    code, p, o = BEST["code"], BEST["p"], BEST["o"]
    return FAMILIES[code][1](p).sig(o["t1"], o["t2"], o["sm"])


def main(argv):
    disc_only = "--disc-only" in argv
    codes = [a for a in argv if not a.startswith("--")] or list(FAMILIES)
    t0 = time.time()
    print("coverage:", frost.coverage(), "| 2025 complete:", y2025_complete(), "| DISC trading days:", disc_days())
    print("drift table (DISC):\n", drift_table().round(3).to_string())
    results = []
    for code in codes:
        res = tune(code)
        if not disc_only:
            res = evaluate(res)
        results.append(res)
        sys.stdout.flush()
    if not disc_only:
        print("\n" + table(results))
    print(f"\n[{time.time() - t0:.0f}s]")
    return results


if __name__ == "__main__":
    main(sys.argv[1:])
