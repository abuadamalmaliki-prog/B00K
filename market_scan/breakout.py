"""Donchian/ATR volatility breakout (Turtle-style) on H1, per-trade R multiples, 21-day $30 windows."""
import numpy as np, pandas as pd, scan
from numba import njit

@njit(cache=True)
def run(o, h, l, c, atr, n_in, n_out, k_sl, cost):
    n = len(c); R = []; E = []
    pos = 0; entry = 0.0; stop = 0.0; risk = 0.0; ei = 0
    for t in range(n_in + 1, n - 1):
        if pos != 0:
            j = t
            if pos > 0:
                trail = l[j - n_out:j].min()
                if trail > stop: stop = trail
                if o[j] <= stop or l[j] <= stop:
                    px = min(o[j], stop); R.append((px - entry) / risk); E.append(ei); pos = 0
            else:
                trail = h[j - n_out:j].max()
                if trail < stop: stop = trail
                if o[j] + cost >= stop or h[j] + cost >= stop:
                    px = max(o[j] + cost, stop); R.append((entry - px) / risk); E.append(ei); pos = 0
        if pos == 0 and atr[t] > 0:
            hh = h[t - n_in:t].max(); ll = l[t - n_in:t].min()
            if c[t] > hh:
                pos = 1; entry = o[t + 1] + cost; risk = k_sl * atr[t]; stop = entry - risk; ei = t + 1
            elif c[t] < ll:
                pos = -1; entry = o[t + 1]; risk = k_sl * atr[t]; stop = entry + risk; ei = t + 1
    return np.array(R), np.array(E)

rows = []
for inst in ['xauusd', 'usatechidxusd', 'usa500idxusd', 'eurusd', 'gbpusd', 'usdjpy', 'gbpjpy', 'eurjpy', 'audusd']:
    pip, cost = scan.SPEC[inst]
    d = scan.load(inst, '2021')
    H = d.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    tr = np.maximum(H.high - H.low, np.maximum((H.high - H.close.shift()).abs(), (H.low - H.close.shift()).abs()))
    atr = tr.rolling(14).mean().fillna(0).to_numpy()
    R, E = run(*(H[k].to_numpy() for k in ('open', 'high', 'low', 'close')), atr, 20, 10, 2.0, cost * pip)
    T = pd.DataFrame({'R': R, 'day': H.index[E].normalize()})
    days = pd.Series(sorted(H.index.normalize().unique()))
    ends = []
    for s in range(0, len(days) - 21, 5):
        w = T[(T.day >= days[s]) & (T.day < days[s + 21])]
        eq = 30.0
        for r in w.R:
            eq = max(eq * (1 + 0.10 * max(r, -1.5)), 0.0)
        ends.append(eq)
    ends = np.array(ends)
    for per, g in [('2021-23', T[T.day < '2024']), ('2024-26', T[T.day >= '2024'])]:
        rows.append(dict(market=scan.NAME.get(inst, inst.upper()), period=per, trades=len(g),
                         win=round((g.R > 0).mean(), 3), avgR=round(g.R.mean(), 3),
                         bigwins_3R=int((g.R >= 3).sum())))
    rows.append(dict(market=scan.NAME.get(inst, inst.upper()), period='21d from $30 @10% risk',
                     trades=len(ends), win=round((ends > 30).mean(), 3), avgR=round(np.median(ends), 1),
                     bigwins_3R=round((ends >= 60).mean(), 3)))
print(pd.DataFrame(rows).to_string(index=False))
print('columns for "21d" rows: win = share of windows ending above $30, avgR = median ending $, bigwins_3R = share ending >= $60')
