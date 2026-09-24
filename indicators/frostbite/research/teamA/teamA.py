"""Frostbite research, Team A: TREND and MOMENTUM scalps on XAUUSD (M1-M15).

Run from research/:   <venv>/bin/python teamA/teamA.py          (full report, prints every table number)
                      <venv>/bin/python teamA/teamA.py F3       (one family only)

Protocol (BRIEF.md): tune on DISC (Jan-Apr 2026) only, <= ~40 combos per family, freeze the best DISC
variant (highest avgR with >= 0.5 trades per trading day), then report it unchanged on VAL, Y2025, HOLD,
plus random control and stress test on VAL.

Search per family (identical staging for every family):
  stage 1  signal grid (family specific) at the default orders TP1 1.0R / TP2 2.0R, split, max_hold 120
  stage 2  refinements of the stage-1 winner (stop multiple, one extra filter), same default orders
  stage 3  orders on the winner: (TP1,TP2) in 6 pairs x be {False, True} at max_hold 120
  stage 4  max_hold {60, 240} on the stage-3 winner
The frozen variant is the highest DISC avgR over ALL combos tried (per_day >= 0.5).

No lookahead: every rule uses values of the CLOSED signal bar (and earlier); higher-timeframe values come
from frost.htf_on_ltf (last completed HTF bar); the engine enters at the next 1-minute open.
Stops are k x ATR(14) of the chart timeframe unless the family says otherwise.
"""
import os, sys, math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import frost  # noqa: E402

PAIRS = [(0.5, 1.5), (0.75, 1.5), (0.75, 2.0), (1.0, 2.0), (1.0, 3.0), (1.5, 3.0)]
ORDER0 = dict(t1=1.0, t2=2.0, be=False, hold=120)
MIN_PER_DAY = 0.5

# ─── cached building blocks ──────────────────────────────────────────────────
_C = {}


def _cache(key, fn):
    if key not in _C:
        _C[key] = fn()
    return _C[key]


def B(tf):
    return _cache(("b", tf), lambda: frost.bars(tf))


def EMA(tf, n, src="c"):
    return _cache(("ema", tf, n, src), lambda: frost.ema(B(tf)[src].values, n))


def ATR(tf, n=14):
    return _cache(("atr", tf, n), lambda: frost.atr(B(tf), n))


def VWAP(tf):
    return _cache(("vwap", tf), lambda: frost.vwap_session(B(tf)))


def ema_nan(x, n):
    """EMA of a series that starts with NaNs (e.g. MACD line)."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    ok = np.where(np.isfinite(x))[0]
    if len(ok) == 0:
        return out
    f = ok[0]
    out[f:] = frost.ema(x[f:], n)
    return out


def HTF_TREND(tf, htf, n=50):
    """+1 if the last completed HTF close is above its EMA(n), -1 if below (as known at each tf bar close)."""
    def f():
        bh = B(htf)
        e = frost.ema(bh.c.values, n)
        s = np.sign(bh.c.values - e)
        s[~np.isfinite(e)] = 0
        return np.nan_to_num(frost.htf_on_ltf(B(tf), bh, s))
    return _cache(("htf", tf, htf, n), f)


def supertrend(tf, mult, n=10):
    """TradingView ta.supertrend(mult, n): returns (line, dir) with dir = +1 up, -1 down (TV sign flipped)."""
    def f():
        b = B(tf)
        h, l, c = b.h.values, b.l.values, b.c.values
        a = frost.atr(b, n)
        src = (h + l) / 2
        N = len(c)
        up_b = src + mult * a
        lo_b = src - mult * a
        line = np.full(N, np.nan)
        dr = np.zeros(N)
        pu = pl = np.nan
        pst = np.nan
        for i in range(N):
            if not np.isfinite(a[i]):
                continue
            u, lo = up_b[i], lo_b[i]
            ppl = 0.0 if not np.isfinite(pl) else pl
            ppu = 0.0 if not np.isfinite(pu) else pu
            lo = lo if (lo > ppl or c[i - 1] < ppl) else ppl
            u = u if (u < ppu or c[i - 1] > ppu) else ppu
            if i == 0 or not np.isfinite(a[i - 1]):
                d_tv = 1
            elif pst == ppu:
                d_tv = -1 if c[i] > u else 1
            else:
                d_tv = 1 if c[i] < lo else -1
            st = lo if d_tv == -1 else u
            line[i] = st
            dr[i] = -d_tv
            pu, pl, pst = u, lo, st
        return line, dr
    return _cache(("st", tf, mult, n), f)


def macd(tf, f=12, s=26, sg=9):
    def g():
        m = EMA(tf, f) - EMA(tf, s)
        sig = ema_nan(m, sg)
        return m, sig, m - sig
    return _cache(("macd", tf, f, s, sg), g)


def rma_nan(x, n):
    """RMA (TradingView ta.rma) of a series that starts with NaNs."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    ok = np.where(np.isfinite(x))[0]
    if len(ok) == 0:
        return out
    f = ok[0]
    out[f:] = frost.rma(x[f:], n)
    return out


