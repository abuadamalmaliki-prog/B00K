"""Causal (look-ahead-free) Smart Money Concepts features.

Input: DataFrame with DatetimeIndex and lowercase open/high/low/close, single timeframe.
Every output value at row t uses only rows <= t (known at the close of bar t).
"""
import numpy as np
import pandas as pd
from numba import njit

_OB_CAP = 50    # max active order blocks tracked per side (oldest dropped)
_FVG_CAP = 100  # max active FVGs tracked per side (oldest dropped)


def _arr(df, col):
    return df[col].to_numpy(dtype=np.float64)


def _swing_arrays(df, length):
    """Swing high at pivot i: high[i] > max(high[i-L:i]) and high[i] >= max(high[i+1:i+L+1]).
    It is only CONFIRMED at bar i+L. Returns per-bar confirmation flags and pivot levels."""
    h = df["high"].astype(np.float64)
    l = df["low"].astype(np.float64)
    L = int(length)
    left_h = h.rolling(L).max().shift(1)   # max(high[i-L..i-1]) at i
    left_l = l.rolling(L).min().shift(1)
    right_h = h.rolling(L).max()            # max(high[t-L+1..t]) at t
    right_l = l.rolling(L).min()
    ph = h.shift(L)                         # pivot candidate i = t-L
    pl = l.shift(L)
    conf_h = ((ph > left_h.shift(L)) & (ph >= right_h)).to_numpy()
    conf_l = ((pl < left_l.shift(L)) & (pl <= right_l)).to_numpy()
    return conf_h, ph.to_numpy(), conf_l, pl.to_numpy()


def swings(df, length=5):
    """Last confirmed swing high/low levels and bars since the pivot bar (pivot confirmed length bars later)."""
    conf_h, ph, conf_l, pl = _swing_arrays(df, length)
    n = len(df)
    pos = np.arange(n, dtype=np.float64)
    sh = pd.Series(np.where(conf_h, ph, np.nan)).ffill().to_numpy()
    sl = pd.Series(np.where(conf_l, pl, np.nan)).ffill().to_numpy()
    shi = pd.Series(np.where(conf_h, pos - length, np.nan)).ffill().to_numpy()
    sli = pd.Series(np.where(conf_l, pos - length, np.nan)).ffill().to_numpy()
    return pd.DataFrame({
        "last_swing_high": sh,
        "last_swing_low": sl,
        "bars_since_swing_high": pos - shi,
        "bars_since_swing_low": pos - sli,
    }, index=df.index)


@njit(cache=True)
def _structure_nb(close, conf_h, ph, conf_l, pl, L):
    n = close.shape[0]
    trend = np.zeros(n, np.int8)
    bos = np.zeros(n, np.int8)
    choch = np.zeros(n, np.int8)
    ref = np.full(n, -1, np.int64)       # pivot index of the swing broken at t
    sh = np.nan; sh_i = -1; sh_live = False
    sl = np.nan; sl_i = -1; sl_live = False
    tr = 0
    for t in range(n):
        if conf_h[t]:
            sh = ph[t]; sh_i = t - L; sh_live = True
        if conf_l[t]:
            sl = pl[t]; sl_i = t - L; sl_live = True
        c = close[t]
        if sh_live and c > sh:
            if tr == -1:
                choch[t] = 1
            else:
                bos[t] = 1
            tr = 1; sh_live = False; ref[t] = sh_i
        elif sl_live and c < sl:
            if tr == 1:
                choch[t] = -1
            else:
                bos[t] = -1
            tr = -1; sl_live = False; ref[t] = sl_i
        trend[t] = tr
    return trend, bos, choch, ref


def _structure_arrays(df, length):
    conf_h, ph, conf_l, pl = _swing_arrays(df, length)
    return _structure_nb(_arr(df, "close"), conf_h, ph, conf_l, pl, int(length))


def structure(df, length=5):
    """BOS/CHoCH on CLOSE break of the last confirmed swing. Each swing level can be broken once.
    Break against the current trend = CHoCH, with trend (or first break) = BOS."""
    trend, bos, choch, _ = _structure_arrays(df, length)
    return pd.DataFrame({"trend": trend, "bos": bos, "choch": choch}, index=df.index)


