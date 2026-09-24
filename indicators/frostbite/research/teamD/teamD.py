"""Frostbite research, Team D: price action and smart-money concepts (SMC) on M1-M15 for XAUUSD.

Run from research/:   python teamD/teamD.py          (full protocol: DISC search, then frozen VAL/Y2025/HOLD)
                      python teamD/teamD.py disc     (DISC search only, for development)

Families (all long/short mirrored, signals on CLOSED bars, pivots confirmed k bars later):
  SESS_SWEEP  sweep of Asian H/L (18:00-03:00 NY), London H/L (03:00-08:00 NY) or PDH/PDL, close back inside
              (source: PineGen-AI "ICT Daily Liquidity Sweep", github.com/PineGen-AI/ICT-Daily-Liquidity-Sweep-PineGen-AI-)
  SWING_SWEEP sweep of the last confirmed swing high/low, close back inside (+ optional MSS-lite confirmation)
  CHOCH       sweep of the last swing low, then a close above the last swing high (change of character)
  FVG         fair value gap retest in the direction of the displacement
              (FVG >= x*ATR idea from BAKOME-Hub "Ultimate ICT Gold Scalper", github.com/BAKOME-Hub/BAKOMEGoldScalper)
  OB          order-block retest after a break of structure
  BOS_PB      break of structure, then a Fibonacci pullback entry with an H1 EMA50 trend filter
  PA_LEVEL    engulfing / pin bar at session VWAP, $10 round numbers or PDH/PDL
  EQ_SWEEP    sweep of equal highs/lows (two most recent swing points within tol*ATR)
  SILVER_BULLET  ICT Silver Bullet: FVG formed and retested inside 03-04, 10-11, 14-15 New York
              (Silver Bullet windows from BAKOME-Hub "Ultimate ICT Gold Scalper")

Stops are structural (beyond the sweep wick / zone / pattern low, plus 0.1 ATR) and clipped to [0.5, 2.0] ATR of
the signal timeframe. HTF trend = H1 close vs H1 EMA50, last COMPLETED H1 bar (frost.htf_on_ltf).
"""
import os, sys, math
import numpy as np
import pandas as pd
import numba as nb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import frost  # noqa: E402

BUF, FLOOR, CAP = 0.10, 0.50, 2.00          # stop buffer, floor and cap in ATR(14) of the signal timeframe
DEFAULT_EXIT = (1.0, 2.0, False, 120)       # stage-A exits: TP1 R, TP2 R, be, max_hold
EXIT_PAIRS = [(0.5, 1.5), (0.75, 2.0), (1.0, 2.0), (1.0, 3.0), (1.5, 3.0)]
WINDOWS = {"all": [(0, 1440)], "day": [(120, 960)], "lnny": [(120, 720)], "kz": [(120, 300), (420, 660)],
           "sb": [(180, 240), (600, 660), (840, 900)]}   # ICT Silver Bullet hours, New York clock
NAN = np.nan


# ─── context per timeframe ───────────────────────────────────────────────────
_CTX = {}


def ctx(tf):
    if tf in _CTX:
        return _CTX[tf]
    b = frost.bars(tf)
    c = {"b": b, "o": b.o.values, "h": b.h.values, "l": b.l.values, "c": b.c.values, "atr": frost.atr(b, 14)}
    # H1 trend as of the last completed H1 bar
    h1 = frost.bars(60)
    e50 = frost.ema(h1.c.values, 50)
    trend = np.where(np.isnan(e50), 0, np.sign(h1.c.values - e50))
    c["htf"] = frost.htf_on_ltf(b, h1, trend)
    c["vwap"] = frost.vwap_session(b)
    # previous trading day high/low (complete before the current trading day starts)
    td = b.tday.values
    g = pd.DataFrame({"td": td, "h": b.h.values, "l": b.l.values}).groupby("td").agg(h=("h", "max"), l=("l", "min"))
    ph_map = dict(zip(g.index.values, np.r_[NAN, g.h.values[:-1]]))
    pl_map = dict(zip(g.index.values, np.r_[NAN, g.l.values[:-1]]))
    c["pdh"] = np.array([ph_map[x] for x in td]); c["pdl"] = np.array([pl_map[x] for x in td])
    # session ranges: Asian 18:00-03:00 NY (locked 03:00-17:00), London 03:00-08:00 NY (locked 08:00-17:00)
    nm = b.ny_min.values
    c["ash"], c["asl"] = _session_range(td, nm, b.h.values, b.l.values, tf, lambda m: (m >= 1080) | (m < 180), 180)
    c["lnh"], c["lnl"] = _session_range(td, nm, b.h.values, b.l.values, tf, lambda m: (m >= 180) & (m < 480), 480)
    # 00:00-08:00 UTC in winter = 19:00-03:00 New York (PineGen-AI's Asian box, on the New York clock)
    c["ash19"], c["asl19"] = _session_range(td, nm, b.h.values, b.l.values, tf, lambda m: (m >= 1140) | (m < 180), 180)
    _CTX[tf] = c
    return c


def _session_range(td, nm, h, l, tf, in_sess, lock_min):
    m = in_sess(nm)
    df = pd.DataFrame({"td": td, "h": np.where(m, h, NAN), "l": np.where(m, l, NAN)})
    hh = df.groupby("td").h.transform("max").values
    ll = df.groupby("td").l.transform("min").values
    locked = (nm >= lock_min) & (nm < 17 * 60)
    return np.where(locked, hh, NAN), np.where(locked, ll, NAN)