def ADX(tf, n=14):
    """TradingView ta.dmi(n, n) ADX."""
    def f():
        b = B(tf); h, l, c = b.h.values, b.l.values, b.c.values
        up = h - prev(h); dn = prev(l) - l
        pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
        pdm[0] = np.nan; mdm[0] = np.nan
        pc = prev(c)
        tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
        tr[0] = h[0] - l[0]
        trur = frost.rma(tr, n)
        with np.errstate(divide="ignore", invalid="ignore"):
            pl = 100 * rma_nan(pdm, n) / trur
            mi = 100 * rma_nan(mdm, n) / trur
            sm = pl + mi
            dx = np.abs(pl - mi) / np.where(sm == 0, 1, sm)
        return 100 * rma_nan(dx, n)
    return _cache(("adx", tf, n), f)


def RSI(tf, n=14):
    return _cache(("rsi", tf, n), lambda: frost.rsi(B(tf).c.values, n))


def prev(x, k=1):
    x = np.asarray(x)
    out = np.empty_like(x, dtype=float)
    out[:k] = np.nan
    out[k:] = x[:-k]
    return out


def in_window(b, windows):
    """bar OPEN time (New York) inside any [start, end) window, minutes since midnight."""
    m = np.zeros(len(b), bool)
    for a, z in windows:
        m |= (b.ny_min.values >= a) & (b.ny_min.values < z)
    return m


LONDON = (3 * 60, 6 * 60)
NYAM = (8 * 60, 11 * 60)


# ─── families: each returns (tf, long_mask, short_mask, stop_dist_array) ─────
def f1_ema_pullback(tf=5, line=20, htf=0, k=1.5, stack200=0):
    """EMA pullback: EMA20 > EMA50 (and > EMA200 if stack200); bar low touches EMA<line>, closes above it
    as a bullish bar (close > open). Mirror for shorts. Optional H1 filter: H1 close vs H1 EMA50."""
    b = B(tf); o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    e20, e50 = EMA(tf, 20), EMA(tf, 50)
    el = e20 if line == 20 else e50
    up = e20 > e50
    dn = e20 < e50
    if stack200:
        e200 = EMA(tf, 200)
        up &= e50 > e200
        dn &= e50 < e200
    L = up & (l <= el) & (c > el) & (c > o)
    S = dn & (h >= el) & (c < el) & (c < o)
    if htf:
        t = HTF_TREND(tf, 60)
        L &= t > 0
        S &= t < 0
    return tf, L, S, k * ATR(tf)


def f2_ema_cross(tf=5, fast=9, slow=21, htf=60, k=1.5):
    """EMA crossover on the closed bar, only in the direction of the HTF trend (HTF close vs HTF EMA50)."""
    b = B(tf)
    ef, es = EMA(tf, fast), EMA(tf, slow)
    x = ef - es
    xp = prev(x)
    t = HTF_TREND(tf, htf)
    L = (x > 0) & (xp <= 0) & (t > 0)
    S = (x < 0) & (xp >= 0) & (t < 0)
    return tf, L, S, k * ATR(tf)