@njit(cache=True)
def _fvg_nb(high, low, min_size, cap):
    n = high.shape[0]
    new = np.zeros(n, np.int8)
    o_bt = np.full(n, np.nan); o_bb = np.full(n, np.nan)
    o_st = np.full(n, np.nan); o_sb = np.full(n, np.nan)
    bt = np.empty(cap); bb = np.empty(cap); nb = 0
    st = np.empty(cap); sb = np.empty(cap); ns = 0
    for t in range(n):
        # mitigation: price trades fully through the gap
        k = 0
        for j in range(nb):
            if not (low[t] < bb[j]):
                bt[k] = bt[j]; bb[k] = bb[j]; k += 1
        nb = k
        k = 0
        for j in range(ns):
            if not (high[t] > st[j]):
                st[k] = st[j]; sb[k] = sb[j]; k += 1
        ns = k
        if t >= 2:
            if low[t] - high[t - 2] > min_size:
                if nb == cap:
                    for j in range(cap - 1):
                        bt[j] = bt[j + 1]; bb[j] = bb[j + 1]
                    nb -= 1
                bt[nb] = low[t]; bb[nb] = high[t - 2]; nb += 1
                new[t] = 1
            elif low[t - 2] - high[t] > min_size:
                if ns == cap:
                    for j in range(cap - 1):
                        st[j] = st[j + 1]; sb[j] = sb[j + 1]
                    ns -= 1
                st[ns] = low[t - 2]; sb[ns] = high[t]; ns += 1
                new[t] = -1
        # nearest to price: bullish with highest top, bearish with lowest bottom
        best = -1
        for j in range(nb):
            if best < 0 or bt[j] > bt[best]:
                best = j
        if best >= 0:
            o_bt[t] = bt[best]; o_bb[t] = bb[best]
        best = -1
        for j in range(ns):
            if best < 0 or sb[j] < sb[best]:
                best = j
        if best >= 0:
            o_st[t] = st[best]; o_sb[t] = sb[best]
    return new, o_bt, o_bb, o_st, o_sb


def fvg(df, min_size=0.0):
    """3-candle FVG known at close of bar i: bull if low[i] > high[i-2] (zone high[i-2]..low[i]), bear mirror.
    Mitigated when price trades fully through (bull: low < bottom; bear: high > top).
    Reports the unmitigated FVG nearest to price on each side."""
    new, bt, bb, st, sb = _fvg_nb(_arr(df, "high"), _arr(df, "low"), float(min_size), _FVG_CAP)
    return pd.DataFrame({"bull_fvg_top": bt, "bull_fvg_bot": bb,
                         "bear_fvg_top": st, "bear_fvg_bot": sb, "fvg_new": new}, index=df.index)


@njit(cache=True)
def _ob_nb(open_, high, low, close, bos, choch, ref, cap):
    n = close.shape[0]
    o_bt = np.full(n, np.nan); o_bb = np.full(n, np.nan)
    o_st = np.full(n, np.nan); o_sb = np.full(n, np.nan)
    bt = np.empty(cap); bb = np.empty(cap); nb = 0
    st = np.empty(cap); sb = np.empty(cap); ns = 0
    for t in range(n):
        c = close[t]
        k = 0
        for j in range(nb):
            if not (c < bb[j]):
                bt[k] = bt[j]; bb[k] = bb[j]; k += 1
        nb = k
        k = 0
        for j in range(ns):
            if not (c > st[j]):
                st[k] = st[j]; sb[k] = sb[j]; k += 1
        ns = k
        ev = bos[t] + choch[t]
        if ev != 0:
            p = ref[t]
            lo = min(p + 1, t - 1)
            hi = t - 1
            if ev > 0:
                # leg origin = lowest low between broken swing high and break bar
                jx = lo
                for j in range(lo, hi + 1):
                    if low[j] <= low[jx]:
                        jx = j
                ob = jx
                for j in range(jx, p - 1, -1):   # last down-close candle at/before leg low
                    if close[j] < open_[j]:
                        ob = j
                        break
                if nb == cap:
                    for j in range(cap - 1):
                        bt[j] = bt[j + 1]; bb[j] = bb[j + 1]
                    nb -= 1
                bt[nb] = high[ob]; bb[nb] = low[ob]; nb += 1
            else:
                jx = lo
                for j in range(lo, hi + 1):
                    if high[j] >= high[jx]:
                        jx = j
                ob = jx
                for j in range(jx, p - 1, -1):
                    if close[j] > open_[j]:
                        ob = j
                        break
                if ns == cap:
                    for j in range(cap - 1):
                        st[j] = st[j + 1]; sb[j] = sb[j + 1]
                    ns -= 1
                st[ns] = high[ob]; sb[ns] = low[ob]; ns += 1
        if nb > 0:
            o_bt[t] = bt[nb - 1]; o_bb[t] = bb[nb - 1]
        if ns > 0:
            o_st[t] = st[ns - 1]; o_sb[t] = sb[ns - 1]
    return o_bt, o_bb, o_st, o_sb


def order_blocks(df, length=5):
    """OB created on every structure break (BOS or CHoCH). Bull: find the leg low between the broken
    swing high pivot and the break bar, then the last down-close candle at/before it (fallback: the
    leg-low bar); zone = that candle's high..low. Bear mirrors. Mitigated when CLOSE passes the far
    side. Reports the most recent unmitigated OB per side."""
    _, bos, choch, ref = _structure_arrays(df, length)
    bt, bb, st, sb = _ob_nb(_arr(df, "open"), _arr(df, "high"), _arr(df, "low"), _arr(df, "close"),
                            bos, choch, ref, _OB_CAP)
    return pd.DataFrame({"bull_ob_top": bt, "bull_ob_bot": bb,
                         "bear_ob_top": st, "bear_ob_bot": sb}, index=df.index)


