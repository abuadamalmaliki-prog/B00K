"""SMC daily-bias scalper for XAUUSD M1: fixed 50-pip TP, up to 20 entries a day.

Rules (all known at the close of the signal bar; entry at the next bar's open):
  1. HTF bias: SMC market structure (BOS/CHoCH trend) on D1 bars built from the M1 feed.
  2. Daily confirmation: the previous day's candle closed in the bias direction.
     If D1 structure and the previous candle disagree, there are no trades that day.
  3. Session: entries from 01:00 to 21:59 (skips the rollover hours).
  4. Pacing: one entry every `spacing` minutes in the bias direction, capped at 20 a day
     by the backtester.
Exits: TP exactly 50 pips ($5.00), SL 800 pips ($80.00). The wide SL is what buys the
high hit rate. See README.md for the out-of-sample results, including the losing test.

Parameters were chosen on 2025 data and checked on Jan-Apr 2026. May-Aug 2026 was run
once, after the rules were locked.
"""
import numpy as np
import pandas as pd
from numba import njit

import smc

HTF = {'M15': ('15min', 3), 'H1': ('1h', 3), 'H4': ('4h', 3), 'D1': ('1D', 2)}

FINAL = dict(bias=('D1',), prev_candle=True, hours=range(1, 22), spacing=5)
FINAL_SIM = dict(tp_pips=50, sl_pips=800, spread_pips=3.0, max_trades_per_day=20,
                 max_open=None, strict_tp=True, close_at_gap=True)
FINAL_GAP = '3h'   # data holes longer than this close open trades (weekends, missing chunks)


def htf_features(m, rule, length):
    """Resample M1 to a higher timeframe, run SMC on it, and map it back to M1 causally.

    An HTF bar labelled L covering [L, L+rule) is known at the close of the M1 bar
    stamped L+rule-1min, so its features apply from that M1 bar onward.
    """
    r = m.resample(rule, label='left', closed='left').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    f = smc.compute_all(r, length=length)
    f.index = f.index + pd.Timedelta(rule) - pd.Timedelta('1min')
    return pd.merge_asof(pd.DataFrame(index=m.index), f, left_index=True,
                         right_index=True, direction='backward')


def build_features(m, tfs=('M15', 'H1', 'H4', 'D1')):
    feats = {'M1': smc.compute_all(m, length=5)}
    for name in tfs:
        rule, length = HTF[name]
        feats[name] = htf_features(m, rule, length)
    return feats


def prev_day_candle(m):
    """Sign of the previous calendar day's candle (close - open), aligned to M1 bars."""
    day = m.index.normalize()
    d = m.groupby(day).agg(o=('open', 'first'), c=('close', 'last'))
    return np.sign(d.c - d.o).shift(1).reindex(day).fillna(0).to_numpy()


@njit(cache=True)
def _pace(cond, block, spacing):
    n = cond.shape[0]
    out = np.zeros(n, np.int8)
    last = -(1 << 40)
    for i in range(n - 1):
        if cond[i] != 0 and i - last >= spacing and block[i + 1] == block[i]:
            out[i] = cond[i]
            last = i
    return out


def signals(m, feats, bias=('D1',), prev_candle=True, use_pd=False, use_fvg=False,
            hours=range(1, 22), spacing=5):
    """Return an int8 array: +1 long, -1 short, 0 none (known at the close of bar t)."""
    n = len(m)
    long_ok = np.ones(n, bool)
    short_ok = np.ones(n, bool)
    for tf in bias:
        t = feats[tf]['trend'].to_numpy()
        long_ok &= t == 1
        short_ok &= t == -1
    if prev_candle:
        pc = prev_day_candle(m)
        long_ok &= pc == 1
        short_ok &= pc == -1
    if use_pd:
        p = feats['M15']['pd_pos'].to_numpy()
        long_ok &= p < 0.5
        short_ok &= p > 0.5
    if use_fvg:
        f, c = feats['M1'], m['close'].to_numpy()
        long_ok &= (f['bull_fvg_bot'].to_numpy() <= c) & (c <= f['bull_fvg_top'].to_numpy())
        short_ok &= (f['bear_fvg_bot'].to_numpy() <= c) & (c <= f['bear_fvg_top'].to_numpy())
    if hours is not None:
        hm = np.isin(m.index.hour, list(hours))
        long_ok &= hm
        short_ok &= hm
    cond = np.where(long_ok, 1, np.where(short_ok, -1, 0)).astype(np.int8)
    block = m['block'].to_numpy(np.int64) if 'block' in m else np.zeros(n, np.int64)
    return _pace(cond, block, int(spacing))