def f3_vwap(tf=5, trig="pb", htf=0, k=1.5, sess=0):
    """Session VWAP trend (anchored 17:00 NY).
    pb:  previous close above VWAP, bar low touches VWAP, bar closes above VWAP and bullish (mirror short).
    rc:  reclaim, previous close below VWAP and this close above it (mirror short)."""
    b = B(tf); o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    v = VWAP(tf)
    cp = prev(c); vp = prev(v)
    if trig == "pb":
        L = (cp > vp) & (l <= v) & (c > v) & (c > o)
        S = (cp < vp) & (h >= v) & (c < v) & (c < o)
    else:
        L = (cp <= vp) & (c > v)
        S = (cp >= vp) & (c < v)
    if htf:
        t = HTF_TREND(tf, 60)
        L &= t > 0
        S &= t < 0
    if sess:
        w = in_window(b, [LONDON, NYAM])
        L &= w; S &= w
    return tf, L, S, k * ATR(tf)


def f4_supertrend(tf=5, mult=3, htf=0, stop="st", k=1.5):
    """Supertrend(ATR 10, mult) flip on the closed bar, optional H1 filter.
    stop 'st' = distance from close to the Supertrend line at the signal bar, 'atr' = k x ATR(14)."""
    line, dr = supertrend(tf, mult)
    c = B(tf).c.values
    dp = prev(dr)
    L = (dr > 0) & (dp < 0)
    S = (dr < 0) & (dp > 0)
    if htf:
        t = HTF_TREND(tf, 60)
        L &= t > 0
        S &= t < 0
    sd = np.abs(c - line) if stop == "st" else k * ATR(tf)
    return tf, L, S, sd


def f5_thrust(tf=5, trig="macd0", k=1.5, sess=0):
    """Momentum thrust in the H1 trend direction (H1 close vs H1 EMA50 must agree).
    macd0: MACD(12,26,9) histogram crosses zero; macdx: MACD line crosses zero;
    rsi60: RSI(14) crosses above 60 / below 40; rsi55: crosses 55 / 45."""
    t = HTF_TREND(tf, 60)
    if trig in ("macd0", "macdx"):
        m, sg, hist = macd(tf)
        x = hist if trig == "macd0" else m
        xp = prev(x)
        L = (x > 0) & (xp <= 0)
        S = (x < 0) & (xp >= 0)
    else:
        r = RSI(tf); rp = prev(r)
        hi = 60 if trig == "rsi60" else 55
        lo = 100 - hi
        L = (r > hi) & (rp <= hi)
        S = (r < lo) & (rp >= lo)
    L &= t > 0
    S &= t < 0
    if sess:
        w = in_window(B(tf), [LONDON, NYAM])
        L &= w; S &= w
    return tf, L, S, k * ATR(tf)


def f6_burst(tf=5, mult=2.0, htf=0, k=1.5, ext=0.25):
    """Momentum burst: bar range > mult x ATR(14) of the PREVIOUS bar, closing in the outer <ext> of its range;
    enter in the bar's direction. Optional H1 filter."""
    b = B(tf); o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    a = prev(ATR(tf))
    rng = h - l
    big = rng > mult * a
    L = big & (c > o) & (c >= h - ext * rng)
    S = big & (c < o) & (c <= l + ext * rng)
    if htf:
        t = HTF_TREND(tf, 60)
        L &= t > 0
        S &= t < 0
    return tf, L, S, k * ATR(tf)


def _session_drift(b):
    """For each bar: sign of the drift of the session before its window.
    London window (03-06): close of the last bar before 03:00 minus the trading day's first open (Asia drift).
    NY window (08-11): close of the last bar before 08:00 minus the open of the first bar at/after 03:00 (London drift)."""
    tday = b.tday.values; nm = b.ny_min.values; o = b.o.values; c = b.c.values
    n = len(b)
    out = np.zeros(n)
    day_open = np.nan; lon_open = np.nan; asia_close = np.nan; lon_close = np.nan
    cur = None
    for i in range(n):
        if tday[i] != cur:
            cur = tday[i]; day_open = o[i]; lon_open = np.nan; asia_close = np.nan; lon_close = np.nan
        m = nm[i]
        in_eve = m >= 17 * 60
        if LONDON[0] <= m < LONDON[1] and not in_eve:
            if np.isfinite(asia_close):
                out[i] = np.sign(asia_close - day_open)
        elif NYAM[0] <= m < NYAM[1] and not in_eve:
            if np.isfinite(lon_close) and np.isfinite(lon_open):
                out[i] = np.sign(lon_close - lon_open)
        # update anchors with this bar's (closed) values for later bars
        if not in_eve and m < LONDON[0]:
            asia_close = c[i]
        if not in_eve and m >= LONDON[0] and not np.isfinite(lon_open):
            lon_open = o[i]
        if not in_eve and LONDON[0] <= m < NYAM[0]:
            lon_close = c[i]
    return out