@njit(cache=True)
def _sweep_nb(high, low, close, conf_h, ph, conf_l, pl):
    n = close.shape[0]
    out = np.zeros(n, np.int8)
    sh = np.nan; sh_live = False
    sl = np.nan; sl_live = False
    for t in range(n):
        if conf_h[t]:
            sh = ph[t]; sh_live = True
        if conf_l[t]:
            sl = pl[t]; sl_live = True
        s = 0
        if sh_live and high[t] > sh:
            sh_live = False            # liquidity taken (swept or broken)
            if close[t] < sh:
                s -= 1
        if sl_live and low[t] < sl:
            sl_live = False
            if close[t] > sl:
                s += 1
        out[t] = s                     # both sides swept on one bar -> 0
    return out


def liquidity_sweep(df, length=5):
    """Bear sweep (-1): high > last confirmed swing high and close back below it. Bull (+1) mirror.
    Each swing level is consumed the first time price trades beyond it (swept or broken)."""
    conf_h, ph, conf_l, pl = _swing_arrays(df, length)
    s = _sweep_nb(_arr(df, "high"), _arr(df, "low"), _arr(df, "close"), conf_h, ph, conf_l, pl)
    return pd.DataFrame({"sweep": s}, index=df.index)


@njit(cache=True)
def _pd_nb(high, low, close, conf_h, ph, conf_l, pl):
    n = close.shape[0]
    out = np.full(n, np.nan)
    hi = np.nan; lo = np.nan
    for t in range(n):
        if conf_h[t]:
            hi = ph[t]
        elif hi == hi and high[t] > hi:
            hi = high[t]
        if conf_l[t]:
            lo = pl[t]
        elif lo == lo and low[t] < lo:
            lo = low[t]
        if hi == hi and lo == lo and hi > lo:
            v = (close[t] - lo) / (hi - lo)
            out[t] = min(1.0, max(0.0, v))
    return out


def premium_discount(df, length=5):
    """Position of close in the dealing range [last swing low, last swing high], each extended by any
    price beyond it since confirmation. 0 = range low (discount), 1 = range high (premium)."""
    conf_h, ph, conf_l, pl = _swing_arrays(df, length)
    v = _pd_nb(_arr(df, "high"), _arr(df, "low"), _arr(df, "close"), conf_h, ph, conf_l, pl)
    return pd.DataFrame({"pd_pos": v}, index=df.index)


@njit(cache=True)
def _session_nb(day, minute, high, low, asia_end):
    n = high.shape[0]
    pdh = np.full(n, np.nan); pdl = np.full(n, np.nan)
    ah = np.full(n, np.nan); al = np.full(n, np.nan)
    cur_day = -1
    dh = np.nan; dl = np.nan; p_h = np.nan; p_l = np.nan
    rah = np.nan; ral = np.nan; pub_h = np.nan; pub_l = np.nan
    for t in range(n):
        if day[t] != cur_day:
            if cur_day >= 0:
                p_h = dh; p_l = dl
                if rah == rah:           # asia session of previous day ended
                    pub_h = rah; pub_l = ral
            cur_day = day[t]
            dh = high[t]; dl = low[t]
            rah = np.nan; ral = np.nan
        else:
            dh = max(dh, high[t]); dl = min(dl, low[t])
        if minute[t] < asia_end:
            rah = high[t] if rah != rah else max(rah, high[t])
            ral = low[t] if ral != ral else min(ral, low[t])
        elif rah == rah:                 # first bar at/after session end
            pub_h = rah; pub_l = ral
            rah = np.nan; ral = np.nan
        pdh[t] = p_h; pdl[t] = p_l
        ah[t] = pub_h; al[t] = pub_l
    return pdh, pdl, ah, al


def session_levels(df, asia_end_hour=7):
    """pdh/pdl: previous calendar day (index time) high/low, from the first bar of the new day.
    asia_high/low: most recently COMPLETED 00:00-asia_end_hour session, published at the first bar
    with timestamp >= asia_end_hour (or first bar of the next day)."""
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    ns = np.asarray(idx.as_unit("ns").asi8, dtype=np.int64)
    day = ns // 86_400_000_000_000
    minute = (ns % 86_400_000_000_000) // 60_000_000_000
    pdh, pdl, ah, al = _session_nb(day, minute, _arr(df, "high"), _arr(df, "low"), int(asia_end_hour) * 60)
    return pd.DataFrame({"pdh": pdh, "pdl": pdl, "asia_high": ah, "asia_low": al}, index=df.index)


def compute_all(df, length=5):
    """All SMC features concatenated, aligned to df.index."""
    return pd.concat([
        swings(df, length),
        structure(df, length),
        fvg(df),
        order_blocks(df, length),
        liquidity_sweep(df, length),
        premium_discount(df, length),
        session_levels(df),
    ], axis=1)