def pivots(tf, k):
    key = ("piv", k)
    c = ctx(tf)
    if key not in c:
        c[key] = _pivots(c["h"], c["l"], k)
    return c[key]


def window_ok(tf, win):
    nm = ctx(tf)["b"].ny_min.values
    ok = np.zeros(len(nm), bool)
    for a, z in WINDOWS[win]:
        ok |= (nm >= a) & (nm < z)
    return ok


def shift1(x):
    return np.r_[x[:1] * NAN, x[:-1]]


# ─── numba kernels (long side; shorts run on negated prices) ─────────────────
@nb.njit(cache=True)
def _pivots(h, l, k):
    """Last and previous confirmed pivot high/low as known at each bar close (pivot j confirmed at bar j+k)."""
    n = len(h)
    ph = np.full(n, np.nan); phi = np.full(n, -1, np.int64); ph2 = np.full(n, np.nan)
    pl = np.full(n, np.nan); pli = np.full(n, -1, np.int64); pl2 = np.full(n, np.nan)
    aph = np.nan; aphi = -1; aph2 = np.nan; apl = np.nan; apli = -1; apl2 = np.nan
    for i in range(n):
        j = i - k
        if j - k >= 0:
            isH = True; isL = True
            for m in range(j - k, j + k + 1):
                if m < j:
                    if h[m] > h[j]: isH = False
                    if l[m] < l[j]: isL = False
                elif m > j:
                    if h[m] >= h[j]: isH = False
                    if l[m] <= l[j]: isL = False
            if isH:
                aph2 = aph; aph = h[j]; aphi = j
            if isL:
                apl2 = apl; apl = l[j]; apli = j
        ph[i] = aph; phi[i] = aphi; ph2[i] = aph2; pl[i] = apl; pli[i] = apli; pl2[i] = apl2
    return ph, phi, ph2, pl, pli, pl2


@nb.njit(cache=True)
def _sweep_long(h, l, c, lvl, pre, m_rec, conf, conf_n, chl, ok):
    """Sweep of a level below price: low trades below lvl, then a close back above it within m_rec bars.
    conf 0: signal on the reclaim close. conf 1: after the reclaim, a close above the reclaim bar's high
    within conf_n bars (MSS-lite). conf 2: CHoCH, a close above chl (last swing high at the sweep) within
    conf_n bars of the sweep. Returns signal flags and the sweep extreme (lowest low since the sweep)."""
    n = len(c)
    sig = np.zeros(n, np.int8); ext = np.full(n, np.nan)
    st = 0; cur = np.nan; p = -1; e = 0.0; r = -1; ref = 0.0; Lsw = 0.0; ch = np.nan
    for i in range(1, n):
        if st == 0 or st == 2:
            L = lvl[i]
            if np.isnan(L):
                st = 0; cur = np.nan
                continue
            if np.isnan(cur) or L != cur:
                cur = L; st = 0
            if st == 2:
                continue
            if l[i] < L and c[i - 1] > L and pre[i]:
                st = 1; p = i; e = l[i]; Lsw = L; ch = chl[i]
            else:
                continue
        else:
            if l[i] < e:
                e = l[i]
        if st == 1:
            if c[i] > Lsw:
                if conf == 0:
                    if ok[i]:
                        sig[i] = 1; ext[i] = e
                    st = 2
                elif conf == 1:
                    st = 3; r = i; ref = h[i]
                else:
                    if np.isnan(ch):
                        st = 2
                    elif c[i] > ch:
                        if ok[i]:
                            sig[i] = 1; ext[i] = e
                        st = 2
                    else:
                        st = 3
            elif i - p >= m_rec:
                st = 2
        elif st == 3:
            if conf == 1:
                if c[i] > ref:
                    if ok[i]:
                        sig[i] = 1; ext[i] = e
                    st = 2
                elif c[i] < Lsw or i - r >= conf_n:
                    st = 2
            else:
                if c[i] > ch:
                    if ok[i]:
                        sig[i] = 1; ext[i] = e
                    st = 2
                elif i - p >= conf_n:
                    st = 2
        if st == 2:
            cur = Lsw
    return sig, ext


@nb.njit(cache=True)
def _fvg_long(o, h, l, c, atr, gmin, maxage, rej, stopmode, ok, okf):
    """Latest bullish FVG (low[i] > high[i-2], gap >= gmin*ATR, bullish middle candle, formed on a bar where
    okf is true); signal on the first later bar that trades into the gap and closes above its bottom
    (bullish close if rej)."""
    n = len(c)
    sig = np.zeros(n, np.int8); stp = np.full(n, np.nan)
    act = False; top = 0.0; bot = 0.0; c1 = 0.0; t0 = -1
    for i in range(2, n):
        if act:
            if i - t0 > maxage or c[i] < bot:
                act = False
            elif l[i] <= top and c[i] > bot and (rej == 0 or c[i] > o[i]) and ok[i]:
                sig[i] = 1; stp[i] = bot if stopmode == 0 else c1
                act = False
        if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= gmin * atr[i] and c[i - 1] > o[i - 1] and okf[i]:
            act = True; top = l[i]; bot = h[i - 2]; c1 = l[i - 2]; t0 = i
    return sig, stp


