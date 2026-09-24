"""Frostbite research, Team B: MEAN-REVERSION scalps on XAUUSD (M1-M15).

Run from the research folder:
    python teamB/teamB.py            # full search on DISC + frozen evaluation of every family
    python teamB/teamB.py BB RSI     # only some families

Families: BB, RSI, VWAP, KC, STOCH, EXT, ROUND, ASIA, plus scout-report techniques ZSCORE (#10),
BBRSI (#12), VWAPZ (#13); round numbers (#20) are the ROUND family.

Protocol (BRIEF.md):
  * Every family is tuned on DISC (Jan-Apr 2026) only, with a fixed staged search:
      stage A  signal params          (stop 1.5 ATR, TP1 1.0R, TP2 2.0R, split, max_hold 120)
      stage B1 stop k in {1.0, 2.0} x ATR14 of the signal timeframe (+ the source stop for ZSCORE)
      stage B2 (TP1,TP2) in {(0.5,1.5),(0.75,1.5),(1.0,2.0),(1.5,3.0)} x be in {False, True}
      stage B3 max_hold in {60, 240}
    Each stage keeps the incumbent, so the frozen variant is the highest DISC avgR among
    everything tried with >= 0.5 trades per trading day. Combos are counted without duplicates.
  * The frozen variant is then reported unchanged on VAL, Y2025 and HOLD, with a random control
    (20 runs, VAL, same ATR stop and targets) and a VAL stress test (spread 0.45, slip 0.05).
  * All signals are on CLOSED bars of the chart timeframe; H1 trend values come from
    frost.htf_on_ltf (last completed H1 bar). Entry is at the next 1-minute open (engine).

best_signals() returns the sig DataFrame for the team's best technique; simulate it with
BEST_SIM (be / max_hold), e.g. frost.simulate(best_signals(), **BEST_SIM).
"""
import os, sys, math, itertools, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import frost  # noqa: E402

MIN_PER_DAY = 0.5
BASE_EXIT = dict(k=1.5, t1=1.0, t2=2.0, be=False, mh=120)
K_GRID = [1.0, 2.0]
PAIRS = [(0.5, 1.5), (0.75, 1.5), (1.0, 2.0), (1.5, 3.0)]
MH_GRID = [60, 240]


# ─── shared context per timeframe (bars + common indicators) ─────────────────
_CTX = {}


def ctx(tf):
    if tf in _CTX:
        return _CTX[tf]
    b = frost.bars(tf)
    C = {"tf": tf, "b": b, "o": b.o.values, "h": b.h.values, "l": b.l.values, "c": b.c.values,
         "time": b.time.values, "ny_min": b.ny_min.values, "ny_h": b.ny_h.values, "tday": b.tday.values}
    C["atr"] = frost.atr(b, 14)
    # H1 trend: close of the last completed H1 bar vs its EMA50
    h1 = frost.bars(60)
    up = np.where(np.isnan(frost.ema(h1.c.values, 50)), np.nan,
                  (h1.c.values > frost.ema(h1.c.values, 50)).astype(float))
    C["h1up"] = frost.htf_on_ltf(b, h1, up)
    ny_h = C["ny_h"]
    C["asia"] = (ny_h >= 18) | (ny_h < 3)          # 18:00-02:59 New York
    _CTX[tf] = C
    return C


def prev(x, k=1):
    x = np.asarray(x, float)
    return np.r_[np.full(k, np.nan), x[:-k]]


def apply_filters(C, L, S, sp):
    """Common optional filters: H1 trend (buy only above H1 EMA50, sell only below) and session."""
    L = L.copy(); S = S.copy()
    if sp.get("htf") == "H1":
        up = C["h1up"]
        L &= (up == 1.0); S &= (up == 0.0)
    if sp.get("sess") == "asia":
        L &= C["asia"]; S &= C["asia"]
    return L, S