def f7_session(tf=5, win="both", bias="drift", trig="ema", k=1.5):
    """Time-of-day trend continuation in London 03-06 NY and/or NY 08-11 NY.
    bias 'drift': direction of the preceding session (Asia for London, London for NY);
         'h1': H1 close vs H1 EMA50; 'both': both must agree.
    trig 'ema': EMA20 pullback (low touches EMA20, bullish close above it);
         'brk': previous bar bearish (pullback) and this bar closes above the previous high."""
    b = B(tf); o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    wins = {"lon": [LONDON], "ny": [NYAM], "both": [LONDON, NYAM]}[win]
    w = in_window(b, wins)
    dr = _cache(("drift", tf), lambda: _session_drift(b))
    t = HTF_TREND(tf, 60)
    if bias == "drift":
        bs = dr
    elif bias == "h1":
        bs = t
    else:
        bs = np.where(dr == t, dr, 0)
    if trig == "ema":
        e = EMA(tf, 20)
        L = (l <= e) & (c > e) & (c > o)
        S = (h >= e) & (c < e) & (c < o)
    else:
        op, cp, hp, lp = prev(o), prev(c), prev(h), prev(l)
        L = (cp < op) & (c > hp) & (c > o)
        S = (cp > op) & (c < lp) & (c < o)
    L &= w & (bs > 0)
    S &= w & (bs < 0)
    return tf, L, S, k * ATR(tf)


def f8_topdown(tf=1, sess=1, bias_tf=10, vw=1, k=1.1):
    """Top-down 1m/5m/10m scalp, after junutala/XAUStrategy 'XAU_Scalping_Strategy.pine' (scout reference).
    Bias (bias_tf, last completed bar): EMA20 > EMA50 and close > session VWAP of that TF (mirror short).
    Setup (M5, last completed bar): RSI(14) < 70 for longs, > 30 for shorts.
    Trigger (chart tf): EMA9 crosses EMA21 in the bias direction, chart RSI(14) in (45, 70) for longs /
    (30, 55) for shorts, and (vw) close on the right side of the chart session VWAP.
    Session (sess): 02:00-11:00 New York (the script's 07:00-16:00 London). Stop k x ATR(14) (script: 1.1)."""
    b = B(tf); c = b.c.values
    bh = B(bias_tf)
    bf, bs_, bv = frost.ema(bh.c.values, 20), frost.ema(bh.c.values, 50), VWAP(bias_tf)
    bl = frost.htf_on_ltf(b, bh, ((bf > bs_) & (bh.c.values > bv)).astype(float))
    bsh = frost.htf_on_ltf(b, bh, ((bf < bs_) & (bh.c.values < bv)).astype(float))
    r5 = frost.htf_on_ltf(b, B(5), RSI(5))
    x = EMA(tf, 9) - EMA(tf, 21)
    xp = prev(x)
    r = RSI(tf)
    L = (bl > 0) & (r5 < 70) & (x > 0) & (xp <= 0) & (r > 45) & (r < 70)
    S = (bsh > 0) & (r5 > 30) & (x < 0) & (xp >= 0) & (r < 55) & (r > 30)
    if vw:
        v = VWAP(tf)
        L &= c > v
        S &= c < v
    if sess:
        w = in_window(b, [(2 * 60, 11 * 60)])
        L &= w; S &= w
    return tf, L, S, k * ATR(tf)


