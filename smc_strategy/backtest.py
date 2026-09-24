"""Honest M1 bar backtester (numba core) for XAUUSD.

Price data is treated as BID. Longs enter at ask (open + spread) and exit on bid;
shorts enter at bid (open) and exit on ask (bid + spread). The spread is thus paid once
per round trip. Signal at CLOSE of bar t -> entry at OPEN of bar t+1 (skipped if t+1 is
in a different data block unless allow_gap_entry=True). Same-bar TP+SL -> SL. A bar that
opens beyond TP/SL fills at the open. Touch (==) counts as a hit for both TP and SL.
"""
import numpy as np
import pandas as pd
from numba import njit

RESULTS = np.array(['TP', 'SL', 'TIME', 'EOD', 'GAP'])
_TP, _SL, _TIME, _EOD, _GAP = 0, 1, 2, 3, 4
_EPS = 1e-7


@njit(cache=True)
def _core(o, h, l, c, day, block, sig, tp_arr, sl_arr, spread, max_per_day, max_open,
          time_stop, allow_gap_entry, strict_tp, close_at_gap):
    n = o.shape[0]
    cap = 0
    for i in range(n):
        if sig[i] != 0:
            cap += 1
    e_bar = np.empty(cap, np.int64)
    x_bar = np.empty(cap, np.int64)
    dirs = np.empty(cap, np.int8)
    e_px = np.empty(cap, np.float64)
    x_px = np.empty(cap, np.float64)
    res = np.empty(cap, np.int8)
    tpl = np.empty(cap, np.float64)
    sll = np.empty(cap, np.float64)
    active = np.empty(min(max_open, cap) + 1, np.int64)
    nact = 0
    nt = 0
    cur_day = -1
    day_cnt = 0
    for i in range(n):
        # ---- entry at open of bar i for signal at close of bar i-1
        if i > 0 and sig[i - 1] != 0 and nact < max_open and \
                (allow_gap_entry or block[i] == block[i - 1]):
            if day[i] != cur_day:
                cur_day = day[i]
                day_cnt = 0
            if day_cnt < max_per_day:
                d = sig[i - 1]
                tp = tp_arr[i - 1]
                sl = sl_arr[i - 1]
                if d > 0:
                    ep = o[i] + spread
                    tpl[nt] = ep + tp
                    sll[nt] = ep - sl
                else:
                    ep = o[i]
                    tpl[nt] = ep - tp
                    sll[nt] = ep + sl
                e_bar[nt] = i
                dirs[nt] = 1 if d > 0 else -1
                e_px[nt] = ep
                active[nact] = nt
                nact += 1
                nt += 1
                day_cnt += 1
        # ---- manage open positions on bar i
        k = 0
        while k < nact:
            t = active[k]
            first = e_bar[t] == i
            done = False
            px = 0.0
            r = 0
            if dirs[t] > 0:                       # long: exits on bid
                if not first and o[i] <= sll[t] + _EPS:
                    px = min(o[i], sll[t]); r = _SL; done = True
                elif not first and o[i] >= tpl[t] - _EPS:
                    px = tpl[t] if strict_tp else max(o[i], tpl[t]); r = _TP; done = True
                elif l[i] <= sll[t] + _EPS:
                    px = sll[t]; r = _SL; done = True
                elif h[i] >= tpl[t] - _EPS:
                    px = tpl[t]; r = _TP; done = True
            else:                                 # short: exits on ask = bid + spread
                ao = o[i] + spread
                if not first and ao >= sll[t] - _EPS:
                    px = max(ao, sll[t]); r = _SL; done = True
                elif not first and ao <= tpl[t] + _EPS:
                    px = tpl[t] if strict_tp else min(ao, tpl[t]); r = _TP; done = True
                elif h[i] + spread >= sll[t] - _EPS:
                    px = sll[t]; r = _SL; done = True
                elif l[i] + spread <= tpl[t] + _EPS:
                    px = tpl[t]; r = _TP; done = True
            if not done and time_stop > 0 and i - e_bar[t] + 1 >= time_stop:
                px = c[i] if dirs[t] > 0 else c[i] + spread
                r = _TIME; done = True
            if not done and close_at_gap and i + 1 < n and block[i + 1] != block[i]:
                px = c[i] if dirs[t] > 0 else c[i] + spread
                r = _GAP; done = True
            if done:
                x_bar[t] = i; x_px[t] = px; res[t] = r
                nact -= 1
                active[k] = active[nact]
            else:
                k += 1
    for k in range(nact):                         # end of data
        t = active[k]
        x_bar[t] = n - 1
        x_px[t] = c[n - 1] if dirs[t] > 0 else c[n - 1] + spread
        res[t] = _EOD
    return e_bar[:nt], x_bar[:nt], dirs[:nt], e_px[:nt], x_px[:nt], res[:nt]


def _arr(v, default, n):
    if v is None:
        v = default
    a = np.asarray(v, dtype=np.float64)
    return np.full(n, float(a)) if a.ndim == 0 else a