# ─── families: each returns (long_mask, short_mask) on closed bars ───────────
def g_bb(C, sp):
    """Bollinger fade: previous close outside the band (20, mult), this close back inside."""
    c = C["c"]; n = 20
    mid = frost.sma(c, n); sd = frost.stdev(c, n)
    up, lo = mid + sp["mult"] * sd, mid - sp["mult"] * sd
    pc, pu, pl = prev(c), prev(up), prev(lo)
    L = (pc < pl) & (c > lo)
    S = (pc > pu) & (c < up)
    return apply_filters(C, L, S, sp)


def g_rsi(C, sp):
    """RSI(n) extremes. trig 'in': RSI crosses into the extreme zone (Connors style, buy the close);
    trig 'out': RSI was in the zone on the previous bar and closes back out of it (hook)."""
    r = frost.rsi(C["c"], sp["n"]); pr = prev(r); lo = sp["lo"]; hi = 100 - lo
    if sp["trig"] == "in":
        L = (r < lo) & (pr >= lo); S = (r > hi) & (pr <= hi)
    else:
        L = (pr < lo) & (r >= lo); S = (pr > hi) & (r <= hi)
    return apply_filters(C, L, S, sp)


_VW = {}


def vwap_bands(C):
    tf = C["tf"]
    if tf in _VW:
        return _VW[tf]
    b = C["b"]
    tp = (b.h.values + b.l.values + b.c.values) / 3; v = np.maximum(b.v.values, 1e-9)
    day = b.tday.values
    grp = np.cumsum(np.r_[True, day[1:] != day[:-1]])
    vv = pd.Series(v).groupby(grp).cumsum().values
    pv = pd.Series(tp * v).groupby(grp).cumsum().values
    p2 = pd.Series(tp * tp * v).groupby(grp).cumsum().values
    vw = pv / vv
    sd = np.sqrt(np.maximum(p2 / vv - vw * vw, 0.0))   # TradingView ta.vwap stdev band
    _VW[tf] = (vw, sd)
    return vw, sd


def g_vwap(C, sp):
    """Session VWAP (17:00 NY anchor) deviation-band fade: previous close outside VWAP +/- m*sd,
    this close back inside. No signals in the first hour after the 18:00 reopen (bands too narrow)."""
    vw, sd = vwap_bands(C); c = C["c"]; m = sp["m"]
    up, lo = vw + m * sd, vw - m * sd
    pc, pu, pl = prev(c), prev(up), prev(lo)
    same = C["tday"] == np.r_[-1, C["tday"][:-1]]
    ok = same & ~((C["ny_min"] >= 17 * 60) & (C["ny_min"] < 19 * 60))
    L = (pc < pl) & (c > lo) & ok
    S = (pc > pu) & (c < up) & ok
    return apply_filters(C, L, S, sp)


def g_kc(C, sp):
    """Keltner fade (TradingView defaults: EMA20 +/- m * ATR10): previous close outside, this close inside."""
    c = C["c"]; mid = frost.ema(c, 20); a = frost.atr(C["b"], 10)
    up, lo = mid + sp["m"] * a, mid - sp["m"] * a
    pc, pu, pl = prev(c), prev(up), prev(lo)
    L = (pc < pl) & (c > lo)
    S = (pc > pu) & (c < up)
    return apply_filters(C, L, S, sp)


def g_stoch(C, sp):
    """Stochastic(14,3,3) extreme on the previous bar + reversal candle on this bar.
    candle 'simple': close > open and close > previous close; 'strong': close > previous high."""
    h, l, c, o = C["h"], C["l"], C["c"], C["o"]
    hh = pd.Series(h).rolling(14).max().values; ll = pd.Series(l).rolling(14).min().values
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(hh > ll, 100 * (c - ll) / (hh - ll), 50.0)
    k = frost.sma(raw, 3); pk = prev(k); thr = sp["thr"]
    if sp["candle"] == "simple":
        bull = (c > o) & (c > prev(c)); bear = (c < o) & (c < prev(c))
    else:
        bull = (c > o) & (c > prev(h)); bear = (c < o) & (c < prev(l))
    L = (pk < thr) & bull
    S = (pk > 100 - thr) & bear
    return apply_filters(C, L, S, sp)