def f9_ema9_21_200(tf=5, adx_min=25, sess=1, k=1.5):
    """EMA 9/21/200 trend pullback, after andamagodwin/forex xau_scalper/strategy.py (scout #1).
    Long: close > EMA200 and EMA21 > EMA200; low touched EMA21 within the last 5 bars; bullish bar closing
    above EMA9 with EMA9 > EMA21; RSI(14) in [45, 70] and rising; ADX(14) >= adx_min; bar range <= 3 ATR.
    Mirror for shorts (RSI in [30, 55] and falling). sess: entries only 07-17 UTC, none on Friday from 15 UTC.
    Stop max(k x ATR(14), $1.50) (source: k = 1.5)."""
    b = B(tf); o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    e9, e21, e200 = EMA(tf, 9), EMA(tf, 21), EMA(tf, 200)
    a = ATR(tf); r = RSI(tf); rp = prev(r); ax = ADX(tf)
    tl = pd.Series((l <= e21).astype(float)).rolling(5, min_periods=1).max().values > 0
    ts = pd.Series((h >= e21).astype(float)).rolling(5, min_periods=1).max().values > 0
    common = (ax >= adx_min) & ((h - l) <= 3 * a)
    L = (c > e200) & (e21 > e200) & tl & (c > e9) & (c > o) & (e9 > e21) & (r >= 45) & (r <= 70) & (r > rp) & common
    S = (c < e200) & (e21 < e200) & ts & (c < e9) & (c < o) & (e9 < e21) & (r >= 30) & (r <= 55) & (r < rp) & common
    if sess:
        uh = b.utc_h.values
        w = (uh >= 7) & (uh < 17) & ~((b.dow.values == 4) & (uh >= 15))
        L &= w; S &= w
    return tf, L, S, np.maximum(k * a, 1.5)


def f10_fa_scalper(tf=15, sess="13-17", adx_min=20, stop="swing", k=1.5):
    """FA Gold Scalper v6 (ruthphillipsi/XAUUSD-EA-20PROJECT FA_Gold_Scalper_v6.pine, scout #2).
    Long: EMA34 > EMA50 > EMA200 and close > EMA200; lowest low of the last 3 bars <= EMA34; bullish bar
    closing above the previous high and above EMA34; ADX(14) > adx_min; RSI(14) in (45, 70). Mirror short
    (RSI in (30, 55)). Session in UTC ('13-17' source default, '07-17', 'all').
    stop 'swing': 5-bar swing low - 0.2 ATR, clamped to [0.6, 3] ATR (source); 'atr': k x ATR(14).
    For the random control (random direction) the swing stop uses the mean of the long and short distances."""
    b = B(tf); o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    ef, es, et = EMA(tf, 34), EMA(tf, 50), EMA(tf, 200)
    a = ATR(tf); r = RSI(tf); ax = ADX(tf)
    lo3 = pd.Series(l).rolling(3).min().values; hi3 = pd.Series(h).rolling(3).max().values
    L = (ef > es) & (es > et) & (c > et) & (lo3 <= ef) & (c > o) & (c > prev(h)) & (c > ef) & (ax > adx_min) \
        & (r > 45) & (r < 70)
    S = (ef < es) & (es < et) & (c < et) & (hi3 >= ef) & (c < o) & (c < prev(l)) & (c < ef) & (ax > adx_min) \
        & (r < 55) & (r > 30)
    if sess != "all":
        a0, z0 = (13, 17) if sess == "13-17" else (7, 17)
        uh = b.utc_h.values
        w = (uh >= a0) & (uh < z0)
        L &= w; S &= w
    if stop == "swing":
        sl_l = pd.Series(l).rolling(5).min().values - 0.2 * a
        sl_s = pd.Series(h).rolling(5).max().values + 0.2 * a
        dl = np.minimum(np.maximum(c - sl_l, 0.6 * a), 3 * a)
        ds = np.minimum(np.maximum(sl_s - c, 0.6 * a), 3 * a)
        return tf, L, S, (dl, ds)
    return tf, L, S, k * a


# ─── family search specs: stage-1 grid and stage-2 refinements (dict overrides of the stage-1 winner) ──
def _grid(**axes):
    keys = list(axes)
    out = [{}]
    for kk in keys:
        out = [dict(g, **{kk: v}) for g in out for v in axes[kk]]
    return out