@nb.njit(cache=True)
def _ob_long(o, h, l, c, php, phip, maxage, body, rej, ok):
    """Bullish BOS = first close above the last confirmed swing high. Order block = last bearish candle at or
    up to 5 bars before the leg low. Signal on the first later bar that trades into the OB and closes above it."""
    n = len(c)
    sig = np.zeros(n, np.int8); stp = np.full(n, np.nan)
    act = False; top = 0.0; bot = 0.0; t0 = -1; broken = np.nan
    for i in range(1, n):
        if act:
            if i - t0 > maxage or c[i] < bot:
                act = False
            elif l[i] <= top and c[i] > bot and (rej == 0 or c[i] > o[i]) and ok[i]:
                sig[i] = 1; stp[i] = bot
                act = False
        P = php[i]
        if not np.isnan(P) and P != broken and c[i] > P and c[i - 1] <= P:
            broken = P
            j0 = phip[i]
            jl = j0
            for m in range(j0, i + 1):
                if l[m] < l[jl]:
                    jl = m
            ob = -1
            lo_k = max(j0, jl - 5)
            for m in range(jl, lo_k - 1, -1):
                if c[m] < o[m]:
                    ob = m
                    break
            if ob < 0:
                ob = jl
            top = max(o[ob], c[ob]) if body else h[ob]
            bot = l[ob]
            if top < c[i]:
                act = True; t0 = i
    return sig, stp


@nb.njit(cache=True)
def _bospb_long(o, h, l, c, php, phip, fib, maxage, stopmode, ok):
    """Bullish BOS, then a pullback to fib of the impulse leg (leg low to highest high since the BOS) and a
    bullish close. Stop: pullback low (stopmode 0) or leg low (stopmode 1)."""
    n = len(c)
    sig = np.zeros(n, np.int8); stp = np.full(n, np.nan)
    act = False; lo = 0.0; hi = 0.0; t0 = -1; broken = np.nan
    for i in range(1, n):
        if act:
            lv = hi - fib * (hi - lo)
            if i - t0 > maxage or c[i] < lo:
                act = False
            elif l[i] <= lv and c[i] > o[i] and ok[i]:
                sig[i] = 1
                stp[i] = min(l[i], l[i - 1]) if stopmode == 0 else lo
                act = False
            if h[i] > hi:
                hi = h[i]
        P = php[i]
        if not np.isnan(P) and P != broken and c[i] > P and c[i - 1] <= P:
            broken = P
            j0 = phip[i]
            lo = l[j0]
            for m in range(j0, i + 1):
                if l[m] < lo:
                    lo = l[m]
            hi = h[i]; t0 = i; act = True
    return sig, stp


@nb.njit(cache=True)
def _pa_long(o, h, l, c, atr, lv, use_round, tol, pat, ok):
    """Bullish engulfing (pat 0), pin bar (pat 1) or either (pat 2) whose low touched a support level
    (rows of lv, or the $10 round number below the close) within tol*ATR and closed above it."""
    n = len(c); K = lv.shape[0]
    sig = np.zeros(n, np.int8); stp = np.full(n, np.nan)
    for i in range(1, n):
        if not ok[i]:
            continue
        eng = c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]
        rg = h[i] - l[i]; bd = abs(c[i] - o[i]); lw = min(o[i], c[i]) - l[i]
        pin = rg >= 0.3 * atr[i] and lw >= 2.0 * bd and lw >= 0.6 * rg
        if pat == 0:
            cond = eng
        elif pat == 1:
            cond = pin
        else:
            cond = eng or pin
        if not cond:
            continue
        plow = min(l[i], l[i - 1]) if (eng and pat != 1) else l[i]
        hit = False
        for k in range(K):
            L = lv[k, i]
            if not np.isnan(L) and plow <= L + tol * atr[i] and c[i] > L:
                hit = True
        if use_round:
            L = math.floor(c[i] / 10.0) * 10.0
            if plow <= L + tol * atr[i] and c[i] > L:
                hit = True
        if hit:
            sig[i] = 1; stp[i] = plow
    return sig, stp


@nb.njit(cache=True)
def _pd_break_long(o, h, l, c, lvl, ok):
    """AhadRasheed/gold-strategy (scout #16), long side: price trades below the previous-day low, a green
    reversal candle closes still below it, then a later bar CLOSES above that candle's high (the source uses an
    intrabar stop entry; a closed-bar indicator needs the close). Stop = lowest low since the level was taken.
    The setup is cancelled if a bar closes back above the level without breaking the reversal high."""
    n = len(c)
    sig = np.zeros(n, np.int8); stp = np.full(n, np.nan)
    st = 0; ext = 0.0; rh = 0.0; cur = np.nan
    for i in range(1, n):
        L = lvl[i]
        if np.isnan(L):
            st = 0; cur = np.nan
            continue
        if np.isnan(cur) or L != cur:
            cur = L; st = 0
        if st == 0:
            if l[i] < L:
                st = 1; ext = l[i]
            continue
        if l[i] < ext:
            ext = l[i]
        if st == 1:
            if c[i] > o[i] and c[i] < L:
                st = 2; rh = h[i]
        elif st == 2:
            if c[i] > rh:
                if ok[i]:
                    sig[i] = 1; stp[i] = ext
                st = 0
            elif c[i] >= L and h[i] < rh:
                st = 0
    return sig, stp