def g_ext(C, sp):
    """Overextension from EMA(n) in ATR14 units on the previous bar, then a reversal-colour candle."""
    c, o = C["c"], C["o"]; e = frost.ema(c, sp["n"]); a = C["atr"]
    dist = (c - e) / a; pd_ = prev(dist)
    L = (pd_ <= -sp["x"]) & (c > o)
    S = (pd_ >= sp["x"]) & (c < o)
    return apply_filters(C, L, S, sp)


def g_round(C, sp):
    """Round-number fade: the bar wicks through the nearest $step level beyond the previous close
    (by at least pen*ATR) and closes back on the original side."""
    h, l, c = C["h"], C["l"], C["c"]; pc = prev(c); st = sp["step"]; pen = sp["pen"] * C["atr"]
    lvl_dn = np.floor(pc / st) * st      # nearest level at/below previous close
    lvl_up = np.ceil(pc / st) * st       # nearest level at/above previous close
    L = (pc > lvl_dn) & (l < lvl_dn - pen) & (c > lvl_dn)
    S = (pc < lvl_up) & (h > lvl_up + pen) & (c < lvl_up)
    return apply_filters(C, L, S, sp)


def g_asia(C, sp):
    """Asian-range fade: range = high/low of bars from 18:00 NY to r_end; afterwards (until t_end)
    a bar that wicks above the range high and closes back below it is a SELL (mirror for BUY)."""
    b = C["b"]; h, l, c = C["h"], C["l"], C["c"]; m = C["ny_min"]; tday = C["tday"]
    # minutes since 18:00 NY on a 0..(24h) clock
    t18 = (m - 18 * 60) % 1440
    r_end = (sp["r_end"] - 18 * 60) % 1440; t_end = (sp["t_end"] - 18 * 60) % 1440
    tf = C["tf"]
    # a bar belongs to the range window if it is fully closed by r_end
    in_rng = (t18 + tf <= r_end)
    in_trd = (t18 >= r_end) & (t18 < t_end)
    df = pd.DataFrame({"d": tday, "h": np.where(in_rng, h, np.nan), "l": np.where(in_rng, l, np.nan)})
    rh = df.groupby("d").h.transform("max").values   # the range is complete before any trade bar
    rl = df.groupby("d").l.transform("min").values
    S = in_trd & (h > rh) & (c < rh)
    L = in_trd & (l < rl) & (c > rl)
    S &= np.isfinite(rh); L &= np.isfinite(rl)
    return apply_filters(C, L, S, sp)


def rma_nan(x, n):
    """frost.rma that starts at the first finite value (for series with a NaN warm-up)."""
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    ok = np.where(np.isfinite(x))[0]
    if len(ok):
        out[ok[0]:] = frost.rma(x[ok[0]:], n)
    return out


_ADX = {}


def adx(C, n=14):
    """Wilder ADX(14,14) as in TradingView ta.dmi / the exlux99 script."""
    if C["tf"] in _ADX:
        return _ADX[C["tf"]]
    h, l, c = C["h"], C["l"], C["c"]
    up = np.r_[0.0, np.diff(h)]; dn = np.r_[0.0, -np.diff(l)]
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    trur = frost.rma(tr, n)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus = 100 * frost.rma(pdm, n) / trur; minus = 100 * frost.rma(mdm, n) / trur
        sm = plus + minus
        dx = np.abs(plus - minus) / np.where(sm == 0, 1, sm)
    out = 100 * rma_nan(dx, n)
    _ADX[C["tf"]] = out
    return out