FAMILIES = {
    "F1": dict(name="EMA pullback (20/50 stack)", fn=f1_ema_pullback,
               grid=_grid(tf=[1, 3, 5, 15], line=[20, 50], htf=[0, 1]),
               refine=[dict(k=1.0), dict(k=2.0), dict(stack200=1)]),
    "F2": dict(name="EMA cross + HTF filter", fn=f2_ema_cross,
               grid=_grid(tf=[3, 5, 15], fast_slow=[(9, 21), (20, 50)], htf=[15, 60]),
               refine=[dict(k=1.0), dict(k=2.0)]),
    "F3": dict(name="Session VWAP trend", fn=f3_vwap,
               grid=_grid(tf=[3, 5, 15], trig=["pb", "rc"], htf=[0, 1]),
               refine=[dict(k=1.0), dict(k=2.0), dict(sess=1)]),
    "F4": dict(name="Supertrend flip", fn=f4_supertrend,
               grid=_grid(tf=[3, 5, 15], mult=[2, 3], htf=[0, 1], stop=["st", "atr"]),
               refine=[]),
    "F5": dict(name="MACD/RSI thrust with H1 trend", fn=f5_thrust,
               grid=_grid(tf=[3, 5, 15], trig=["macd0", "macdx", "rsi60", "rsi55"]),
               refine=[dict(k=1.0), dict(k=2.0), dict(sess=1)]),
    "F6": dict(name="Momentum burst bar", fn=f6_burst,
               grid=_grid(tf=[3, 5, 15], mult=[1.5, 2.0, 2.5], htf=[0, 1]),
               refine=[dict(k=1.0), dict(k=2.0)]),
    "F7": dict(name="Session continuation (London/NY)", fn=f7_session,
               grid=_grid(win=["lon", "ny", "both"], bias=["drift", "h1", "both"], trig=["ema", "brk"]),
               refine=[dict(tf=3), dict(tf=15), dict(k=1.0), dict(k=2.0)]),
    "F8": dict(name="Top-down 1m EMA9/21 cross (junutala)", fn=f8_topdown,
               grid=_grid(tf=[1, 3], sess=[0, 1], bias_tf=[10, 15]),
               refine=[dict(vw=0), dict(k=1.5), dict(k=2.0)]),
    "F9": dict(name="EMA 9/21/200 pullback + ADX (andamagodwin)", fn=f9_ema9_21_200,
               grid=_grid(tf=[3, 5, 15], adx_min=[20, 25], sess=[0, 1]),
               refine=[dict(k=1.0), dict(k=2.0)]),
    "F10": dict(name="FA Gold Scalper v6 EMA34/50/200 (ruthphillipsi)", fn=f10_fa_scalper,
                grid=_grid(tf=[5, 15], sess=["13-17", "07-17", "all"], adx_min=[20, 25]),
                refine=[dict(stop="atr")]),
}


def build(fam, p):
    p = dict(p)
    if "fast_slow" in p:
        p["fast"], p["slow"] = p.pop("fast_slow")
    tf, L, S, sd = FAMILIES[fam]["fn"](**p)
    L = np.nan_to_num(L).astype(bool); S = np.nan_to_num(S).astype(bool)
    both = L & S
    L &= ~both; S &= ~both
    idx = np.where(L | S)[0]
    d = np.where(L[idx], 1, -1)
    if isinstance(sd, tuple):  # direction-dependent stop (long, short)
        sdl, sds = np.asarray(sd[0], float), np.asarray(sd[1], float)
        sdi = np.where(d > 0, sdl[idx], sds[idx])
        sd_all = 0.5 * (sdl + sds)
    else:
        sd_all = np.asarray(sd, float)
        sdi = sd_all[idx]
    ok = np.isfinite(sdi) & (sdi > 0)
    return tf, idx[ok], d[ok], sdi[ok], sd_all


# ─── evaluation ──────────────────────────────────────────────────────────────
_DAYS = {}


def pdays(name):
    if name not in _DAYS:
        a, z = frost.PERIODS[name]
        _DAYS[name] = frost.trading_days(frost._ts(a), frost._ts(z))
    return _DAYS[name]


def eval_disc(fam, p, o):
    """DISC-only evaluation used for tuning (signals outside DISC are not simulated)."""
    tf, idx, d, sd, _ = build(fam, p)
    b = B(tf)
    m = frost.in_period(b.iloc[idx], "DISC").values
    sig = frost.levels(b, idx[m], d[m], sd[m], o["t1"], o["t2"])
    t = frost.simulate(sig, be=o["be"], max_hold=o["hold"])
    return frost.stats(t, "DISC", pdays("DISC"))


def pick(rows):
    ok = [r for r in rows if r["st"].get("n", 0) and r["st"]["per_day"] >= MIN_PER_DAY]
    pool = ok if ok else [r for r in rows if r["st"].get("n", 0)]
    return max(pool, key=lambda r: r["st"]["avgR"])


def okey(o):
    return (o["t1"], o["t2"], o["be"], o["hold"])