@nb.njit(cache=True)
def _sweep_fvg_long(o, h, l, c, atr, ev, evx, fvg_n, disp, gmin, tap_n, okf, okt, blk, once):
    """Sweep, then displacement FVG, then retest (scout #17 Silver Bullet and #18 SMC sweep + FVG), long side.
    ev/evx: sweep events (a low taken and the bar closing back inside) and the sweep-bar low. Within fvg_n bars
    a bullish FVG must form (gap >= gmin*ATR, bullish middle candle with range >= disp*ATR, on a bar where okf);
    within tap_n bars after it, a bar must trade into the gap and close above its far edge (on a bar where okt).
    Cancelled on a close below the sweep low. blk: block id (state resets when it changes, -1 = inactive);
    once: at most one signal per block. Stop = sweep low."""
    n = len(c)
    sig = np.zeros(n, np.int8); stp = np.full(n, np.nan)
    st = 0; ext = 0.0; ts = -1; near = 0.0; far = 0.0; tfv = -1; b0 = -2
    for i in range(2, n):
        if blk[i] != b0:
            st = 0; b0 = blk[i]
        if blk[i] < 0 or st == 3:
            continue
        if st == 2:
            if c[i] < ext or i - tfv > tap_n:
                st = 0
            elif l[i] <= near and c[i] > far and okt[i]:
                sig[i] = 1; stp[i] = ext
                st = 3 if once else 0
                continue
        elif st == 1:
            if c[i] < ext or i - ts > fvg_n:
                st = 0
            elif (l[i] > h[i - 2] and (l[i] - h[i - 2]) >= gmin * atr[i] and c[i - 1] > o[i - 1]
                  and (h[i - 1] - l[i - 1]) >= disp * atr[i] and okf[i]):
                st = 2; near = l[i]; far = h[i - 2]; tfv = i
        if ev[i] and st < 2:
            st = 1; ext = evx[i]; ts = i
    return sig, stp


# ─── signal builders: return (idx, d, stop_dist) on the tf bars ──────────────
def _finish(tf, sl_long, stp_long, sl_short, stp_short):
    """Combine long/short flags with structural stop prices into (idx, d, stop_dist) with ATR floor/cap."""
    c = ctx(tf); a = c["atr"]; cl = c["c"]
    both = (sl_long > 0) & (sl_short > 0)
    L = np.where((sl_long > 0) & ~both)[0]; S = np.where((sl_short > 0) & ~both)[0]
    sdL = cl[L] - (stp_long[L] - BUF * a[L]); sdS = (stp_short[S] + BUF * a[S]) - cl[S]
    idx = np.r_[L, S]; d = np.r_[np.ones(len(L), int), -np.ones(len(S), int)]; sd = np.r_[sdL, sdS]
    sd = np.clip(sd, FLOOR * a[idx], CAP * a[idx])
    good = np.isfinite(sd) & (sd > 0)
    idx, d, sd = idx[good], d[good], sd[good]
    o = np.argsort(idx, kind="stable")
    return idx[o], d[o], sd[o]


def _htf_masks(tf, p, win):
    c = ctx(tf); ok = window_ok(tf, win)
    if p.get("htf", 0):
        return ok & (c["htf"] > 0), ok & (c["htf"] < 0)
    return ok, ok


def _run_sweep(tf, lv_long, lv_short, p, chl=None, chs=None, preL=None, preS=None, win="day"):
    c = ctx(tf); okL, okS = _htf_masks(tf, p, win)
    n = len(c["c"])
    preL = np.ones(n, bool) if preL is None else preL
    preS = np.ones(n, bool) if preS is None else preS
    chl = np.full(n, NAN) if chl is None else chl
    chs = np.full(n, NAN) if chs is None else chs
    sigL = np.zeros(n, np.int8); extL = np.full(n, NAN); sigS = np.zeros(n, np.int8); extS = np.full(n, NAN)
    for lv in lv_long:
        s, e = _sweep_long(c["h"], c["l"], c["c"], lv, preL, p.get("m_rec", 3), p["conf"], p.get("conf_n", 10), chl, okL)
        new = (s > 0) & (sigL == 0); sigL[new] = 1; extL[new] = e[new]
    for lv in lv_short:
        s, e = _sweep_long(-c["l"], -c["h"], -c["c"], -lv, preS, p.get("m_rec", 3), p["conf"], p.get("conf_n", 10), -chs, okS)
        new = (s > 0) & (sigS == 0); sigS[new] = 1; extS[new] = -e[new]
    return _finish(tf, sigL, extL, sigS, extS)


def sig_sess_sweep(p):
    tf = p["tf"]; c = ctx(tf)
    return _run_sweep(tf, [c["asl"], c["lnl"], c["pdl"]], [c["ash"], c["lnh"], c["pdh"]], p, win=p.get("win", "lnny"))


def sig_swing_sweep(p):
    tf = p["tf"]
    ph, phi, ph2, pl, pli, pl2 = pivots(tf, p["k"])
    return _run_sweep(tf, [shift1(pl)], [shift1(ph)], p, win=p.get("win", "day"))


