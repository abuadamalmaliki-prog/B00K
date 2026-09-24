"""Which market gives 18+ of 20 fixed-time setups hitting a fixed TP with the smallest SL?

Data: Dukascopy M5 bid bars (UTC), downloaded with dukascopy-node.
Entries: 20 per trading day at the first bar of each hour 08:00..03:00 Malaysia time.
Fill: long at open + cost, short at open; TP/SL touch rules are pessimistic (same bar -> SL).
For every entry and direction we record the first bar each TP and SL level is touched, then
any (TP, SL) pair is scored without re-scanning.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
from numba import njit

DATA = os.environ.get('DUKA', 'data')
MYT = pd.Timedelta(hours=8)
SLOTS = list(range(8, 24)) + [0, 1, 2, 3]

# pip size and assumed JustMarkets Standard round-trip cost (pips). Indices: 1 pip = 1 point.
SPEC = {
    'eurusd': (1e-4, 1.0), 'gbpusd': (1e-4, 1.3), 'audusd': (1e-4, 1.2), 'nzdusd': (1e-4, 1.5),
    'usdjpy': (1e-2, 1.2), 'usdchf': (1e-4, 1.5), 'usdcad': (1e-4, 1.6), 'eurgbp': (1e-4, 1.5),
    'eurchf': (1e-4, 2.0), 'audnzd': (1e-4, 3.0), 'audcad': (1e-4, 2.5), 'eurjpy': (1e-2, 1.8),
    'gbpjpy': (1e-2, 2.8), 'audjpy': (1e-2, 2.0), 'euraud': (1e-4, 2.5), 'eurcad': (1e-4, 2.5),
    'gbpchf': (1e-4, 3.0), 'usatechidxusd': (1.0, 1.5), 'usa500idxusd': (1.0, 0.6),
    'usa30idxusd': (1.0, 3.0), 'xauusd': (0.1, 3.0),
}
NAME = {'usatechidxusd': 'US100 (NASDAQ)', 'usa500idxusd': 'US500', 'usa30idxusd': 'US30',
        'xauusd': 'XAUUSD'}
TP_P = np.array([10, 20, 30, 50], np.float64)
SL_P = np.array([10, 20, 30, 50, 75, 100, 150, 200, 300, 450, 600, 900, 1200], np.float64)


def load(inst, since='2021'):
    fs = sorted(f for f in glob.glob(os.path.join(DATA, f'{inst}-20*.csv')) if f[-8:-4] >= since)
    d = pd.concat([pd.read_csv(f) for f in fs])
    d.index = pd.to_datetime(d.pop('timestamp'), unit='ms').astype('datetime64[ns]')
    d = d[~d.index.duplicated()].sort_index().astype(float)
    u = d.index
    dw = u.dayofweek
    closed = (dw == 5) | ((dw == 6) & (u.hour < 21)) | ((dw == 4) & (u.hour >= 22))
    d = d[~closed]
    flat = (d.high == d.low) & (d.high.diff() == 0)          # no-trade filler bars
    return d[~flat]


def slot_entries(d):
    myt = d.index + MYT
    hr = myt.hour.values
    first = np.r_[True, (myt.floor('h')[1:] != myt.floor('h')[:-1])]
    ok = first & np.isin(hr, SLOTS) & (myt.minute.values < 5)
    i = np.flatnonzero(ok)
    i = i[i > 0]
    tday = (myt[i] - pd.Timedelta(hours=7)).normalize()
    return i, tday


@njit(cache=True)
def first_hits(o, h, l, c, idx, tp, sl, cost, horizon):
    m = idx.shape[0]
    nt, ns = tp.shape[0], sl.shape[0]
    INF = 1 << 40
    LT = np.full((m, nt), INF, np.int64); LS = np.full((m, ns), INF, np.int64)
    ST = np.full((m, nt), INF, np.int64); SS = np.full((m, ns), INF, np.int64)
    ML = np.zeros(m); MS = np.zeros(m)
    for k in range(m):
        i = idx[k]
        el = o[i] + cost          # long fill (ask); exits on bid
        es = o[i]                 # short fill (bid); exits on ask = bid + cost
        lt = 0; ls = 0; st = 0; ss = 0
        end = min(o.shape[0], i + horizon)
        ML[k] = c[end - 1] - el
        MS[k] = es - c[end - 1] - cost
        for j in range(i, end):
            while lt < nt and h[j] >= el + tp[lt] - 1e-12:
                LT[k, lt] = j; lt += 1
            while ls < ns and l[j] <= el - sl[ls] + 1e-12:
                LS[k, ls] = j; ls += 1
            while st < nt and l[j] + cost <= es - tp[st] + 1e-12:
                ST[k, st] = j; st += 1
            while ss < ns and h[j] + cost >= es + sl[ss] - 1e-12:
                SS[k, ss] = j; ss += 1
            if lt == nt and ls == ns and st == nt and ss == ns:
                break
    return LT, LS, ST, SS, ML, MS


def rules(d, i):
    """Direction candidates known at the close of bar i-1 (+1 buy, -1 sell)."""
    c = d.close
    D = c.resample('1D').last().dropna()
    def daily(s):
        s = s.copy(); s.index = s.index + pd.Timedelta('1D')
        return pd.merge_asof(pd.DataFrame(index=d.index[i - 1]), s.rename('v').to_frame(),
                             left_index=True, right_index=True).v.fillna(0).to_numpy()
    cl = c.to_numpy()
    out = {'buy': np.ones(len(i)), 'sell': -np.ones(len(i)),
           'trend_sma50d': np.sign(daily(D - D.rolling(50).mean())),
           'trend_20d': np.sign(daily(D - D.shift(20)))}
    for hrs in (4, 24):
        k = hrs * 12
        mean = c.rolling(k).mean().to_numpy()
        out[f'fade_{hrs}h_mean'] = -np.sign(cl[i - 1] - mean[i - 1])
        out[f'follow_{hrs}h_mean'] = np.sign(cl[i - 1] - mean[i - 1])
    return {k: np.where(v == 0, 1, v) for k, v in out.items()}


def score(inst, horizon_days=30):
    pip, cost = SPEC[inst]
    d = load(inst)
    o, h, l = (d[k].to_numpy() for k in ('open', 'high', 'low'))
    i, tday = slot_entries(d)
    c = d['close'].to_numpy()
    LT, LS, ST, SS, ML, MS = first_hits(o, h, l, c, i, TP_P * pip, SL_P * pip, cost * pip,
                                        horizon_days * 288)
    keep = d.index[i] < d.index[-1] - pd.Timedelta(days=horizon_days + 3)
    i, tday, LT, LS, ST, SS, ML, MS = (x[keep] for x in (i, tday, LT, LS, ST, SS, ML, MS))
    R = rules(d, i)
    per = np.where(tday < pd.Timestamp('2024-01-01'), 'A 2021-23', 'B 2024-26')
    rows = []
    for rn, dr in R.items():
        buy = dr > 0
        for a, tp in enumerate(TP_P):
            for b, sl in enumerate(SL_P):
                if sl < tp:
                    continue
                tpt = np.where(buy, LT[:, a], ST[:, a]); slt = np.where(buy, LS[:, b], SS[:, b])
                win = tpt < slt
                lose = (slt <= tpt) & (slt < (1 << 40))
                pnl = np.where(win, tp, np.where(lose, -sl, np.where(buy, ML, MS) / pip))
                df = pd.DataFrame({'tday': tday, 'per': per, 'win': win, 'pnl': pnl})
                for pn, g in df.groupby('per'):
                    dd = g.groupby('tday')
                    n = dd.size(); w = dd.win.sum()
                    full = n[n == 20].index
                    rows.append(dict(inst=NAME.get(inst, inst.upper()), rule=rn, tp=tp, sl=sl,
                                     period=pn, days=len(full), win=g.win.mean(),
                                     tp20=w.loc[full].mean(), ge18=(w.loc[full] >= 18).mean(),
                                     exp_pips=g.pnl.mean()))
    return pd.DataFrame(rows)


if __name__ == '__main__':
    insts = sys.argv[1:] or list(SPEC)
    out = []
    for inst in insts:
        if not glob.glob(os.path.join(DATA, f'{inst}-20*.csv')):
            print('missing', inst); continue
        r = score(inst); out.append(r); print('done', inst, flush=True)
    pd.concat(out).to_csv('scan_results.csv', index=False)