def search(fam, verbose=True):
    spec = FAMILIES[fam]
    rows = []
    seen = set()

    def run(p, o, stage):
        key = (tuple(sorted(p.items())), okey(o))
        if key in seen:
            return
        seen.add(key)
        st = eval_disc(fam, p, o)
        rows.append(dict(stage=stage, p=dict(p), o=dict(o), st=st))
        if verbose:
            print(f"  [{stage}] {p} {okey(o)}  n={st.get('n', 0)} /day={st.get('per_day')} "
                  f"avgR={st.get('avgR')} se={st.get('se')}", flush=True)

    for p in spec["grid"]:
        run(p, ORDER0, 1)
    best1 = pick(rows)["p"]
    for r in spec["refine"]:
        run(dict(best1, **r), ORDER0, 2)
    bestp = pick(rows)["p"]
    for (t1, t2) in PAIRS:
        for be in (False, True):
            run(bestp, dict(t1=t1, t2=t2, be=be, hold=120), 3)
    o3 = pick([r for r in rows if r["p"] == bestp])["o"]
    for hold in (60, 240):
        run(bestp, dict(o3, hold=hold), 4)
    best = pick(rows)
    return best, rows


def fmt_p(fam, p, o):
    s = ", ".join(f"{k}={v}" for k, v in p.items())
    return f"{s}; TP1 {o['t1']}R TP2 {o['t2']}R {'BE' if o['be'] else 'split'} hold {o['hold']}"


def full_eval(fam, p, o, n_runs=20):
    """Frozen variant on every period, random control and stress test on VAL."""
    tf, idx, d, sd, sd_all = build(fam, p)
    b = B(tf)
    sig = frost.levels(b, idx, d, sd, o["t1"], o["t2"])
    t = frost.simulate(sig, be=o["be"], max_hold=o["hold"])
    per = {r["label"]: r for r in frost.by_period(t)}
    mval = frost.in_period(b.iloc[idx], "VAL").values
    stop_fn = lambda bb, ii: sd_all[ii]  # same stop rule as the real signals
    rc = frost.random_control(idx[mval], b, stop_fn, o["t1"], o["t2"], n_runs=n_runs,
                              be=o["be"], max_hold=o["hold"])
    rc = np.array([x for x in rc if np.isfinite(x)])
    sig_v = frost.levels(b, idx[mval], d[mval], sd[mval], o["t1"], o["t2"])
    ts = frost.simulate(sig_v, spread=0.45, slip=0.05, be=o["be"], max_hold=o["hold"])
    stress = frost.stats(ts, "VAL-stress", pdays("VAL"))
    mon = frost.monthly(t)
    return dict(per=per, rc=rc, stress=stress, monthly=mon, trades=t)


def verdict(ev, y2025_available):
    v = ev["per"]["VAL"]; y = ev["per"]["Y2025"]
    rc_med = float(np.median(ev["rc"])) if len(ev["rc"]) else float("nan")
    checks = {
        "VAL avgR>0 & t>=1": v.get("n", 0) > 1 and v["avgR"] > 0 and v["avgR"] / v["se"] >= 1.0,
        "Y2025 avgR>0": (y.get("n", 0) > 0 and y["avgR"] > 0) if y2025_available else True,
        "VAL - rand med >= 0.05": v.get("n", 0) > 0 and v["avgR"] - rc_med >= 0.05,
        "stress avgR>=0": ev["stress"].get("n", 0) > 0 and ev["stress"]["avgR"] >= 0,
        "VAL per_day>=0.5": v.get("n", 0) > 0 and v["per_day"] >= MIN_PER_DAY,
    }
    return all(checks.values()), checks, rc_med


def y2025_available():
    return os.path.exists(os.path.join(frost.DATA, "XAUUSD_2025_m1.csv.gz"))


def best_signals():
    """Signal frame (i, d, ref, sl, tp1, tp2) of Team A's single best technique, frozen from DISC.
    Simulate with: frost.simulate(best_signals(), be=BEST_ORDER['be'], max_hold=BEST_ORDER['hold'])."""
    tf, idx, d, sd, _ = build(BEST_FAM, BEST_PARAMS)
    return frost.levels(B(tf), idx, d, sd, BEST_ORDER["t1"], BEST_ORDER["t2"])