def sig_choch(p):
    tf = p["tf"]
    ph, phi, ph2, pl, pli, pl2 = pivots(tf, p["k"])
    php, ph2p, plp, pl2p = shift1(ph), shift1(ph2), shift1(pl), shift1(pl2)
    n = len(ph)
    if p.get("need_trend", 0):   # prior structure against the trade: lower high before a long, higher low before a short
        preL = php < ph2p; preS = plp > pl2p
    else:
        preL = preS = np.ones(n, bool)
    q = dict(p, conf=2, m_rec=p.get("conf_n", 20), conf_n=p.get("conf_n", 20))
    return _run_sweep(tf, [plp], [php], q, chl=php, chs=plp, preL=preL, preS=preS, win=p.get("win", "day"))


def sig_eq_sweep(p):
    tf = p["tf"]; c = ctx(tf); a = c["atr"]
    ph, phi, ph2, pl, pli, pl2 = pivots(tf, p["k"])
    eql = np.where(np.abs(pl - pl2) <= p["tol"] * a, np.minimum(pl, pl2), NAN)
    eqh = np.where(np.abs(ph - ph2) <= p["tol"] * a, np.maximum(ph, ph2), NAN)
    return _run_sweep(tf, [shift1(eql)], [shift1(eqh)], p, win=p.get("win", "day"))


def sig_fvg(p):
    tf = p["tf"]; c = ctx(tf); win = p.get("win", "day"); okL, okS = _htf_masks(tf, p, win)
    okf = window_ok(tf, win) if p.get("form_in_win", 0) else np.ones(len(c["c"]), bool)
    sL, pL = _fvg_long(c["o"], c["h"], c["l"], c["c"], c["atr"], p["gmin"], p.get("maxage", 30), 1, p["stop"], okL, okf)
    sS, pS = _fvg_long(-c["o"], -c["l"], -c["h"], -c["c"], c["atr"], p["gmin"], p.get("maxage", 30), 1, p["stop"], okS, okf)
    return _finish(tf, sL, pL, sS, -pS)


def sig_silver_bullet(p):
    """ICT Silver Bullet: FVG formed and retested inside 03-04, 10-11 or 14-15 New York."""
    return sig_fvg(dict(p, win="sb", form_in_win=1, stop=0, maxage=p.get("maxage", 12)))


def sig_ob(p):
    tf = p["tf"]; c = ctx(tf); okL, okS = _htf_masks(tf, p, p.get("win", "day"))
    ph, phi, ph2, pl, pli, pl2 = pivots(tf, p["k"])
    sL, pL = _ob_long(c["o"], c["h"], c["l"], c["c"], shift1(ph), np.r_[-1, phi[:-1]], p.get("maxage", 30), p["body"], 1, okL)
    sS, pS = _ob_long(-c["o"], -c["l"], -c["h"], -c["c"], -shift1(pl), np.r_[-1, pli[:-1]], p.get("maxage", 30), p["body"], 1, okS)
    return _finish(tf, sL, pL, sS, -pS)


def sig_bos_pb(p):
    tf = p["tf"]; c = ctx(tf); okL, okS = _htf_masks(tf, dict(p, htf=1), p.get("win", "day"))
    ph, phi, ph2, pl, pli, pl2 = pivots(tf, p["k"])
    sL, pL = _bospb_long(c["o"], c["h"], c["l"], c["c"], shift1(ph), np.r_[-1, phi[:-1]], p["fib"], p.get("maxage", 30), p["stop"], okL)
    sS, pS = _bospb_long(-c["o"], -c["l"], -c["h"], -c["c"], -shift1(pl), np.r_[-1, pli[:-1]], p["fib"], p.get("maxage", 30), p["stop"], okS)
    return _finish(tf, sL, pL, sS, -pS)


def sig_pa_level(p):
    tf = p["tf"]; c = ctx(tf); okL, okS = _htf_masks(tf, p, p.get("win", "day"))
    lv = p["lv"]; rows = []
    if lv in ("vwap", "all"):
        rows.append(c["vwap"])
    if lv == "all":
        rows += [c["pdh"], c["pdl"]]
    use_round = lv in ("r10", "all")
    n = len(c["c"])
    M = np.vstack(rows) if rows else np.full((0, n), NAN)
    sL, pL = _pa_long(c["o"], c["h"], c["l"], c["c"], c["atr"], M, use_round, p.get("tol", 0.1), p["pat"], okL)
    sS, pS = _pa_long(-c["o"], -c["l"], -c["h"], -c["c"], c["atr"], -M, use_round, p.get("tol", 0.1), p["pat"], okS)
    return _finish(tf, sL, pL, sS, -pS)


# ─── scout references #15-#18 (source-faithful, adapted to closed-bar signals) ──
def sig_s15_ict_sweep(p):
    """#15 PineGen-AI ICT Daily Liquidity Sweep: Asian box (19:00-03:00 NY) or PDH/PDL wicked through and the
    same bar closes back inside, 03:00-12:00 NY, stop beyond the wick + 0.1 ATR."""
    tf = p["tf"]; c = ctx(tf)
    q = dict(p, conf=0, m_rec=0)
    return _run_sweep(tf, [c["asl19"], c["pdl"]], [c["ash19"], c["pdh"]], q, win="lnny")


def sig_s16_pd_break(p):
    """#16 AhadRasheed/gold-strategy: PDH/PDL taken, reversal candle, close beyond the reversal candle."""
    tf = p["tf"]; c = ctx(tf); okL, okS = _htf_masks(tf, p, "all")
    sL, pL = _pd_break_long(c["o"], c["h"], c["l"], c["c"], c["pdl"], okL)
    sS, pS = _pd_break_long(-c["o"], -c["l"], -c["h"], -c["c"], -c["pdh"], okS)
    return _finish(tf, sL, pL, sS, -pS)