def g_zscore(C, sp):
    """Scout #10 (n30dyn4m1c/gold-pro-scalper, XAU_Quant_Reversion_TickRobust.mq5, MIT):
    z = (close - SMA20) / StdDev20 on the closed bar, |z| >= 2.2, turn bar (no new lower close for a buy),
    optional ADX(14) <= 22, ATR14 / mean(ATR14, 50) in [0.4, 2.0], cost gates StdDev >= 3x$0.30 and
    distance to the SMA >= 4x$0.30 + spread. Source session 10-20 broker time = 03:00-12:59 New York."""
    c = C["c"]; ma = frost.sma(c, 20); sd = frost.stdev(c, 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (c - ma) / sd
        ratio = C["atr"] / frost.sma(C["atr"], 50)
    pc = prev(c)
    ok = (ratio >= 0.4) & (ratio <= 2.0) & (sd >= 0.9) & (np.abs(ma - c) >= 1.2 + frost.SPREAD)
    L = (z <= -sp["z"]) & (c >= pc) & ok
    S = (z >= sp["z"]) & (c <= pc) & ok
    if sp["adx"]:
        a = adx(C); L &= a <= sp["adx"]; S &= a <= sp["adx"]
    if sp["sess"] == "src":
        m = C["ny_min"]; w = (m >= 3 * 60) & (m < 13 * 60); L &= w; S &= w
    return apply_filters(C, L, S, dict(htf=sp["htf"]))


def g_bbrsi(C, sp):
    """Scout #12 (hasnocool/tradingview-pine-scripts, exlux99 'Bollinger Bands, RSI and ADX Trading System',
    MPL-2.0): BB(60,2), RSI(20) crossover 35 / crossunder 65, ADX(14) < 32.
    band 'src' = the source as coded (long: close < upper band; short: close > upper band);
    band 'mid' = long only below the BB basis, short only above it."""
    c = C["c"]; basis = frost.sma(c, 60); up = basis + 2.0 * frost.stdev(c, 60)
    r = frost.rsi(c, 20); pr = prev(r)
    co = (r > 35) & (pr <= 35); cu = (r < 65) & (pr >= 65)
    if sp["band"] == "src":
        L = (c < up) & co; S = (c > up) & cu
    else:
        L = (c < basis) & co; S = (c > basis) & cu
    if sp["adx"]:
        a = adx(C); L &= a < sp["adx"]; S &= a < sp["adx"]
    return apply_filters(C, L, S, sp)


def g_vwapz(C, sp):
    """Scout #13 (nopponkaeward-max/EA_ATR_news, StatDayTrade.pine): z = (close - daily VWAP) / stdev(close, 20);
    BUY when z <= -zt on a bullish candle, SELL when z >= zt on a bearish candle."""
    vw, _ = vwap_bands(C); c, o = C["c"], C["o"]; sd = frost.stdev(c, 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (c - vw) / sd
    L = (z <= -sp["z"]) & (c > o)
    S = (z >= sp["z"]) & (c < o)
    return apply_filters(C, L, S, sp)


def grid(**kw):
    keys = list(kw)
    return [dict(zip(keys, v)) for v in itertools.product(*[kw[k] for k in keys])]


FAMILIES = {
    "BB": (g_bb, grid(tf=[5, 15], mult=[2.0, 2.5], htf=["none", "H1"], sess=["all", "asia"])
           + grid(tf=[1], mult=[2.0, 2.5], htf=["none", "H1"], sess=["all"])),
    "RSI": (g_rsi, [dict(tf=tf, n=n, lo=lo, trig=tr, htf=f) for tf in (5, 15)
                    for (n, lo) in ((2, 10), (3, 15), (7, 25)) for tr in ("in", "out") for f in ("none", "H1")]),
    "VWAP": (g_vwap, grid(tf=[5, 15], m=[1.5, 2.0, 2.5], htf=["none", "H1"], sess=["all", "asia"])),
    "KC": (g_kc, grid(tf=[5, 15], m=[1.5, 2.0, 2.5], htf=["none", "H1"], sess=["all", "asia"])),
    "STOCH": (g_stoch, grid(tf=[5, 15], thr=[10, 20], candle=["simple", "strong"], htf=["none", "H1"])),
    "EXT": (g_ext, [dict(tf=tf, n=n, x=x, htf=f) for tf in (1, 5, 15)
                    for (n, x) in ((20, 2.0), (20, 3.0), (50, 3.0), (50, 4.0)) for f in ("none", "H1")]),
    "ROUND": (g_round, grid(tf=[1, 5, 15], step=[5.0, 10.0], pen=[0.0, 0.25], htf=["none", "H1"])),
    "ASIA": (g_asia, grid(tf=[5, 15], r_end=[20 * 60, 21 * 60, 22 * 60], t_end=[1 * 60, 2 * 60 + 30],
                          htf=["none", "H1"])),
    # scout-report techniques (#10, #12, #13); #20 round numbers is the ROUND family above
    "ZSCORE": (g_zscore, grid(tf=[1, 5], z=[2.2], adx=[22, 0], sess=["all", "src"], htf=["none", "H1"])),
    "BBRSI": (g_bbrsi, grid(tf=[1, 5, 15], band=["src", "mid"], adx=[32, 0], htf=["none", "H1"])),
    "VWAPZ": (g_vwapz, grid(tf=[1, 5, 15], z=[2.0, 3.0, 4.0], htf=["none", "H1"])),
}
# extra stop rules tried in stage B1 (the source's own stop), per family
EXTRA_K = {"ZSCORE": ["src"]}   # 'src' = max($8, 2.5 x ATR14), n30dyn4m1c


def stop_dist(C, k):
    if k == "src":
        return np.maximum(8.0, 2.5 * C["atr"])
    return k * C["atr"]


# ─── signal building and evaluation ──────────────────────────────────────────
def signals(fam, sp, ex, period=None):
    """Return (sig, bar_idx, C) for a family / params / exit. period restricts signal bars."""
    g = FAMILIES[fam][0]
    C = ctx(sp["tf"])
    L, S = g(C, sp)
    L = np.nan_to_num(L).astype(bool); S = np.nan_to_num(S).astype(bool)
    both = L & S
    L &= ~both; S &= ~both
    sd = stop_dist(C, ex["k"])
    m = (L | S) & np.isfinite(sd) & (sd > 0)
    if period is not None:
        m &= frost.in_period(C["b"], period).values
    idx = np.where(m)[0]
    d = np.where(L[idx], 1, -1)
    sig = frost.levels(C["b"], idx, d, sd[idx], ex["t1"], ex["t2"])
    return sig, idx, C


_DAYS = {}


def pdays(name):
    if name not in _DAYS:
        a, z = frost.PERIODS[name]
        _DAYS[name] = frost.trading_days(frost._ts(a), frost._ts(z))
    return _DAYS[name]


def disc_eval(fam, sp, ex):
    sig, idx, C = signals(fam, sp, ex, "DISC")
    t = frost.simulate(sig, be=ex["be"], max_hold=ex["mh"])
    t = t[frost.in_period(t, "DISC")]
    return frost.stats(t, "DISC", pdays("DISC"))


def key(sp, ex):
    return tuple(sorted(sp.items())) + tuple(sorted(ex.items()))


def better(a, b):
    """a better than b? qualifying (>= MIN_PER_DAY) first, then avgR."""
    if b is None:
        return True
    qa = a["n"] > 0 and a["per_day"] >= MIN_PER_DAY; qb = b["n"] > 0 and b["per_day"] >= MIN_PER_DAY
    if qa != qb:
        return qa
    return a.get("avgR", -9) > b.get("avgR", -9)


def search(fam, verbose=True):
    """Staged DISC search. Returns (best_sp, best_ex, best_stats, n_combos, log)."""
    seen = {}; log = []

    def run(sp, ex, stage):
        kk = key(sp, ex)
        if kk not in seen:
            st = disc_eval(fam, sp, ex)
            seen[kk] = st
            log.append((stage, sp, ex, st))
            if verbose:
                print(f"  [{stage}] {fmt_sp(sp)} | {fmt_ex(ex)} -> n={st['n']} pd={st.get('per_day')} "
                      f"win={st.get('win')} avgR={st.get('avgR')} se={st.get('se')}")
        return seen[kk]

    best = None; bsp = None; bex = None
    for sp in FAMILIES[fam][1]:
        st = run(sp, dict(BASE_EXIT), "A")
        if better(st, best):
            best, bsp, bex = st, sp, dict(BASE_EXIT)
    for k in K_GRID + EXTRA_K.get(fam, []):
        ex = dict(bex, k=k); st = run(bsp, ex, "B1")
        if better(st, best):
            best, bex = st, ex
    cur = dict(bex)
    for (t1, t2) in PAIRS:
        for be in (False, True):
            ex = dict(cur, t1=t1, t2=t2, be=be); st = run(bsp, ex, "B2")
            if better(st, best):
                best, bex = st, ex
    cur = dict(bex)
    for mh in MH_GRID:
        ex = dict(cur, mh=mh); st = run(bsp, ex, "B3")
        if better(st, best):
            best, bex = st, ex
    return bsp, bex, best, len(seen), log


def fmt_sp(sp):
    return ",".join(f"{k}={v}" for k, v in sp.items())


def fmt_ex(ex):
    ks = "max($8,2.5ATR)" if ex["k"] == "src" else f"{ex['k']}ATR"
    return f"stop={ks} TP1={ex['t1']} TP2={ex['t2']} be={ex['be']} mh={ex['mh']}"


def full_eval(fam, sp, ex, rc_runs=20):
    """Frozen variant on all periods + random control on VAL + stress test on VAL."""
    sig, idx, C = signals(fam, sp, ex)
    t = frost.simulate(sig, be=ex["be"], max_hold=ex["mh"])
    rows = {r["label"]: r for r in frost.by_period(t)}
    # bar index of every VAL trade (the signal bars actually traded)
    tv = t[frost.in_period(t, "VAL")]
    bidx = np.searchsorted(C["b"].end.values, tv.i.values)
    sdv = stop_dist(C, ex["k"])
    rc = frost.random_control(bidx, C["b"], lambda b, ii: sdv[ii], ex["t1"], ex["t2"],
                              n_runs=rc_runs, be=ex["be"], max_hold=ex["mh"])
    rc = np.array([x for x in rc if np.isfinite(x)])
    rcm = float(np.median(rc)) if len(rc) else float("nan")
    rc5, rc95 = (float(np.percentile(rc, 5)), float(np.percentile(rc, 95))) if len(rc) else (np.nan, np.nan)
    ts = frost.simulate(sig, spread=0.45, slip=0.05, be=ex["be"], max_hold=ex["mh"])
    ts = ts[frost.in_period(ts, "VAL")]
    stress = frost.stats(ts, "VAL-stress", pdays("VAL"))
    return dict(rows=rows, rc_med=rcm, rc5=rc5, rc95=rc95, stress=stress, trades=t, sig=sig)


def y2025_available():
    return os.path.exists(os.path.join(frost.DATA, "XAUUSD_2025_m1.csv.gz"))


def verdict(ev):
    v = ev["rows"]["VAL"]; y = ev["rows"]["Y2025"]
    if v["n"] == 0:
        return False, ["no VAL trades"]
    fails = []
    ratio = v["avgR"] / v["se"] if v["se"] and v["se"] > 0 else 0
    if not (v["avgR"] > 0 and ratio >= 1.0):
        fails.append(f"VAL avgR/se={ratio:.2f}")
    if y2025_available():
        if not (y["n"] > 0 and y["avgR"] > 0):
            fails.append("Y2025 avgR<=0")
    if not (v["avgR"] - ev["rc_med"] >= 0.05):
        fails.append(f"VAL-rc={v['avgR'] - ev['rc_med']:.3f}")
    if not (ev["stress"].get("avgR", -1) >= 0):
        fails.append("stress<0")
    if not (v["per_day"] >= MIN_PER_DAY):
        fails.append("per_day<0.5")
    return len(fails) == 0, fails


# ─── frozen best technique for the lead ──────────────────────────────────────
# Frozen from the DISC search (see RESULTS.md); main() checks that the search reproduces it.
# No family passed, so this is the highest-VAL-avgR family: ROUND ($5 round-number wick-and-reject, M15).
BEST_FAM = "ROUND"
BEST_SP = dict(tf=15, step=5.0, pen=0.25, htf="H1")
BEST_EX = dict(k=2.0, t1=1.0, t2=2.0, be=False, mh=240)
BEST_SIM = dict(be=False, max_hold=240)


def best_signals():
    """sig DataFrame (all dates) for Team B's single best technique. Simulate with BEST_SIM."""
    sig, _, _ = signals(BEST_FAM, BEST_SP, BEST_EX)
    sig.attrs.update(BEST_SIM)
    return sig


def main(fams):
    print("coverage", frost.coverage(), "| Y2025 file:", y2025_available())
    print("trading days", {p: pdays(p) for p in frost.PERIODS})
    summary = []
    for fam in fams:
        t0 = time.time()
        print(f"\n=== {fam} ===")
        sp, ex, st, n, log = search(fam)
        print(f"  BEST DISC: {fmt_sp(sp)} | {fmt_ex(ex)} | combos={n} | avgR={st['avgR']} n={st['n']} pd={st['per_day']}")
        ev = full_eval(fam, sp, ex)
        print(frost.fmt([ev["rows"][p] for p in frost.PERIODS] + [ev["stress"]]))
        print(f"  random control VAL: median={ev['rc_med']:.4f}  5-95%=[{ev['rc5']:.4f}, {ev['rc95']:.4f}]")
        ok, fails = verdict(ev)
        print("  PASS" if ok else "  FAIL: " + "; ".join(fails))
        print("  monthly:", " ".join(f"{m}:{r['count']}/{r['mean']:+.3f}" for m, r in frost.monthly(ev["trades"]).iterrows()))
        print(f"  ({time.time() - t0:.0f}s)")
        summary.append((fam, sp, ex, n, ev, ok, fails))
    print("\n=== SUMMARY TABLE (markdown) ===")
    print("| family | best params (DISC-frozen) | combos | DISC avgR/n | VAL n | per_day | win% | TP1% | TP2% "
          "| VAL avgR±se | PF | Y2025 avgR (n) | HOLD avgR (n) | random median [5-95%] | stress avgR | PASS/FAIL |")
    print("|" + "---|" * 16)
    for fam, sp, ex, n, ev, ok, fails in summary:
        R = ev["rows"]; d, v, y, h = R["DISC"], R["VAL"], R["Y2025"], R["HOLD"]
        yv = f"{y.get('avgR')} ({y['n']})" if y2025_available() else f"n/a, file missing ({y.get('avgR')}, {y['n']})"
        print(f"| {fam} | {fmt_sp(sp)}; {fmt_ex(ex)} | {n} | {d.get('avgR')}/{d['n']} | {v['n']} | {v.get('per_day')} | "
              f"{v.get('win')} | {v.get('tp1')} | {v.get('tp2')} | {v.get('avgR')}±{v.get('se')} | {v.get('pf')} | "
              f"{yv} | {h.get('avgR')} ({h['n']}) | {ev['rc_med']:.4f} [{ev['rc5']:.4f}, {ev['rc95']:.4f}] | "
              f"{ev['stress'].get('avgR')} | {'PASS' if ok else 'FAIL: ' + '; '.join(fails)} |")
    if BEST_FAM is not None:
        chk = [s for s in summary if s[0] == BEST_FAM]
        if chk:
            print("\nbest_signals() frozen params reproduced by search:", chk[0][1] == BEST_SP and chk[0][2] == BEST_EX)
    return summary


if __name__ == "__main__":
    fams = [a for a in sys.argv[1:] if a in FAMILIES] or list(FAMILIES)
    main(fams)