# Filled in from the final run (the variant with the highest VAL avgR among passes, else highest VAL avgR).
BEST_FAM = "F1"
BEST_PARAMS = dict(tf=5, line=20, htf=0)
BEST_ORDER = dict(t1=1.0, t2=2.0, be=False, hold=120)


def main(fams):
    print("coverage", frost.coverage())
    y25 = y2025_available()
    print("2025 file complete:", y25, "| 2026 file complete:",
          os.path.exists(os.path.join(frost.DATA, "XAUUSD_2026_m1.csv.gz")))
    print("trading days", {k: pdays(k) for k in frost.PERIODS})
    table = []
    for fam in fams:
        spec = FAMILIES[fam]
        print(f"\n=== {fam} {spec['name']} ===", flush=True)
        best, rows = search(fam)
        p, o = best["p"], best["o"]
        print(f"  combos tried: {len(rows)}")
        print(f"  FROZEN: {fmt_p(fam, p, o)}")
        ev = full_eval(fam, p, o)
        print(frost.fmt(list(ev["per"].values())))
        print("  VAL stress (spread 0.45, slip 0.05):", ev["stress"])
        rc = ev["rc"] if len(ev["rc"]) else np.array([np.nan])
        ok, checks, rc_med = verdict(ev, y25)
        print(f"  random control VAL: median {rc_med:.4f}  5-95%: {np.percentile(rc, 5):.4f} .. {np.percentile(rc, 95):.4f}")
        print("  checks:", checks, "->", "PASS" if ok else "FAIL")
        print("  monthly (count, mean R):")
        print(ev["monthly"].T.to_string())
        v, y, hd, ds = ev["per"]["VAL"], ev["per"]["Y2025"], ev["per"]["HOLD"], ev["per"]["DISC"]
        table.append(dict(fam=fam, name=spec["name"], params=fmt_p(fam, p, o), combos=len(rows),
                          disc=f"{ds.get('avgR')}/{ds.get('n')}",
                          val=f"{v.get('n')}/{v.get('per_day')}/{v.get('win')}/{v.get('tp1')}/{v.get('tp2')}/"
                              f"{v.get('avgR')}±{v.get('se')}/{v.get('pf')}",
                          y25=(f"{y.get('avgR')} (n={y.get('n')})" if y.get("n") else "n/a") if y25
                          else f"{y.get('avgR', 'n/a')} (n={y.get('n', 0)}, partial year)",
                          hold=f"{hd.get('avgR', 'n/a')} (n={hd.get('n', 0)})", rmed=f"{rc_med:.4f} [{np.percentile(rc, 5):.3f},{np.percentile(rc, 95):.3f}]",
                          stress=ev["stress"].get("avgR"), res="PASS" if ok else "FAIL",
                          val_avgR=v.get("avgR", -9)))
    print("\n| family | best params | combos | DISC avgR/n | VAL n/per_day/win%/TP1%/TP2%/avgR±se/PF | "
          "Y2025 avgR | HOLD avgR | random median [5-95%] | stress avgR | result |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in table:
        print(f"| {r['fam']} {r['name']} | {r['params']} | {r['combos']} | {r['disc']} | {r['val']} | {r['y25']} | "
              f"{r['hold']} | {r['rmed']} | {r['stress']} | {r['res']} |")
    passed = [r for r in table if r["res"] == "PASS"]
    pool = passed if passed else table
    top = max(pool, key=lambda r: r["val_avgR"])
    print(f"\nBEST (highest VAL avgR among {'passes' if passed else 'all, none passed'}): {top['fam']} {top['params']}")
    return table


def search_only(fams):
    """Tuning pass: DISC numbers only (nothing from VAL / Y2025 / HOLD is computed)."""
    print("coverage", frost.coverage(), "| DISC trading days", pdays("DISC"))
    for fam in fams:
        print(f"\n=== {fam} {FAMILIES[fam]['name']} ===", flush=True)
        best, rows = search(fam)
        print(f"  combos tried: {len(rows)} | FROZEN: {fmt_p(fam, best['p'], best['o'])} | DISC {best['st']}")


if __name__ == "__main__":
    fams = [a for a in sys.argv[1:] if a in FAMILIES] or list(FAMILIES)
    if "--search" in sys.argv:
        search_only(fams)
    else:
        main(fams)