def sig_s17_silver_bullet(p):
    """#17 cjosh4toyotas-stack/silver-bullet-backtest: in 03-04, 10-11, 14-15 NY, the first bar (scanned from
    30 min before the window) that takes the prior 2-hour extreme and closes back inside sets the bias; the first
    FVG in that direction inside the window, then a retest before the window closes. One trade per window."""
    tf = p["tf"]; c = ctx(tf); b = c["b"]; h, l, cl = c["h"], c["l"], c["c"]
    lb = max(1, 120 // tf)
    rl = pd.Series(l).rolling(lb).min().shift(1).values
    rh = pd.Series(h).rolling(lb).max().shift(1).values
    evL = (l < rl) & (cl > rl); evS = (h > rh) & (cl < rh)
    nm = b.ny_min.values; td = b.tday.values
    blk = np.full(len(cl), -1, np.int64); inwin = np.zeros(len(cl), bool)
    for w, (a, z) in enumerate(WINDOWS["sb"]):
        m = (nm >= a - 30) & (nm < z)
        blk[m] = td[m].astype(np.int64) * 10 + w
        inwin |= (nm >= a) & (nm < z)
    # first sweep of either direction in each block sets the bias
    ev = (evL | evS) & (blk >= 0)
    first = np.zeros(len(cl), bool)
    ii = np.where(ev)[0]
    if len(ii):
        _, pos = np.unique(blk[ii], return_index=True)
        first[ii[pos]] = True
    evL &= first; evS &= first
    okL, okS = _htf_masks(tf, p, "sb")
    g = p.get("gmin", 0.05)
    sL, pL = _sweep_fvg_long(c["o"], h, l, cl, c["atr"], evL, l, 10 ** 6, 0.0, g, 10 ** 6, inwin, okL, blk, True)
    sS, pS = _sweep_fvg_long(-c["o"], -l, -h, -cl, c["atr"], evS, -h, 10 ** 6, 0.0, g, 10 ** 6, inwin, okS, blk, True)
    return _finish(tf, sL, pL, sS, -pS)


def sig_s18_sweep_fvg(p):
    """#18 ManasDoitto SMC liquidity sweep + FVG v1.0: sweep (wick through, same-bar close back inside) of the
    last confirmed k-bar swing or PDH/PDL; within 5 bars a displacement FVG (middle candle range >= 1 ATR);
    retest within 10 bars; stop beyond the sweep wick + 0.1 ATR. No session filter in the source."""
    tf = p["tf"]; c = ctx(tf); n = len(c["c"])
    ph, phi, ph2, pl, pli, pl2 = pivots(tf, p["k"])
    allok = np.ones(n, bool)
    evL = np.zeros(n, bool); xL = np.full(n, NAN); evS = np.zeros(n, bool); xS = np.full(n, NAN)
    for lv in (shift1(pl), c["pdl"]):
        s_, e_ = _sweep_long(c["h"], c["l"], c["c"], lv, allok, 0, 0, 0, np.full(n, NAN), allok)
        new = (s_ > 0) & ~evL; evL |= new; xL[new] = e_[new]
    for lv in (shift1(ph), c["pdh"]):
        s_, e_ = _sweep_long(-c["l"], -c["h"], -c["c"], -lv, allok, 0, 0, 0, np.full(n, NAN), allok)
        new = (s_ > 0) & ~evS; evS |= new; xS[new] = -e_[new]
    okL, okS = _htf_masks(tf, p, "all")
    z = np.zeros(n, np.int64)
    sL, pL = _sweep_fvg_long(c["o"], c["h"], c["l"], c["c"], c["atr"], evL, xL, 5, 1.0, 0.0, 10, allok, okL, z, False)
    sS, pS = _sweep_fvg_long(-c["o"], -c["l"], -c["h"], -c["c"], c["atr"], evS, -xS, 5, 1.0, 0.0, 10, allok, okS, z, False)
    return _finish(tf, sL, pL, sS, -pS)


# ─── search grids (DISC only) ────────────────────────────────────────────────
def grid(**kw):
    keys = list(kw); out = [{}]
    for k in keys:
        out = [dict(g, **{k: v}) for g in out for v in kw[k]]
    return out


FAMILIES = {   # name: (signal builder, stage-A grid, stage-A exits)
    "SESS_SWEEP": (sig_sess_sweep, grid(tf=[1, 3, 5, 15], conf=[0, 1], htf=[0, 1]), DEFAULT_EXIT),             # 16
    "SWING_SWEEP": (sig_swing_sweep, grid(tf=[1, 3, 5], k=[5, 10], conf=[0, 1], htf=[0, 1]), DEFAULT_EXIT),    # 24
    "CHOCH": (sig_choch, grid(tf=[1, 3, 5], k=[3, 5], need_trend=[0, 1], htf=[0, 1]), DEFAULT_EXIT),            # 24
    "FVG": (sig_fvg, grid(tf=[1, 3, 5], gmin=[0.25, 0.5], stop=[0, 1], htf=[0, 1]), DEFAULT_EXIT),              # 24
    "OB": (sig_ob, grid(tf=[1, 3, 5], k=[3, 5], body=[0, 1], htf=[0, 1]), DEFAULT_EXIT),                        # 24
    "BOS_PB": (sig_bos_pb, grid(tf=[1, 3, 5], k=[3, 5], fib=[0.5, 0.618], stop=[0, 1]), DEFAULT_EXIT),          # 24
    "PA_LEVEL": (sig_pa_level, grid(tf=[3, 5, 15], lv=["vwap", "r10", "all"], pat=[0, 1]), DEFAULT_EXIT),       # 18
    "EQ_SWEEP": (sig_eq_sweep, grid(tf=[1, 3, 5], k=[3, 5], tol=[0.1, 0.25], conf=[0, 1]), DEFAULT_EXIT),       # 24
    "SILVER_BULLET": (sig_silver_bullet, grid(tf=[1, 3, 5], gmin=[0.25, 0.5], htf=[0, 1]), DEFAULT_EXIT),       # 12
    # scout references, stage A at the source's own targets
    "S15_ICT_SWEEP": (sig_s15_ict_sweep, grid(tf=[1, 3, 5, 15], htf=[0, 1]), (1.5, 3.0, False, 240)),           # 8
    "S16_PD_BREAK": (sig_s16_pd_break, grid(tf=[1, 3, 5, 15], htf=[0, 1]), (1.5, 2.0, False, 240)),             # 8
    "S17_SB_SWEEP_FVG": (sig_s17_silver_bullet, grid(tf=[1, 3, 5], htf=[0, 1]), (1.5, 2.0, False, 120)),        # 6
    "S18_SWEEP_FVG": (sig_s18_sweep_fvg, grid(tf=[1, 3, 5, 15], k=[5, 10], htf=[0, 1]), (1.5, 3.0, False, 240)),  # 16
}


def exit_grid():
    """Stage B: 5 target pairs x {split, be} at 120 min (9 new beyond the default), then max_hold 60/240 on the best."""
    return [(t1, t2, be, 120) for (t1, t2) in EXIT_PAIRS for be in (False, True)]


# ─── evaluation ──────────────────────────────────────────────────────────────
_SIGCACHE = {}


def signals(fam, p):
    key = (fam, tuple(sorted(p.items())))
    if key not in _SIGCACHE:
        _SIGCACHE[key] = FAMILIES[fam][0](p)
    return _SIGCACHE[key]


def make_sig(fam, p, ex):
    tf = p["tf"]; idx, d, sd = signals(fam, p)
    return frost.levels(ctx(tf)["b"], idx, d, sd, ex[0], ex[1])


def run(fam, p, ex, **kw):
    return frost.simulate(make_sig(fam, p, ex), be=ex[2], max_hold=ex[3], **kw)


def disc_stats(fam, p, ex):
    t = run(fam, p, ex)
    return frost.by_period(t)[0]


def search(fam, verbose=True):
    """Two-stage DISC search. Returns (best params, best exits, number of combos, log rows)."""
    log = []
    grid_ = FAMILIES[fam][1]; ex0 = FAMILIES[fam][2]
    for p in grid_:
        s = disc_stats(fam, p, ex0)
        log.append((p, ex0, s))
    elig = [r for r in log if r[2].get("n", 0) and r[2]["per_day"] >= 0.5]
    pool = elig if elig else [r for r in log if r[2].get("n", 0)]
    bestA = max(pool, key=lambda r: r[2]["avgR"])[0]
    for ex in exit_grid():
        if ex == ex0:
            continue
        log.append((bestA, ex, disc_stats(fam, bestA, ex)))
    rowsB = [r for r in log if r[0] is bestA]
    bex = max(rowsB, key=lambda r: r[2]["avgR"])[1]
    for mh in (60, 120, 240):
        ex = (bex[0], bex[1], bex[2], mh)
        if any(r[0] is bestA and r[1] == ex for r in log):
            continue
        log.append((bestA, ex, disc_stats(fam, bestA, ex)))
    elig = [r for r in log if r[2].get("n", 0) and r[2]["per_day"] >= 0.5]
    pool = elig if elig else [r for r in log if r[2].get("n", 0)]
    best = max(pool, key=lambda r: r[2]["avgR"])
    if verbose:
        print(f"\n## {fam}: {len(log)} DISC combos (stage A {len(grid_)}, stage B {len(log) - len(grid_)})")
        for p, ex, s in log:
            print(f"  {pstr(p):38s} {exstr(ex):22s} n={s.get('n', 0):4d} pd={s.get('per_day', 0):5.2f} "
                  f"avgR={s.get('avgR', float('nan')):+.4f} se={s.get('se', float('nan')):.4f}")
        print(f"  BEST {pstr(best[0])} {exstr(best[1])} (eligible={bool(elig)})")
    return best[0], best[1], len(log), log, bool(elig)


def pstr(p):
    return ",".join(f"{k}={v}" for k, v in p.items())


def exstr(ex):
    return f"TP{ex[0]}/{ex[1]} {'be' if ex[2] else 'split'} mh{ex[3]}"


def stop_fn_for(fam, p):
    """Random-control stop rule: the family's own stop sizes, expressed in ATR of the signal timeframe,
    re-sampled onto the random bars (structural stops depend on the trade direction, which stop_fn cannot see)."""
    tf = p["tf"]; a = ctx(tf)["atr"]; idx, d, sd = signals(fam, p)
    mult = sd / a[idx]
    rng = np.random.default_rng(123)

    def fn(b, ridx):
        return a[ridx] * rng.choice(mult, size=len(ridx))
    return fn


def validate(fam, p, ex):
    tf = p["tf"]; b = ctx(tf)["b"]
    t = run(fam, p, ex)
    per = {r["label"]: r for r in frost.by_period(t)}
    idx, d, sd = signals(fam, p)
    vmask = frost.in_period(b.iloc[idx], "VAL").values
    rc = frost.random_control(idx[vmask], b, stop_fn_for(fam, p), ex[0], ex[1], n_runs=20, be=ex[2], max_hold=ex[3])
    rc = np.array([x for x in rc if np.isfinite(x)])
    ts = run(fam, p, ex, spread=0.45, slip=0.05)
    ts = ts[frost.in_period(ts, "VAL")]
    st = frost.stats(ts, "VAL-stress", frost.trading_days(frost._ts(frost.PERIODS["VAL"][0]), frost._ts(frost.PERIODS["VAL"][1])))
    v = per["VAL"]; y = per["Y2025"]
    rmed = float(np.median(rc)) if len(rc) else float("nan")
    y_ok = (y.get("n", 0) == 0) or (y.get("avgR", -1) > 0)
    passed = (v.get("n", 0) > 1 and v["avgR"] > 0 and v["avgR"] / v["se"] >= 1.0 and y_ok
              and v["avgR"] >= rmed + 0.05 and st.get("avgR", -1) >= 0 and v["per_day"] >= 0.5)
    return {"per": per, "rc_med": rmed, "rc_lo": float(np.percentile(rc, 5)) if len(rc) else NAN,
            "rc_hi": float(np.percentile(rc, 95)) if len(rc) else NAN, "stress": st, "pass": passed, "t": t}


def row_md(fam, p, ex, ncomb, res):
    per = res["per"]; d_ = per["DISC"]; v = per["VAL"]; y = per["Y2025"]; h = per["HOLD"]; s = res["stress"]
    f = lambda x: "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:+.3f}"
    yv = f(y["avgR"]) + f" (n={y['n']})" if y.get("n", 0) else "n/a"
    hv = f(h["avgR"]) + f" (n={h['n']})" if h.get("n", 0) else "n/a"
    vv = (f"{v['n']} | {v['per_day']} | {v['win']} | {v['tp1']} | {v['tp2']} | {v['avgR']:+.3f}±{v['se']:.3f} | {v['pf']}"
          if v.get("n", 0) else "0 | 0 | - | - | - | - | -")
    return (f"| {fam} | {pstr(p)}; {exstr(ex)} | {ncomb} | {d_.get('avgR', float('nan')):+.3f}/{d_.get('n', 0)} | {vv} | "
            f"{yv} | {hv} | {f(res['rc_med'])} [{f(res['rc_lo'])}, {f(res['rc_hi'])}] | {f(s.get('avgR', NAN))} | "
            f"{'PASS' if res['pass'] else 'FAIL'} |")


HEADER = ("| family | best params | combos | DISC avgR/n | VAL n | per_day | win% | TP1% | TP2% | avgR±se | PF | "
          "Y2025 avgR | HOLD avgR | random median [5-95%] | stress avgR | PASS/FAIL |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

# Frozen DISC winners, copied from the search that main() prints (main() re-derives them and checks they match).
# BEST_FAMILY = highest VAL avgR among the families that PASS, or the highest VAL avgR if none pass.
BEST_FAMILY = None
FROZEN = {}


def best_signals():
    """Signal frame (i, d, ref, sl, tp1, tp2) for Team D's single best technique.
    Simulate with frost.simulate(sig, be=best_exit()[2], max_hold=best_exit()[3])."""
    p, ex = FROZEN[BEST_FAMILY]
    return make_sig(BEST_FAMILY, p, ex)


def best_exit():
    """(TP1 R, TP2 R, be, max_hold) of the best technique."""
    return FROZEN[BEST_FAMILY][1]


def main(disc_only=False):
    print("coverage", frost.coverage())
    rows = []; results = {}
    for fam in FAMILIES:
        p, ex, ncomb, log, elig = search(fam)
        if FROZEN.get(fam) and FROZEN[fam] != (p, ex):
            print(f"  WARNING: {fam} search result differs from FROZEN {FROZEN[fam]}")
        if disc_only:
            continue
        res = validate(fam, p, ex)
        results[fam] = (p, ex, ncomb, res)
        rows.append(row_md(fam, p, ex, ncomb, res))
        print(frost.fmt(list(res["per"].values()) + [res["stress"]]))
        print("random control VAL:", round(res["rc_med"], 4), [round(res["rc_lo"], 4), round(res["rc_hi"], 4)])
        print(frost.monthly(res["t"]).T.to_string())
    if disc_only:
        return
    print("\n" + HEADER)
    for r in rows:
        print(r)
    passed = [f for f in results if results[f][3]["pass"]]
    pool = passed if passed else list(results)
    best = max(pool, key=lambda f: results[f][3]["per"]["VAL"].get("avgR", -9))
    print(f"\nBEST_FAMILY = {best!r}  (passed: {passed})")
    print("FROZEN = {" + ", ".join(f"{f!r}: ({results[f][0]!r}, {results[f][1]!r})" for f in results) + "}")
    return results


if __name__ == "__main__":
    main(disc_only=(len(sys.argv) > 1 and sys.argv[1] == "disc"))