def simulate(df, direction, tp_pips=50, sl_pips=50, pip=0.10, spread_pips=3.0,
             max_trades_per_day=20, max_open=1, time_stop_bars=None, tp_pips_arr=None,
             sl_pips_arr=None, allow_gap_entry=False, strict_tp=False, close_at_gap=False):
    """Backtest signals (+1/-1/0 known at close of bar t) on M1 bars from data.load.

    tp_pips_arr/sl_pips_arr (aligned to df, read at the signal bar) override tp/sl_pips.
    max_open=None means unlimited. strict_tp: TP always fills at exactly the TP price (no gap
    bonus). close_at_gap: trades still open on the last bar before a data hole are closed at
    that bar's close (result 'GAP'), since the price path through a hole is unknown.
    Returns (trades DataFrame, summary dict).
    """
    n = len(df)
    sig = np.asarray(direction).astype(np.int8)
    assert sig.shape[0] == n
    tp = _arr(tp_pips_arr, tp_pips, n) * pip
    sl = _arr(sl_pips_arr, sl_pips, n) * pip
    idx = df.index
    day = idx.values.astype('datetime64[D]').astype(np.int64)
    block = df['block'].to_numpy(np.int64) if 'block' in df else np.zeros(n, np.int64)
    eb, xb, d, ep, xp, r = _core(
        df['open'].to_numpy(np.float64), df['high'].to_numpy(np.float64),
        df['low'].to_numpy(np.float64), df['close'].to_numpy(np.float64),
        day, block, sig, tp, sl, float(spread_pips) * pip, int(max_trades_per_day),
        int(max_open) if max_open else 1 << 40, int(time_stop_bars or 0), bool(allow_gap_entry),
        bool(strict_tp), bool(close_at_gap))
    trades = pd.DataFrame({
        'entry_time': idx[eb], 'exit_time': idx[xb], 'dir': d.astype(np.int64),
        'entry': ep, 'exit': xp, 'pips': (xp - ep) * d / pip, 'result': RESULTS[r],
        'bars_held': xb - eb + 1})
    return trades, summarize(trades, df, max_trades_per_day)


def summarize(trades, df=None, cap=20):
    """Summary stats; per-day stats keyed on entry date."""
    p = trades['pips'].to_numpy()
    n = len(p)
    s = {'n_trades': n,
         'trading_days': int(df.index.normalize().nunique()) if df is not None else None}
    if n == 0:
        return s
    days = trades['entry_time'].dt.normalize()
    per_day = trades.groupby(days).size()
    tp_per_day = (trades['result'] == 'TP').groupby(days).sum()
    wins, losses = p[p > 0], p[p < 0]
    eq = np.cumsum(p[np.argsort(trades['exit_time'].to_numpy(), kind='stable')])
    full = per_day[per_day >= 20].index
    tp20 = tp_per_day.loc[full]
    s.update({
        'active_days': len(per_day),
        'trades_per_day': float(per_day.mean()),
        'trades_per_trading_day': n / s['trading_days'] if s['trading_days'] else None,
        'win_rate': float((trades['result'] == 'TP').mean()),
        'avg_win_pips': float(wins.mean()) if len(wins) else 0.0,
        'avg_loss_pips': float(losses.mean()) if len(losses) else 0.0,
        'total_pips': float(p.sum()),
        'expectancy_pips': float(p.mean()),
        'profit_factor': float(wins.sum() / -losses.sum()) if len(losses) else np.inf,
        'max_drawdown_pips': float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()),
        'results': trades['result'].value_counts().to_dict(),
        'pct_days_with_20_trades': float(len(full) / len(per_day)),
        'tp_hits_on_20_trade_days': tp20.value_counts().sort_index().to_dict(),
        'days_ge18_tp_of_20': int((tp20 >= 18).sum()),
    })
    return s


def random_signals(df, n_per_day=20, seed=0):
    """Random +/-1 signals at n_per_day random bars per calendar day (bars with a same-block next bar)."""
    rng = np.random.default_rng(seed)
    n = len(df)
    blk = df['block'].to_numpy() if 'block' in df else np.zeros(n)
    ok = np.zeros(n, bool)
    ok[:-1] = blk[1:] == blk[:-1]
    day = df.index.normalize().asi8
    sig = np.zeros(n, np.int8)
    cand = np.flatnonzero(ok)
    starts = np.flatnonzero(np.r_[True, day[cand][1:] != day[cand][:-1]])
    for a, b in zip(starts, np.r_[starts[1:], len(cand)]):
        pick = rng.choice(cand[a:b], size=min(n_per_day, b - a), replace=False)
        sig[pick] = rng.choice(np.array([-1, 1], np.int8), size=len(pick))
    return sig


def simulate_random(df, n_per_day=20, tp_pips=50, sl_pips=50, seed=0, spread_pips=3.0,
                    pip=0.10, max_open=None, time_stop_bars=None):
    """Null baseline: random direction at random times, n_per_day per day.

    max_open=None (default) takes every random signal independently (overlapping trades),
    which gives the cleanest estimate of the null win rate for a TP/SL pair.
    summary['rw_win_rate'] = (sl-spread)/(tp+sl), the driftless random-walk reference.
    """
    sig = random_signals(df, n_per_day, seed)
    tr, s = simulate(df, sig, tp_pips, sl_pips, pip, spread_pips, n_per_day, max_open,
                     time_stop_bars)
    s['rw_win_rate'] = (sl_pips - spread_pips) / (tp_pips + sl_pips)
    return tr, s
