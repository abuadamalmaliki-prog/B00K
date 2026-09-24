"""Backtest engine for fixed-time XAUUSD entries with fixed TP/SL.

Prices are Twelve Data XAU/USD mid/bid bars in UTC. Conventions (all pessimistic):
  * Entry at the OPEN of the bar that starts at the slot time. A long fills at open + spread.
  * TP and SL are measured from the fill. Long exits on bid (the bar prices).
  * If TP and SL are touched inside the same bar, the trade is an SL.
  * A bar that opens through the SL (gap, weekend) fills at that open (worse than SL).
  * A TP always pays exactly TP (no gap bonus).
  * Default: no time exit, a trade ends only at TP or SL. With `max_hold_days`, trades still
    open after that long are closed at market and count as not-TP.
  * Trades still open at the end of the data are marked OPEN and left out of the stats.
"""
import numpy as np
import pandas as pd
from numba import njit

PIP = 0.10          # XAUUSD: 1 pip = $0.10, so 50 pips = $5.00
EPS = 1e-7          # a touch of the TP/SL price counts as a hit
MYT = pd.Timedelta(hours=8)


def load(path):
    d = pd.read_csv(path, parse_dates=['datetime']).set_index('datetime').sort_index()
    d = d[~d.index.duplicated()].astype(float)
    u = d.index
    dw = u.dayofweek
    closed = (dw == 5) | ((dw == 6) & (u.hour < 21)) | ((dw == 4) & (u.hour >= 22))
    return d[~closed]


@njit(cache=True)
def _run(o, h, l, c, t_ns, entry_idx, direction, tp, sl, spread, max_hold_ns):
    n = o.shape[0]
    m = entry_idx.shape[0]
    res = np.zeros(m, np.int8)       # 1 TP, -1 SL, 0 closed at max hold / end of data
    exit_idx = np.zeros(m, np.int64)
    pnl = np.zeros(m)
    for k in range(m):
        i = entry_idx[k]
        d = direction[k]
        if d > 0:
            e = o[i] + spread
            T = e + tp
            S = e - sl
        else:
            e = o[i]
            T = e - tp
            S = e + sl
        exit_idx[k] = n - 1
        pnl[k] = (c[n - 1] - e) if d > 0 else (e - c[n - 1] - spread)
        for j in range(i, n):
            if t_ns[j] - t_ns[i] > max_hold_ns:
                exit_idx[k] = j
                pnl[k] = (o[j] - e) if d > 0 else (e - o[j] - spread)
                break
            if d > 0:
                if j > i and o[j] <= S + EPS:
                    res[k] = -1; exit_idx[k] = j; pnl[k] = o[j] - e; break
                if l[j] <= S + EPS:
                    res[k] = -1; exit_idx[k] = j; pnl[k] = S - e; break
                if h[j] >= T - EPS:
                    res[k] = 1; exit_idx[k] = j; pnl[k] = tp; break
            else:
                if j > i and o[j] + spread >= S - EPS:
                    res[k] = -1; exit_idx[k] = j; pnl[k] = e - o[j] - spread; break
                if h[j] + spread >= S - EPS:
                    res[k] = -1; exit_idx[k] = j; pnl[k] = e - S; break
                if l[j] + spread <= T + EPS:
                    res[k] = 1; exit_idx[k] = j; pnl[k] = tp; break
    return res, exit_idx, pnl


def slot_entries(bars, slots_myt, tolerance='5min'):
    """Index of the first bar at or after each MYT slot time (within tolerance), per trading day.

    The trading day runs 07:00 MYT to 06:59 MYT the next morning.
    """
    idx = bars.index
    rows = []
    days = pd.date_range((idx[0] + MYT).normalize(), (idx[-1] + MYT).normalize(), freq='D')
    tol = pd.Timedelta(tolerance)
    for day in days:
        for s in slots_myt:
            hh, mm = map(int, s.split(':'))
            t_myt = day + pd.Timedelta(hours=hh, minutes=mm)
            if hh < 7:
                t_myt += pd.Timedelta(days=1)
            t_utc = t_myt - MYT
            j = idx.searchsorted(t_utc)
            if j < len(idx) and idx[j] - t_utc <= tol:
                rows.append((day, s, j))
    e = pd.DataFrame(rows, columns=['tday', 'slot', 'i']).drop_duplicates('i')
    return e


def backtest(bars, slots_myt, direction_fn, tp_pips=50, sl_pips=1200, spread_pips=3.0,
             max_hold_days=None, tolerance='5min'):
    e = slot_entries(bars, slots_myt, tolerance)
    d = direction_fn(bars, e).astype(np.int64)
    o, h, l, c = (bars[k].to_numpy(np.float64) for k in ('open', 'high', 'low', 'close'))
    t_ns = bars.index.values.astype('datetime64[ns]').astype(np.int64)
    res, xi, pnl = _run(o, h, l, c, t_ns, e.i.to_numpy(np.int64), d,
                        tp_pips * PIP, sl_pips * PIP, spread_pips * PIP,
                        np.int64(max_hold_days * 86400 * 10**9) if max_hold_days else np.int64(2**62))
    e = e.assign(dir=d, entry_utc=bars.index[e.i], exit_utc=bars.index[xi],
                 result=np.where(res == 1, 'TP', np.where(res == -1, 'SL', 'CLOSED')),
                 open_at_end=(res == 0) & (xi == len(bars) - 1),
                 pips=pnl / PIP)
    e.loc[e.open_at_end, 'result'] = 'OPEN'
    return e.drop(columns=['i', 'open_at_end']).reset_index(drop=True)


def summarize(T, n_slots=20):
    T = T[T.result != 'OPEN']
    g = T.groupby('tday')
    n = g.size()
    tp = g.result.apply(lambda x: (x == 'TP').sum())
    full = n[n == n_slots].index
    tpf = tp.loc[full]
    # concurrency: open trades at each entry time
    ev = np.r_[T.entry_utc.values.astype(np.int64), T.exit_utc.values.astype(np.int64)]
    st = np.r_[np.ones(len(T)), -np.ones(len(T))]
    order = np.lexsort((-st, ev))
    conc = np.cumsum(st[order]).max() if len(T) else 0
    daily = g.pips.sum()
    return {
        'trading_days': len(n),
        'days_with_20': len(full),
        'avg_tp_per_20': float(tpf.mean()),
        'days_ge18': float((tpf >= 18).mean()),
        'days_20_of_20': float((tpf == 20).mean()),
        'win_rate': float((T.result == 'TP').mean()),
        'expectancy_pips': float(T.pips.mean()),
        'total_pips': float(T.pips.sum()),
        'worst_day_pips': float(daily.min()),
        'best_day_pips': float(daily.max()),
        'max_open_trades': int(conc),
        'median_hold_min': float(((T.exit_utc - T.entry_utc).dt.total_seconds() / 60).median()),
        'tp_distribution': tpf.value_counts().sort_index().to_dict(),
    }
